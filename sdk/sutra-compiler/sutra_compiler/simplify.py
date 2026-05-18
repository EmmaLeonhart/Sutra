"""AST simplification pass + basis_vector-argument collection.

Runs after parsing, before codegen. Takes an `ast.Module` and
returns a simplified `ast.Module` with algebraic rewrites applied.

The rewrite set below is deliberately aggressive: Sutra's language
contract is that `.su` source describes *what* to compute, and the
compiler is responsible for reducing that to the minimum substrate
work. Every rewrite here is either an exact algebraic identity or
a soundness-preserving structural match. No approximate rewrites.

### Rewrites applied

1. **bundle-of-one elision.** `bundle(v)` → `v`.
   Exact identity for unit-norm inputs; harmless re-normalization of
   non-unit inputs is also algebraically `v / |v|`, still the identity
   after any downstream cosine-based consumption.

2. **bundle flattening.** `bundle(bundle(a,b), c, bundle(d,e))` →
   `bundle(a,b,c,d,e)`. Nested bundles are sums-of-sums; flattening
   surfaces all terms so the parallel-scheduling pass sees them as
   independent leaves.

3. **compose flattening.** `compose(compose(a,b), c)` → `compose(a,b,c)`.
   Same motivation as bundle flattening: `compose` is associative,
   and nested forms hide parallelism from the scheduling pass.

4. **similarity of self.** `similarity(a, a)` → `1.0`. Cosine of a
   vector with itself is 1 for any non-zero vector. The rare
   zero-vector case also agrees with runtime (runtime returns 0 for
   zero norms, but `similarity(zero, zero)` in actual programs means
   "I made a bug"; the rewrite surfaces that earlier).

5. **displacement of self.** `displacement(a, a)` → `zero_vector()`.
   `a - a = 0` exactly. Downstream rewrites (6, 7) then absorb the
   zero into surrounding expressions.

6. **zero absorption in bundle.** `bundle(..., zero_vector(), ...)` →
   `bundle(...)` (drop the zero arg). If that leaves bundle empty,
   the rewrite emits `zero_vector()` directly.

7. **zero absorption in addition.** `x + zero_vector()` → `x`,
   `zero_vector() + x` → `x`. For BinaryOp with `+` or `-`.

8. **unbind/bind inverse.** `unbind(R, bind(R, x))` → `x` when the
   two R arguments are structurally-identical Identifier references.
   This is exact: Q.T @ (Q @ x) = x for orthogonal Q. The role
   matrix is recomputed at runtime from the role vector, so
   bit-identical role vectors produce bit-identical Q matrices.

9. **bind/unbind inverse.** `bind(R, unbind(R, x))` → `x`. Same
   identity in the other direction.

10. **displacement-addition bundle rewrite.** A `bundle(...)` whose
    args include a `displacement(a, b)` and a `b` in adjacent positions
    *could* collapse to `bundle(..., a)`, but this requires reasoning
    about bundle's normalization, which is lossy for repeated terms.
    Not implemented — left as a comment for future work. The
    cartography-style `a - b + c` (= `bundle(displacement(a,b), c)`)
    stays as written.

11. **Arithmetic constant folding.** `x + 0` → `x`, `x - 0` → `x`,
    `x * 1` → `x`, `1 * x` → `x`, `x * 0` → `0`, `0 * x` → `0`,
    `x / 1` → `x` for scalar literal operands. Applied to IntLiteral
    and FloatLiteral.

12. **bind of zero_vector() absorbs.** `bind(role, zero_vector())`
    → `zero_vector()`. Q @ 0 = 0 for any orthogonal Q. Independent
    of role. Enables cascading: rule 5's `displacement(a, a)` →
    zero can propagate through bind, and rule 6 then drops it from
    an enclosing bundle.

13. **unbind of zero_vector() absorbs.** `unbind(role,
    zero_vector())` → `zero_vector()`. Q^T @ 0 = 0 by the same
    argument.

14. **compose with identity_permutation drops.**
    `compose(identity_permutation(), x)` → `x` and
    `compose(x, identity_permutation())` → `x`. `identity_permutation()`
    is the all-ones vector; pointwise multiply by all-ones is the
    identity. If all args are identities, the result is
    `identity_permutation()` itself.

15. **argmax_cosine of single-candidate list.** `argmax_cosine(v,
    [x])` → `x`. Only fires when the candidates are a compile-time
    `ArrayLiteral` with exactly one element.

16. **Subscript of ArrayLiteral with literal int index.** `[a, b,
    c][1]` → `b`. Compile-time array indexing. Negative indices
    are handled Python-style; out-of-range indices are left
    unsimplified so the runtime IndexError surfaces as a real
    diagnostic.

### Rewrites NOT applied (documented non-rewrites)

- `bundle(x, x)` → `x` (NOT applied). `bundle` normalizes to unit
  norm, so `bundle(x, x) = (x+x)/|x+x| = x/|x| = x` for unit x.
  True algebraically, but the rewrite requires reasoning about
  norms we don't track statically. Skipped.
- `bind(R1, bind(R2, x))` → `bind(compose(R1,R2), x)`. The product
  of two Haar rotations is not itself a single cached role, so the
  rewrite would require materializing a composite rotation at
  runtime rather than at compile time. Skipped.

### Design invariants

- Post-order traversal: children are simplified before the parent
  looks at them. This lets nested rewrites cascade in one pass.
- No rewrite produces a new node type the codegen doesn't already
  handle. `zero_vector()` is a new builtin emitted via the normal
  `Call(Identifier("zero_vector"), ...)` path.
- Rewrites are applied unconditionally — there is no user-facing
  flag to disable them. If a rewrite produces wrong output for some
  program, the rewrite is wrong and has to be removed, not hidden
  behind a flag.
"""
from __future__ import annotations

