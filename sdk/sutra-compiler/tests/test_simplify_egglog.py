"""Unit tests for simplify_egglog — one test per rewrite rule.

Covers every rule in `sutra_compiler.simplify_egglog`'s docstring
(R01..R16 plus R_CHAIN) and a handful of cascades. Runs under the
same pytest suite as the rest of the compiler tests.

If egglog is not installed, the tests are skipped rather than failed —
the hand-written simplify.py pipeline still covers these rewrites,
and the egglog path is additive.
"""
from __future__ import annotations

import pytest

pytest.importorskip("egglog")

from egglog import eq  # noqa: E402

from sutra_compiler.simplify_egglog import (  # noqa: E402
    Mat, Num, Vec, make_egraph,
    bind, bundle, bundle1, compose_identity, displacement,
    argmax_cosine_single, matrix_chain_cost_model, similarity,
    simplify, simplify_with_cost, unbind, vec_add, vec_sub,
)


def assert_equiv(lhs, rhs, iters: int = 30) -> None:
    """Assert lhs and rhs saturate into the same e-class.

    Use this instead of `str(simplify(lhs)) == str(simplify(rhs))` when
    the default extractor's choice of canonical form could tiebreak
    differently between two runs of the same saturation (e.g. on
    pure-associativity tests where neither side has a cost advantage).
    """
    eg = make_egraph()
    eg.register(lhs); eg.register(rhs)
    eg.run(iters)
    eg.check(eq(lhs).to(rhs))


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------


def simp(expr):
    return str(simplify(expr))


# ---------------------------------------------------------------------
# R01 — bundle(v) -> v
# ---------------------------------------------------------------------


def test_r01_bundle_single_arg_is_identity():
    v = Vec.named("v")
    assert simp(bundle1(v)) == str(v)


# ---------------------------------------------------------------------
# R02 — bundle flattens (associativity)
# ---------------------------------------------------------------------


def test_r02_bundle_associates_in_both_directions():
    """bundle(bundle(a, b), c) and bundle(a, bundle(b, c)) must land in
    the same e-class after saturation. Either form is a valid
    extraction; the rewrite captures that they're equal, not that one
    is canonical. Checking via `eq(...)` avoids a false failure from
    the default extractor tiebreaking between them.
    """
    a, b, c = Vec.named("a"), Vec.named("b"), Vec.named("c")
    assert_equiv(bundle(bundle(a, b), c), bundle(a, bundle(b, c)))


# ---------------------------------------------------------------------
# R03 — matrix-compose associativity
# ---------------------------------------------------------------------


def test_r03_matrix_compose_associates():
    """Same associativity equivalence, on matrix composition."""
    A, B, C = Mat.named("A"), Mat.named("B"), Mat.named("C")
    v = Vec.named("v")
    assert_equiv(((A @ B) @ C).apply(v), (A @ (B @ C)).apply(v))


# ---------------------------------------------------------------------
# R04 — similarity(a, a) = 1
# ---------------------------------------------------------------------


def test_r04_similarity_self_is_one():
    v = Vec.named("v")
    assert simp(similarity(v, v)) == str(Num.lit(1.0))


# ---------------------------------------------------------------------
# R05 — displacement(a, a) = 0
# ---------------------------------------------------------------------


def test_r05_displacement_self_is_zero():
    v = Vec.named("v")
    assert simp(displacement(v, v)) == str(Vec.zero())


# ---------------------------------------------------------------------
# R06 — bundle drops zero arguments
# ---------------------------------------------------------------------


def test_r06_bundle_drops_zero_left():
    v = Vec.named("v")
    assert simp(bundle(Vec.zero(), v)) == str(v)


def test_r06_bundle_drops_zero_right():
    v = Vec.named("v")
    assert simp(bundle(v, Vec.zero())) == str(v)


# ---------------------------------------------------------------------
# R07 — vector + / - zero absorption
# ---------------------------------------------------------------------


def test_r07_vec_add_zero_left():
    v = Vec.named("v")
    assert simp(vec_add(Vec.zero(), v)) == str(v)


def test_r07_vec_add_zero_right():
    v = Vec.named("v")
    assert simp(vec_add(v, Vec.zero())) == str(v)


def test_r07_vec_sub_zero_right():
    v = Vec.named("v")
    assert simp(vec_sub(v, Vec.zero())) == str(v)


# ---------------------------------------------------------------------
# R08 / R09 — bind / unbind roundtrips
# ---------------------------------------------------------------------


