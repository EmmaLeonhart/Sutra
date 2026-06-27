"""Formal-verification artifact: §3.3 loop-convergence obligation via the
Z-transform poles of the recurrence ``state ← R · state``.

`planning/sutra-spec/formal-verification.md` (Pillar 3) frames each loop as a
bounded recurrence with a soft-halt cell. `fv_loop_convergence.analyze_loop_
recurrence` adds the principled criterion under the observational halt check: the
linear core is a discrete-time LTI system whose poles are the eigenvalues of
``R`` (roots of ``det(zI − R)``), and stability reads off whether those poles sit
inside / on / outside the unit circle.

Two layers:
  1. the classifier on known operators (contraction, rotation, expansion,
     defective unit pole) — pure linear algebra, no substrate;
  2. a substrate cross-check: the ACTUAL Haar-orthogonal bind rotation the loop
     runs is measured to be marginally stable (all poles on the unit circle),
     which is the principled statement that termination is the halt gate's job,
     not spectral decay.

Referenced by `paper/formal-verification/paper.md` §3.3 (loop convergence).
"""
from __future__ import annotations

import math

import pytest

np = pytest.importorskip("numpy", reason="the pole analysis needs numpy")

from sutra_compiler.fv_loop_convergence import (
    ASYMPTOTICALLY_STABLE,
    MARGINALLY_STABLE,
    UNSTABLE,
    analyze_loop_recurrence,
)


# --- Layer 1: the classifier on known operators -------------------------------

def test_contraction_is_asymptotically_stable() -> None:
    # 0.5 * I: both poles at 0.5, strictly inside the unit disk -> decay.
    rep = analyze_loop_recurrence(0.5 * np.eye(4))
    assert rep.classification == ASYMPTOTICALLY_STABLE
    assert rep.spectral_radius == pytest.approx(0.5)
    assert rep.satisfies_convergence_obligation()
    assert rep.terminates_by_spectral_decay()
    assert rep.poles_outside_unit_disk == 0


def test_rotation_is_marginally_stable_and_orthogonal() -> None:
    # A planar rotation by 40 degrees: eigenvalues e^{±iθ} on the unit circle,
    # R orthogonal -> marginally stable, NOT decaying.
    theta = math.radians(40.0)
    rot = np.array(
        [[math.cos(theta), -math.sin(theta)],
         [math.sin(theta), math.cos(theta)]]
    )
    rep = analyze_loop_recurrence(rot)
    assert rep.classification == MARGINALLY_STABLE
    assert rep.is_orthogonal
    assert rep.spectral_radius == pytest.approx(1.0, abs=1e-9)
    assert rep.poles_on_unit_circle == 2
    assert rep.poles_outside_unit_disk == 0
    # passes the obligation (bounded) but does NOT terminate by decay.
    assert rep.satisfies_convergence_obligation()
    assert not rep.terminates_by_spectral_decay()
    assert "halt-gate" in rep.termination_mechanism()


def test_expansion_is_unstable() -> None:
    # 1.5 * I: poles outside the unit disk -> divergence, obligation FAILS.
    rep = analyze_loop_recurrence(1.5 * np.eye(3))
    assert rep.classification == UNSTABLE
    assert rep.spectral_radius == pytest.approx(1.5)
    assert rep.poles_outside_unit_disk == 3
    assert not rep.satisfies_convergence_obligation()
    assert "unstable" in rep.termination_mechanism().lower()


def test_defective_unit_pole_flagged_non_orthogonal() -> None:
    # A Jordan block [[1,1],[0,1]]: spectral radius 1 but DEFECTIVE (not
    # diagonalizable) -> polynomial growth t·1^t. It is on-circle (so the radius
    # test calls it marginal) but NOT orthogonal, so the report must withhold the
    # semisimple certificate and warn.
    jordan = np.array([[1.0, 1.0], [0.0, 1.0]])
    rep = analyze_loop_recurrence(jordan)
    assert rep.classification == MARGINALLY_STABLE
    assert not rep.is_orthogonal
    assert "WARNING" in rep.termination_mechanism()


def test_accepts_torch_tensor() -> None:
    torch = pytest.importorskip("torch")
    rep = analyze_loop_recurrence(0.25 * torch.eye(3, dtype=torch.float64))
    assert rep.classification == ASYMPTOTICALLY_STABLE
    assert rep.spectral_radius == pytest.approx(0.25)


# --- Layer 2: the actual emitted bind rotation --------------------------------

# A program with NO embed/string/basis call, so exec-ing the emitted module
# instantiates _VSA without precomputing any embedding (no model backend needed).
# We only need the _VSA instance to draw a real Haar bind rotation.
TRIVIAL = "function number main() { return 1; }\n"


def _vsa_instance():
    torch = pytest.importorskip(
        "torch", reason="the bind rotation lives on the torch substrate"
    )
    from sutra_compiler.codegen_pytorch import translate_module as torch_translate
    from sutra_compiler.lexer import Lexer
    from sutra_compiler.parser import Parser

    lexer = Lexer(TRIVIAL, file="<fv-loop>")
    toks = lexer.tokenize()
    module = Parser(
        toks, file="<fv-loop>", diagnostics=lexer.diagnostics
    ).parse_module()
    assert not lexer.diagnostics.has_errors(), list(lexer.diagnostics)
    # The rotation is a seeded Haar draw, so no embedding model is loaded
    # (embed() is lazy); we only need a real bind-rotation matrix. runtime_dim
    # mirrors the sibling test_fv_termination (a known-good no-model-load path).
    py = torch_translate(module, llm_model="nomic-embed-text", runtime_dim=768)
    ns: dict = {}
    exec(compile(py, "<fv-loop>", "exec"), ns)
    return ns["_VSA"]  # module-level instance


def test_emitted_bind_rotation_is_marginally_stable() -> None:
    """The operator the loop actually iterates (``state ← R · state`` with R the
    Haar-orthogonal bind rotation) is measured to have ALL its Z-transform poles
    on the unit circle: marginally stable, no spectral decay. So the linear core
    cannot, on its own, drive termination — it is the §3.3 halt gate that does,
    exactly as the principled criterion predicts."""
    torch = pytest.importorskip("torch")
    vsa = _vsa_instance()
    dim = vsa.dim

    # A real bind rotation, seeded from a role vector (no embedding model needed).
    role = torch.zeros(dim, dtype=vsa.dtype, device=vsa.device)
    role[3] = 1.0
    R = vsa._rotation_for(role)

    rep = analyze_loop_recurrence(R, tol=1e-6)
    print(
        f"[fv-loop] emitted bind rotation dim={dim} "
        f"spectral_radius={rep.spectral_radius:.8f} "
        f"orthogonal={rep.is_orthogonal} class={rep.classification} "
        f"poles_on_circle={rep.poles_on_unit_circle}/{dim} "
        f"poles_outside={rep.poles_outside_unit_disk}"
    )

    assert rep.is_orthogonal, "bind rotation must be orthogonal (norm-preserving)"
    assert rep.classification == MARGINALLY_STABLE, (
        f"orthogonal R must be marginally stable, got {rep.classification} "
        f"(spectral radius {rep.spectral_radius})"
    )
    # All poles on the unit circle, none outside -> bounded, no decay.
    assert rep.poles_outside_unit_disk == 0
    assert rep.poles_on_unit_circle == dim
    assert rep.spectral_radius == pytest.approx(1.0, abs=1e-6)
    # The obligation is satisfied (bounded state), but NOT by spectral decay.
    assert rep.satisfies_convergence_obligation()
    assert not rep.terminates_by_spectral_decay()