from typing import Callable, List, Optional

from . import ast_nodes as ast
from .diagnostics import SourceSpan


# Optional tracing hook. When set to a callable, every rewrite that
# fires invokes `_trace_callback(rule_name, before_node, after_node)`.
# Used by `sutra_compiler.review` to show step-by-step simplification.
# None in production — zero overhead when not used.
_trace_callback: Optional[Callable[[str, object, object], None]] = None


def set_trace_callback(cb: Optional[Callable[[str, object, object], None]]) -> None:
    """Set (or clear with None) the per-rewrite tracing callback.

    The callback receives (rule_name, before_node, after_node) every
    time a rewrite fires. Intended for the --review compiler mode;
    production code leaves this at None.
    """
    global _trace_callback
    _trace_callback = cb


def _trace(rule: str, before, after):
    """Invoke the trace callback if one is registered. Inline helper so
    rewrite sites read as `return _trace("R01", call, result)`."""
    if _trace_callback is not None:
        _trace_callback(rule, before, after)
    return after


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------


def simplify_module(module: ast.Module) -> ast.Module:
    """Apply all simplification passes to a module and return the result.

    Two passes:
    1. The hand-rolled rule set in this file (R01..R16, structural).
    2. An egglog-driven post-pass that tries to reduce expressions
       the hand-rolled pass leaves intact — primarily cases where
       cascading rewrites need equality saturation rather than the
       fixed-order pattern matching the hand-rolled simplifier does.

    The egglog pass is conservative: it only replaces a subtree when
    the result lowers to a recognized simpler shape (a literal, an
    identifier, a `zero_vector()` call). Anything else round-trips
    losslessly. If the `egglog` package isn't installed, the post-
    pass is a no-op.

    The module is mutated in place; the return value is the same
    object, returned for call-chain convenience.
    """
    for decl in module.items:
        _simplify_top_level(decl)
    _egglog_post_pass(module)
    return module


def _egglog_post_pass(module: ast.Module) -> None:
    """Walk every expression in the module and try the egglog
    simplifier on it. Replace the expression in its parent if egglog
    found a simpler shape.

    Conservative — only replaces when the result is structurally
    simpler (a literal, identifier, or zero_vector call). The lift /
    lower bridge in `simplify_egglog` returns the original expression
    unchanged when it can't make progress, so the identity-comparison
    `out is expr` is the signal for "no change."
    """
    try:
        from . import simplify_egglog as _eg
    except ImportError:
        # egglog not installed — post-pass is a no-op.
        return

    def _try(expr: ast.Expr) -> ast.Expr:
        # Try vec context first; if no progress, try num. Bridge is
        # conservative on both sides — never returns a wrong result.
        out = _eg.simplify_ast_vec(expr)
        if out is not expr:
            return out
        out = _eg.simplify_ast_num(expr)
        return out

    def _walk_expr(expr: ast.Expr) -> ast.Expr:
        """Bottom-up walk: simplify children first, then the node."""
        if isinstance(expr, ast.Call):
            expr.args = [_walk_expr(a) for a in expr.args]
        elif isinstance(expr, ast.BinaryOp):
            expr.left = _walk_expr(expr.left)
            expr.right = _walk_expr(expr.right)
        elif isinstance(expr, ast.UnaryOp):
            expr.operand = _walk_expr(expr.operand)
        elif isinstance(expr, ast.Parenthesized):
            expr.inner = _walk_expr(expr.inner)
        elif isinstance(expr, ast.ArrayLiteral):
            expr.elements = [_walk_expr(e) for e in expr.elements]
        elif isinstance(expr, ast.CastExpr):
            expr.expr = _walk_expr(expr.expr)
        elif isinstance(expr, ast.UnsafeCastExpr):
            expr.expr = _walk_expr(expr.expr)
        return _try(expr)

    def _walk_stmt(stmt: ast.Stmt) -> None:
        # Skip if there's no obvious place an expr could be.
        if isinstance(stmt, ast.VarDecl):
            if stmt.initializer is not None:
                stmt.initializer = _walk_expr(stmt.initializer)
        elif isinstance(stmt, ast.ExprStmt):
            stmt.expr = _walk_expr(stmt.expr)
        elif isinstance(stmt, ast.ReturnStmt):
            if stmt.value is not None:
                stmt.value = _walk_expr(stmt.value)
        elif isinstance(stmt, ast.IfStmt):
            stmt.condition = _walk_expr(stmt.condition)
            for s in stmt.then_branch.statements:
                _walk_stmt(s)
            if stmt.else_branch is not None:
                for s in stmt.else_branch.statements:
                    _walk_stmt(s)
        elif isinstance(stmt, ast.Block):
            for s in stmt.statements:
                _walk_stmt(s)
        elif isinstance(stmt, ast.WhileStmt):
            stmt.condition = _walk_expr(stmt.condition)
            for s in stmt.body.statements:
                _walk_stmt(s)
        elif isinstance(stmt, ast.LoopStmt):
            for s in stmt.body.statements:
                _walk_stmt(s)
        # Other statement types: walked-through children are out of
        # scope for this post-pass; the hand-written pass already
        # handled them.

    for decl in module.items:
        if isinstance(decl, ast.VarDecl):
            if decl.initializer is not None:
                decl.initializer = _walk_expr(decl.initializer)
        elif isinstance(decl, ast.FunctionDecl):
            for s in decl.body.statements:
                _walk_stmt(s)
        elif isinstance(decl, ast.MethodDecl):
            for s in decl.body.statements:
                _walk_stmt(s)
        elif isinstance(decl, ast.ClassDecl):
            # Empty bodies for now; nothing to walk inside.
            pass
        elif isinstance(decl, ast.Stmt):
            _walk_stmt(decl)


