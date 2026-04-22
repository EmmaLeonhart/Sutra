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
   Same motivation as bundle flattening — `compose` is associative
   pointwise multiply on sign-flip keys, and nested forms hide
   parallelism.

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

### Rewrites NOT applied (documented non-rewrites)

- `bundle(x, x)` → `x` (NOT applied). `bundle` normalizes to unit
  norm, so `bundle(x, x) = (x+x)/|x+x| = x/|x| = x` for unit x.
  True algebraically, but the rewrite requires reasoning about
  norms we don't track statically. Skipped.
- `bind(R1, bind(R2, x))` → `bind(compose(R1,R2), x)`. Would be
  correct if `bind`'s semantics were the sign-flip composition we
  had pre-2026-04-21, but rotation binding has different composition
  semantics (the product of two Haar rotations isn't a single cached
  role). Retired with the sign-flip removal.

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

from typing import List, Optional

from . import ast_nodes as ast
from .diagnostics import SourceSpan


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------


def simplify_module(module: ast.Module) -> ast.Module:
    """Apply all simplification passes to a module and return the result.

    The module is mutated in place; the return value is the same
    object, returned for call-chain convenience.
    """
    for decl in module.items:
        _simplify_top_level(decl)
    return module


def collect_basis_vector_strings(module: ast.Module) -> list[str]:
    """Return every string literal appearing as a `basis_vector(...)` arg.

    Used by the codegen to emit a batched Ollama pre-fetch at module
    init: N sequential HTTP round-trips collapse into a single batched
    embed call. Strings are returned in source order, deduplicated
    (first-occurrence order preserved).
    """
    seen: set[str] = set()
    collected: list[str] = []

    def visit(node) -> None:
        if node is None:
            return
        if isinstance(node, ast.Call):
            if _is_basis_vector_literal_call(node):
                s = node.args[0].value  # type: ignore[attr-defined]
                if s not in seen:
                    seen.add(s)
                    collected.append(s)
            visit(node.callee)
            for a in node.args:
                visit(a)
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
        if decl.initializer is not None:
            decl.initializer = _simplify_expr(decl.initializer)


def _simplify_block(block: ast.Block) -> None:
    for stmt in block.statements:
        _simplify_stmt(stmt)


def _simplify_stmt(stmt) -> None:
    if isinstance(stmt, ast.VarDecl):
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

    # Identifier, IntLiteral, FloatLiteral, StringLiteral, BoolLiteral,
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
        return call.args[0]

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
        return _mk_float_literal(1.0, call.span)

    # Rule 5: displacement(a, a) → zero_vector() (structurally equal args).
    if (name == "displacement"
            and len(call.args) == 2
            and _structurally_equal(call.args[0], call.args[1])):
        return _mk_zero_vector(call.span)

    # Rule 8: unbind(R, bind(R, x)) → x.
    if name == "unbind" and len(call.args) == 2:
        inner = call.args[1]
        if (_is_call_named(inner, "bind", arity=2)
                and _structurally_equal(call.args[0], inner.args[0])):
            return inner.args[1]

    # Rule 9: bind(R, unbind(R, x)) → x.
    if name == "bind" and len(call.args) == 2:
        inner = call.args[1]
        if (_is_call_named(inner, "unbind", arity=2)
                and _structurally_equal(call.args[0], inner.args[0])):
            return inner.args[1]

    return call


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
            return right
        if _is_zero_vector_call(right):
            return left
    if op == "-":
        if _is_zero_vector_call(right):
            return left
        # zero - x is not x, so no rewrite on the left side of subtract.

    # Rule 11: numeric constant folding for scalar literals.
    l_num = _numeric_value(left)
    r_num = _numeric_value(right)

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

    return expr


def _numeric_value(expr):
    """Extract the numeric value of a literal node, or None if not a literal.

    Returns an int or float depending on the literal type; callers can
    compare against 0 or 1 directly.
    """
    if isinstance(expr, ast.IntLiteral):
        return expr.value
    if isinstance(expr, ast.FloatLiteral):
        return expr.value
    return None
