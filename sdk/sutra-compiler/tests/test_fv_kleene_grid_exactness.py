"""Formal-verification artifact: Kleene grid-exactness of the polynomial
logical connectives.

`planning/sutra-spec/formal-verification.md` § Pillar 2 ("grid exactness"
obligation): the branchless polynomial forms the compiler emits for `&&`,
`||`, `!` must reproduce the three-valued Kleene truth table EXACTLY at the
nine grid points {-1, 0, +1}^2 (true=+1, unknown=0, false=-1). On that
antipodal encoding Kleene strong logic is and=min, or=max, not=negate.

This is the first mechanical discharge of an FV obligation: it compiles the
REAL pipeline (parse -> inline the polynomial -> simplify -> torch codegen
-> runtime) and evaluates the connectives at every grid point on the
substrate, asserting an exact match. Referenced by
`paper/formal-verification/paper.md`. If a future change makes a connective
non-exact on the grid, this fails loudly.

The emitted polynomials (see `sutra_compiler/inliner.py`):
    !x     = -x
    a && b = (a + b + ab - a^2 - b^2 + a^2 b^2) / 2     (smooth min)
    a || b = (a + b - ab + a^2 + b^2 - a^2 b^2) / 2     (smooth max)
"""
from __future__ import annotations

import itertools

import pytest

torch = pytest.importorskip(
    "torch", reason="grid-exactness runs on the torch substrate"
)

from sutra_compiler.codegen_pytorch import translate_module as torch_translate
from sutra_compiler.lexer import Lexer
from sutra_compiler.parser import Parser

GRID = (-1.0, 0.0, 1.0)  # false, unknown, true

# vector-typed params so `&&`/`||`/`!` lower to the inlined polynomials on
# whatever truth-axis vectors we pass; a trivial main keeps the module valid.
SRC = """
function vector kand(vector a, vector b) { return a && b; }
function vector kor(vector a, vector b)  { return a || b; }
function vector knot(vector a)           { return !a; }
function vector main() { return true && false; }
"""


def _build() -> dict:
    lexer = Lexer(SRC, file="<fv-kleene>")
    toks = lexer.tokenize()
    parser = Parser(toks, file="<fv-kleene>", diagnostics=lexer.diagnostics)
    module = parser.parse_module()
    assert not lexer.diagnostics.has_errors(), list(lexer.diagnostics)
    py = torch_translate(module, llm_model="nomic-embed-text", runtime_dim=768)
    ns: dict = {}
    exec(compile(py, "<fv-kleene>", "exec"), ns)
    return ns


def test_kleene_grid_exactness() -> None:
    ns = _build()
    vsa = ns["_VSA"]
    kand, kor, knot = ns["kand"], ns["kor"], ns["knot"]

    def truth(v) -> float:
        return float(vsa.truth(v))

    def mt(x: float):
        return vsa.make_truth(x)

    worst = 0.0
    bad: list[str] = []
    for a, b in itertools.product(GRID, GRID):
        got_and = truth(kand(mt(a), mt(b)))
        got_or = truth(kor(mt(a), mt(b)))
        exp_and, exp_or = min(a, b), max(a, b)
        for name, got, exp in (("and", got_and, exp_and), ("or", got_or, exp_or)):
            err = abs(got - exp)
            worst = max(worst, err)
            if err >= 1e-5:
                bad.append(f"{name}({a:+.0f},{b:+.0f})={got:+.4f} exp {exp:+.0f}")
    for a in GRID:
        got_not = truth(knot(mt(a)))
        err = abs(got_not - (-a))
        worst = max(worst, err)
        if err >= 1e-5:
            bad.append(f"not({a:+.0f})={got_not:+.4f} exp {-a:+.0f}")

    print(f"[fv-kleene] grid-exactness worst |err| = {worst:.3e}")
    assert not bad, (
        f"Kleene connectives NOT exact on the {{-1,0,+1}}^2 grid "
        f"(worst |err|={worst:.3e}): {bad}"
    )


def test_kleene_range_within_truth_domain() -> None:
    """FV §3.2 off-grid branch-range obligation: the connective polynomials
    must produce VALID truth values — stay within [-1, +1] — across the WHOLE
    continuous fuzzy domain [-1,+1]^2, not just at the {-1,0,+1} grid.

    Off the grid the polynomials interpolate (they do not reproduce min/max
    exactly there — that is by design, C^inf between grid points); what must
    hold for them to be sound truth-axis operations is that they never
    over/undershoot the truth range. Measured on a dense 21x21 sweep on the
    substrate; reports the real min/max so an excursion would be visible, not
    hidden.
    """
    ns = _build()
    vsa = ns["_VSA"]
    kand, kor, knot = ns["kand"], ns["kor"], ns["knot"]

    def truth(v) -> float:
        return float(vsa.truth(v))

    def mt(x: float):
        return vsa.make_truth(x)

    n = 21
    xs = [-1.0 + 2.0 * i / (n - 1) for i in range(n)]
    lo, hi = 1.0, -1.0
    for a in xs:
        for b in xs:
            for val in (truth(kand(mt(a), mt(b))), truth(kor(mt(a), mt(b)))):
                lo, hi = min(lo, val), max(hi, val)
    for a in xs:
        val = truth(knot(mt(a)))
        lo, hi = min(lo, val), max(hi, val)

    print(f"[fv-kleene] truth-value range over [-1,1]^2: "
          f"min={lo:.6f} max={hi:.6f}")
    tol = 1e-5
    assert -1.0 - tol <= lo and hi <= 1.0 + tol, (
        f"a Kleene connective produced an out-of-range truth value off-grid: "
        f"min={lo:.6f} max={hi:.6f} — must stay within [-1, +1]"
    )
