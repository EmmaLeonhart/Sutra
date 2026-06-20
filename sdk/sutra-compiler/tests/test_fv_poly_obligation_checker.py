"""Formal-verification artifact: closed-form discharge of the Pillar-2
branch-range obligation with the bespoke polynomial-obligation checker.

`planning/sutra-spec/formal-verification.md` Pillar 2 states the branch-range
obligation as "bound [each reduced branch polynomial's] range and sign over the
truth-axis domain [-1, +1] — a closed-form question (a polynomial
extremum/root problem), not a path enumeration." `paper/formal-verification.md`
§3.2 promises this is discharged by a *critical-point box bound* (closed-form),
not a numerical sweep. This test makes that real, using
`sutra_compiler.fv_poly_bound.bound_polynomial_over_box`.

The integrity hazard this test guards against (CLAUDE.md, top): the bounder
operates on a *symbolic* polynomial, but the obligation is about the polynomial
the COMPILER ACTUALLY EMITS on the substrate. A bound on a hand-copied
polynomial that has silently drifted from the compiled form proves nothing. So
this test does two things, in order:

  1. CROSS-CHECK the symbolic polynomial against the compiled substrate. The
     connective polynomials are degree <= 2 in each variable, so their values
     on the 3x3 grid {-1,0,+1}^2 determine them uniquely; we assert agreement
     on that grid AND on off-grid points, on the real torch substrate. Match
     there means the symbolic form IS the compiled form (as polynomials).
  2. BOUND the (now-validated) symbolic polynomial in closed form and assert
     its exact range is contained in [-1, +1].

Together: the range bound proven on the symbolic form transfers to the
substrate connectives, exactly.
"""
from __future__ import annotations

import itertools

import pytest

torch = pytest.importorskip(
    "torch", reason="cross-check runs on the torch substrate"
)
sympy = pytest.importorskip(
    "sympy", reason="the polynomial-obligation checker needs sympy (sutra-dev[dev])"
)

from sutra_compiler.codegen_pytorch import translate_module as torch_translate  # noqa: E402
from sutra_compiler.fv_obligation_checker import (  # noqa: E402
    check_branch_range, range_sound_by_composition)
from sutra_compiler.fv_poly_bound import bound_polynomial_over_box  # noqa: E402
from sutra_compiler.lexer import Lexer  # noqa: E402
from sutra_compiler.parser import Parser  # noqa: E402

_a, _b = sympy.symbols("a b", real=True)

# The polynomials the inliner emits (antipodal Kleene, true=+1, false=-1).
# These are CROSS-CHECKED against the compiled substrate below; they are not
# trusted on their own.
AND_POLY = (_a + _b + _a * _b - _a**2 - _b**2 + _a**2 * _b**2) / 2
OR_POLY = (_a + _b - _a * _b + _a**2 + _b**2 - _a**2 * _b**2) / 2
NOT_POLY = -_a

SRC = """
function vector kand(vector a, vector b) { return a && b; }
function vector kor(vector a, vector b)  { return a || b; }
function vector knot(vector a)           { return !a; }
function vector main() { return true && false; }
"""


def _build() -> dict:
    lexer = Lexer(SRC, file="<fv-poly>")
    toks = lexer.tokenize()
    parser = Parser(toks, file="<fv-poly>", diagnostics=lexer.diagnostics)
    module = parser.parse_module()
    assert not lexer.diagnostics.has_errors(), list(lexer.diagnostics)
    py = torch_translate(module, llm_model="nomic-embed-text", runtime_dim=768)
    ns: dict = {}
    exec(compile(py, "<fv-poly>", "exec"), ns)
    return ns


def test_symbolic_polys_match_compiled_substrate() -> None:
    """Step 1: the symbolic polynomials equal what the compiler emits.

    Checked on the {-1,0,+1}^2 grid (which uniquely determines a degree-<=2-per-
    variable polynomial) PLUS off-grid points, evaluated on the torch substrate.
    """
    ns = _build()
    vsa = ns["_VSA"]
    kand, kor, knot = ns["kand"], ns["kor"], ns["knot"]

    def truth(v) -> float:
        return float(vsa.truth_axis(v))

    def mt(x: float):
        return vsa.make_truth(x)

    grid = (-1.0, 0.0, 1.0)
    offgrid = (-0.7, -0.25, 0.4, 0.85)
    pts = tuple(itertools.product(grid + offgrid, repeat=2))

    f_and = sympy.lambdify((_a, _b), AND_POLY, "math")
    f_or = sympy.lambdify((_a, _b), OR_POLY, "math")
    f_not = sympy.lambdify(_a, NOT_POLY, "math")

    worst = 0.0
    bad: list[str] = []
    for a, b in pts:
        for name, got, exp in (
            ("and", truth(kand(mt(a), mt(b))), f_and(a, b)),
            ("or", truth(kor(mt(a), mt(b))), f_or(a, b)),
        ):
            err = abs(got - exp)
            worst = max(worst, err)
            if err >= 1e-5:
                bad.append(f"{name}({a:+.2f},{b:+.2f}) substrate={got:+.5f} sym={exp:+.5f}")
    for a in grid + offgrid:
        err = abs(truth(knot(mt(a))) - f_not(a))
        worst = max(worst, err)
        if err >= 1e-5:
            bad.append(f"not({a:+.2f}) mismatch err={err:.3e}")

    print(f"[fv-poly] symbolic-vs-substrate worst |err| = {worst:.3e} "
          f"over {len(pts)} grid+off-grid points")
    assert not bad, (
        "symbolic connective polynomial has drifted from the compiled "
        f"substrate form — the closed-form bound would not apply: {bad}"
    )


