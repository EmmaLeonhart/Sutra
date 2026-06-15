"""Formal-verification artifact: the GENERAL polynomial-obligation checker.

`fv_poly_bound` discharges obligations for the three *primitive* Kleene
connectives. `fv_obligation_checker` generalises to ARBITRARY Kleene
expressions (`&&`/`||`/`!`, any depth) by running the compiler's own inliner
and walking the lowered arithmetic into a sympy polynomial. What it discharges,
and the honest limits, are below — every claim here is checked by a real run.

Two equivalence notions, and why they differ (a real result):
  * `reduces_to_same_graph` — polynomial identity (same tensor graph, agree
    everywhere on [-1,1]^n). The notion behind the paper's canonicalisation
    claim.
  * `kleene_equivalent` — agree on the {-1,0,+1}^n grid (three-valued logic).
  Distributivity is `kleene_equivalent` but NOT `reduces_to_same_graph`: equal
  on the grid, different polynomials off-grid. De Morgan/commutativity are
  both. So the reduction canonicalises some equivalences, not all.

Honest scope (measured): `check_branch_range` solves a critical-point system
per box face; it is reliable for the primitive connectives and shallow
2-variable nestings, but for deep 4+-variable nestings the polynomial degree
grows (the §3.4 explosion) and the sympy solve becomes intractable — so this
test bounds only the tractable cases and does NOT pretend the bounder scales.
The equivalence checks have no such limit (identity / grid eval are cheap).

Integrity guard (CLAUDE.md §"Integrity"): the polynomial is extracted from the
inliner, but the obligation is about what the SUBSTRATE computes.
`test_extracted_polynomial_matches_substrate` compiles a sample expression and
checks the extracted polynomial against the real torch substrate on the grid,
via exact `.subs` (no lambdify), before the result is trusted.
"""
from __future__ import annotations

import itertools

import pytest

sympy = pytest.importorskip("sympy", reason="the checker needs sympy (sutra-dev[dev])")

from sutra_compiler.fv_obligation_checker import (  # noqa: E402
    NonPolynomialResidual,
    check_branch_range,
    extract_truth_polynomial,
    kleene_equivalent,
    range_sound_by_composition,
    reduces_to_same_graph,
    reduces_to_same_graph_randomized,
    structural_degree_bound,
)


def test_extraction_produces_a_polynomial() -> None:
    """An arbitrary Kleene expression extracts to a polynomial (no residual)."""
    poly, syms = extract_truth_polynomial("(a && b) || !c", ["a", "b", "c"])
    assert poly.free_symbols == {syms["a"], syms["b"], syms["c"]}
    # double negation collapses to the bare variable
    poly2, _ = extract_truth_polynomial("!!a", ["a"])
    assert sympy.expand(poly2 - sympy.Symbol("a", real=True)) == 0


def test_reduces_to_same_graph_for_polynomial_identities() -> None:
    """De Morgan, commutativity, double-negation reduce to identical graphs."""
    assert reduces_to_same_graph("!!a", "a", ["a"])
    assert reduces_to_same_graph("a && b", "b && a", ["a", "b"])
    assert reduces_to_same_graph("!(a && b)", "!a || !b", ["a", "b"])
    assert reduces_to_same_graph("!(a || b)", "!a && !b", ["a", "b"])
    # Not a vacuous True: clearly different expressions are not the same graph.
    assert not reduces_to_same_graph("a && b", "a || b", ["a", "b"])
    assert not reduces_to_same_graph("a", "!a", ["a"])


def test_randomized_pit_agrees_with_exact_identity() -> None:
    """Randomized PIT (Schwartz-Zippel) decides the SAME notion as the exact
    `reduces_to_same_graph` — verified to AGREE on identities (De Morgan,
    commutativity, double negation → same graph) and non-identities (distributivity,
    absorption, plainly different → not the same graph)."""
    same = [("!!a", "a", ["a"]), ("a && b", "b && a", ["a", "b"]),
            ("!(a && b)", "!a || !b", ["a", "b"]), ("!(a || b)", "!a && !b", ["a", "b"])]
    diff = [("(a && b) || (a && c)", "a && (b || c)", ["a", "b", "c"]),  # distributivity
            ("a || (a && b)", "a", ["a", "b"]),  # absorption (off-grid)
            ("a && b", "a || b", ["a", "b"]), ("a", "!a", ["a"])]
    for ea, eb, vs in same:
        ident, info = reduces_to_same_graph_randomized(ea, eb, vs)
        assert ident is True, f"{ea} vs {eb}: randomized said not-identical"
        assert reduces_to_same_graph(ea, eb, vs) is True  # exact agrees
        assert info["false_positive_bound"] < 1e-9  # negligible one-sided error
    for ea, eb, vs in diff:
        ident, info = reduces_to_same_graph_randomized(ea, eb, vs)
        assert ident is False, f"{ea} vs {eb}: randomized missed the difference"
        assert reduces_to_same_graph(ea, eb, vs) is False  # exact agrees
        assert "witness" in info  # a disproof carries an exact witness point


