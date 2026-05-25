"""The public formal-verification API surface (`from sutra_compiler import fv`).

Guards the release surface: the documented entry point imports and the exported
checks behave. The full mechanical verification (incl. substrate cross-checks)
lives in test_fv_general_checker.py and test_fv_poly_obligation_checker.py; this
test just pins that the public facade re-exports them and they work through it.
"""
from __future__ import annotations

import pytest

pytest.importorskip("sympy", reason="the fv API needs sympy (sutra-dev[fv])")

from sutra_compiler import fv


def test_public_api_surface() -> None:
    for name in (
        "RangeBound", "bound_polynomial_over_box", "check_branch_range",
        "reduces_to_same_graph", "kleene_equivalent",
        "extract_truth_polynomial", "NonPolynomialResidual",
    ):
        assert hasattr(fv, name), f"fv.{name} missing from the public API"
        assert name in fv.__all__


def test_equivalence_via_facade() -> None:
    # graph-identity (polynomial identity)
    assert fv.reduces_to_same_graph("!(a && b)", "!a || !b", ["a", "b"])
    assert not fv.reduces_to_same_graph(
        "a && (b || c)", "(a && b) || (a && c)", ["a", "b", "c"]
    )
    # logical (Kleene-grid) equivalence: distributivity holds on the grid
    assert fv.kleene_equivalent(
        "a && (b || c)", "(a && b) || (a && c)", ["a", "b", "c"]
    )


def test_branch_range_via_facade() -> None:
    rb = fv.check_branch_range("a && b", ["a", "b"])
    assert rb.within(-1, 1)
    assert rb.minimum == -1 and rb.maximum == 1


def test_refusal_via_facade() -> None:
    with pytest.raises(fv.NonPolynomialResidual):
        fv.extract_truth_polynomial("a == b", ["a", "b"])
