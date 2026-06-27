"""Formal-verification tooling for Sutra — the public API.

This is the supported entry point to Sutra's formal-verification checks. Import
it as a package facade rather than reaching into module internals:

    from sutra_compiler import fv

    # Decide whether two Kleene-logic expressions reduce to the SAME tensor
    # graph (polynomial identity) — exact, any nesting depth:
    fv.reduces_to_same_graph("!(a && b)", "!a || !b", ["a", "b"])   # True
    fv.reduces_to_same_graph("a && (b || c)",
                             "(a && b) || (a && c)", ["a", "b", "c"])  # False

    # Decide three-valued (Kleene-grid) logical equivalence:
    fv.kleene_equivalent("a && (b || c)",
                         "(a && b) || (a && c)", ["a", "b", "c"])      # True

    # Branch-range obligation: exact range of a reduced polynomial over the
    # truth domain [-1, +1]^n (RangeBound.within(-1, 1) decides soundness):
    fv.check_branch_range("a && b", ["a", "b"]).within(-1, 1)          # True

Needs the optional dependency sympy:  pip install sutra-dev[fv]

Background: paper/formal-verification/paper.md (the framework + results) and
planning/sutra-spec/formal-verification.md (the obligation spec). The checks here
operate on the compiler's OWN lowering of an expression, and the obligation/
range results are cross-checked against the compiled substrate in the test suite
(tests/test_fv_general_checker.py, test_fv_poly_obligation_checker.py).
"""
from __future__ import annotations

from .fv_obligation_checker import (
    NonPolynomialResidual,
    check_branch_range,
    extract_truth_polynomial,
    kleene_equivalent,
    range_sound_by_composition,
    reduces_to_same_graph,
)
from .fv_loop_convergence import (
    ASYMPTOTICALLY_STABLE,
    MARGINALLY_STABLE,
    UNSTABLE,
    LoopConvergenceReport,
    analyze_loop_recurrence,
)
from .fv_poly_bound import RangeBound, bound_polynomial_over_box
from .fv_sampler_convergence import (
    SamplerConvergenceReport,
    analyze_sampler_convergence,
    integrate_master_equation,
    measured_decay_rate,
)

__all__ = [
    # polynomial range bounding (the §3.2 branch-range obligation)
    "RangeBound",
    "bound_polynomial_over_box",
    "check_branch_range",
    # branch-range at ANY nesting depth, by structural composition
    "range_sound_by_composition",
    # equivalence over the Kleene fragment (§2)
    "reduces_to_same_graph",
    "kleene_equivalent",
    # extraction + the verifiable-fragment boundary
    "extract_truth_polynomial",
    "NonPolynomialResidual",
    # loop-convergence obligation via the Z-transform poles (the §3.3 linear core)
    "analyze_loop_recurrence",
    "LoopConvergenceReport",
    "ASYMPTOTICALLY_STABLE",
    "MARGINALLY_STABLE",
    "UNSTABLE",
    # continuous-time convergence of the probabilistic sampler (the §7 SDE angle)
    "analyze_sampler_convergence",
    "SamplerConvergenceReport",
    "integrate_master_equation",
    "measured_decay_rate",
]