def _auto_embed_var_decl_init(decl: ast.VarDecl) -> None:
    """Type-directed rewrite of StringLiteral initializers.

    String literals are interpreted by the type they are being
    assigned into:

    - `vector v = "foo"` — the string is implicitly embedded. We wrap
      it in `EmbedExpr` so the codegen emits `_VSA.embed("foo")`.
    - `char c = "c"` — the string must be exactly one character; we
      rewrite it to a `CharLiteral`. A longer string is a type error
      the validator will catch separately; for now we leave longer
      strings in place so the program still parses (codegen will
      diagnose).
    - `var x = "foo"` (untyped) — defaults to embed. User direction
      was clear: "var x = 'x' will default embed". The programmer
      writes `var x : string = "foo"` or `string x = "foo"` to keep
      the string as a string.
    - `string x = "foo"` — untouched. Explicit string type keeps the
      string.

    Only the literal case — `StringLiteral` — is rewritten. Non-literal
    RHS expressions (e.g. `vector v = lookup_name();`) are left to
    whatever the normal expression-typing story produces.
    """
    if decl.initializer is None:
        return
    if not isinstance(decl.initializer, ast.StringLiteral):
        return
    s_lit: ast.StringLiteral = decl.initializer
    type_name = decl.type_ref.name if decl.type_ref is not None else None

    # `string x = "foo"` — explicit string, no rewrite.
    if type_name == "string":
        return

    # `char c = "c"` — fold to CharLiteral at compile time.
    if type_name == "char":
        if len(s_lit.value) == 1:
            decl.initializer = ast.CharLiteral(
                value=ord(s_lit.value), span=s_lit.span,
            )
        # Length != 1 is left alone; the validator / codegen will
        # complain when a string hits a `char` context.
        return

    # `vector v = "foo"` OR `var v = "foo"` (untyped) — implicit embed.
    if type_name == "vector" or decl.is_var_inferred:
        decl.initializer = ast.EmbedExpr(expr=s_lit, span=s_lit.span)
        return

    # Other typed contexts (int, float, fuzzy, etc.) — don't rewrite.
    # Fuzzy-with-StringLiteral is a type error the validator catches;
    # int/float with a string is a cast the validator catches too.


def collect_basis_vector_strings(module: ast.Module) -> list[str]:
    """Return every string literal that will be embedded at runtime.

    Covers two sources:
    - `basis_vector("name")` — explicit source-level basis_vector call
      with a string literal argument.
    - `embed(<StringLiteral>)` — the `EmbedExpr` AST node, which the
      auto-embed pass inserts in type-directed contexts (`vector v =
      "foo"`, untyped `var x = "foo"`, etc.) and which may also be
      written explicitly.

    Used by the codegen to emit a batched Ollama pre-fetch at module
    init: N sequential HTTP round-trips collapse into a single batched
    embed call. Strings are returned in source order, deduplicated
    (first-occurrence order preserved).
    """
    seen: set[str] = set()
    collected: list[str] = []

    def record(s: str) -> None:
        if s not in seen:
            seen.add(s)
            collected.append(s)

    def visit(node) -> None:
        if node is None:
            return
        if isinstance(node, ast.Call):
            if _is_basis_vector_literal_call(node):
                record(node.args[0].value)  # type: ignore[attr-defined]
            visit(node.callee)
            for a in node.args:
                visit(a)
            return
        if isinstance(node, ast.EmbedExpr) and isinstance(node.expr, ast.StringLiteral):
            record(node.expr.value)
            return
        for child in _children(node):
            visit(child)

    for item in module.items:
        visit(item)
    return collected


