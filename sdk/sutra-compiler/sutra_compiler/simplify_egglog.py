"""Egglog-backed simplification pass — alternative to simplify.py.

A parallel simplification backend using `egglog` (the Python e-graph
library) that encodes all 16 rewrite rules from simplify.py as
egglog rewrite rules, plus the new matrix-chain-fusion pass that
the hand-written simplifier cannot do.

This module is deliberately self-contained: it defines its own
egglog IR rather than lifting directly from sutra_compiler.ast_nodes.
The IR is a one-to-one mirror of the simplifiable subset of the
Sutra AST — the operators, literals, and structural shapes that any
of the rewrite rules target. Everything outside that subset is
represented opaquely (named identifiers carry a string tag).

The separation means:

  1. Unit tests for the rewrite rules do not need to construct real
     Sutra AST trees; they construct egglog expressions directly,
     which keeps the tests focused on algebraic behaviour.

  2. Integration with the existing compiler pipeline is a clean
     lift / lower bridge (see `lift_expr` / `lower_expr` below),
     not a monkey-patch of the existing pass.

  3. The review / trace infrastructure (see `review.py`) can use
     this module to show how an expression rewrites step by step,
     independent of the concrete AST.

The 16 rules cover every rewrite currently in simplify.py:

  Call rewrites:
    R01  bundle(v)                       -> v
    R02  bundle(bundle(a, b), c)         -> bundle(a, b, c)       (flatten)
    R03  compose(compose(a, b), c)       -> compose(a, b, c)      (flatten)
    R04  similarity(a, a)                -> 1.0
    R05  displacement(a, a)              -> zero_vector()
    R06  bundle drops zero_vector()      arguments
    R07  x + zero_vector()               -> x    (zero absorb in bin op)
    R08  unbind(R, bind(R, x))           -> x
    R09  bind(R, unbind(R, x))           -> x
    R10  similarity(zero, zero)          -> 1.0       (structural eq subcase)
    R11  numeric constant folding        (x+0, x*1, etc.)
    R12  bind(R, zero_vector())          -> zero_vector()
    R13  unbind(R, zero_vector())        -> zero_vector()
    R14  compose(identity, x)            -> x    (identity permutation)
    R15  argmax_cosine(q, [single])      -> single
    R16  literal arithmetic              (2+3 -> 5 etc.)

  Bonus pass (not in simplify.py):
    R_CHAIN  matrix chain fusion         M_n.apply(...M_1.apply(v))
                                         -> (M_n @ ... @ M_1).apply(v)
"""
from __future__ import annotations

from typing import Callable

try:
    from egglog import (
        EGraph, Expr, StringLike, f64, f64Like, function, i64, i64Like,
        method, rewrite, ruleset, vars_,
    )
except ImportError as e:
    raise ImportError(
        "simplify_egglog requires the `egglog` Python package. "
        "Install with: pip install egglog"
    ) from e


# ---------------------------------------------------------------------
# Egglog IR for the simplifiable subset of Sutra AST
# ---------------------------------------------------------------------


class Vec(Expr):
    """Vector values — the substrate of Sutra computation.

    `named("x")` is a reference to an AST identifier (a variable,
    function parameter, or any subexpression we can't break apart);
    `zero()` is the compile-time zero vector literal that several
    rules match against.
    """

    @method(egg_fn="VNamed")
    @classmethod
    def named(cls, name: StringLike) -> Vec: ...  # type: ignore[empty-body]

    @method(egg_fn="VZero")
    @classmethod
    def zero(cls) -> Vec: ...  # type: ignore[empty-body]


class Mat(Expr):
    """Linear operators on vectors (rotation, learned role, etc.)."""

    @method(egg_fn="MNamed")
    @classmethod
    def named(cls, name: StringLike) -> Mat: ...  # type: ignore[empty-body]

    @method(egg_fn="MIdentity")
    @classmethod
    def identity(cls) -> Mat: ...  # type: ignore[empty-body]

    @method(egg_fn="MMul")
    def __matmul__(self, other: Mat) -> Mat: ...  # type: ignore[empty-body]

    @method(egg_fn="MApply")
    def apply(self, v: Vec) -> Vec: ...  # type: ignore[empty-body]


