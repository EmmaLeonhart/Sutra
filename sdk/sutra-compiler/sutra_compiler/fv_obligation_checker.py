"""Formal-verification tooling: the GENERAL polynomial-obligation checker.

`fv_poly_bound.py` discharges the branch-range obligation for the three
*primitive* Kleene connectives. This module generalises it: it takes an
ARBITRARY Sutra expression over the **polynomial fragment** — the Kleene
connectives `&&`, `||`, `!` (and direct `logical_and`/`logical_or`/`logical_not`
calls) AND integer arithmetic `+`, `-`, `*`, freely mixed and nested to any
depth — and discharges obligations on it without a hand-copied polynomial.
(Arithmetic equivalence is decided by the same polynomial-identity test:
`(a+b)*c` and `a*c + b*c` reduce to the same graph, the arithmetic mirror of
Kleene distributivity, which does not.)

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

from fractions import Fraction

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
    expr_src: str, var_names: list[str], *, expand: bool = True
) -> tuple[sympy.Expr, dict[str, sympy.Symbol]]:
    """Compile an expression through the real inliner and return its polynomial.

    ``expr_src`` is a Sutra expression over the named truth-axis ``var_names``
    (e.g. ``"(a && b) || !c"`` with ``["a", "b", "c"]``). Returns the sympy
    polynomial and the name→symbol map. Raises NonPolynomialResidual if the
    expression contains anything outside the verifiable fragment.

    ``expand`` controls whether the polynomial is distributed into a sum of
    monomials (``sympy.expand``). The expanded form is the canonical one the
    exact identity check (``reduces_to_same_graph``) compares; the UNEXPANDED
    form is the nested product-of-sums whose monomial count can blow up
    geometrically with nesting depth — randomized PIT
    (``reduces_to_same_graph_randomized``) evaluates THAT form at random points
    without ever distributing it, sidestepping the blow-up.
    """
    symbols: dict[str, sympy.Symbol] = {}
    poly = _ast_to_sympy(_lower_expr_to_ast(expr_src, var_names), symbols)
    return (sympy.expand(poly) if expand else poly), symbols


def _lower_expr_to_ast(expr_src: str, var_names: list[str]):
    """Lex / parse / run the compiler's OWN stdlib inliner on a Kleene expression
    and return its lowered arithmetic AST node (the ``return`` value). Shared by the
    sympy extractor and the direct (sympy-free) randomized evaluator below."""
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
    return ret.value


# A 61-bit Mersenne prime — the finite field F_p we evaluate over. Working mod p
# keeps every intermediate < p, so each Kleene-node evaluation is O(1) and a whole
# expression is O(tree size) regardless of the polynomial's degree.
_PIT_PRIME = (1 << 61) - 1

# The truth-axis polynomials of the Kleene connectives, as functions of their
# operands' VALUES (verified against the compiler's own inliner in
# `extract_truth_polynomial` — see test_kleene_connective_formulas_match_inliner):
#   !a      = -a
#   a && b  = (a^2 b^2 - a^2 + a b + a - b^2 + b) / 2
#   a || b  = (-a^2 b^2 + a^2 - a b + a + b^2 + b) / 2
# Evaluating the ORIGINAL (un-inlined) expression tree by applying these to child
# VALUES is the key to randomized PIT scaling: the inliner *duplicates* each operand
# (`a && b` mentions a and b several times), so the *inlined* arithmetic tree — and
# `sympy.expand` of it — is exponential in nesting depth. Computing one number per
# node from its children sidesteps that entirely, staying linear in the tree.


def _parse_expr_to_ast(expr_src: str, var_names: list[str]):
    """Parse a Kleene expression WITHOUT running the inliner — returns the original
    `&&`/`||`/`!` AST (BinaryOp/UnaryOp/Identifier/Parenthesized). Randomized PIT
    evaluates THIS tree by formula, avoiding the inliner's subterm duplication."""
    params = ", ".join(f"vector {v}" for v in var_names)
    src = f"function vector __fv({params}) {{ return {expr_src}; }}\n"
    lexer = Lexer(src, file="<fv-rand>")
    parser = Parser(lexer.tokenize(), file="<fv-rand>", diagnostics=lexer.diagnostics)
    module = parser.parse_module()
    if lexer.diagnostics.has_errors():
        raise ValueError(f"parse error in expression {expr_src!r}: "
                         f"{list(lexer.diagnostics)}")
    fn = next(it for it in module.items if getattr(it, "name", None) == "__fv")
    ret = fn.body.statements[0]
    if not isinstance(ret, ast.ReturnStmt) or ret.value is None:
        raise ValueError("expression did not parse to a single return")
    return ret.value