# ---------------------------------------------------------------------------
# Internal: AST traversal helpers
# ---------------------------------------------------------------------------


def _children(node):
    """Yield direct child AST nodes of `node`. Covers every expression
    and statement type the simplifier may encounter.
    """
    if node is None:
        return
    if isinstance(node, ast.BinaryOp):
        yield node.left; yield node.right; return
    if isinstance(node, ast.UnaryOp):
        yield node.operand; return
    if isinstance(node, ast.PostfixOp):
        yield node.operand; return
    if isinstance(node, ast.ArrayLiteral):
        for e in node.elements: yield e
        return
    if isinstance(node, ast.MapLiteral):
        for k in node.keys: yield k
        for v in node.values: yield v
        return
    if isinstance(node, ast.Subscript):
        yield node.target; yield node.index; return
    if isinstance(node, ast.MemberAccess):
        yield node.obj; return
    if isinstance(node, ast.Assignment):
        yield node.target; yield node.value; return
    if isinstance(node, ast.Parenthesized):
        yield node.inner; return
    if isinstance(node, ast.CastExpr):
        yield node.expr; return
    if isinstance(node, ast.UnsafeCastExpr):
        yield node.expr; return
    if isinstance(node, ast.UnsafeOverrideExpr):
        yield node.expr; return
    if isinstance(node, ast.DefuzzyExpr):
        yield node.expr; return
    if isinstance(node, ast.EmbedExpr):
        yield node.expr; return
    if isinstance(node, ast.InterpolatedString):
        for part in node.parts:
            if not isinstance(part, str):
                yield part
        return
    if isinstance(node, ast.VarDecl):
        yield node.initializer; return
    if isinstance(node, ast.FunctionDecl):
        for s in node.body.statements: yield s
        return
    if isinstance(node, ast.ReturnStmt):
        yield node.value; return
    if isinstance(node, ast.ExprStmt):
        yield node.expr; return
    if isinstance(node, ast.IfStmt):
        yield node.condition
        for s in node.then_branch.statements: yield s
        if node.else_branch is not None:
            if isinstance(node.else_branch, ast.IfStmt):
                yield node.else_branch
            else:
                for s in node.else_branch.statements: yield s
        return
    if isinstance(node, ast.WhileStmt):
        yield node.condition
        for s in node.body.statements: yield s
        return
    if isinstance(node, ast.ForStmt):
        yield node.init; yield node.condition; yield node.step
        for s in node.body.statements: yield s
        return
    if isinstance(node, ast.DoWhileStmt):
        yield node.condition
        for s in node.body.statements: yield s
        return
    if isinstance(node, ast.ForeachStmt):
        yield node.iterable
        for s in node.body.statements: yield s
        return
    if isinstance(node, ast.LoopStmt):
        yield node.count; yield node.condition
        for s in node.body.statements: yield s
        return
    if isinstance(node, ast.Block):
        for s in node.statements: yield s
        return
    if isinstance(node, ast.TryStmt):
        for s in node.try_body.statements: yield s
        for s in node.catch_body.statements: yield s
        return
    # Leaf nodes (Identifier, literals, etc.) have no children.


# ---------------------------------------------------------------------------
# Internal: structural equality on expressions
# ---------------------------------------------------------------------------


def _structurally_equal(a, b) -> bool:
    """Conservative structural equality for expressions.

    Returns True only when we can prove the two subtrees evaluate to
    the same value — which is exact for literal constants and for
    identifier references to the same name. Pessimistic elsewhere:
    a `MemberAccess`, a `Call`, or anything with side effects compares
    unequal even if textually identical, because a cautious rewriter
    needs to assume they might differ.

    This is used by the unbind/bind inverse rewrites to decide whether
    the two role arguments are "the same". In practice, roles in .su
    programs are top-level `vector r_foo = basis_vector("...")`
    declarations referenced by identifier — exactly the case this
    function handles exactly.
    """
    if type(a) is not type(b):
        return False
    if isinstance(a, ast.Identifier):
        return a.name == b.name
    if isinstance(a, ast.IntLiteral):
        return a.value == b.value
    if isinstance(a, ast.FloatLiteral):
        return a.value == b.value
    if isinstance(a, ast.StringLiteral):
        return a.value == b.value
    if isinstance(a, ast.BoolLiteral):
        return a.value == b.value
    # Anything else: be conservative.
    return False


# ---------------------------------------------------------------------------
# Internal: call-pattern matchers
# ---------------------------------------------------------------------------