def test_r08_unbind_of_bind_is_filler():
    v = Vec.named("v"); R = Mat.named("R")
    assert simp(unbind(R, bind(R, v))) == str(v)


def test_r09_bind_of_unbind_is_record():
    v = Vec.named("v"); R = Mat.named("R")
    assert simp(bind(R, unbind(R, v))) == str(v)


# ---------------------------------------------------------------------
# R10 — similarity(zero, zero) = 1 (subcase of R04 via structural eq)
# ---------------------------------------------------------------------


def test_r10_similarity_zero_zero():
    assert simp(similarity(Vec.zero(), Vec.zero())) == str(Num.lit(1.0))


# ---------------------------------------------------------------------
# R11 + R16 — numeric identities + literal folding
# ---------------------------------------------------------------------


def test_r11_x_plus_zero_is_x():
    x = Num.named("x")
    assert simp(x + Num.lit(0.0)) == str(x)


def test_r11_x_times_one_is_x():
    x = Num.named("x")
    assert simp(x * Num.lit(1.0)) == str(x)


def test_r11_x_times_zero_is_zero():
    x = Num.named("x")
    assert simp(x * Num.lit(0.0)) == str(Num.lit(0.0))


def test_r11_x_div_one_is_x():
    x = Num.named("x")
    assert simp(x / Num.lit(1.0)) == str(x)


# ---------------------------------------------------------------------
# R12 / R13 — bind / unbind of zero absorbs
# ---------------------------------------------------------------------


def test_r12_bind_of_zero_is_zero():
    R = Mat.named("R")
    assert simp(bind(R, Vec.zero())) == str(Vec.zero())


def test_r13_unbind_of_zero_is_zero():
    R = Mat.named("R")
    assert simp(unbind(R, Vec.zero())) == str(Vec.zero())


# ---------------------------------------------------------------------
# R14 — matrix compose with identity drops the identity
# ---------------------------------------------------------------------


def test_r14_matrix_compose_identity_right():
    R = Mat.named("R")
    assert simp(R @ Mat.identity()) == str(R)


def test_r14_matrix_compose_identity_left():
    R = Mat.named("R")
    assert simp(Mat.identity() @ R) == str(R)


# ---------------------------------------------------------------------
# R15 — argmax_cosine over a singleton candidate list is the element
# ---------------------------------------------------------------------


def test_r15_argmax_single_is_element():
    q = Vec.named("q"); c = Vec.named("c")
    assert simp(argmax_cosine_single(q, c)) == str(c)


# ---------------------------------------------------------------------
# Cascades — multiple rules firing in one saturation pass
# ---------------------------------------------------------------------


def test_cascade_bundle_of_roundtrip():
    """bundle(unbind(R, bind(R, x))) -> bundle(x) -> x."""
    x = Vec.named("x"); R = Mat.named("R")
    assert simp(bundle1(unbind(R, bind(R, x)))) == str(x)


def test_cascade_bind_of_bundle_of_zero():
    """bind(R, bundle(zero, v)) -> bind(R, v)."""
    v = Vec.named("v"); R = Mat.named("R")
    out = simp(bind(R, bundle(Vec.zero(), v)))
    assert out == str(bind(R, v))


def test_cascade_similarity_after_roundtrip():
    """similarity(unbind(R, bind(R, x)), x) -> 1.0."""
    x = Vec.named("x"); R = Mat.named("R")
    assert simp(similarity(unbind(R, bind(R, x)), x)) == str(Num.lit(1.0))


# ---------------------------------------------------------------------
# R_CHAIN — matrix-chain fusion (the new pass simplify.py lacks)
# ---------------------------------------------------------------------


def test_rchain_two_matrix_fuse():
    M1, M2 = Mat.named("M1"), Mat.named("M2")
    v = Vec.named("v")
    extracted, cost = simplify_with_cost(
        M2.apply(M1.apply(v)),
        cost_model=matrix_chain_cost_model,
    )
    # Fused form has exactly one .apply(.
    s = str(extracted)
    assert s.count(".apply(") == 1
    # Cost of the fused form is strictly lower than the unfused
    # (2 applies * 100 + overhead = 200+) when cost > 100 implies fused.
    assert cost < 200


