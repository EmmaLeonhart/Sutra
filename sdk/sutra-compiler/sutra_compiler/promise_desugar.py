"""Stage-1 promise desugar — `async function` + `await` → `Promise<T>`.

Per planning/sutra-spec/promises.md §"Lowering" Stage 1, this pass
rewrites async functions so they return explicit Promise<T> values
constructed via `Promise.resolve` / `Promise.reject` / `.then` chains.
The output is still Sutra source (no `async` or `await` keywords); a
later pass (Stage 2, queue.md item 1 phase 6) lowers each Promise into
a substrate `while_loop` declaration.

### What this covers today

Two simple shapes — the ones that don't require lambdas / first-class
function values to express:

  1. **Thin async wrapper:**
       async function Promise<T> f(...) { return await e; }
     →
       function Promise<T> f(...) { return e; }
     (When `await e` is the entire body, the surrounding promise
     resolves to whatever `e`'s promise resolves to. Pass-through.)

  2. **Pure-return async function:**
       async function Promise<T> f(...) { return e; }
     →
       function Promise<T> f(...) { return Promise.resolve(e); }
     (No await — every `return e` in an async function wraps the
     value in an already-fulfilled promise.)

### What this doesn't cover (yet)

  - Async functions with `await` followed by post-await code:
       async function f() { vector v = await x; return g(v); }
    Lowering needs lambda / first-class-function values to express
    the post-await code as a `.then(v -> g(v))` callback. Sutra's
    arrow functions today get hoisted to top-level functions
    (per the 2026-05-08 TS transpiler note), so until that lifts,
    this shape needs the desugar to also generate an explicit named
    continuation function. Tracked as a follow-on for phase 3.

  - `try { await ... } catch { ... }` lowering to `.then().catch()`.

  - Multiple sequential awaits / nested awaits.

Anything not covered falls through to the codegen's existing async-
rejection error, which points at planning/sutra-spec/promises.md.
"""

from __future__ import annotations

from . import ast_nodes as ast


def desugar_promises(module: ast.Module) -> ast.Module:
    """Walk the module, transform async function decls in place where
    the body matches one of the two simple shapes above. Mutates and
    returns the module."""
    for i, item in enumerate(module.items):
        if isinstance(item, ast.FunctionDecl) and item.is_async:
            transformed = _try_desugar_async_function(item)
            if transformed is not None:
                module.items[i] = transformed
    return module


def _try_desugar_async_function(
    decl: ast.FunctionDecl,
) -> ast.FunctionDecl | None:
    """Try to desugar an async function's body into a non-async form.

    Returns a new FunctionDecl with is_async=False on success, None if
    the body's shape isn't one of the supported patterns (caller
    leaves is_async=True so the codegen rejects with the spec pointer).
    """
    stmts = decl.body.statements
    # Case A: body is exactly one statement, a `return <expr>;`.
    if len(stmts) == 1 and isinstance(stmts[0], ast.ReturnStmt):
        ret = stmts[0]
        if ret.value is None:
            # `return;` in an async fn → `return Promise.resolve(<void>)`.
            # Skip — the no-value case isn't useful enough to special-case
            # and the caller can wrap if needed.
            return None
        if isinstance(ret.value, ast.AwaitExpr):
            # Shape 1 — `return await e;` becomes `return e;`.
            new_ret = ast.ReturnStmt(value=ret.value.operand, span=ret.span)
            new_body = ast.Block(statements=[new_ret], span=decl.body.span)
            return _clone_decl_non_async(decl, new_body)
        # Shape 2 — `return e;` (no await) becomes
        # `return Promise.resolve(e);`.
        if not _contains_await(ret.value):
            promise_resolve = ast.MemberAccess(
                obj=ast.Identifier(name="Promise", span=ret.span),
                member="resolve",
                span=ret.span,
            )
            wrapped = ast.Call(
                callee=promise_resolve,
                type_args=[],
                args=[ret.value],
                span=ret.span,
            )
            new_ret = ast.ReturnStmt(value=wrapped, span=ret.span)
            new_body = ast.Block(statements=[new_ret], span=decl.body.span)
            return _clone_decl_non_async(decl, new_body)
    # Anything else falls through; caller leaves is_async=True and the
    # codegen errors with the spec pointer.
    return None


def _contains_await(expr: ast.Expr) -> bool:
    """True iff `expr` (or any sub-expression) is an AwaitExpr.

    Used to skip the `Promise.resolve` wrap when the return value
    already contains an await — those shapes need full Stage-1
    lowering (callbacks + .then chains), not the trivial wrap.
    """
    if isinstance(expr, ast.AwaitExpr):
        return True
    for attr in ("operand", "left", "right", "callee", "obj", "target", "index"):
        sub = getattr(expr, attr, None)
        if isinstance(sub, ast.Expr) and _contains_await(sub):
            return True
    args = getattr(expr, "args", None)
    if isinstance(args, list):
        for a in args:
            if isinstance(a, ast.Expr) and _contains_await(a):
                return True
    return False


def _clone_decl_non_async(
    decl: ast.FunctionDecl, new_body: ast.Block,
) -> ast.FunctionDecl:
    """Return a copy of `decl` with `is_async=False` and a new body."""
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
