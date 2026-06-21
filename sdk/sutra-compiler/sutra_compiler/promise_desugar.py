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


class _AwaitHoister:
    """Per-function state for the await → propagate lowering.

    Walks a straight-line statement list, hoisting each `await x` into a
    fresh temp Promise VarDecl (`Promise _await_pN = x;`) emitted before
    the statement that contained the await, and replacing the await
    in-place with `Promise.await_value(_await_pN)`. The ordered list of
    hoisted temp names is then folded into every `return` so that any
    awaited promise which rejected propagates its rejection through the
    surrounding promise (promises.md §"Rejection propagation").
    """

    def __init__(self) -> None:
        self._counter = 0
        # Temps awaited so far in the current straight-line scope, in
        # source order. Returns fold propagate(...) over all of them.
        self._awaited_temps: list[str] = []

    def _fresh(self) -> str:
        name = f"_await_p{self._counter}"
        self._counter += 1
        return name

    def lower_block(self, block: ast.Block) -> ast.Block:
        out: list[ast.Stmt] = []
        for stmt in block.statements:
            out.extend(self._lower_stmt(stmt))
        return ast.Block(statements=out, span=block.span)

    def _lower_stmt(self, stmt: ast.Stmt) -> list[ast.Stmt]:
        """Lower one statement, returning the (possibly multiple)
        statements that replace it — hoisted await-temp decls plus the
        rewritten statement."""
        if isinstance(stmt, ast.ReturnStmt):
            if stmt.value is None:
                return [stmt]
            hoists, new_value = self._extract_awaits(stmt.value)
            if not _is_already_promise(new_value):
                new_value = _wrap_in_promise_resolve(new_value, stmt.span)
            # Fold rejection-propagation over every awaited temp in scope
            # (outermost wrap = first-awaited temp): if any awaited
            # promise rejected, the surrounding promise rejects.
            for temp in reversed(self._awaited_temps):
                new_value = _wrap_in_propagate(temp, new_value, stmt.span)
            return [*hoists, ast.ReturnStmt(value=new_value, span=stmt.span)]
        if isinstance(stmt, ast.VarDecl):
            if stmt.initializer is None:
                return [stmt]
            hoists, new_init = self._extract_awaits(stmt.initializer)
            new_decl = ast.VarDecl(
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
            return [*hoists, new_decl]
        if isinstance(stmt, ast.ExprStmt):
            hoists, new_expr = self._extract_awaits(stmt.expr)
            return [*hoists, ast.ExprStmt(expr=new_expr, span=stmt.span)]
        # Anything else (control-flow bodies, slot decls, loop calls) —
        # pass through. An await surviving inside such a statement still
        # falls through to the codegen rejection, which points at the spec.
        return [stmt]

    def _extract_awaits(self, expr: ast.Expr) -> tuple[list[ast.Stmt], ast.Expr]:
        """Walk `expr`, hoisting every `await x` into a fresh temp decl
        and replacing it with `Promise.await_value(temp)`. Returns the
        list of hoist decls (in source order) and the rewritten expr."""
        hoists: list[ast.Stmt] = []

        def walk(e: ast.Expr) -> ast.Expr:
            if isinstance(e, ast.AwaitExpr):
                # Recurse first (await await x — uncommon but legal), so
                # the inner promise's own awaits hoist ahead of this one.
                inner = walk(e.operand)
                temp = self._fresh()
                # Promise _await_pN = <inner promise expr>;
                hoists.append(ast.VarDecl(
                    is_const=False,
                    is_var_inferred=False,
                    type_ref=ast.TypeRef(name="Promise", type_args=[],
                                         span=e.span),
                    name=temp,
                    initializer=inner,
                    span=e.span,
                ))
                self._awaited_temps.append(temp)
                # await x → Promise.await_value(_await_pN)
                return _wrap_in_promise_value(
                    ast.Identifier(name=temp, span=e.span), e.span)
            if isinstance(e, ast.Call):
                return ast.Call(
                    callee=walk(e.callee),
                    type_args=e.type_args,
                    args=[walk(a) for a in e.args],
                    span=e.span,
                )
            if isinstance(e, ast.BinaryOp):
                return ast.BinaryOp(
                    op=e.op, left=walk(e.left), right=walk(e.right),
                    span=e.span)
            if isinstance(e, ast.UnaryOp):
                return ast.UnaryOp(op=e.op, operand=walk(e.operand),
                                   span=e.span)
            if isinstance(e, ast.MemberAccess):
                return ast.MemberAccess(obj=walk(e.obj), member=e.member,
                                        span=e.span)
            if isinstance(e, ast.Subscript):
                return ast.Subscript(target=walk(e.target),
                                     index=walk(e.index), span=e.span)
            return e

        new_expr = walk(expr)
        return hoists, new_expr


def _desugar_async_function(decl: ast.FunctionDecl) -> ast.FunctionDecl:
    """Lower an async function's body into a non-async equivalent.

    Walks every statement, hoisting `await x` into a temp Promise and
    replacing it with `Promise.await_value(temp)`, wrapping bare return
    values with `Promise.resolve(...)`, and folding
    `Promise.propagate(temp, ...)` over every awaited promise so a
    rejected await propagates its rejection (promises.md §"Rejection
    propagation").
    """
    new_body = _AwaitHoister().lower_block(decl.body)
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


def _is_already_promise(expr: ast.Expr) -> bool:
    """True iff `expr` already produces a Promise<T> and must not be
    re-wrapped in Promise.resolve(...).

    Only `Promise.resolve(...)` / `Promise.reject(...)` (and the
    `propagate` blend, which returns a Promise) build promise-shaped
    values. `Promise.value/.reason/.await_value` return the UNWRAPPED
    `T` (channels zeroed), so `return await x;` — which lowers to
    `return Promise.await_value(temp);` — DOES need the outer
    `Promise.resolve` so the async function honours its `Promise<T>`
    return contract.
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
    return callee.member in ("resolve", "reject", "propagate")


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


def _wrap_in_propagate(awaited_temp: str, result: ast.Expr, span) -> ast.Expr:
    """Emit Promise.propagate(awaited_temp, result).

    If `awaited_temp` (the promise that was `await`ed) rejected, the
    surrounding promise rejects with the same reason and `result` is
    discarded; otherwise `result` passes through. Substrate-pure blend
    in the runtime — see promises.md §"Rejection propagation".
    """
    callee = ast.MemberAccess(
        obj=ast.Identifier(name="Promise", span=span),
        member="propagate",
        span=span,
    )
    return ast.Call(
        callee=callee,
        type_args=[],
        args=[ast.Identifier(name=awaited_temp, span=span), result],
        span=span,
    )