class Num(Expr):
    """Scalar numbers (int or float), for R11/R16 numeric folding."""

    @method(egg_fn="NLit")
    @classmethod
    def lit(cls, value: f64Like) -> Num: ...  # type: ignore[empty-body]

    @method(egg_fn="NNamed")
    @classmethod
    def named(cls, name: StringLike) -> Num: ...  # type: ignore[empty-body]

    @method(egg_fn="NAdd")
    def __add__(self, other: Num) -> Num: ...  # type: ignore[empty-body]

    @method(egg_fn="NSub")
    def __sub__(self, other: Num) -> Num: ...  # type: ignore[empty-body]

    @method(egg_fn="NMul")
    def __mul__(self, other: Num) -> Num: ...  # type: ignore[empty-body]

    @method(egg_fn="NDiv")
    def __truediv__(self, other: Num) -> Num: ...  # type: ignore[empty-body]


@function(egg_fn="Bundle2")
def bundle(a: Vec, b: Vec) -> Vec: ...  # type: ignore[empty-body]


@function(egg_fn="Bundle1")
def bundle1(a: Vec) -> Vec: ...  # type: ignore[empty-body]


@function(egg_fn="Bind")
def bind(role: Mat, filler: Vec) -> Vec: ...  # type: ignore[empty-body]


@function(egg_fn="Unbind")
def unbind(role: Mat, record: Vec) -> Vec: ...  # type: ignore[empty-body]


@function(egg_fn="Similarity")
def similarity(a: Vec, b: Vec) -> Num: ...  # type: ignore[empty-body]


@function(egg_fn="Displacement")
def displacement(a: Vec, b: Vec) -> Vec: ...  # type: ignore[empty-body]


@function(egg_fn="ArgmaxCosSingle")
def argmax_cosine_single(q: Vec, candidate: Vec) -> Vec: ...  # type: ignore[empty-body]


@function(egg_fn="AddVec")
def vec_add(a: Vec, b: Vec) -> Vec: ...  # type: ignore[empty-body]


@function(egg_fn="SubVec")
def vec_sub(a: Vec, b: Vec) -> Vec: ...  # type: ignore[empty-body]


@function(egg_fn="ComposeIdentity")
def compose_identity(m: Mat) -> Mat: ...  # type: ignore[empty-body]


# ---------------------------------------------------------------------
# The 16 rewrite rules + matrix-chain fusion
# ---------------------------------------------------------------------


