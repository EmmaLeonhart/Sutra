"""Stdlib function inliner — step 2 of the function-expansion pipeline.

Rewrites every `Call(Identifier(name), args)` in a module's AST, for
each name present in the stdlib symbol table whose function body is
a single `return <expr>;` statement, by substituting the arguments
into the parameter slots and replacing the call node with the
substituted expression.

### What this covers today

Functions with a single-return-expr body:

  - logical_not(v)    → `0 - v`
  - logical_and(a, b) → `(a + b + a*b - a*a - b*b + a*a*b*b) * 0.5`
  - logical_or(a, b)  → `(a + b - a*b + a*a + b*b - a*a*b*b) * 0.5`
  - neq(a, b)         → `!(a == b)`
  - lt(a, b)          → `b > a`
  - ge(a, b)          → `a > b`
  - le(a, b)          → `a < b`

A user call like `logical_and(p, q)` becomes the polynomial form
inline; the compiler then sees `(p + q + p*q - p*p - q*q + p*p*q*q)
* 0.5` and can fold arithmetic, re-bundle, and emit tensor ops
directly — no call into the runtime's `_VSA.logical_and` method.

### What this doesn't cover (yet)

  - Statement-bodied functions (today: `defuzzy` with its ten-iter
    loop). Inlining a body that contains statements into an
    expression position needs statement-level hoisting — a call
    site has to become a preceding statement block plus a temp
    variable in the expression slot. That's the next extension
    (call it step 2.5) and the prerequisite for step 3's
    loop-unroll propagation.

  - Intrinsic calls. The stubs in stdlib (eq, gt, make_real,
    complex_mul, bind, bundle, ...) aren't FunctionDecls today —
    they live as commented pseudo-Sutra. When the `@intrinsic`
    mechanism lands (step 5), the inliner will be extended to
    resolve intrinsic calls too, but for now those calls are left
    untouched and continue to hit the hardcoded runtime methods.

### Pipeline position

Runs before `simplify_module` so that the arithmetic constant
folding and zero-absorption rewrites in simplify can fold the
inlined polynomial bodies. Called from `translate_module` in
`codegen.py` and `codegen_pytorch.py` via `inline_stdlib_calls`.
"""

from __future__ import annotations

import copy
from typing import Dict, Optional

from . import ast_nodes as ast
from .stdlib_loader import load_stdlib


_STDLIB_CACHE: Optional[Dict[str, ast.FunctionDecl]] = None


def _stdlib_table() -> Dict[str, ast.FunctionDecl]:
    """Load the stdlib once and cache for this process. Re-loading on
    every module is wasteful; the stdlib source doesn't change during
    a compiler session."""
    global _STDLIB_CACHE
    if _STDLIB_CACHE is None:
        _STDLIB_CACHE = load_stdlib()
    return _STDLIB_CACHE


def inline_stdlib_calls(
    module: ast.Module,
    stdlib_table: Optional[Dict[str, ast.FunctionDecl]] = None,
) -> ast.Module:
    """Inline every stdlib call whose target has a single-return-expr
    body. Mutates `module` in place and returns it.

    Pass `stdlib_table` explicitly to test against a synthetic stdlib;
    otherwise the real `sutra_compiler/stdlib/` is loaded and cached.
    """
    table = stdlib_table if stdlib_table is not None else _stdlib_table()
    inlineable = {
        name: decl
        for name, decl in table.items()
        if _is_single_return_expr(decl)
    }
    for item in module.items:
        _rewrite_top_level(item, inlineable)
    return module


def _is_single_return_expr(decl: ast.FunctionDecl) -> bool:
    """True iff the function body is exactly one `return <expr>;`
    statement with a non-None value. These are the functions step 2
    can inline today."""
    stmts = decl.body.statements
    if len(stmts) != 1:
        return False
    stmt = stmts[0]
    return isinstance(stmt, ast.ReturnStmt) and stmt.value is not None


# ---------------------------------------------------------------------------
# Top-level and statement walk — finds expressions to rewrite
# ---------------------------------------------------------------------------


def _rewrite_top_level(item, table) -> None:
    if isinstance(item, (ast.FunctionDecl, ast.MethodDecl)):
        _rewrite_block(item.body, table)
    elif isinstance(item, ast.VarDecl):
        if item.initializer is not None:
            item.initializer = _rewrite_expr(item.initializer, table)
    elif isinstance(item, ast.Stmt):
        _rewrite_stmt(item, table)


def _rewrite_block(block: ast.Block, table) -> None:
    for stmt in block.statements:
        _rewrite_stmt(stmt, table)