def test_randomized_pit_disproof_witness_is_exact() -> None:
    """A `False` verdict is EXACT (one-sided soundness): the returned witness point
    actually makes the two polynomials differ — re-evaluate it to confirm."""
    ident, info = reduces_to_same_graph_randomized("a && b", "a || b", ["a", "b"])
    assert ident is False and "witness" in info
    pa, sa = extract_truth_polynomial("a && b", ["a", "b"], expand=False)
    pb, sb = extract_truth_polynomial("a || b", ["a", "b"], expand=False)
    env = {sa["a"]: info["witness"]["a"], sa["b"]: info["witness"]["b"]}
    assert (pa - pb).subs(env) != 0  # the witness is a genuine disproof


def test_randomized_pit_scales_without_expansion() -> None:
    """Randomized PIT certifies a NON-trivial nested identity WITHOUT expanding it.
    A nested De Morgan pair is the same graph but is NOT structurally identical to
    sympy (unlike commutativity/associativity, which sympy normalises for free), so
    proving it the exact way genuinely requires `expand`; randomized PIT proves it by
    random evaluation instead. The structural degree bound is therefore positive,
    and the one-sided error is negligible."""
    a = "!((a && b) || (c && d))"
    b = "(!a || !b) && (!c || !d)"  # De Morgan, twice
    vs = ["a", "b", "c", "d"]
    ident, info = reduces_to_same_graph_randomized(a, b, vs, trials=24)
    assert ident is True
    assert reduces_to_same_graph(a, b, vs) is True  # exact agrees (after expansion)
    assert info["degree_bound"] >= 2  # genuinely nested — not an auto-cancelled 0
    assert info["false_positive_bound"] < 1e-6


def test_decision_procedure_covers_integer_arithmetic() -> None:
    """The decision procedure is not limited to AND/OR/NOT: it decides equivalence over
    the whole POLYNOMIAL fragment, including integer `+`/`-`/`*` arithmetic. A clean
    contrast with the Kleene case: arithmetic distributivity IS a same-graph identity
    (the polynomials are equal), whereas Kleene distributivity is NOT (it is only
    grid-equivalent). Both the exact and the scalable randomized checks agree."""
    arithmetic_same = [
        ("(a + b) * c", "a * c + b * c", ["a", "b", "c"]),     # distributivity (arithmetic)
        ("(a + b) * (a + b)", "a*a + 2*a*b + b*b", ["a", "b"]),  # square expansion
        ("a * b", "b * a", ["a", "b"]),                          # commutativity
        ("(a && b) + c", "c + (b && a)", ["a", "b", "c"]),       # mixed Kleene + arithmetic
    ]
    for ea, eb, vs in arithmetic_same:
        assert reduces_to_same_graph(ea, eb, vs) is True, f"{ea} vs {eb}"
        ident, _ = reduces_to_same_graph_randomized(ea, eb, vs)
        assert ident is True, f"randomized: {ea} vs {eb}"
    # Non-identities are caught (exactly) by both routes.
    assert reduces_to_same_graph("a + b", "a - b", ["a", "b"]) is False
    assert reduces_to_same_graph_randomized("a + b", "a - b", ["a", "b"])[0] is False
    # Arithmetic distributivity is same-graph; Kleene distributivity is NOT (only logical).
    assert reduces_to_same_graph("(a + b) * c", "a*c + b*c", ["a", "b", "c"]) is True
    assert reduces_to_same_graph("(a && b) || (a && c)", "a && (b || c)",
                                 ["a", "b", "c"]) is False