def test_rchain_five_matrix_fuse():
    """Five matrices chain-fuse to a single apply."""
    M = [Mat.named(f"M{i}") for i in range(1, 6)]
    v = Vec.named("v")
    expr = v
    for m in M:
        expr = m.apply(expr)
    extracted, cost = simplify_with_cost(
        expr, cost_model=matrix_chain_cost_model,
    )
    s = str(extracted)
    assert s.count(".apply(") == 1
    # 5 applies unfused costs >=500; single apply should be ~100.
    assert cost < 200


# ---------------------------------------------------------------------
# AST <-> egglog bridge tests (lift_vec / lift_num / simplify_ast_*)
# ---------------------------------------------------------------------
#
# These tests exercise the path the compiler takes: real Sutra AST
# nodes go in, the lift/saturate/lower pipeline runs, and the
# resulting AST is checked structurally. The earlier rule-level
# tests cover egglog behavior in isolation; these cover the bridge.

from sutra_compiler import ast_nodes as _ast  # noqa: E402
from sutra_compiler.diagnostics import (  # noqa: E402
    SourcePosition, SourceSpan,
)
from sutra_compiler.simplify_egglog import (  # noqa: E402
    simplify_ast_num, simplify_ast_vec,
)


def _span():
    p = SourcePosition(line=1, column=1, offset=0)
    return SourceSpan(start=p, end=p)


def _id(name: str) -> _ast.Identifier:
    return _ast.Identifier(name=name, span=_span())


def _call(name: str, *args: _ast.Expr) -> _ast.Call:
    s = _span()
    return _ast.Call(
        callee=_ast.Identifier(name=name, span=s),
        type_args=[], args=list(args), span=s,
    )


def test_bridge_bundle_zero_collapses_to_identifier():
    """bundle(zero_vector(), v) -> v after lift+saturate+lower."""
    zero = _call("zero_vector")
    v = _id("v")
    expr = _call("bundle", zero, v)
    out = simplify_ast_vec(expr)
    assert isinstance(out, _ast.Identifier)
    assert out.name == "v"


def test_bridge_bundle_single_arg_is_identity():
    """bundle(v) -> v."""
    v = _id("v")
    expr = _call("bundle", v)
    out = simplify_ast_vec(expr)
    assert isinstance(out, _ast.Identifier)
    assert out.name == "v"


def test_bridge_unbind_bind_roundtrip():
    """unbind(R, bind(R, v)) -> v."""
    R = _id("R")
    v = _id("v")
    expr = _call("unbind", R, _call("bind", R, v))
    out = simplify_ast_vec(expr)
    assert isinstance(out, _ast.Identifier)
    assert out.name == "v"


def test_bridge_bind_zero_is_zero():
    """bind(R, zero_vector()) -> zero_vector()."""
    R = _id("R")
    zero = _call("zero_vector")
    expr = _call("bind", R, zero)
    out = simplify_ast_vec(expr)
    assert isinstance(out, _ast.Call)
    assert isinstance(out.callee, _ast.Identifier)
    assert out.callee.name == "zero_vector"


def test_bridge_displacement_self_is_zero():
    """displacement(v, v) -> zero_vector()."""
    v = _id("v")
    expr = _call("displacement", v, v)
    out = simplify_ast_vec(expr)
    assert isinstance(out, _ast.Call)
    assert out.callee.name == "zero_vector"


def test_bridge_similarity_self_is_one():
    """similarity(v, v) -> 1.0 (numeric context)."""
    v = _id("v")
    expr = _call("similarity", v, v)
    out = simplify_ast_num(expr)
    assert isinstance(out, (_ast.IntLiteral, _ast.FloatLiteral))
    assert float(out.value) == 1.0


def test_bridge_unrecognized_returns_unchanged():
    """A construct outside the egglog IR rounds-trips unchanged.

    Casts aren't modeled — the bridge is conservative and the caller
    sees the same AST node back.
    """
    v = _id("v")
    cast = _ast.CastExpr(
        target_type=_ast.TypeRef(name="vector", type_args=[], span=_span()),
        expr=v, span=_span(),
    )
    out = simplify_ast_vec(cast)
    assert out is cast  # same object — never replaced


def test_bridge_nested_simplification():
    """bundle(unbind(R, bind(R, v)), zero) -> v through saturation."""
    R = _id("R")
    v = _id("v")
    inner = _call("unbind", R, _call("bind", R, v))
    expr = _call("bundle", inner, _call("zero_vector"))
    out = simplify_ast_vec(expr)
    assert isinstance(out, _ast.Identifier)
    assert out.name == "v"
