"""Formal-verification tooling: the loop-convergence obligation via the Z-transform.

`planning/sutra-spec/formal-verification.md` (Pillar 3) and
`paper/formal-verification/paper.md` (§3.3) describe each Sutra loop as a bounded
recurrence ``state ← R · state`` with a soft-halt cell. The shipped termination
obligation is observational ("the halt signal is monotone and crosses its
threshold within the bound"). This module adds the *principled* convergence
criterion that the observation is a consequence of: the linear core of the loop
is a **discrete-time linear time-invariant (LTI) system**, and an LTI system's
convergence is decided exactly by the location of its **poles**.

The recurrence is ``x_{t+1} = R · x_t`` (the `_step` cell computes ``cand = R @
state`` before the halt gate; see `codegen_pytorch.py`). Its one-sided
Z-transform is

    X(z) = (z·I − R)^{-1} · z · x_0,

so the poles of the system — the roots of ``det(z·I − R) = 0`` — are exactly the
**eigenvalues of R**. The standard discrete-time stability classification reads
straight off the pole locations relative to the unit circle |z| = 1:

  * every |λ| < 1  ⟹  **asymptotically stable**: ``x_t → 0`` geometrically, at
    rate = spectral radius. Termination would follow from the linear dynamics
    alone, independent of the halt gate.
  * spectral radius = 1, no pole outside, and the on-circle poles *semisimple*
    (non-defective)  ⟹  **marginally stable**: the state is norm-bounded and does
    not decay to a fixed point. This is Sutra's actual case: ``R`` is a Haar-
    **orthogonal** bind rotation, so every eigenvalue lies exactly on the unit
    circle and (orthogonal ⟹ normal ⟹ diagonalizable) every on-circle pole is
    semisimple. There is no spectral decay, so termination is discharged by the
    §3.3 soft-halt gate, *not* by the linear recurrence — the Z-transform makes
    precise which mechanism is doing the work.
  * any |λ| > 1  ⟹  **unstable**: a pole outside the unit disk, ``x_t`` diverges,
    and the bounded-state premise the obligation rests on fails. A loop whose
    operator is unstable does NOT satisfy the convergence obligation.

This is a host-side **verification analysis of the emitted operator** (an
eigenvalue computation on the actual ``R`` the loop runs), in the same role as
`fv_poly_bound.py`'s sympy extremum solve — compile/verify-time tooling, not a
Sutra runtime op. It decides which stability regime a given loop's ``R`` is in,
on the real matrix, so the termination story is a measured property of the
operator rather than an assertion.

What it does NOT do: bound the *rate* of the halt gate's threshold crossing (that
is the observational §3.3 check), nor model the substrate's sampling noise (the
probabilistic target's convergence is the §7 / SDE story). It classifies the
deterministic linear core.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

# Stability regimes, named off the pole locations relative to |z| = 1.
ASYMPTOTICALLY_STABLE = "asymptotically_stable"
MARGINALLY_STABLE = "marginally_stable"
UNSTABLE = "unstable"


def _to_numpy(matrix) -> np.ndarray:
    """Accept a torch tensor, numpy array, or nested sequence and return a 2-D
    complex numpy array. Torch is imported lazily so this module has no hard
    torch dependency (the analysis is pure linear algebra)."""
    if hasattr(matrix, "detach"):  # torch.Tensor
        matrix = matrix.detach().cpu().numpy()
    arr = np.asarray(matrix, dtype=complex)
    if arr.ndim != 2 or arr.shape[0] != arr.shape[1]:
        raise ValueError(
            f"loop operator R must be a square matrix, got shape {arr.shape}"
        )
    return arr


@dataclass(frozen=True)
class LoopConvergenceReport:
    """The pole analysis of a loop recurrence ``state ← R · state``.

    ``classification`` is one of the three module constants. The pole data are
    the measured eigenvalues of the actual operator; ``spectral_radius`` is the
    decisive quantity (max |pole|).
    """

    classification: str
    spectral_radius: float
    eigenvalues: tuple  # the poles: roots of det(zI - R)
    is_orthogonal: bool  # R^H R == I  -> normal -> on-circle poles semisimple
    poles_outside_unit_disk: int
    poles_on_unit_circle: int
    dim: int
    tol: float

    def satisfies_convergence_obligation(self) -> bool:
        """The loop's linear core meets the convergence obligation iff no pole
        lies outside the unit disk (the state stays bounded). Asymptotically- and
        marginally-stable both pass; unstable fails."""
        return self.classification != UNSTABLE

    def terminates_by_spectral_decay(self) -> bool:
        """True iff the linear dynamics *alone* drive the state to a fixed point
        (all poles strictly inside the unit disk). When False, termination must
        come from the soft-halt gate (§3.3), not the recurrence."""
        return self.classification == ASYMPTOTICALLY_STABLE

    def termination_mechanism(self) -> str:
        """A one-line statement of what discharges termination in this regime —
        the verification-relevant reading of the pole locations."""
        if self.classification == ASYMPTOTICALLY_STABLE:
            return (
                f"spectral decay: all poles inside the unit disk (spectral "
                f"radius {self.spectral_radius:.6f} < 1), so the state contracts "
                f"geometrically to its fixed point independent of the halt gate."
            )
        if self.classification == MARGINALLY_STABLE:
            certified = (
                "R is orthogonal (normal), so the on-circle poles are semisimple "
                "— bounded, norm-preserving, no polynomial growth"
                if self.is_orthogonal
                else "WARNING: on-circle poles are not certified semisimple "
                "(R is not orthogonal); a defective unit pole would give "
                "polynomial growth — analyze the Jordan structure before relying "
                "on this"
            )
            return (
                f"halt-gate-discharged: spectral radius {self.spectral_radius:.6f} "
                f"= 1 with no pole outside the unit disk ({certified}). There is "
                f"no spectral decay, so termination is the §3.3 soft-halt gate's "
                f"job, not the linear recurrence's."
            )
        return (
            f"NONE — unstable: {self.poles_outside_unit_disk} pole(s) lie outside "
            f"the unit disk (spectral radius {self.spectral_radius:.6f} > 1); the "
            f"linear recurrence diverges and the bounded-state premise fails."
        )


def analyze_loop_recurrence(R, *, tol: float = 1e-9) -> LoopConvergenceReport:
    """Classify the loop recurrence ``state ← R · state`` by its Z-transform
    poles (the eigenvalues of ``R``).

    ``R`` may be a torch tensor, numpy array, or nested sequence (square). The
    classification is exact up to ``tol``, the band around |z| = 1 within which a
    pole is judged *on* the unit circle (to absorb floating-point error in the
    eigenvalue solve and the Haar-orthogonal draw).
    """
    arr = _to_numpy(R)
    dim = arr.shape[0]
    eig = np.linalg.eigvals(arr)
    magnitudes = np.abs(eig)
    spectral_radius = float(magnitudes.max()) if dim else 0.0

    outside = int(np.count_nonzero(magnitudes > 1.0 + tol))
    on_circle = int(np.count_nonzero(np.abs(magnitudes - 1.0) <= tol))

    # Orthogonality (R^H R == I) certifies normality ⟹ every eigenvalue is
    # semisimple, so a unit-circle spectrum is genuinely marginally stable
    # (no defective Jordan block, no polynomial growth).
    identity = np.eye(dim, dtype=complex)
    is_orthogonal = bool(np.allclose(arr.conj().T @ arr, identity, atol=1e-6))

    if outside > 0:
        classification = UNSTABLE
    elif spectral_radius < 1.0 - tol:
        classification = ASYMPTOTICALLY_STABLE
    else:
        classification = MARGINALLY_STABLE

    return LoopConvergenceReport(
        classification=classification,
        spectral_radius=spectral_radius,
        eigenvalues=tuple(complex(v) for v in eig),
        is_orthogonal=is_orthogonal,
        poles_outside_unit_disk=outside,
        poles_on_unit_circle=on_circle,
        dim=dim,
        tol=tol,
    )