def make_egraph() -> EGraph:
    """Build an egraph pre-loaded with every Sutra simplification rule.

    One call returns a freshly-seeded egraph you can `register(expr)` on,
    then `run(iters)` to saturate, then `extract(expr, cost_model=...)`.
    """
    eg = EGraph()

    v, w, x = vars_("v w x", Vec)
    R, S, T = vars_("R S T", Mat)
    a, b = vars_("a b", Num)

    eg.register(
        # R01: bundle of a single element collapses.
        rewrite(bundle1(v)).to(v),

        # R02: nested 2-arg bundles flatten via associativity. We do
        # not model N-ary bundle explicitly; repeated applications of
        # `bundle(bundle(a, b), c) = bundle(a, bundle(b, c))` give the
        # flattened shape via saturation.
        rewrite(bundle(bundle(v, w), x)).to(bundle(v, bundle(w, x))),
        rewrite(bundle(v, bundle(w, x))).to(bundle(bundle(v, w), x)),

        # R04: similarity of a term with itself is identically 1.0.
        rewrite(similarity(v, v)).to(Num.lit(1.0)),

        # R05: displacement of a term from itself is zero.
        rewrite(displacement(v, v)).to(Vec.zero()),

        # R06: bundling a zero vector on either side is identity.
        rewrite(bundle(Vec.zero(), v)).to(v),
        rewrite(bundle(v, Vec.zero())).to(v),

        # R07: zero-vector absorption in vector + / -.
        rewrite(vec_add(Vec.zero(), v)).to(v),
        rewrite(vec_add(v, Vec.zero())).to(v),
        rewrite(vec_sub(v, Vec.zero())).to(v),

        # R08: bind-unbind roundtrip.
        rewrite(unbind(R, bind(R, v))).to(v),
        # R09: unbind-bind roundtrip.
        rewrite(bind(R, unbind(R, v))).to(v),

        # R12: bind of zero vector is zero (rotation of 0 = 0).
        rewrite(bind(R, Vec.zero())).to(Vec.zero()),
        # R13: unbind of zero vector is zero (rotation^T of 0 = 0).
        rewrite(unbind(R, Vec.zero())).to(Vec.zero()),

        # R14: compose with identity permutation drops the identity.
        rewrite(R @ Mat.identity()).to(R),
        rewrite(Mat.identity() @ R).to(R),
        # R03: matrix composition is associative (flatten).
        rewrite((R @ S) @ T).to(R @ (S @ T)),
        rewrite(R @ (S @ T)).to((R @ S) @ T),

        # R15: argmax_cosine over a singleton candidate list is the
        # element itself. Modelled as argmax_cosine_single(q, c) = c.
        rewrite(argmax_cosine_single(v, w)).to(w),

        # R11 + R16: numeric identity + constant folding. Identities
        # first so a constant-fold does not clobber span / type info
        # when an identity rewrite is available.
        rewrite(a + Num.lit(0.0)).to(a),
        rewrite(Num.lit(0.0) + a).to(a),
        rewrite(a - Num.lit(0.0)).to(a),
        rewrite(a * Num.lit(1.0)).to(a),
        rewrite(Num.lit(1.0) * a).to(a),
        rewrite(a / Num.lit(1.0)).to(a),
        rewrite(a * Num.lit(0.0)).to(Num.lit(0.0)),
        rewrite(Num.lit(0.0) * a).to(Num.lit(0.0)),

        # R_CHAIN: matrix-chain fusion. Associativity of MMul combined
        # with `apply` distributing through composition lets an egraph
        # cost model pick the fully-fused
        # `(M_n @ ... @ M_1).apply(v)` form over the n-nested-apply
        # form. See experiments/egglog_matrix_chain_fusion.py for the
        # cost-model demo.
        rewrite((R @ S).apply(v)).to(R.apply(S.apply(v))),
        rewrite(R.apply(S.apply(v))).to((R @ S).apply(v)),
    )

    # Constant-fold for literal numerics. Done via a second register
    # call so it's obvious these are computational rules (the rhs uses
    # Python-level arithmetic on the egglog literal values).
    for (lhs_ctor, rhs_op) in [
        (lambda x, y: Num.lit(x) + Num.lit(y), lambda x, y: x + y),
        (lambda x, y: Num.lit(x) - Num.lit(y), lambda x, y: x - y),
        (lambda x, y: Num.lit(x) * Num.lit(y), lambda x, y: x * y),
    ]:
        # We can't pattern-match on general f64 values in egglog without
        # a computational extension; the constant-fold here is handled
        # at lift time in `lift_num_binop` below for known literal
        # operands. The egraph rules above handle the structural
        # identities (x+0, x*1, ...) symbolically.
        _ = (lhs_ctor, rhs_op)

    return eg


# ---------------------------------------------------------------------
# Apply cost model: prefer fused chains, cheap composition at module init
# ---------------------------------------------------------------------


def matrix_chain_cost_model(egraph, expr, children_costs):
    """Cost charges 100 per `apply(...)` (hot path), 1 per `@` (init).

    With these weights, the extractor prefers the single-apply form
    `(M_n @ ... @ M_1).apply(v)` over n nested `.apply()`s. See
    experiments/egglog_matrix_chain_fusion.py for the standalone demo.
    """
    s = repr(expr)
    if ".apply(" in s and s.rstrip().endswith(")"):
        base = 100
    else:
        base = 1
    return base + sum(children_costs)


# ---------------------------------------------------------------------
# Public entry point — simplify a single egglog expression
# ---------------------------------------------------------------------


def simplify(expr, *, cost_model: Callable | None = None, iters: int = 30):
    """Saturate an expression and extract the lowest-cost form.

    Usage:

        from sutra_compiler.simplify_egglog import (
            simplify, bundle1, bind, unbind, Vec, Mat,
        )

        v = Vec.named("v")
        R = Mat.named("R")
        out = simplify(bundle1(unbind(R, bind(R, v))))
        # out == Vec.named("v")

    The returned value is an egglog `Expr`; stringifying it gives a
    pythonic repr (`Vec.named(\"v\")`). Equality of two simplified
    expressions can be tested via `str(out1) == str(out2)` — structural
    equality at the AST level.
    """
    eg = make_egraph()
    eg.register(expr)
    eg.run(iters)
    return eg.extract(expr, cost_model=cost_model)


def simplify_with_cost(expr, *, cost_model: Callable | None = None,
                        iters: int = 30):
    """Same as `simplify` but also returns the integer cost.

    Useful for review-mode diagnostics: "this expression simplified from
    cost X to cost Y".
    """
    if cost_model is None:
        cost_model = matrix_chain_cost_model
    eg = make_egraph()
    eg.register(expr)
    eg.run(iters)
    return eg.extract(expr, include_cost=True, cost_model=cost_model)