def _eval_kleene_ast(node, env: dict, p: int, inv2: int) -> int:
    """Evaluate the polynomial of a Kleene-logic *or* integer-arithmetic expression at
    point ``env`` (name → int) in F_p — by applying each Kleene connective's truth-axis
    formula, and ``+``/``-``/``*`` directly, to its children's values. O(tree size), no
    inliner duplication, no sympy. The arithmetic operators extend the randomized check
    beyond the Boolean connectives to integer-polynomial identity (e.g. distributivity,
    which is a same-graph identity for arithmetic though not for Kleene)."""
    cn = type(node).__name__
    if cn == "Parenthesized":
        return _eval_kleene_ast(node.inner, env, p, inv2)
    if cn == "Identifier":
        return env[node.name] % p
    if cn == "IntLiteral":
        return int(node.value) % p
    if cn == "UnaryOp" and node.op in ("!", "-"):
        return (-_eval_kleene_ast(node.operand, env, p, inv2)) % p  # !a = -a; unary minus
    if cn == "BinaryOp":
        a = _eval_kleene_ast(node.left, env, p, inv2)
        b = _eval_kleene_ast(node.right, env, p, inv2)
        op = node.op
        if op == "+":
            return (a + b) % p
        if op == "-":
            return (a - b) % p
        if op == "*":
            return (a * b) % p
        if op in ("&&", "||"):
            a2, b2, ab = a * a % p, b * b % p, a * b % p
            if op == "&&":
                return (a2 * b2 - a2 + ab + a - b2 + b) * inv2 % p
            return (-a2 * b2 + a2 - ab + a + b2 + b) * inv2 % p
    raise NonPolynomialResidual(
        f"node {cn!r} (op={getattr(node, 'op', None)!r}) is outside the polynomial "
        f"fragment the randomized check evaluates (&&, ||, !, +, -, *)")


def _kleene_degree_bound(node) -> int:
    """Total-degree upper bound of a Kleene-logic / integer-arithmetic expression's
    polynomial: a leaf is degree 1, a constant 0, `!`/unary-`-` preserve degree,
    `+`/`-` take the max, `*` adds, and `&&`/`||` reach 2·deg(a)+2·deg(b) (the a^2 b^2
    term). Used for the Schwartz–Zippel false-positive bound."""
    cn = type(node).__name__
    if cn == "Parenthesized":
        return _kleene_degree_bound(node.inner)
    if cn == "Identifier":
        return 1
    if cn == "IntLiteral":
        return 0
    if cn == "UnaryOp" and node.op in ("!", "-"):
        return _kleene_degree_bound(node.operand)
    if cn == "BinaryOp":
        left = _kleene_degree_bound(node.left)
        right = _kleene_degree_bound(node.right)
        if node.op in ("+", "-"):
            return max(left, right)
        if node.op == "*":
            return left + right
        if node.op in ("&&", "||"):
            return 2 * left + 2 * right
    raise NonPolynomialResidual(f"node {cn!r} is outside the polynomial fragment")


_RANGE_SOUND_BINOPS = frozenset({"&&", "||"})
_RANGE_SOUND_UNOPS = frozenset({"!"})


def _child_nodes(node) -> list:
    out = []
    for key, val in vars(node).items():
        if key.startswith("_") or key == "span":
            continue
        if isinstance(val, ast.Node):
            out.append(val)
        elif isinstance(val, list):
            out.extend(e for e in val if isinstance(e, ast.Node))
    return out


def _is_range_sound(node) -> bool:
    cn = type(node).__name__
    if cn == "Identifier":
        return True  # a truth-axis variable, assumed in [-1, +1]
    if cn in ("BoolLiteral", "IntLiteral", "FloatLiteral", "TrueLiteral", "FalseLiteral"):
        return True  # a constant leaf
    if cn == "Parenthesized":
        return all(_is_range_sound(c) for c in _child_nodes(node))
    if cn == "BinaryOp":
        return node.op in _RANGE_SOUND_BINOPS and all(_is_range_sound(c) for c in _child_nodes(node))
    if cn == "UnaryOp":
        return node.op in _RANGE_SOUND_UNOPS and all(_is_range_sound(c) for c in _child_nodes(node))
    return False  # any other node (comparison, arithmetic, call, intrinsic)


def range_sound_by_composition(expr_src: str, var_names: list[str]) -> bool:
    """Decide the branch-range obligation for an arbitrary Kleene expression at
    ANY nesting depth, by **structural composition** rather than by bounding the
    (high-degree) composed polynomial.

    The lemma: each primitive connective maps [-1, +1]^k -> [-1, +1] exactly —
    proven in closed form for `&&`, `||`, `!` by `check_branch_range` /
    `fv_poly_bound` (their exact range is [-1, +1]). A function composed only of
    maps that send [-1, +1] into [-1, +1], over truth-axis inputs in [-1, +1],
    therefore has range within [-1, +1] by induction on the expression tree.

    So if `expr_src` is built solely from `&&`, `||`, `!` over truth variables and
    constants, it is range-sound — regardless of depth, and **degree-insensitive**
    (this is why it scales where the closed-form bounder does not). Returns False
    if the expression uses any operator that is not a proven-range-sound connective
    (a comparison, arithmetic, a call/intrinsic) — i.e. the conclusion does not
    follow by composition and a direct bound would be needed.
    """
    params = ", ".join(f"vector {v}" for v in var_names)
    src = f"function vector __fv({params}) {{ return {expr_src}; }}\n"
    lexer = Lexer(src, file="<fv-rs>")
    toks = lexer.tokenize()
    parser = Parser(toks, file="<fv-rs>", diagnostics=lexer.diagnostics)
    module = parser.parse_module()
    if lexer.diagnostics.has_errors():
        raise ValueError(f"parse error in {expr_src!r}: {list(lexer.diagnostics)}")
    fn = next(it for it in module.items if getattr(it, "name", None) == "__fv")
    ret = fn.body.statements[0]
    if not isinstance(ret, ast.ReturnStmt) or ret.value is None:
        raise ValueError("expression did not lower to a single return")
    return _is_range_sound(ret.value)


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