def test_branch_range_obligation_discharged_closed_form() -> None:
    """Step 2: bound each (validated) connective polynomial in closed form over
    the truth domain [-1,+1]^2 and assert the exact range is within [-1,+1].

    This is the Pillar-2 branch-range obligation discharged as the spec states
    it — a polynomial extremum problem solved exactly, not sampled.
    """
    box2 = [(_a, -1, 1), (_b, -1, 1)]
    box1 = [(_a, -1, 1)]

    results = {
        "and": bound_polynomial_over_box(AND_POLY, box2),
        "or": bound_polynomial_over_box(OR_POLY, box2),
        "not": bound_polynomial_over_box(NOT_POLY, box1),
    }

    for name, rb in results.items():
        print(f"[fv-poly] {name}: exact range [{rb.minimum}, {rb.maximum}] "
              f"({rb.candidates} critical points evaluated)")
        assert rb.within(-1, 1), (
            f"connective '{name}' range [{rb.minimum}, {rb.maximum}] escapes "
            f"the truth domain [-1, +1] — branch-range obligation FAILS"
        )

    # The exact values, not just containment: min=-1, max=+1 for all three.
    assert results["and"].minimum == sympy.Integer(-1)
    assert results["and"].maximum == sympy.Integer(1)
    assert results["or"].minimum == sympy.Integer(-1)
    assert results["or"].maximum == sympy.Integer(1)


# Composed / whole-program range-soundness ---------------------------------
#
# The closed-form bounder above discharges the obligation for the THREE atomic
# connectives. The whole-program obligation — an arbitrarily NESTED Kleene
# expression's range stays in [-1,+1] — is NOT discharged by bounding the
# composed (high-degree) polynomial directly: that route's cost explodes with
# nesting depth (see experiments/fv_composed_branch_range_cost.py and
# planning/findings/2026-06-20-fv-composed-branch-range-cost.md). It is
# discharged instead by STRUCTURAL INDUCTION on the expression tree
# (`range_sound_by_composition`): each connective maps [-1,+1]^k into [-1,+1]
# exactly (the per-connective lemma above), so any composition of them over
# truth inputs in [-1,+1] is range-sound, degree-insensitively. This matches
# paper/formal-verification/paper.md §3.2 ("Range-soundness scales to arbitrary
# depth by composition, the bounder is NOT on the critical path for depth").

# (label, expr_src, var_names) — increasing branch-nesting depth.
_COMPOSED_CASES = [
    ("(a&&b)||c", "(a && b) || c", ["a", "b", "c"]),
    ("(a&&b)||(c&&d)", "(a && b) || (c && d)", ["a", "b", "c", "d"]),
    ("!((a&&b)||c)", "!((a && b) || c)", ["a", "b", "c"]),
    ("((a&&b)||(c&&d))&&!e", "((a && b) || (c && d)) && !e",
     ["a", "b", "c", "d", "e"]),
    ("((a&&b)||(c&&d))&&(!e||(a&&c))",
     "((a && b) || (c && d)) && (!e || (a && c))", ["a", "b", "c", "d", "e"]),
]


@pytest.mark.parametrize("label,src,vs", _COMPOSED_CASES,
                         ids=[c[0] for c in _COMPOSED_CASES])
def test_composed_range_sound_by_structural_induction(label, src, vs):
    """Whole-program range-soundness: every nested composition of the proven
    connectives is range-sound at ANY depth, decided structurally (degree-
    insensitively) — the discharge the closed-form direct bound cannot scale to."""
    assert range_sound_by_composition(src, vs), (
        f"composed expression {label!r} should be range-sound by induction "
        f"(it is built solely from proven connectives)"
    )


def test_composition_refuses_non_connective_operators():
    """The structural argument is SOUND, not vacuous: it returns False for any
    expression that uses an operator NOT proven to map [-1,+1] into [-1,+1], so
    the [-1,+1] conclusion is never asserted where it does not follow."""
    # Bundle (+) and a comparison are not range-sound connectives → refuse.
    assert not range_sound_by_composition("a + b", ["a", "b"])
    assert not range_sound_by_composition("(a && b) + c", ["a", "b", "c"])
    # ...but the same shape with only connectives IS accepted.
    assert range_sound_by_composition("(a && b) || c", ["a", "b", "c"])


def test_composition_agrees_with_direct_bound_on_the_per_connective_lemma():
    """Anchor the inductive lemma to the exact tool. The closed-form direct
    bounder only completes on a SINGLE connective — depth-2 compositions already
    time out (>30 s; see experiments/fv_composed_branch_range_cost.py), which is
    exactly why composition, not direct bounding, discharges whole programs. On
    the case the direct route CAN evaluate (one connective), its exact range is
    [-1,+1] AND composition agrees — so composition is a sound shortcut for the
    lemma it rests on, not a weaker check."""
    src, vs = "a && b", ["a", "b"]  # single connective: the only direct-tractable case
    assert range_sound_by_composition(src, vs)
    rb = check_branch_range(src, vs)
    assert rb.within(-1, 1), f"direct exact range [{rb.minimum},{rb.maximum}] escapes"
    assert rb.minimum == sympy.Integer(-1) and rb.maximum == sympy.Integer(1)