def test_kleene_connective_formulas_match_inliner() -> None:
    """Integrity guard: the randomized evaluator applies HARD-CODED truth-axis
    formulas for `!`/`&&`/`||` to operand values (the key to scaling). Those formulas
    MUST equal what the compiler's own inliner emits, or the randomized check would
    decide a different polynomial than `reduces_to_same_graph`. Re-derive each single
    connective via the inliner and confirm the formula evaluates identically at a
    grid of points — over the field, via `_eval_kleene_ast`."""
    from sutra_compiler.fv_obligation_checker import (
        _PIT_PRIME, _eval_kleene_ast, _parse_expr_to_ast)
    p, inv2 = _PIT_PRIME, pow(2, -1, _PIT_PRIME)
    for expr, vs in [("!a", ["a"]), ("a && b", ["a", "b"]), ("a || b", ["a", "b"])]:
        poly, syms = extract_truth_polynomial(expr, vs)  # the inliner's polynomial
        tree = _parse_expr_to_ast(expr, vs)
        for point in itertools.product(range(1, 6), repeat=len(vs)):
            env = dict(zip(vs, point))
            inliner_val = int(poly.subs({syms[v]: env[v] for v in vs})) % p
            formula_val = _eval_kleene_ast(tree, env, p, inv2)
            assert formula_val == inliner_val, f"{expr} formula drifted at {env}"


def test_structural_degree_bound_is_an_upper_bound() -> None:
    """The structural degree bound never under-estimates the true (expanded) degree."""
    for expr, vs in [("a && b", ["a", "b"]), ("(a && b) || !c", ["a", "b", "c"]),
                     ("a && (b && (c && d))", ["a", "b", "c", "d"])]:
        unexp, _ = extract_truth_polynomial(expr, vs, expand=False)
        exp, _ = extract_truth_polynomial(expr, vs, expand=True)
        true_deg = sympy.Poly(exp, *sorted(exp.free_symbols, key=str)).total_degree() \
            if exp.free_symbols else 0
        assert structural_degree_bound(unexp) >= true_deg


def test_distributivity_is_grid_equivalent_but_not_the_same_graph() -> None:
    """The headline distinction. Distributivity holds on the Kleene grid but the
    two sides reduce to DIFFERENT polynomials off-grid — a concrete witness that
    "reduce to the same graph" is strictly stronger than "logically equivalent."
    """
    a_side = "a && (b || c)"
    b_side = "(a && b) || (a && c)"
    vs = ["a", "b", "c"]
    assert kleene_equivalent(a_side, b_side, vs)            # equal on the grid
    assert not reduces_to_same_graph(a_side, b_side, vs)    # different off-grid


def test_kleene_equivalent_agrees_with_same_graph_on_identities() -> None:
    """Where two expressions reduce to the same graph they are also grid-equal;
    and a genuine non-equivalence is rejected by both."""
    assert kleene_equivalent("!(a && b)", "!a || !b", ["a", "b"])
    assert kleene_equivalent("!!a", "a", ["a"])
    assert not kleene_equivalent("a && b", "a || b", ["a", "b"])


def test_branch_range_within_truth_domain_for_tractable_cases() -> None:
    """Range bounding for the cases the bounder handles: the primitive
    connectives and a shallow 2-variable nesting. Each reduced polynomial's
    exact range is within [-1, +1]. (Deep 4+-var nesting is the documented
    scalability wall — not exercised here, see the module docstring.)"""
    cases = [
        ("a && b", ["a", "b"]),
        ("a || b", ["a", "b"]),
        ("!a", ["a"]),
        ("!(a && b)", ["a", "b"]),   # 2-var nesting, degree 4 — still tractable
    ]
    for expr, vs in cases:
        rb = check_branch_range(expr, vs)
        print(f"[fv-general] {expr:14} exact range [{rb.minimum}, {rb.maximum}]")
        assert rb.within(-1, 1), f"{expr}: range escapes [-1,+1]"


def test_range_sound_by_composition_scales_to_any_depth() -> None:
    """Range-soundness for arbitrary-depth Kleene expressions, by structural
    composition (the scalable answer where the closed-form bounder does not
    scale). Each connective maps [-1,+1]->[-1,+1] (proven by check_branch_range);
    any composition of them is therefore range-sound, degree-insensitively.

    The deep 4-variable expression below is the one that makes the closed-form
    critical-point bounder intractable; the compositional check decides it
    instantly because it never forms the high-degree polynomial."""
    sound = [
        ("a && b", ["a", "b"]),
        ("(a && b) || !c", ["a", "b", "c"]),
        ("((a && b) || (c && d)) && !(a || d)", ["a", "b", "c", "d"]),
        ("!(!(!(a && b) || c) && d)", ["a", "b", "c", "d"]),
    ]
    for expr, vs in sound:
        assert range_sound_by_composition(expr, vs), f"{expr} should be range-sound"

    # Cross-check the lemma it rests on: a tractable composed case the
    # closed-form bounder CAN handle agrees — range within [-1,+1].
    assert check_branch_range("!(a && b)", ["a", "b"]).within(-1, 1)

    # Expressions that are NOT pure-Kleene compositions: the conclusion does not
    # follow by composition, so it returns False (a comparison).
    assert not range_sound_by_composition("a == b", ["a", "b"])


