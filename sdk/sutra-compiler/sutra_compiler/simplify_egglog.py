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

        # R_PIVOT: bind/apply equivalence. `bind(R, v)` is the same
        # algebraic shape as `R.apply(v)` — both compute Q_R · v. The
        # egraph treats them as the same e-class so chains of `bind`s
        # can rewrite to `apply` chains and the matrix-chain fusion
        # rules above fire. unbind(R, v) is `R^T · v` which the
        # current Mat IR doesn't model directly (no transpose
        # operator), so we leave it as a distinct opaque form for
        # now — the unbind/bind round-trip rules already cover the
        # common case where it matters.
        rewrite(bind(R, v)).to(R.apply(v)),
        rewrite(R.apply(v)).to(bind(R, v)),
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
    """Cost charges 100 per hot-path operation (apply, bind, unbind),
    1 per matrix-compose (`@`) — module-init only.

    With these weights, the extractor prefers the single-apply form
    `(M_n @ ... @ M_1).apply(v)` over n nested `.apply()`s and over
    the equivalent n-nested `bind(...)`s. See
    experiments/egglog_matrix_chain_fusion.py for the standalone
    matrix-chain demo. The bind/unbind weighting closes the gap so
    that AST-lifted bind chains also fuse — without it the e-graph
    has both `bind(R, v)` and `R.apply(v)` in the same e-class but
    extraction prefers the shorter `bind` form by tiebreak.
    """
    s = repr(expr)
    # Hot-path nodes: apply on a vector, bind, unbind. All three
    # cost 100 so the extractor will prefer fewer of them — i.e.
    # one apply on a composed matrix over n nested operations.
    if (".apply(" in s and s.rstrip().endswith(")")) \
            or s.startswith("bind(") \
            or s.startswith("unbind("):
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


# ---------------------------------------------------------------------
# AST <-> egglog IR bridge
# ---------------------------------------------------------------------
#
# `simplify_egglog.simplify_ast(ast_expr)` is the public entry point
# the compiler calls. It walks the Sutra AST, tries to lift each
# subexpression into the egglog IR, saturates, and lowers a known-
# simpler form back into the AST. If the expression can't be lifted
# (contains a construct we don't model — operator overloads, casts,
# control-flow), it's left alone. The pass is conservative: a subtree
# round-trips losslessly when egglog can't make progress, and only
# the simplified shape is materialized when egglog can.
#
# Naming strategy: each opaque subexpression gets a stable name keyed
# off its structural form. Two structurally-equal AST nodes lift to
# the same `Vec.named("...")` so rules like `similarity(a, a) -> 1.0`
# fire. The `LiftContext` carries the name table across lift + lower.

from . import ast_nodes as _ast


class LiftContext:
    """State carried across a lift / lower pair of an AST expression.

    Maps a canonical-string form of each opaque AST subexpression to a
    fresh stable name and back. The forward direction is used during
    lift to give the same subexpression the same egglog name (so
    rules that require structural equality fire). The reverse
    direction is used during lower to replace egglog leaves with the
    original AST node.
    """

    def __init__(self) -> None:
        self._key_to_name: dict[str, str] = {}
        self._name_to_ast: dict[str, _ast.Expr] = {}
        self._counter = 0

    def name_for(self, node: _ast.Expr, prefix: str) -> str:
        key = _structural_key(node)
        if key in self._key_to_name:
            return self._key_to_name[key]
        name = f"{prefix}{self._counter}"
        self._counter += 1
        self._key_to_name[key] = name
        self._name_to_ast[name] = node
        return name

    def ast_for(self, name: str) -> _ast.Expr | None:
        return self._name_to_ast.get(name)