def _rewrite_stmt(stmt, table) -> None:
    if isinstance(stmt, ast.VarDecl):
        if stmt.initializer is not None:
            stmt.initializer = _rewrite_expr(stmt.initializer, table)
    elif isinstance(stmt, ast.ReturnStmt):
        if stmt.value is not None:
            stmt.value = _rewrite_expr(stmt.value, table)
    elif isinstance(stmt, ast.ExprStmt):
        stmt.expr = _rewrite_expr(stmt.expr, table)
    elif isinstance(stmt, ast.Assignment):
        stmt.target = _rewrite_expr(stmt.target, table)
        stmt.value = _rewrite_expr(stmt.value, table)
    elif isinstance(stmt, ast.IfStmt):
        stmt.condition = _rewrite_expr(stmt.condition, table)
        _rewrite_block(stmt.then_branch, table)
        if stmt.else_branch is not None:
            if isinstance(stmt.else_branch, ast.IfStmt):
                _rewrite_stmt(stmt.else_branch, table)
            else:
                _rewrite_block(stmt.else_branch, table)
    elif isinstance(stmt, ast.WhileStmt):
        stmt.condition = _rewrite_expr(stmt.condition, table)
        _rewrite_block(stmt.body, table)
    elif isinstance(stmt, ast.DoWhileStmt):
        _rewrite_block(stmt.body, table)
        stmt.condition = _rewrite_expr(stmt.condition, table)
    elif isinstance(stmt, ast.ForStmt):
        if stmt.init is not None:
            _rewrite_stmt(stmt.init, table)
        if stmt.condition is not None:
            stmt.condition = _rewrite_expr(stmt.condition, table)
        if stmt.step is not None:
            _rewrite_stmt(stmt.step, table)
        _rewrite_block(stmt.body, table)
    elif isinstance(stmt, ast.ForeachStmt):
        stmt.iterable = _rewrite_expr(stmt.iterable, table)
        _rewrite_block(stmt.body, table)
    elif isinstance(stmt, ast.LoopStmt):
        if stmt.count is not None:
            stmt.count = _rewrite_expr(stmt.count, table)
        if stmt.condition is not None:
            stmt.condition = _rewrite_expr(stmt.condition, table)
        _rewrite_block(stmt.body, table)
    elif isinstance(stmt, ast.TryStmt):
        _rewrite_block(stmt.try_block, table)
        for clause in stmt.catches:
            _rewrite_block(clause.body, table)
    elif isinstance(stmt, ast.Block):
        _rewrite_block(stmt, table)
    # BreakStmt / ContinueStmt carry no expressions.


# ---------------------------------------------------------------------------
# Expression rewrite — post-order, inlines Call nodes at the bottom
# ---------------------------------------------------------------------------


def _rewrite_expr(expr, table):
    """Post-order: rewrite children first, then consider the node
    itself for inlining. Returns the (possibly replaced) expression."""
    if expr is None:
        return None

    if isinstance(expr, ast.Call):
        expr.callee = _rewrite_expr(expr.callee, table)
        expr.args = [_rewrite_expr(a, table) for a in expr.args]
        if (isinstance(expr.callee, ast.Identifier)
                and expr.callee.name in table):
            return _do_inline(expr, table[expr.callee.name])
        return expr

    if isinstance(expr, ast.BinaryOp):
        expr.left = _rewrite_expr(expr.left, table)
        expr.right = _rewrite_expr(expr.right, table)
        return expr
    if isinstance(expr, ast.UnaryOp):
        expr.operand = _rewrite_expr(expr.operand, table)
        return expr
    if isinstance(expr, ast.PostfixOp):
        expr.operand = _rewrite_expr(expr.operand, table)
        return expr
    if isinstance(expr, ast.Parenthesized):
        expr.inner = _rewrite_expr(expr.inner, table)
        return expr
    if isinstance(expr, ast.Subscript):
        expr.target = _rewrite_expr(expr.target, table)
        expr.index = _rewrite_expr(expr.index, table)
        return expr
    if isinstance(expr, ast.MemberAccess):
        expr.obj = _rewrite_expr(expr.obj, table)
        return expr
    if isinstance(expr, ast.Assignment):
        expr.target = _rewrite_expr(expr.target, table)
        expr.value = _rewrite_expr(expr.value, table)
        return expr
    if isinstance(expr, ast.CastExpr):
        expr.expr = _rewrite_expr(expr.expr, table)
        return expr
    if isinstance(expr, ast.UnsafeCastExpr):
        expr.expr = _rewrite_expr(expr.expr, table)
        return expr
    if isinstance(expr, ast.UnsafeOverrideExpr):
        expr.expr = _rewrite_expr(expr.expr, table)
        return expr
    if isinstance(expr, ast.DefuzzyExpr):
        expr.expr = _rewrite_expr(expr.expr, table)
        return expr
    if isinstance(expr, ast.EmbedExpr):
        expr.expr = _rewrite_expr(expr.expr, table)
        return expr
    if isinstance(expr, ast.ArrayLiteral):
        expr.elements = [_rewrite_expr(e, table) for e in expr.elements]
        return expr
    if isinstance(expr, ast.MapLiteral):
        expr.keys = [_rewrite_expr(k, table) for k in expr.keys]
        expr.values = [_rewrite_expr(v, table) for v in expr.values]
        return expr
    if isinstance(expr, ast.InterpolatedString):
        expr.parts = [
            part if isinstance(part, str) else _rewrite_expr(part, table)
            for part in expr.parts
        ]
        return expr

    # Leaves: Identifier, IntLiteral, FloatLiteral, StringLiteral,
    # CharLiteral, BoolLiteral, UnknownLiteral, ComplexLiteral,
    # ImaginaryLiteral, TypeRef, etc. Return unchanged.
    return expr