def test_contract_function_correctness_kleene_fragment() -> None:
    """Contract obligation, FUNCTION-CORRECTNESS half — discharged for the Kleene
    fragment via the equivalence procedure.

    A program's contract can specify the role-to-role function it must compute as
    a reference expression. For a trusted program in the Kleene-logic fragment,
    "does the implementation compute the contract's function?" is exactly
    `reduces_to_same_graph(implementation, contract_reference)` — decidable,
    exact, any depth. This is the function-correctness half of §3.1 (the
    confinement half is discharged at the kernel).

    Honest scope: this covers trusted programs that ARE Kleene expressions. A
    program outside the fragment (e.g. echo = an identity axon rebind; switch.su =
    arithmetic + select) is not a Kleene expression, so its function-correctness
    is covered by its own substrate tests, not by this procedure.
    """
    # A trusted program whose contract says "compute NAND" implemented two ways:
    contract_reference = "!(a && b)"
    correct_impl = "!a || !b"            # De Morgan — same function, same graph
    wrong_impl = "!(a || b)"             # NOR, not NAND — different function
    vs = ["a", "b"]

    # Correct implementation satisfies the contract's function (same graph):
    assert reduces_to_same_graph(correct_impl, contract_reference, vs), (
        "a correct NAND implementation should satisfy the contract function"
    )
    # A wrong implementation is caught (not the same graph):
    assert not reduces_to_same_graph(wrong_impl, contract_reference, vs), (
        "NOR must NOT pass as a NAND contract — function-correctness would be vacuous"
    )


def test_refuses_outside_the_polynomial_fragment() -> None:
    """The checker refuses (does not fabricate) on a non-polynomial residual:
    a comparison or a runtime intrinsic. The named verifiable boundary."""
    for expr, vs in [("a == b", ["a", "b"]), ("a > b", ["a", "b"])]:
        with pytest.raises(NonPolynomialResidual):
            extract_truth_polynomial(expr, vs)


def test_extracted_polynomial_matches_substrate() -> None:
    """Integrity guard: the inliner-extracted polynomial equals what the
    compiled torch substrate computes, on the {-1,0,+1}^2 grid. Uses exact
    `.subs` (no lambdify). Skipped if torch is unavailable."""
    torch = pytest.importorskip("torch", reason="substrate cross-check needs torch")
    from sutra_compiler.codegen_pytorch import translate_module as torch_translate
    from sutra_compiler.lexer import Lexer
    from sutra_compiler.parser import Parser

    expr, vs = "!(a && b)", ["a", "b"]
    poly, syms = extract_truth_polynomial(expr, vs)

    src = (f"function vector f(vector a, vector b) {{ return {expr}; }}\n"
           f"function vector main() {{ return true; }}\n")
    lexer = Lexer(src, file="<fv-gen-sub>")
    toks = lexer.tokenize()
    parser = Parser(toks, file="<fv-gen-sub>", diagnostics=lexer.diagnostics)
    module = parser.parse_module()
    assert not lexer.diagnostics.has_errors(), list(lexer.diagnostics)
    py = torch_translate(module, llm_model="nomic-embed-text", runtime_dim=768)
    ns: dict = {}
    exec(compile(py, "<fv-gen-sub>", "exec"), ns)
    f, vsa = ns["f"], ns["_VSA"]

    grid = (-1.0, 0.0, 1.0)
    worst = 0.0
    for av, bv in itertools.product(grid, grid):
        # `truth(v)` accessor was removed in the substrate-purity overhaul
        # (87cfa407); read the truth axis via `truth_axis` (a 0-dim tensor) and
        # float() it here — a monitoring readout at the test boundary, legitimate.
        substrate = float(vsa.truth_axis(f(vsa.make_truth(av), vsa.make_truth(bv))))
        extracted = float(poly.subs({syms["a"]: av, syms["b"]: bv}))
        worst = max(worst, abs(substrate - extracted))
    print(f"\n[fv-general] extracted-vs-substrate worst |err| = {worst:.3e}")
    assert worst < 1e-4, (
        f"extracted polynomial drifted from the compiled substrate "
        f"(worst |err|={worst:.3e}) — a result on it would not transfer"
    )