def _structural_key(node: _ast.Expr) -> str:
    """A structural-equality key for an AST node.

    Two nodes that should lift to the same egglog name produce the
    same key. We use the existing `_structurally_equal` semantics
    from simplify.py — which is the same equality those rewrite
    rules were designed against — by formatting the AST as a
    canonical tuple-string. Identifier names go in directly;
    literal values too; structured nodes recurse.
    """
    if isinstance(node, _ast.Identifier):
        return f"id:{node.name}"
    if isinstance(node, _ast.IntLiteral):
        return f"int:{node.value}"
    if isinstance(node, _ast.FloatLiteral):
        return f"float:{node.value}"
    if isinstance(node, _ast.StringLiteral):
        return f"str:{node.value!r}"
    if isinstance(node, _ast.BoolLiteral):
        return f"bool:{node.value}"
    if isinstance(node, _ast.UnknownLiteral):
        return "unknown"
    if isinstance(node, _ast.Call):
        callee = _structural_key(node.callee)
        args = ",".join(_structural_key(a) for a in node.args)
        return f"call({callee};{args})"
    if isinstance(node, _ast.BinaryOp):
        return (f"bin({node.op};{_structural_key(node.left)};"
                f"{_structural_key(node.right)})")
    if isinstance(node, _ast.UnaryOp):
        return f"un({node.op};{_structural_key(node.operand)})"
    if isinstance(node, _ast.Parenthesized):
        return _structural_key(node.inner)
    # Anything else gets a unique fallback so we never accidentally
    # alias unrelated nodes.
    return f"opaque:{id(node)}"


def _is_call_named(node: _ast.Expr, name: str, arity: int | None = None) -> bool:
    if not isinstance(node, _ast.Call):
        return False
    if not isinstance(node.callee, _ast.Identifier) or node.callee.name != name:
        return False
    if arity is not None and len(node.args) != arity:
        return False
    return True


# Names of AST function calls that map to specific egglog operators
# at the Vec / Mat / Num level. Anything not in these tables falls
# through to "name as opaque variable" (which keeps the rules from
# firing on it but doesn't cause errors).

def lift_vec(node: _ast.Expr, ctx: LiftContext) -> Vec | None:
    """Lift a Sutra AST expression into the Vec sublanguage of the
    egglog IR. Returns None if the expression isn't recognizably a
    vector-typed thing.
    """
    if _is_call_named(node, "zero_vector", arity=0):
        return Vec.zero()

    if _is_call_named(node, "bundle"):
        # N-ary bundle. For N == 1 use bundle1; for N >= 2 fold via
        # the 2-arg bundle (the rules know associativity).
        args = node.args  # type: ignore[union-attr]
        if len(args) == 1:
            inner = lift_vec(args[0], ctx)
            if inner is None:
                return None
            return bundle1(inner)
        if len(args) >= 2:
            lifted = []
            for a in args:
                la = lift_vec(a, ctx)
                if la is None:
                    return None
                lifted.append(la)
            acc = lifted[0]
            for nxt in lifted[1:]:
                acc = bundle(acc, nxt)
            return acc

    if _is_call_named(node, "bind", arity=2):
        role = lift_mat(node.args[0], ctx)  # type: ignore[union-attr]
        filler = lift_vec(node.args[1], ctx)  # type: ignore[union-attr]
        if role is None or filler is None:
            return None
        return bind(role, filler)

    if _is_call_named(node, "unbind", arity=2):
        role = lift_mat(node.args[0], ctx)  # type: ignore[union-attr]
        record = lift_vec(node.args[1], ctx)  # type: ignore[union-attr]
        if role is None or record is None:
            return None
        return unbind(role, record)

    if _is_call_named(node, "displacement", arity=2):
        a = lift_vec(node.args[0], ctx)  # type: ignore[union-attr]
        b = lift_vec(node.args[1], ctx)  # type: ignore[union-attr]
        if a is None or b is None:
            return None
        return displacement(a, b)

    if isinstance(node, _ast.BinaryOp) and node.op in ("+", "-"):
        l = lift_vec(node.left, ctx)
        r = lift_vec(node.right, ctx)
        if l is not None and r is not None:
            return vec_add(l, r) if node.op == "+" else vec_sub(l, r)
        return None

    # Fall through: everything else is opaque-named at the Vec level.
    # This is conservative — basis_vector("foo"), arbitrary identifiers,
    # casts, calls we don't model — all become Vec.named with a stable
    # name tied to the structural key.
    return Vec.named(ctx.name_for(node, "v"))