# ---------------------------------------------------------------------------
# The actual inline: param-arg substitution into a cloned body
# ---------------------------------------------------------------------------


def _do_inline(call: ast.Call, decl: ast.FunctionDecl):
    """Return the inlined expression for `call`, or the original call
    unchanged if arities disagree (let the validator flag it)."""
    if len(call.args) != len(decl.params):
        return call

    # Deep-copy the return expression so we don't alias the stdlib
    # AST across call sites.
    return_stmt: ast.ReturnStmt = decl.body.statements[0]
    body_expr = copy.deepcopy(return_stmt.value)

    subst = {
        param.name: arg
        for param, arg in zip(decl.params, call.args)
    }
    return _substitute_params(body_expr, subst)


def _substitute_params(expr, subst: Dict[str, object]):
    """Replace `Identifier(name)` with `copy.deepcopy(subst[name])`
    wherever `name` is a parameter. Each occurrence gets its own copy
    so downstream mutation doesn't create AST aliasing across the
    different use-sites."""
    if expr is None:
        return None

    if isinstance(expr, ast.Identifier):
        if expr.name in subst:
            return copy.deepcopy(subst[expr.name])
        return expr

    if isinstance(expr, ast.BinaryOp):
        expr.left = _substitute_params(expr.left, subst)
        expr.right = _substitute_params(expr.right, subst)
        return expr
    if isinstance(expr, ast.UnaryOp):
        expr.operand = _substitute_params(expr.operand, subst)
        return expr
    if isinstance(expr, ast.PostfixOp):
        expr.operand = _substitute_params(expr.operand, subst)
        return expr
    if isinstance(expr, ast.Parenthesized):
        expr.inner = _substitute_params(expr.inner, subst)
        return expr
    if isinstance(expr, ast.Call):
        expr.callee = _substitute_params(expr.callee, subst)
        expr.args = [_substitute_params(a, subst) for a in expr.args]
        return expr
    if isinstance(expr, ast.Subscript):
        expr.target = _substitute_params(expr.target, subst)
        expr.index = _substitute_params(expr.index, subst)
        return expr
    if isinstance(expr, ast.MemberAccess):
        expr.obj = _substitute_params(expr.obj, subst)
        return expr
    if isinstance(expr, ast.CastExpr):
        expr.expr = _substitute_params(expr.expr, subst)
        return expr
    if isinstance(expr, ast.UnsafeCastExpr):
        expr.expr = _substitute_params(expr.expr, subst)
        return expr
    if isinstance(expr, ast.UnsafeOverrideExpr):
        expr.expr = _substitute_params(expr.expr, subst)
        return expr
    if isinstance(expr, ast.DefuzzyExpr):
        expr.expr = _substitute_params(expr.expr, subst)
        return expr
    if isinstance(expr, ast.EmbedExpr):
        expr.expr = _substitute_params(expr.expr, subst)
        return expr
    if isinstance(expr, ast.ArrayLiteral):
        expr.elements = [_substitute_params(e, subst) for e in expr.elements]
        return expr
    if isinstance(expr, ast.MapLiteral):
        expr.keys = [_substitute_params(k, subst) for k in expr.keys]
        expr.values = [_substitute_params(v, subst) for v in expr.values]
        return expr

    # Literals and everything else: no substitution.
    return expr