def _is_call_named(expr, name: str, arity: Optional[int] = None) -> bool:
    if not isinstance(expr, ast.Call):
        return False
    if not isinstance(expr.callee, ast.Identifier):
        return False
    if expr.callee.name != name:
        return False
    if arity is not None and len(expr.args) != arity:
        return False
    return True


def _is_zero_vector_call(expr) -> bool:
    """Match `zero_vector()` — the emitted zero primitive."""
    return _is_call_named(expr, "zero_vector", arity=0)


def _is_basis_vector_literal_call(expr) -> bool:
    return (_is_call_named(expr, "basis_vector", arity=1)
            and isinstance(expr.args[0], ast.StringLiteral))


def _mk_zero_vector(span: SourceSpan) -> ast.Call:
    """Construct a fresh `zero_vector()` call node."""
    return ast.Call(
        span=span,
        callee=ast.Identifier(span=span, name="zero_vector"),
        type_args=[],
        args=[],
    )


def _mk_float_literal(value: float, span: SourceSpan) -> ast.FloatLiteral:
    return ast.FloatLiteral(span=span, value=value)


# ---------------------------------------------------------------------------
# Internal: statement dispatch
# ---------------------------------------------------------------------------


def _simplify_top_level(decl) -> None:
    if isinstance(decl, ast.FunctionDecl):
        _simplify_block(decl.body)
    elif isinstance(decl, ast.VarDecl):
        _auto_embed_var_decl_init(decl)
        if decl.initializer is not None:
            decl.initializer = _simplify_expr(decl.initializer)


def _simplify_block(block: ast.Block) -> None:
    for stmt in block.statements:
        _simplify_stmt(stmt)


def _simplify_stmt(stmt) -> None:
    if isinstance(stmt, ast.VarDecl):
        _auto_embed_var_decl_init(stmt)
        if stmt.initializer is not None:
            stmt.initializer = _simplify_expr(stmt.initializer)
        return
    if isinstance(stmt, ast.ReturnStmt):
        if stmt.value is not None:
            stmt.value = _simplify_expr(stmt.value)
        return
    if isinstance(stmt, ast.ExprStmt):
        stmt.expr = _simplify_expr(stmt.expr)
        return
    if isinstance(stmt, ast.IfStmt):
        stmt.condition = _simplify_expr(stmt.condition)
        _simplify_block(stmt.then_branch)
        if stmt.else_branch is not None:
            if isinstance(stmt.else_branch, ast.IfStmt):
                _simplify_stmt(stmt.else_branch)
            else:
                _simplify_block(stmt.else_branch)
        return
    if isinstance(stmt, ast.WhileStmt):
        stmt.condition = _simplify_expr(stmt.condition)
        _simplify_block(stmt.body)
        return
    if isinstance(stmt, ast.ForStmt):
        if stmt.init is not None:
            _simplify_stmt(stmt.init)
        if stmt.condition is not None:
            stmt.condition = _simplify_expr(stmt.condition)
        if stmt.step is not None:
            _simplify_stmt(stmt.step)
        _simplify_block(stmt.body)
        return
    if isinstance(stmt, ast.DoWhileStmt):
        _simplify_block(stmt.body)
        stmt.condition = _simplify_expr(stmt.condition)
        return
    if isinstance(stmt, ast.ForeachStmt):
        stmt.iterable = _simplify_expr(stmt.iterable)
        _simplify_block(stmt.body)
        return
    if isinstance(stmt, ast.LoopStmt):
        if stmt.count is not None:
            stmt.count = _simplify_expr(stmt.count)
        if stmt.condition is not None:
            stmt.condition = _simplify_expr(stmt.condition)
        _simplify_block(stmt.body)
        return
    if isinstance(stmt, ast.Block):
        _simplify_block(stmt)
        return
    if isinstance(stmt, ast.TryStmt):
        _simplify_block(stmt.try_body)
        _simplify_block(stmt.catch_body)
        return
    # Unknown statement types pass through untouched.


# ---------------------------------------------------------------------------
# Internal: expression simplification (post-order)
# ---------------------------------------------------------------------------