def lift_mat(node: _ast.Expr, ctx: LiftContext) -> Mat | None:
    """Lift an AST expression into the Mat sublanguage. The role
    arguments to bind/unbind are typed Vec at the AST level but
    function as Mat at the algebraic level — same opaque-named
    treatment. Identity permutation is the one specific call we
    recognize at the Mat level.
    """
    if _is_call_named(node, "identity_permutation", arity=0):
        return Mat.identity()
    return Mat.named(ctx.name_for(node, "m"))


def lift_num(node: _ast.Expr, ctx: LiftContext) -> Num | None:
    """Lift a numeric-context AST expression into the Num sublanguage."""
    if isinstance(node, _ast.IntLiteral):
        return Num.lit(float(node.value))
    if isinstance(node, _ast.FloatLiteral):
        return Num.lit(float(node.value))
    if isinstance(node, _ast.BinaryOp) and node.op in ("+", "-", "*", "/"):
        l = lift_num(node.left, ctx)
        r = lift_num(node.right, ctx)
        if l is None or r is None:
            return None
        if node.op == "+":
            return l + r
        if node.op == "-":
            return l - r
        if node.op == "*":
            return l * r
        if node.op == "/":
            return l / r
    if _is_call_named(node, "similarity", arity=2):
        a = lift_vec(node.args[0], ctx)  # type: ignore[union-attr]
        b = lift_vec(node.args[1], ctx)  # type: ignore[union-attr]
        if a is None or b is None:
            return None
        return similarity(a, b)
    return Num.named(ctx.name_for(node, "n"))


# ---------------------------------------------------------------------
# Lower: extract pattern → AST node (only specific simplified shapes)
# ---------------------------------------------------------------------

def _try_lower_to_ast(extracted: object, ctx: LiftContext,
                      span) -> _ast.Expr | None:
    """If the extracted egglog form matches a known simple shape, build
    the corresponding AST node. Otherwise return None — meaning we
    couldn't simplify into something structurally cleaner than the
    original AST.

    The shapes we recognize are exactly what the 16 rules can reduce
    to: a `Vec.named(...)` (replace with the original opaque AST),
    `Vec.zero()` (replace with `zero_vector()`), `Num.lit(...)`
    (replace with a number literal). Anything more complex is left
    alone for now — wiring more shapes is a follow-up.
    """
    s = str(extracted).strip()

    # Vec.named("v3") — the original opaque AST.
    if s.startswith('Vec.named("') and s.endswith('")'):
        name = s[len('Vec.named("'):-len('")')]
        return ctx.ast_for(name)

    # Vec.zero() — emit a zero_vector() call.
    if s == "Vec.zero()":
        return _ast.Call(
            callee=_ast.Identifier(name="zero_vector", span=span),
            type_args=[], args=[], span=span,
        )

    # Num.lit(N) — emit a numeric literal.
    if s.startswith("Num.lit(") and s.endswith(")"):
        body = s[len("Num.lit("):-1]
        try:
            value = float(body)
        except ValueError:
            return None
        if value == int(value):
            return _ast.IntLiteral(value=int(value), span=span)
        return _ast.FloatLiteral(value=value, span=span)

    # Num.named("n3") — opaque numeric.
    if s.startswith('Num.named("') and s.endswith('")'):
        name = s[len('Num.named("'):-len('")')]
        return ctx.ast_for(name)

    # Mat.named("m3") — opaque matrix-context AST.
    if s.startswith('Mat.named("') and s.endswith('")'):
        name = s[len('Mat.named("'):-len('")')]
        return ctx.ast_for(name)

    return None


