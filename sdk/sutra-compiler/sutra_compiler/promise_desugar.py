"""Stage-1 promise desugar — `async function` + `await` → `Promise<T>`.

Per planning/sutra-spec/promises.md §"Lowering" Stage 1 and the user's
2026-05-09 clarification, this pass rewrites async functions so they
return explicit Promise<T> values via `Promise.resolve(...)` /
`Promise.value(...)` calls. The output is still Sutra source (no
`async` or `await` keywords); a later pass (Stage 2) lowers any
remaining external-input await into a `while_loop` with the
`norm(slot) > eps` gate from `axon-io.md`.

### The lowering rule

Two rewrites, applied uniformly to every `async function`:

1. **Each `await x` becomes `Promise.value(x)`.** If `x` is already
   fulfilled, this returns the resolved value directly. If `x` is
   pending (its substrate-level loop is still cycling), this returns
   a noisy vector — Stage 2 wraps the surrounding code in a loop
   that gates on arrival, so by the time `Promise.value(x)` runs the
   promise has resolved.

2. **Each `return e;` (where `e` isn't already a Promise call)
   becomes `return Promise.resolve(e);`.** The async function's
   contract is to return a Promise<T>, so the body's bare values
   need to be wrapped at the boundary. `return await e;` becomes
   `return Promise.resolve(Promise.value(e));` which simplifies to
   the pass-through `return e;` only when `e` is already a Promise —
   the runtime's resolve(value(p)) chain stays valid otherwise.

Both rewrites are AST-local: we don't generate new top-level
functions, we don't need callbacks, we don't need first-class
function values. `vector v = await x; return g(v);` lowers cleanly
to `vector v = Promise.value(x); return Promise.resolve(g(v));`.

### What this still doesn't cover

  - `try { await ... } catch { ... }` — needs the AXIS_EXCEPTION
    fuzzy-blend lowering (separate work). Without that, `try`/
    `catch` still falls through to the codegen's existing rejection
    pointing at promises.md.

  - The Stage-2 loop wrap for external-input awaits — when an
    awaited value isn't already resolved at compile time, the
    surrounding code needs to live inside a `while_loop` body
    gating on `norm(slot) > eps` (per axon-io.md). Phase 6+ work.

Anything not covered falls through to the codegen's existing async-
rejection error, which points at planning/sutra-spec/promises.md.
"""

from __future__ import annotations

from . import ast_nodes as ast


def desugar_promises(module: ast.Module) -> ast.Module:
    """Walk the module, transform every async function decl in place."""
    for i, item in enumerate(module.items):
        if isinstance(item, ast.FunctionDecl) and item.is_async:
            module.items[i] = _desugar_async_function(item)
    return module


def _desugar_async_function(decl: ast.FunctionDecl) -> ast.FunctionDecl:
    """Lower an async function's body into a non-async equivalent.

    Walks every statement, replacing `await x` with `Promise.value(x)`
    and wrapping bare return values with `Promise.resolve(...)`.
    """
    new_stmts = [_lower_stmt(s) for s in decl.body.statements]
    new_body = ast.Block(statements=new_stmts, span=decl.body.span)
    return ast.FunctionDecl(
        modifiers=decl.modifiers,
        return_type=decl.return_type,
        name=decl.name,
        type_params=decl.type_params,
        params=decl.params,
        body=new_body,
        is_operator=decl.is_operator,
        is_implicit_conversion=decl.is_implicit_conversion,
        is_intrinsic=decl.is_intrinsic,
        is_async=False,
        span=decl.span,
    )