def _simplify_expr(expr):
    """Recursively simplify an expression. Post-order traversal: simplify
    children first, then look at the resulting node for rewrite matches.
    Rewrites may compound in a single pass because children are finalized
    before the parent inspects them.
    """
    if expr is None:
        return None

    if isinstance(expr, ast.Call):
        if not isinstance(expr.callee, ast.Identifier):
            expr.callee = _simplify_expr(expr.callee)
        expr.args = [_simplify_expr(a) for a in expr.args]
        return _rewrite_call(expr)

    if isinstance(expr, ast.BinaryOp):
        expr.left = _simplify_expr(expr.left)
        expr.right = _simplify_expr(expr.right)
        return _rewrite_binary(expr)

    if isinstance(expr, ast.UnaryOp):
        expr.operand = _simplify_expr(expr.operand)
        # Unary minus on an imaginary literal folds at compile time
        # (`-5i` → ImaginaryLiteral(-5)). Unary plus is a no-op.
        if expr.op == "-" and isinstance(expr.operand, ast.ImaginaryLiteral):
            return ast.ImaginaryLiteral(
                value=-expr.operand.value, span=expr.span,
            )
        if expr.op == "+" and isinstance(expr.operand, ast.ImaginaryLiteral):
            return expr.operand
        # Unary minus on a numeric literal: `-5` → IntLiteral(-5),
        # `-3.14` → FloatLiteral(-3.14). Matters for inlined
        # polynomials where a `0 - x` form from logical_not on a
        # literal input should collapse.
        if expr.op == "-":
            if isinstance(expr.operand, ast.IntLiteral):
                return ast.IntLiteral(
                    value=-expr.operand.value, span=expr.span,
                )
            if isinstance(expr.operand, ast.FloatLiteral):
                return ast.FloatLiteral(
                    value=-expr.operand.value, span=expr.span,
                )
        if expr.op == "+":
            if isinstance(expr.operand, (ast.IntLiteral, ast.FloatLiteral)):
                return expr.operand
        return expr

    if isinstance(expr, ast.ArrayLiteral):
        expr.elements = [_simplify_expr(e) for e in expr.elements]
        return expr

    if isinstance(expr, ast.MapLiteral):
        expr.keys = [_simplify_expr(k) for k in expr.keys]
        expr.values = [_simplify_expr(v) for v in expr.values]
        return expr

    if isinstance(expr, ast.Subscript):
        expr.target = _simplify_expr(expr.target)
        expr.index = _simplify_expr(expr.index)
        # Rule 16: Subscript of an ArrayLiteral with a literal int index
        # → the indexed element. Compile-time array indexing. Out-of-
        # range indices are left unsimplified (the runtime IndexError
        # is the right behavior; silent truncation would hide a program bug).
        # Negative indices are handled in Python style (-1 → last).
        if (isinstance(expr.target, ast.ArrayLiteral)
                and isinstance(expr.index, ast.IntLiteral)):
            elements = expr.target.elements
            idx = expr.index.value
            if -len(elements) <= idx < len(elements):
                return elements[idx]
        return expr

    if isinstance(expr, ast.MemberAccess):
        expr.obj = _simplify_expr(expr.obj)
        return expr

    if isinstance(expr, ast.Assignment):
        expr.target = _simplify_expr(expr.target)
        expr.value = _simplify_expr(expr.value)
        return expr

    if isinstance(expr, ast.Parenthesized):
        expr.inner = _simplify_expr(expr.inner)
        return expr

    if isinstance(expr, ast.CastExpr):
        expr.expr = _simplify_expr(expr.expr)
        return expr

    if isinstance(expr, ast.UnsafeCastExpr):
        expr.expr = _simplify_expr(expr.expr)
        return expr

    if isinstance(expr, ast.UnsafeOverrideExpr):
        expr.expr = _simplify_expr(expr.expr)
        return expr

    if isinstance(expr, ast.DefuzzyExpr):
        expr.expr = _simplify_expr(expr.expr)
        return expr

    if isinstance(expr, ast.EmbedExpr):
        expr.expr = _simplify_expr(expr.expr)
        return expr

    if isinstance(expr, ast.InterpolatedString):
        new_parts = []
        for p in expr.parts:
            if isinstance(p, str):
                new_parts.append(p)
            else:
                new_parts.append(_simplify_expr(p))
        expr.parts = new_parts
        return expr

    # Identifier, IntLiteral, FloatLiteral, CharLiteral, StringLiteral,
    # BoolLiteral, UnknownLiteral, ImaginaryLiteral, ComplexLiteral —
    # ThisExpr — no simplification.
    return expr


# ---------------------------------------------------------------------------
# Internal: call-level rewrites (post children-simplified)
# ---------------------------------------------------------------------------