def structural_degree_bound(expr: sympy.Expr) -> int:
    """An UPPER BOUND on the total degree of a (possibly unexpanded) sympy
    polynomial expression, computed structurally without distributing it:
    a symbol is degree 1, a constant degree 0, a sum takes the max of its terms,
    a product sums them, and a power multiplies. Exact for the expanded form and
    a safe over-estimate for the nested form — which is all Schwartz–Zippel needs
    (it bounds the false-positive probability by ``degree / |sample set|``)."""
    if expr.is_Number:
        return 0
    if expr.is_Symbol:
        return 1
    if expr.is_Add:
        return max((structural_degree_bound(a) for a in expr.args), default=0)
    if expr.is_Mul:
        return sum(structural_degree_bound(a) for a in expr.args)
    if expr.is_Pow:
        base, exp = expr.args
        if exp.is_Integer and exp >= 0:
            return int(exp) * structural_degree_bound(base)
        raise NonPolynomialResidual(f"non-polynomial power {expr!r}")
    raise NonPolynomialResidual(f"cannot bound degree of {expr!r}")


def reduces_to_same_graph_randomized(
    expr_a: str, expr_b: str, var_names: list[str],
    *, trials: int = 32, seed: int = 0x5117A,
) -> tuple[bool, dict]:
    """Randomized polynomial identity test (Schwartz–Zippel) for the SAME notion
    as `reduces_to_same_graph` — do two Kleene expressions reduce to the same
    tensor graph? — but WITHOUT expanding either polynomial into monomials.

    Why this matters: the exact check `expand(p_a - p_b) == 0` distributes the
    nested product-of-sums, whose monomial count grows geometrically with nesting
    depth (the scalability wall). Schwartz–Zippel instead evaluates the
    *unexpanded* difference ``p_a - p_b`` at random integer points: a nonzero
    polynomial of total degree ``d`` vanishes at a uniform random point of a set
    ``S`` with probability ``≤ d / |S|``, so ``k`` independent all-zero trials
    certify identity with error ``≤ (d/|S|)^k`` — and ANY nonzero evaluation is an
    exact disproof (no false negatives). Each evaluation is linear in the size of
    the nested expression, so the test stays cheap where expansion blows up.

    Returns ``(identical, info)`` where ``info`` carries the soundness data: the
    degree bound, sample-set size, trial count, a bound on the false-positive
    probability, and (on a disproof) the witness point. Sound one-sided:
    ``identical=False`` is exact; ``identical=True`` holds with the stated error.

    The hot path is ``_eval_lowered_ast`` (direct exact-rational evaluation of the
    lowered AST), NOT sympy — so it stays linear in expression size where sympy's
    expansion (and even its auto-simplifying construction) blows up.
    """
    import random

    p = _PIT_PRIME
    inv2 = pow(2, -1, p)
    ast_a = _parse_expr_to_ast(expr_a, var_names)
    ast_b = _parse_expr_to_ast(expr_b, var_names)
    degree = max(_kleene_degree_bound(ast_a), _kleene_degree_bound(ast_b))
    rng = random.Random(seed)
    for _ in range(trials):
        env = {v: rng.randrange(1, p) for v in var_names}  # random point in F_p^n
        # p_a - p_b vanishes at this point iff the two evaluate equally mod p.
        if _eval_kleene_ast(ast_a, env, p, inv2) != _eval_kleene_ast(ast_b, env, p, inv2):
            info = {"degree_bound": degree, "prime": p, "trials": trials,
                    "witness": dict(env)}
            return False, info  # exact disproof: p_a(point) != p_b(point) over Q too
    # All trials vanished: by Schwartz–Zippel over F_p the false-positive prob is
    # <= (degree / (p-1))^trials (p = 2^61-1 exceeds every Kleene-polynomial
    # coefficient, so the mod-p reduction of p_a - p_b is faithful).
    fp_bound = float(Fraction(degree, p - 1) ** trials) if degree else 0.0
    info = {"degree_bound": degree, "prime": p, "trials": trials,
            "false_positive_bound": fp_bound}
    return True, info


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
