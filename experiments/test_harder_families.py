"""Correctness guard for the W2C harder families (Emma option A 2026-05-30).

The 5 hardening families added to weight_to_code_corpus.STRUCTURES must each
compute what their name claims on the substrate. For each, generate at K=4,
compile through the real Sutra compiler, run apply(x) on the substrate, and
compare to the intended formula computed independently (host-side — this is
monitoring/verification, NOT a runtime substrate op). Also asserts the
coefficient families actually emit their per-program coefficient as a literal
(so the seq2seq target carries the value it must infer, not a fixed template).
"""
from __future__ import annotations

import importlib.util
import os
import tempfile

import pytest

torch = pytest.importorskip("torch", reason="substrate requires torch")

HERE = os.path.dirname(os.path.abspath(__file__))


def _gen_mod():
    spec = importlib.util.spec_from_file_location(
        "w2c_gen", os.path.join(HERE, "weight_to_code_corpus.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _make(m, structure, K=4, seed=0):
    """Generate one program; return (compiled apply, _VSA, loaded weights, coeffs, source)."""
    rid = f"{structure}_K{K}_gaussian_s{seed}"
    gen = torch.Generator().manual_seed(hash((structure, K, "gaussian", seed)) & 0x7FFFFFFF)
    td = tempfile.mkdtemp()
    abs_paths, mats = {}, {}
    for mm in m.STRUCTURES[structure]["mats"]:
        W = m.make_weight("gaussian", K, gen)
        p = os.path.join(td, f"{rid}_{mm}.csv")
        m.write_csv(p, W)
        abs_paths[mm] = p.replace("\\", "/")
        mats[mm] = W
    cv = (m._coeff_values(rid, m.STRUCTURES[structure]["coeffs"])
          if m.STRUCTURES[structure].get("coeffs") else None)
    src = m.build_source(structure, abs_paths, cv)
    ns = m.compile_source(src, K)
    return ns["apply"], ns["_VSA"], mats, cv, src


# intended formula per new family, in terms of loaded mats + coeffs + x (host ref)
def _expected(structure, mats, cv, x):
    M = {k: torch.tensor(v.tolist(), dtype=torch.float64) for k, v in mats.items()}
    xv = x.to(torch.float64)
    mm = lambda k: M[k] @ xv
    a = cv["a"] if cv else None
    b = cv["b"] if cv and "b" in cv else None
    if structure == "chain4":
        return M["M3"] @ (M["M2"] @ (M["M1"] @ (M["M0"] @ xv)))
    if structure == "scaled_res":
        return a * mm("M0") + xv
    if structure == "gen_affine":
        return a * mm("M0") + b * xv
    if structure == "scaled_diff":
        return a * mm("M0") - b * xv
    if structure == "two_mat_affine":
        return a * mm("M0") + b * mm("M1")
    raise AssertionError(structure)


NEW = ["chain4", "scaled_res", "gen_affine", "scaled_diff", "two_mat_affine"]


@pytest.mark.parametrize("structure", NEW)
def test_new_family_matches_intended_formula(structure):
    m = _gen_mod()
    apply_fn, vsa, mats, cv, src = _make(m, structure)
    g = torch.Generator().manual_seed(7)
    for _ in range(5):
        x = torch.randn(4, generator=g, dtype=vsa.dtype).to(vsa.device)
        got = apply_fn(x).detach().reshape(-1).to(torch.float64).cpu()
        exp = _expected(structure, mats, cv, x.to(torch.float64).cpu())
        assert torch.max(torch.abs(got - exp)).item() < 1e-4, \
            f"{structure}: substrate output != intended formula"


@pytest.mark.parametrize("structure", ["scaled_res", "gen_affine", "scaled_diff", "two_mat_affine"])
def test_coeff_family_emits_literal(structure):
    m = _gen_mod()
    _, _, _, cv, src = _make(m, structure)
    assert cv, f"{structure} should have drawn coefficients"
    for name, val in cv.items():
        assert repr(float(val)) in src, f"coeff {name}={val} not a literal in source"


def test_fifteen_structures_present():
    m = _gen_mod()
    assert len(m.STRUCTURES) == 15
    assert set(NEW).issubset(m.STRUCTURES)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