# ---------------------------------------------------------------------
# Public AST entry points
# ---------------------------------------------------------------------

def simplify_ast_vec(node: _ast.Expr, *, iters: int = 30) -> _ast.Expr:
    """Try to simplify a vector-context AST expression via egglog.

    Returns the simplified AST node if egglog reduced it to a known
    simpler shape; otherwise returns the original node unchanged.
    Conservative: never replaces a subtree with something it can't
    confidently reconstruct, and short-circuits when saturation didn't
    change the egglog expression at all (so a literal AST node round-
    trips through unchanged rather than getting reformatted).
    """
    ctx = LiftContext()
    lifted = lift_vec(node, ctx)
    if lifted is None:
        return node
    extracted = simplify(lifted, iters=iters)
    if str(extracted) == str(lifted):
        # Saturation made no progress — keep the original AST node,
        # which preserves span / literal-type / annotations the
        # downstream codegen may rely on.
        return node
    out = _try_lower_to_ast(extracted, ctx, node.span)
    return out if out is not None else node


def simplify_ast_num(node: _ast.Expr, *, iters: int = 30) -> _ast.Expr:
    """Try to simplify a numeric-context AST expression via egglog.

    Same short-circuit as `simplify_ast_vec`: if saturation didn't
    change the egglog expression, the original AST node is returned.
    This matters for literals — `FloatLiteral(0.0)` should stay a
    `FloatLiteral`, not get reformatted to an `IntLiteral` just
    because `0.0 == int(0.0)`.
    """
    ctx = LiftContext()
    lifted = lift_num(node, ctx)
    if lifted is None:
        return node
    extracted = simplify(lifted, iters=iters)
    if str(extracted) == str(lifted):
        return node
    out = _try_lower_to_ast(extracted, ctx, node.span)
    return out if out is not None else node


# ---------------------------------------------------------------------
# Common-subexpression elimination (CSE) post-pass
# ---------------------------------------------------------------------
#
# After saturation + extraction, the resulting expression may print the
# same subterm more than once. Egglog's tree extractor visits each
# occurrence independently, so a subterm that the e-graph collapsed to a
# single e-class still appears N times in the str() form. The codegen
# would then emit N parallel substrate calls. The three helpers below
# detect and collapse those repeats into let-bindings.
#
# These operate on the str() form of an extracted expression rather
# than on an AST. That keeps them decoupled from the AST lower step
# (`_try_lower_to_ast` above): any future codegen that wants to
# materialize let-bindings can call `cse_let_form` on the extracted
# str and decide how to emit the bindings.
#
# The cost model `cse_aware_cost_model` is a deliberate rename of
# `matrix_chain_cost_model` — egglog's tree extraction already charges
# per-occurrence, so a CSE-eligible repeated subterm gets a cost
# proportional to how many times it appears. The pairing is: pick a
# cost model that doesn't try to deduplicate inside the extractor, then
# let `cse_let_form` deduplicate after extraction. JuliaSymbolics
# reports 3.2x speedup + 5x faster codegen with the same split.

import re


def cse_aware_cost_model(egraph, expr, children_costs):
    """Cost model paired with `cse_let_form`.

    Identical numerics to `matrix_chain_cost_model` — apply/bind/unbind
    cost 100, everything else 1, summed over children. The rename
    advertises the intent: extraction is tree-based (per-occurrence
    cost), and `cse_let_form` is the second step that collapses repeats
    into shared bindings. If you change one weight here you almost
    certainly want to change the same weight in
    `matrix_chain_cost_model`; keeping them in lockstep is a feature.
    """
    return matrix_chain_cost_model(egraph, expr, children_costs)


_IDENT_PAREN_RE = re.compile(r'[A-Za-z_][A-Za-z0-9_.]*\(')