def _lower_stmt(stmt: ast.Stmt) -> ast.Stmt:
    """Recursively rewrite a statement, lowering AwaitExpr inside it."""
    if isinstance(stmt, ast.ReturnStmt):
        if stmt.value is None:
            return stmt
        new_value = _lower_expr(stmt.value)
        # Wrap the return value in Promise.resolve(...) unless it's
        # already a Promise.* call (Promise.resolve / Promise.reject /
        # a recursive async function call returning Promise<T>).
        if not _is_already_promise(new_value):
            new_value = _wrap_in_promise_resolve(new_value, stmt.span)
        return ast.ReturnStmt(value=new_value, span=stmt.span)
    if isinstance(stmt, ast.VarDecl):
        if stmt.initializer is None:
            return stmt
        new_init = _lower_expr(stmt.initializer)
        return ast.VarDecl(
            is_const=stmt.is_const,
            is_var_inferred=stmt.is_var_inferred,
            type_ref=stmt.type_ref,
            name=stmt.name,
            initializer=new_init,
            is_role=stmt.is_role,
            is_var_colon=stmt.is_var_colon,
            array_size=stmt.array_size,
            is_slot=stmt.is_slot,
            span=stmt.span,
        )
    if isinstance(stmt, ast.ExprStmt):
        return ast.ExprStmt(expr=_lower_expr(stmt.expr), span=stmt.span)
    # Anything else (slot decls, loop calls, etc.) — pass through. The
    # codegen rejection still fires if it contains an unhandled await.
    return stmt


def _lower_expr(expr: ast.Expr) -> ast.Expr:
    """Recursively rewrite an expression, replacing AwaitExpr with
    Promise.value(...) calls."""
    if isinstance(expr, ast.AwaitExpr):
        # `await x` → `Promise.value(x)`. The inner x is also walked,
        # in case there are nested awaits (await await x — uncommon but
        # legal).
        inner = _lower_expr(expr.operand)
        return _wrap_in_promise_value(inner, expr.span)
    if isinstance(expr, ast.Call):
        return ast.Call(
            callee=_lower_expr(expr.callee),
            type_args=expr.type_args,
            args=[_lower_expr(a) for a in expr.args],
            span=expr.span,
        )
    if isinstance(expr, ast.BinaryOp):
        return ast.BinaryOp(
            op=expr.op,
            left=_lower_expr(expr.left),
            right=_lower_expr(expr.right),
            span=expr.span,
        )
    if isinstance(expr, ast.UnaryOp):
        return ast.UnaryOp(
            op=expr.op,
            operand=_lower_expr(expr.operand),
            span=expr.span,
        )
    if isinstance(expr, ast.MemberAccess):
        return ast.MemberAccess(
            obj=_lower_expr(expr.obj),
            member=expr.member,
            span=expr.span,
        )
    if isinstance(expr, ast.Subscript):
        return ast.Subscript(
            target=_lower_expr(expr.target),
            index=_lower_expr(expr.index),
            span=expr.span,
        )
    # Leaf nodes — Identifier, literals, etc. — pass through unchanged.
    return expr


def _is_already_promise(expr: ast.Expr) -> bool:
    """True iff `expr` is a Promise.* call (resolve / reject / value).

    Used to skip the outer Promise.resolve wrap when the return
    expression already produces a Promise<T> — `return await x;`
    after lowering becomes `return Promise.value(x);` and we don't
    want to re-wrap that into `Promise.resolve(Promise.value(x))`.
    """
    if not isinstance(expr, ast.Call):
        return False
    callee = expr.callee
    if not isinstance(callee, ast.MemberAccess):
        return False
    if not isinstance(callee.obj, ast.Identifier):
        return False
    if callee.obj.name != "Promise":
        return False
    return callee.member in (
        "resolve", "reject", "value", "reason", "await_value",
    )


def _wrap_in_promise_resolve(value: ast.Expr, span) -> ast.Expr:
    callee = ast.MemberAccess(
        obj=ast.Identifier(name="Promise", span=span),
        member="resolve",
        span=span,
    )
    return ast.Call(callee=callee, type_args=[], args=[value], span=span)


def _wrap_in_promise_value(promise: ast.Expr, span) -> ast.Expr:
    """Emit Promise.await_value(p) — the loop-bodied await intrinsic.

    The substrate-equivalent shape is a while_loop gating on
    Promise.isPending; the runtime currently implements it as a 100-
    iteration soft-halt loop in Python (no progress without external
    I/O). For an already-resolved promise, exits in 0 iterations and
    returns the value — same effect as Promise.value. When Yantra-
    side I/O wires up, the producer side flips isPending and the
    loop iterates until arrival.
    """
    callee = ast.MemberAccess(
        obj=ast.Identifier(name="Promise", span=span),
        member="await_value",
        span=span,
    )
    return ast.Call(callee=callee, type_args=[], args=[promise], span=span)