def _rewrite_call(call: ast.Call):
    if not isinstance(call.callee, ast.Identifier):
        return call
    name = call.callee.name

    # Rule 1: bundle(v) → v  (single-arg bundle is identity).
    if name == "bundle" and len(call.args) == 1:
        return _trace("R01 bundle(v) -> v", call, call.args[0])

    # Rule 2: flatten nested bundles.
    if name == "bundle":
        flattened: List = []
        changed = False
        for a in call.args:
            if _is_call_named(a, "bundle"):
                flattened.extend(a.args)
                changed = True
            else:
                flattened.append(a)
        if changed:
            call.args = flattened
            # Re-check rule 1 after flattening.
            if len(call.args) == 1:
                return call.args[0]

    # Rule 6: drop zero_vector() arguments from bundle.
    if name == "bundle":
        non_zero = [a for a in call.args if not _is_zero_vector_call(a)]
        if len(non_zero) != len(call.args):
            if not non_zero:
                # bundle(zero, zero, ...) → zero_vector()
                return _mk_zero_vector(call.span)
            call.args = non_zero
            if len(call.args) == 1:
                return call.args[0]

    # Rule 3: compose(compose(a,b), c) → compose(a,b,c).
    if name == "compose":
        flattened = []
        changed = False
        for a in call.args:
            if _is_call_named(a, "compose"):
                flattened.extend(a.args)
                changed = True
            else:
                flattened.append(a)
        if changed:
            call.args = flattened

    # Rule 4: similarity(a, a) → 1.0 (structurally equal args only).
    if (name == "similarity"
            and len(call.args) == 2
            and _structurally_equal(call.args[0], call.args[1])):
        return _trace("R04 similarity(a, a) -> 1.0", call,
                      _mk_float_literal(1.0, call.span))

    # Rule 5: displacement(a, a) → zero_vector() (structurally equal args).
    if (name == "displacement"
            and len(call.args) == 2
            and _structurally_equal(call.args[0], call.args[1])):
        return _trace("R05 displacement(a, a) -> zero", call,
                      _mk_zero_vector(call.span))

    # Rule 8: unbind(R, bind(R, x)) → x.
    if name == "unbind" and len(call.args) == 2:
        inner = call.args[1]
        if (_is_call_named(inner, "bind", arity=2)
                and _structurally_equal(call.args[0], inner.args[0])):
            return _trace("R08 unbind(R, bind(R, x)) -> x", call,
                          inner.args[1])

    # Rule 9: bind(R, unbind(R, x)) → x.
    if name == "bind" and len(call.args) == 2:
        inner = call.args[1]
        if (_is_call_named(inner, "unbind", arity=2)
                and _structurally_equal(call.args[0], inner.args[0])):
            return _trace("R09 bind(R, unbind(R, x)) -> x", call,
                          inner.args[1])

    # Rule 12: bind(role, zero_vector()) → zero_vector().
    # Q @ 0 = 0 for any orthogonal Q. The rotation of the zero vector is
    # the zero vector. Independent of role.
    if (name == "bind" and len(call.args) == 2
            and _is_zero_vector_call(call.args[1])):
        return _trace("R12 bind(R, zero) -> zero", call,
                      _mk_zero_vector(call.span))

    # Rule 13: unbind(role, zero_vector()) → zero_vector().
    # Q^T @ 0 = 0 by the same argument. Independent of role.
    if (name == "unbind" and len(call.args) == 2
            and _is_zero_vector_call(call.args[1])):
        return _trace("R13 unbind(R, zero) -> zero", call,
                      _mk_zero_vector(call.span))

    # Rule 14: compose with identity_permutation() on either side →
    # drop the identity. `identity_permutation()` is the all-ones
    # vector and `compose` is elementwise multiply, so multiplying
    # by all-ones is the identity. Works after rule 3 has flattened
    # nested composes.
    if name == "compose" and len(call.args) >= 2:
        non_identity = [
            a for a in call.args if not _is_call_named(a, "identity_permutation", arity=0)
        ]
        if len(non_identity) != len(call.args):
            if not non_identity:
                # compose(identity, identity, ...) is identity itself.
                return _mk_identity_permutation(call.span)
            if len(non_identity) == 1:
                # compose(x, identity) → x; compose(identity, x) → x.
                return non_identity[0]
            call.args = non_identity

    # Rule 15: argmax_cosine(query, [single]) → single.
    # Single-candidate argmax has no choice; the literal element is the
    # result regardless of the query. Only fires when the candidates
    # are an ArrayLiteral with exactly one element (structural match
    # against the compile-time shape).
    if name == "argmax_cosine" and len(call.args) == 2:
        candidates = call.args[1]
        if (isinstance(candidates, ast.ArrayLiteral)
                and len(candidates.elements) == 1):
            return _trace("R15 argmax_cosine(q, [x]) -> x", call,
                          candidates.elements[0])

    return call


def _mk_identity_permutation(span):
    """Synthesize an `identity_permutation()` call for rule 14's empty
    compose case."""
    return ast.Call(
        callee=ast.Identifier(name="identity_permutation", span=span),
        type_args=[],
        args=[],
        span=span,
    )


# ---------------------------------------------------------------------------
# Internal: binary-op rewrites
# ---------------------------------------------------------------------------