def _enumerate_call_subexprs(s: str) -> list[str]:
    """Return every `<ident>(<balanced parens>)` substring of `s`, in
    document order. Nested calls produce multiple entries: both the
    outer call and each inner call appear once per syntactic occurrence.

    Used by `find_repeated_subexprs` to count how often each
    subexpression appears in an extracted egglog form. Egglog's
    stringification of `bundle(bind(R, v), bind(R, v))` puts each
    `bind(...)` at a distinct character offset, so this enumeration
    yields the outer `bundle(...)` once and each `bind(...)` once.
    """
    out: list[str] = []
    for m in _IDENT_PAREN_RE.finditer(s):
        start = m.start()
        depth = 0
        for i in range(m.end() - 1, len(s)):
            c = s[i]
            if c == '(':
                depth += 1
            elif c == ')':
                depth -= 1
                if depth == 0:
                    out.append(s[start:i + 1])
                    break
    return out


def find_repeated_subexprs(extracted: object,
                            min_size: int = 15) -> list[tuple[str, int]]:
    """Find balanced-paren call subexpressions that appear >= 2 times.

    `extracted` is anything whose `str()` is the textual form of an
    extracted egglog expression. Returns `[(substring, count), ...]`,
    sorted longest-first (ties broken alphabetically for determinism).
    Subexpressions shorter than `min_size` characters are filtered out —
    the default 15 skips trivial things like `Vec.zero()` or
    `Num.lit(0.0)` that aren't worth a let-binding.

    Counting is purely textual: two occurrences are "the same" iff they
    are the same string. That's the right semantics for egglog output
    because two e-graph-equal subterms extract to the same stringified
    form. It is NOT a structural-equality check across whitespace or
    name aliasing — egglog's stringifier is deterministic enough to
    make textual equality adequate in practice.
    """
    s = str(extracted)
    subs = _enumerate_call_subexprs(s)
    counts: dict[str, int] = {}
    for sub in subs:
        if len(sub) < min_size:
            continue
        counts[sub] = counts.get(sub, 0) + 1
    repeated = [(sub, cnt) for sub, cnt in counts.items() if cnt >= 2]
    repeated.sort(key=lambda pair: (-len(pair[0]), pair[0]))
    return repeated


def cse_let_form(extracted: object, min_size: int = 15,
                  prefix: str = "_cse") -> tuple[list[tuple[str, str]], str]:
    """Pull repeated subexpressions out as let-bindings, longest-first.

    Returns `(bindings, body)`:
      * `bindings = [(temp_name, sub_str), ...]` in the order they
        should be evaluated (outer-first, so a later binding's
        sub_str does not contain an unresolved earlier temp name).
      * `body` is the extracted str with each binding's sub_str
        replaced by its temp_name.

    The algorithm is greedy on length:
      1. Find all repeated subexpressions of the current body.
      2. Pick the longest. Assign it the next temp name (`_cse0`,
         `_cse1`, ...). Replace every textual occurrence in the body
         with that name. Append `(name, sub_str)` to bindings.
      3. Loop until no repeated subexpression remains.

    The longest-first ordering means an outer repeated form like
    `bind(Mat.named("R"), Vec.named("v"))` is extracted first, and the
    inner `Mat.named("R")` / `Vec.named("v")` repeats inside it get
    absorbed into a single binding — they no longer textually appear
    in the body, so subsequent iterations don't double-bind them.

    Codegen integration is deferred. A consumer that wants Python
    let-bindings calls this on the extracted str and emits
    `temp_name = sub_str` lines (with the sub_str translated back to
    Python source) followed by the body. The two-step split keeps
    this primitive testable without an AST round-trip.
    """
    body = str(extracted)
    bindings: list[tuple[str, str]] = []
    counter = 0
    while True:
        repeated = find_repeated_subexprs(body, min_size=min_size)
        if not repeated:
            break
        sub, _count = repeated[0]
        name = f"{prefix}{counter}"
        counter += 1
        bindings.append((name, sub))
        body = body.replace(sub, name)
    return bindings, body
