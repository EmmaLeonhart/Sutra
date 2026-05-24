"""Formal-verification tooling: the GENERAL polynomial-obligation checker.

`fv_poly_bound.py` discharges the branch-range obligation for the three
*primitive* Kleene connectives. This module generalises it: it takes an
ARBITRARY Sutra expression built from the Kleene connectives `&&`, `||`, `!`
(and direct `logical_and`/`logical_or`/`logical_not` calls), nested to any
depth, and discharges obligations on it — without a hand-copied polynomial.

How it stays faithful to what the compiler actually emits
---------------------------------------------------------
It does not re-derive the connective formulas. It runs the compiler's OWN
lowering pass (`inline_stdlib_calls`, the same pass `translate_module` uses)
on the parsed expression, then walks the resulting *arithmetic* AST — the
exact tree the codegen turns into tensor ops — into a sympy polynomial. The
only nodes it accepts are the ones the inliner produces for pure Kleene logic:
`BinaryOp` (`+`/`-`/`*`, and `/` by a constant), `Parenthesized`, `Identifier`,
and integer/float literals.

The honest boundary (CLAUDE.md §"Integrity"): any node it cannot reduce to a
polynomial — a comparison (`==`/`>`/`<`), or an intrinsic call (`make_real`,
`bind`, `bundle`, an embedding-model invocation) — makes it RAISE
`NonPolynomialResidual`. It never guesses a value for a term it does not
understand. So the fragment it covers is exactly the pure-Kleene-logic one,
named rather than papered over.

Obligations it discharges on that fragment
------------------------------------------
- ``reduces_to_same_graph`` — the Pillar-1 *reduction* notion: do two
  expressions reduce to the SAME tensor graph? Decided by polynomial identity
  (``expand(p1 - p2) == 0``). This is the notion the paper's "semantically
  equivalent programs reduce to the same graph" claim is about, and it is
  exact and decidable for this fragment.
- ``kleene_equivalent`` — the *three-valued-logic* notion: do two expressions
  agree at every point of the {-1, 0, +1}^n Kleene grid? Decided by evaluating
  both polynomials on the finite grid.
- ``check_branch_range`` — the §3.2 branch-range obligation: the exact range
  of the reduced polynomial over [-1, +1]^n.

These two equivalence notions are NOT the same, and the difference is a real
result, not a wrinkle. Example: distributivity, ``a && (b || c)`` vs
``(a && b) || (a && c)``, is ``kleene_equivalent`` (the two agree at all 27
grid points — Kleene logic is a distributive lattice) but NOT
``reduces_to_same_graph`` (their polynomial interpolants differ off-grid, so
the reduced tensor graphs differ). De Morgan and commutativity, by contrast,
are both — they reduce to identical polynomials. So the polynomial reduction
canonicalises *some* logical equivalences but not all; distributivity is a
concrete witness that "reduce to the same graph" is strictly stronger than
"logically equivalent." (See planning/findings/2026-05-24-distributivity-not-
canonical.md.)

Scope/limit (measured, not hidden): ``check_branch_range`` solves a
critical-point system per box face with sympy; for deeply nested expressions
over 4+ variables the reduced polynomial's degree grows (the §3.4
expression/degree growth) and the solve becomes intractable / hangs. The
bounder is reliable for the primitive connectives and shallow nestings over a
few variables; it does NOT currently scale to deep, high-variable nesting. The
two equivalence checks above do NOT have this problem (identity and grid
evaluation are cheap).

Callers that need to trust a result against the substrate (not just against
the inliner) should also cross-check the extracted polynomial against a
compiled run — see ``tests/test_fv_general_checker.py``.
"""
from __future__ import annotations

import sympy

from . import ast_nodes as ast
from .fv_poly_bound import RangeBound, bound_polynomial_over_box
from .inliner import inline_stdlib_calls
from .lexer import Lexer
from .parser import Parser


class NonPolynomialResidual(Exception):
    """Raised when an expression contains a term the checker cannot reduce to
    a polynomial (a comparison or a runtime intrinsic). The checker refuses
    rather than fabricate a value — the boundary of the verifiable fragment."""


def _ast_to_sympy(node, symbols: dict) -> sympy.Expr:
    """Walk an inlined arithmetic AST node into a sympy expression.

    Accepts only the node shapes the inliner emits for Kleene logic; anything
    else raises NonPolynomialResidual (the named verifiable boundary).
    """
    cn = type(node).__name__
    if cn == "Parenthesized":
        return _ast_to_sympy(node.inner, symbols)
    if cn == "Identifier":
        return symbols.setdefault(node.name, sympy.Symbol(node.name, real=True))
    if cn == "IntLiteral":
        return sympy.Integer(int(node.value))
    if cn == "FloatLiteral":
        # nsimplify turns 0.5 into the exact rational 1/2 (the inliner's *0.5).
        return sympy.nsimplify(node.value)
    if cn == "BinaryOp":
        left = _ast_to_sympy(node.left, symbols)
        right = _ast_to_sympy(node.right, symbols)
        op = node.op
        if op == "+":
            return left + right
        if op == "-":
            return left - right
        if op == "*":
            return left * right
        if op == "/":
            # Division is polynomial only when the denominator is a constant.
            if not right.free_symbols:
                return left / right
            raise NonPolynomialResidual(
                f"division by a non-constant {right} — not a polynomial obligation"
            )
        raise NonPolynomialResidual(f"operator {op!r} is not polynomial")
    raise NonPolynomialResidual(
        f"cannot reduce AST node {cn!r} to a polynomial — a non-arithmetic "
        f"residual remains after inlining (a comparison like ==/>/<, or an "
        f"intrinsic such as make_real/bind/bundle). This expression is "
        f"outside the checker's pure-Kleene-logic fragment."
    )