def _rewrite_binary(expr: ast.BinaryOp):
    """Arithmetic constant folding + zero-vector absorption."""
    op = expr.op
    left = expr.left
    right = expr.right

    # Rule 7: zero-vector absorption in +/-.
    if op == "+":
        if _is_zero_vector_call(left):
            return _trace("R07 zero + x -> x", expr, right)
        if _is_zero_vector_call(right):
            return _trace("R07 x + zero -> x", expr, left)
    if op == "-":
        if _is_zero_vector_call(right):
            return _trace("R07 x - zero -> x", expr, left)
        # zero - x is not x, so no rewrite on the left side of subtract.

    # Complex-literal folding: `re ± im·i` at compile time. Turns the
    # two-literal expression into a single ComplexLiteral so the
    # codegen emits one _VSA.make_complex(re, im) allocation instead
    # of a vector-add over two partial literals. Handles int+imag,
    # float+imag, imag+int, imag+float, and the four subtraction
    # variants. Imag+imag collapses to a single ImaginaryLiteral.
    if op in ("+", "-"):
        folded = _fold_complex_literal(left, right, op, expr.span)
        if folded is not None:
            return folded

    # Rule 11: numeric constant folding for scalar literals.
    l_num = _numeric_value(left)
    r_num = _numeric_value(right)

    # Identity-element rules first — preserve the original operand
    # node so its type/span stays. (Pre-dates the step-6 full fold
    # and has tests asserting specific node types survive.)
    if op == "+":
        if l_num == 0:
            return right
        if r_num == 0:
            return left
    elif op == "-":
        if r_num == 0:
            return left
    elif op == "*":
        if l_num == 0 or r_num == 0:
            return _mk_float_literal(0.0, expr.span)
        if l_num == 1:
            return right
        if r_num == 1:
            return left
    elif op == "/":
        if r_num == 1:
            return left

    # Step 6 — full literal-on-literal fold: `2 + 3` → `5`,
    # `0.7 * 0.3` → `0.21`, `(poly on literal args) * 0.5` → single
    # constant. Applies when both operands have a numeric-literal
    # value AND neither is an identity element (caught above). This
    # is the starter for the fusion pass: inlined polynomial bodies
    # where all operands are literals collapse to a single literal
    # at compile time. `logical_and(0.7, 0.3)` inlines to the
    # polynomial on `0.7` / `0.3`; this fold collapses that chain to
    # `FloatLiteral(0.33705)`, so the runtime sees a constant
    # (wrapped in `make_truth` by the fuzzy-literal coercion) rather
    # than a tree of arithmetic ops.
    if l_num is not None and r_num is not None:
        try:
            if op == "+":
                return _trace("R16 fold (lit + lit)", expr,
                              _lit_from_num(l_num + r_num, expr.span))
            if op == "-":
                return _trace("R16 fold (lit - lit)", expr,
                              _lit_from_num(l_num - r_num, expr.span))
            if op == "*":
                return _trace("R16 fold (lit * lit)", expr,
                              _lit_from_num(l_num * r_num, expr.span))
            if op == "/" and r_num != 0:
                return _trace("R16 fold (lit / lit)", expr,
                              _lit_from_num(l_num / r_num, expr.span))
        except (ZeroDivisionError, OverflowError):
            pass  # fall through; leave expr unchanged

    return expr


def _lit_from_num(value, span: SourceSpan):
    """Pick IntLiteral vs FloatLiteral based on the value's type.
    Integer-valued floats that came from a pure int computation become
    IntLiteral for pleasanter emission; anything with a fractional
    component stays FloatLiteral."""
    if isinstance(value, int):
        return ast.IntLiteral(span=span, value=value)
    if isinstance(value, float) and value.is_integer():
        # Keep as float — mixing int and float folds should produce
        # float per language semantics, even if the math happens to
        # land on an integer value.
        return _mk_float_literal(value, span)
    return _mk_float_literal(float(value), span)


def _numeric_value(expr):
    """Extract the numeric value of a literal node, or None if not a literal.

    Returns an int or float depending on the literal type; callers can
    compare against 0 or 1 directly. Unwraps `Parenthesized(...)`
    wrappers so a literal inside parens still folds.
    """
    while isinstance(expr, ast.Parenthesized):
        expr = expr.inner
    if isinstance(expr, ast.IntLiteral):
        return expr.value
    if isinstance(expr, ast.FloatLiteral):
        return expr.value
    return None


def _fold_complex_literal(left, right, op: str, span):
    """Compile-time fold of `re ± im·i` into a single ComplexLiteral.

    Recognises the four pairings (number ± imag, imag ± number) and
    the imag ± imag case. Returns the folded node or None if the
    operands don't form a complex-literal pattern.
    """
    assert op in ("+", "-")
    sign = 1.0 if op == "+" else -1.0
    l_num = _numeric_value(left)
    r_num = _numeric_value(right)
    l_is_imag = isinstance(left, ast.ImaginaryLiteral)
    r_is_imag = isinstance(right, ast.ImaginaryLiteral)

    # number ± imag → Complex(number, ±imag)
    if l_num is not None and r_is_imag:
        return ast.ComplexLiteral(
            re=float(l_num), im=sign * float(right.value), span=span,
        )
    # imag ± number → Complex(±number, imag)  (because `5i - 3 = -3 + 5i`)
    if l_is_imag and r_num is not None:
        return ast.ComplexLiteral(
            re=sign * float(r_num), im=float(left.value), span=span,
        )
    # imag ± imag → ImaginaryLiteral(sum/diff).
    if l_is_imag and r_is_imag:
        return ast.ImaginaryLiteral(
            value=float(left.value) + sign * float(right.value), span=span,
        )
    return None