def extract_truth_polynomial(
    expr_src: str, var_names: list[str]
) -> tuple[sympy.Expr, dict[str, sympy.Symbol]]:
    """Compile an expression through the real inliner and return its polynomial.

    ``expr_src`` is a Sutra expression over the named truth-axis ``var_names``
    (e.g. ``"(a && b) || !c"`` with ``["a", "b", "c"]``). Returns the expanded
    sympy polynomial and the name→symbol map. Raises NonPolynomialResidual if
    the expression contains anything outside the verifiable fragment.
    """
    params = ", ".join(f"vector {v}" for v in var_names)
    src = f"function vector __fv({params}) {{ return {expr_src}; }}\n"
    lexer = Lexer(src, file="<fv-general>")
    toks = lexer.tokenize()
    parser = Parser(toks, file="<fv-general>", diagnostics=lexer.diagnostics)
    module = parser.parse_module()
    if lexer.diagnostics.has_errors():
        raise ValueError(f"parse error in expression {expr_src!r}: "
                         f"{list(lexer.diagnostics)}")
    inline_stdlib_calls(module)  # the compiler's OWN lowering pass
    fn = next(it for it in module.items if getattr(it, "name", None) == "__fv")
    ret = fn.body.statements[0]
    if not isinstance(ret, ast.ReturnStmt) or ret.value is None:
        raise ValueError("expression did not lower to a single return")
    symbols: dict[str, sympy.Symbol] = {}
    poly = _ast_to_sympy(ret.value, symbols)
    return sympy.expand(poly), symbols


def check_branch_range(expr_src: str, var_names: list[str]) -> RangeBound:
    """Discharge the §3.2 branch-range obligation for an arbitrary Kleene
    expression: return the exact range of its reduced polynomial over the
    truth box [-1, +1]^n. (`RangeBound.within(-1, 1)` decides soundness.)
    """
    poly, symbols = extract_truth_polynomial(expr_src, var_names)
    used = sorted(poly.free_symbols, key=lambda s: s.name)
    if not used:  # a constant expression
        const = sympy.Integer(0) + poly
        return RangeBound(minimum=const, maximum=const, argmin={}, argmax={},
                          candidates=1)
    box = [(s, -1, 1) for s in used]
    return bound_polynomial_over_box(poly, box)


def reduces_to_same_graph(
    expr_a: str, expr_b: str, var_names: list[str]
) -> bool:
    """Decide whether two Kleene expressions reduce to the SAME tensor graph —
    the Pillar-1 reduction notion behind "semantically equivalent programs
    reduce to the same graph." Decided exactly by polynomial identity:
    ``expand(p_a - p_b)`` is identically zero iff the reduced polynomials (the
    graphs) are equal everywhere on [-1, +1]^n, not merely on the grid.

    NB this is STRICTLY STRONGER than `kleene_equivalent`: two expressions can
    be logically equivalent (agree on the grid) yet reduce to different graphs
    (differ off-grid) — distributivity is the witness.
    """
    poly_a, _ = extract_truth_polynomial(expr_a, var_names)
    poly_b, _ = extract_truth_polynomial(expr_b, var_names)
    return sympy.expand(poly_a - poly_b) == 0


def kleene_equivalent(
    expr_a: str, expr_b: str, var_names: list[str]
) -> bool:
    """Decide three-valued-logic equivalence: do two Kleene expressions agree
    at every point of the {-1, 0, +1}^n grid? Evaluates both reduced
    polynomials on the finite grid (cheap; no critical-point solve). This is
    the weaker, logic-level notion — `reduces_to_same_graph` implies it but not
    conversely.
    """
    import itertools

    poly_a, syms_a = extract_truth_polynomial(expr_a, var_names)
    poly_b, syms_b = extract_truth_polynomial(expr_b, var_names)
    grid = (sympy.Integer(-1), sympy.Integer(0), sympy.Integer(1))
    for point in itertools.product(grid, repeat=len(var_names)):
        env_a = {syms_a[v]: val for v, val in zip(var_names, point) if v in syms_a}
        env_b = {syms_b[v]: val for v, val in zip(var_names, point) if v in syms_b}
        if sympy.simplify(poly_a.subs(env_a) - poly_b.subs(env_b)) != 0:
            return False
    return True
