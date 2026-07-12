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
    """Rewrite operators to stdlib calls, then inline every stdlib
    call whose target has a single-return-expr body. Mutates
    `module` in place and returns it.

    Pass `stdlib_table` explicitly to test against a synthetic stdlib;
    otherwise the real `sutra_compiler/stdlib/` is loaded and cached.
    """
    table = stdlib_table if stdlib_table is not None else _stdlib_table()
    inlineable = {
        name: decl
        for name, decl in table.items()
        if _is_single_return_expr(decl)
    }
    # Step 2.6 — lower operators to stdlib calls for the ones with
    # stdlib bodies. After this pass, `a && b` is a Call to
    # logical_and, `!v` is a Call to logical_not, etc. — and the
    # inliner below expands them uniformly with direct user calls.
    _lower_operators_to_stdlib_calls(module, inlineable)
    # Step 2 — inline stdlib calls.
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
    elif isinstance(item, ast.LoopFunctionDecl):
        # Walk the loop function's condition + body so stdlib calls
        # inside (like `<` → `lt(a,b)` → `b > a`) get inlined.
        item.condition = _rewrite_expr(item.condition, table)
        _rewrite_block(item.body, table)
    elif isinstance(item, ast.ClassDecl):
        for m in item.methods:
            _rewrite_block(m.body, table)
        for lf in item.loop_functions:
            lf.condition = _rewrite_expr(lf.condition, table)
            _rewrite_block(lf.body, table)
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
    elif isinstance(stmt, ast.PassStmt):
        # Each pass value is either an Expr or a ReplaceMarker.
        # Rewrite expressions in place; ReplaceMarker is a leaf.
        for i, val in enumerate(stmt.values):
            if not isinstance(val, ast.ReplaceMarker):
                stmt.values[i] = _rewrite_expr(val, table)
    elif isinstance(stmt, ast.LoopCallStmt):
        stmt.condition_arg = _rewrite_expr(stmt.condition_arg, table)
    elif isinstance(stmt, ast.TryStmt):
        _rewrite_block(stmt.try_body, table)
        _rewrite_block(stmt.catch_body, table)
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
            return _do_inline(expr, table[expr.callee.name], table)
        # Namespaced stdlib call `Math.exp(z)` — callee is a
        # MemberAccess, not a bare Identifier. The loader registers
        # class static methods under both `exp` and `Math.exp`;
        # resolve the qualified name so a class-bodied stdlib method
        # body IS the executable beta-reduction (the language's whole
        # premise) rather than a call into a `Math` object that does
        # not exist in the emitted module. Single-return bodies
        # inline; intrinsic leaves (no body) are absent from the
        # inlineable table and pass through to the codegen `_VSA.*`
        # dispatch unchanged.
        if (isinstance(expr.callee, ast.MemberAccess)
                and isinstance(expr.callee.obj, ast.Identifier)):
            qualified = f"{expr.callee.obj.name}.{expr.callee.member}"
            if qualified in table:
                return _do_inline(expr, table[qualified], table)
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
    if isinstance(expr, ast.LoopCallExpr):
        # The loop function itself is not inlined (it lowers to its own
        # driver), but the cond + state arg expressions may reference
        # inlineable calls.
        expr.condition_arg = _rewrite_expr(expr.condition_arg, table)
        expr.state_args = [_rewrite_expr(a, table) for a in expr.state_args]
        return expr

    # Leaves: Identifier, IntLiteral, FloatLiteral, StringLiteral,
    # CharLiteral, BoolLiteral, UnknownLiteral, ComplexLiteral,
    # ImaginaryLiteral, TypeRef, etc. Return unchanged.
    return expr


# ---------------------------------------------------------------------------
# The actual inline: param-arg substitution into a cloned body
# ---------------------------------------------------------------------------


# Stdlib functions whose body is a Lagrange/Zadeh polynomial over the
# TRUTH axis — `a && b`, `a || b`, `!v`, and the derived nand/xor/xnor.
# Their inlined arithmetic (`+ - * /` over boolean operands) must be
# emitted ELEMENT-WISE on the truth axis, never routed to the number-axis
# `num_*` runtime ops — the operands carry their value on AXIS_TRUTH, so a
# real-axis `num_*` reads them as ~0 and destroys the truth value. A
# logical operator's result is always a truth-axis vector REGARDLESS of the
# operands' declared type (e.g. `int a, int b`), which is exactly the case
# `_is_vectory_expr`'s static type check misses. We mark every node of the
# inlined polynomial body with `_logical_truth = True` so codegen can force
# the element-wise route. See codegen_base.py `_is_vectory_expr` /
# arithmetic-routing.
_LOGICAL_TRUTH_FORMS = frozenset({
    "logical_and",
    "logical_or",
    "logical_not",
    "logical_nand",
    "logical_xor",
    "logical_xnor",
})


def _mark_logical_truth(expr) -> None:
    """Recursively set `_logical_truth = True` on `expr` and every
    sub-expression node, so codegen treats the inlined logical-operator
    polynomial as a truth-axis vector (element-wise arithmetic) rather than
    routing its `+ - * /` to the number axis."""
    if expr is None or not isinstance(expr, ast.Node):
        return
    try:
        expr._logical_truth = True
    except (AttributeError, TypeError):
        # __slots__ without the attr, or otherwise unsettable — skip; the
        # marker is best-effort over the polynomial's arithmetic nodes.
        pass
    for child in _iter_child_exprs(expr):
        _mark_logical_truth(child)


def _iter_child_exprs(expr):
    """Yield the child-expression nodes of `expr` for marker recursion.
    Mirrors the node shapes handled by `_substitute_params`."""
    if isinstance(expr, ast.BinaryOp):
        yield expr.left
        yield expr.right
    elif isinstance(expr, ast.UnaryOp):
        yield expr.operand
    elif isinstance(expr, ast.PostfixOp):
        yield expr.operand
    elif isinstance(expr, ast.Parenthesized):
        yield expr.inner
    elif isinstance(expr, ast.Call):
        yield expr.callee
        for a in expr.args:
            yield a
    elif isinstance(expr, ast.Subscript):
        yield expr.target
        yield expr.index
    elif isinstance(expr, ast.MemberAccess):
        yield expr.obj
    elif isinstance(expr, ast.Assignment):
        yield expr.target
        yield expr.value
    elif isinstance(expr, (ast.CastExpr, ast.UnsafeCastExpr,
                           ast.UnsafeOverrideExpr, ast.DefuzzyExpr,
                           ast.EmbedExpr)):
        yield expr.expr
    elif isinstance(expr, ast.ArrayLiteral):
        for e in expr.elements:
            yield e
    elif isinstance(expr, ast.MapLiteral):
        for k in expr.keys:
            yield k
        for v in expr.values:
            yield v
    elif isinstance(expr, ast.InterpolatedString):
        for part in expr.parts:
            if not isinstance(part, str):
                yield part


def _do_inline(call: ast.Call, decl: ast.FunctionDecl, table=None):
    """Return the inlined expression for `call`, or the original call
    unchanged if arities disagree (let the validator flag it).

    After substituting params into the body we re-run the rewriter on
    the result, so inlined bodies that themselves contain stdlib
    calls get fully expanded in one pass. Today's stdlib has no
    recursion, so this terminates trivially; a future `@intrinsic`
    form that's self-referential would need a depth guard."""
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
    substituted = _substitute_params(body_expr, subst)
    # Recurse: the substituted body may contain operators or stdlib
    # calls that still need lowering/inlining. e.g. neq's body is
    # `!(a == b)` — the `!` is a UnaryOp that needs operator-lowering
    # into a logical_not Call, which itself then inlines. A single
    # pre-order pass over user code wouldn't see this `!` because it
    # only appeared after inlining.
    if table is not None:
        substituted = _lower_ops_expr(substituted, table)
        substituted = _rewrite_expr(substituted, table)
    # Provenance: if this call was a logical operator, the produced body is
    # a truth-axis polynomial. Mark it so codegen keeps the arithmetic
    # element-wise (truth axis) and never routes to the number axis, even
    # when the operands are int-typed. Marking AFTER the recursive
    # lower/rewrite above so the whole final sub-AST is covered.
    callee = call.callee
    callee_name = callee.name if isinstance(callee, ast.Identifier) else None
    if callee_name in _LOGICAL_TRUTH_FORMS:
        _mark_logical_truth(substituted)
    return substituted


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


# ---------------------------------------------------------------------------
# Step 2.6 — operator lowering to stdlib calls
# ---------------------------------------------------------------------------
#
# Rewrite `!v`, `a && b`, `a || b`, `a != b`, `a < b`, `a <= b`, `a >= b`
# into explicit Call nodes targeting their stdlib counterparts. After this
# runs, the inliner pass below sees a uniform Call shape whether the user
# wrote `logical_and(a, b)` or `a && b`. The operators that don't have a
# stdlib body today (`==`, `>`) are left alone — they continue to compile
# through the hardcoded runtime methods until their stdlib forms land
# (blocked on eq/gt intrinsics).
#
# Operators that aren't part of this set — `+`, `-`, `*`, `/`, etc. — are
# not candidates for stdlib lowering. They're not "logic ops with a
# Sutra-source definition;" they're primitive tensor arithmetic the
# codegen knows how to emit directly.

_BINARY_OP_TO_STDLIB = {
    "&&":   "logical_and",
    "||":   "logical_or",
    "nand": "logical_nand",
    "xor":  "logical_xor",
    "xnor": "logical_xnor",
    "!=":   "neq",
    "<":    "lt",
    "<=":   "le",
    ">=":   "ge",
}
_UNARY_OP_TO_STDLIB = {
    "!": "logical_not",
}


def _lower_operators_to_stdlib_calls(
    module: ast.Module, inlineable: Dict[str, ast.FunctionDecl]
) -> None:
    """Walk the module and replace each operator node whose stdlib
    counterpart is present and inlineable with a Call to it. Filters
    by the inlineable set so operators without a stdlib body (or
    stdlib body that can't yet be inlined) stay as operators."""
    for item in module.items:
        _lower_ops_top_level(item, inlineable)


def _lower_loop_condition_ops(cond, kind, inlineable):
    """Operator-lower a loop's halt condition, KEEPING top-level `&&`/`||`
    connectives as raw operators for a while_loop/do_while.

    The general `&&`/`||` lowering inlines the Zadeh POLYNOMIAL, which is
    only correct on [0, 1] truth. A loop halt composes SIGNED comparison
    truth ([-1, 1], positive = true) and thresholds it at 0 — there `&&`/
    `||` are min/max, not the polynomial; fed signed truth the polynomial
    gives the wrong sign, so a compound `(a) && (b)` halt was honored only
    on its first conjunct (finding 2026-06-17-while-loop-halt-is-single-
    condition-only.md). Keeping the connectives un-lowered lets codegen's
    `_translate_loop_condition` emit `_VSA.truth_and`/`truth_or` (min/max).
    The connectives' OPERANDS are still lowered normally (so `i < 5` →
    `5 > i`, `i != 3` → `neq(...)`); only the `&&`/`||` nodes survive.
    Other loop kinds (iterative_loop / foreach_loop) lower as before."""
    if kind not in ("while_loop", "do_while"):
        return _lower_ops_expr(cond, inlineable)
    return _lower_ops_keep_logic(cond, inlineable)


def _lower_ops_keep_logic(expr, inlineable):
    """Lower operators in `expr` but leave top-level `&&`/`||` connectives
    (and parens around them) as raw operators, recursing through them so
    nested connectives also survive; everything else lowers normally."""
    if isinstance(expr, ast.Parenthesized):
        expr.inner = _lower_ops_keep_logic(expr.inner, inlineable)
        return expr
    if isinstance(expr, ast.BinaryOp) and expr.op in ("&&", "||"):
        expr.left = _lower_ops_keep_logic(expr.left, inlineable)
        expr.right = _lower_ops_keep_logic(expr.right, inlineable)
        return expr
    return _lower_ops_expr(expr, inlineable)


def _lower_ops_top_level(item, inlineable) -> None:
    if isinstance(item, (ast.FunctionDecl, ast.MethodDecl)):
        _lower_ops_block(item.body, inlineable)
    elif isinstance(item, ast.LoopFunctionDecl):
        item.condition = _lower_loop_condition_ops(
            item.condition, item.kind, inlineable
        )
        _lower_ops_block(item.body, inlineable)
    elif isinstance(item, ast.ClassDecl):
        for m in item.methods:
            _lower_ops_block(m.body, inlineable)
        for lf in item.loop_functions:
            lf.condition = _lower_loop_condition_ops(
                lf.condition, lf.kind, inlineable
            )
            _lower_ops_block(lf.body, inlineable)
    elif isinstance(item, ast.VarDecl):
        if item.initializer is not None:
            item.initializer = _lower_ops_expr(item.initializer, inlineable)
    elif isinstance(item, ast.Stmt):
        _lower_ops_stmt(item, inlineable)


def _lower_ops_block(block: ast.Block, inlineable) -> None:
    for stmt in block.statements:
        _lower_ops_stmt(stmt, inlineable)


def _lower_ops_stmt(stmt, inlineable) -> None:
    if isinstance(stmt, ast.VarDecl):
        if stmt.initializer is not None:
            stmt.initializer = _lower_ops_expr(stmt.initializer, inlineable)
    elif isinstance(stmt, ast.ReturnStmt):
        if stmt.value is not None:
            stmt.value = _lower_ops_expr(stmt.value, inlineable)
    elif isinstance(stmt, ast.ExprStmt):
        stmt.expr = _lower_ops_expr(stmt.expr, inlineable)
    elif isinstance(stmt, ast.Assignment):
        stmt.target = _lower_ops_expr(stmt.target, inlineable)
        stmt.value = _lower_ops_expr(stmt.value, inlineable)
    elif isinstance(stmt, ast.IfStmt):
        stmt.condition = _lower_ops_expr(stmt.condition, inlineable)
        _lower_ops_block(stmt.then_branch, inlineable)
        if stmt.else_branch is not None:
            if isinstance(stmt.else_branch, ast.IfStmt):
                _lower_ops_stmt(stmt.else_branch, inlineable)
            else:
                _lower_ops_block(stmt.else_branch, inlineable)
    elif isinstance(stmt, ast.WhileStmt):
        stmt.condition = _lower_ops_expr(stmt.condition, inlineable)
        _lower_ops_block(stmt.body, inlineable)
    elif isinstance(stmt, ast.DoWhileStmt):
        _lower_ops_block(stmt.body, inlineable)
        stmt.condition = _lower_ops_expr(stmt.condition, inlineable)
    elif isinstance(stmt, ast.ForStmt):
        if stmt.init is not None:
            _lower_ops_stmt(stmt.init, inlineable)
        if stmt.condition is not None:
            stmt.condition = _lower_ops_expr(stmt.condition, inlineable)
        if stmt.step is not None:
            _lower_ops_stmt(stmt.step, inlineable)
        _lower_ops_block(stmt.body, inlineable)
    elif isinstance(stmt, ast.ForeachStmt):
        stmt.iterable = _lower_ops_expr(stmt.iterable, inlineable)
        _lower_ops_block(stmt.body, inlineable)
    elif isinstance(stmt, ast.LoopStmt):
        if stmt.count is not None:
            stmt.count = _lower_ops_expr(stmt.count, inlineable)
        if stmt.condition is not None:
            stmt.condition = _lower_ops_expr(stmt.condition, inlineable)
        _lower_ops_block(stmt.body, inlineable)
    elif isinstance(stmt, ast.PassStmt):
        for i, val in enumerate(stmt.values):
            if not isinstance(val, ast.ReplaceMarker):
                stmt.values[i] = _lower_ops_expr(val, inlineable)
    elif isinstance(stmt, ast.LoopCallStmt):
        stmt.condition_arg = _lower_ops_expr(stmt.condition_arg, inlineable)
    elif isinstance(stmt, ast.TryStmt):
        _lower_ops_block(stmt.try_body, inlineable)
        _lower_ops_block(stmt.catch_body, inlineable)
    elif isinstance(stmt, ast.Block):
        _lower_ops_block(stmt, inlineable)


def _lower_ops_expr(expr, inlineable):
    if expr is None:
        return None

    # Recurse into children first (post-order).
    if isinstance(expr, ast.BinaryOp):
        expr.left = _lower_ops_expr(expr.left, inlineable)
        expr.right = _lower_ops_expr(expr.right, inlineable)
        stdlib_name = _BINARY_OP_TO_STDLIB.get(expr.op)
        if stdlib_name is not None and stdlib_name in inlineable:
            return ast.Call(
                callee=ast.Identifier(name=stdlib_name, span=expr.span),
                type_args=[],
                args=[expr.left, expr.right],
                span=expr.span,
            )
        return expr

    if isinstance(expr, ast.UnaryOp):
        expr.operand = _lower_ops_expr(expr.operand, inlineable)
        stdlib_name = _UNARY_OP_TO_STDLIB.get(expr.op)
        if stdlib_name is not None and stdlib_name in inlineable:
            return ast.Call(
                callee=ast.Identifier(name=stdlib_name, span=expr.span),
                type_args=[],
                args=[expr.operand],
                span=expr.span,
            )
        return expr

    # Structural recursion for every other expression shape.
    if isinstance(expr, ast.PostfixOp):
        expr.operand = _lower_ops_expr(expr.operand, inlineable)
        return expr
    if isinstance(expr, ast.Call):
        expr.callee = _lower_ops_expr(expr.callee, inlineable)
        expr.args = [_lower_ops_expr(a, inlineable) for a in expr.args]
        return expr
    if isinstance(expr, ast.Parenthesized):
        expr.inner = _lower_ops_expr(expr.inner, inlineable)
        return expr
    if isinstance(expr, ast.Subscript):
        expr.target = _lower_ops_expr(expr.target, inlineable)
        expr.index = _lower_ops_expr(expr.index, inlineable)
        return expr
    if isinstance(expr, ast.MemberAccess):
        expr.obj = _lower_ops_expr(expr.obj, inlineable)
        return expr
    if isinstance(expr, ast.Assignment):
        expr.target = _lower_ops_expr(expr.target, inlineable)
        expr.value = _lower_ops_expr(expr.value, inlineable)
        return expr
    if isinstance(expr, (ast.CastExpr, ast.UnsafeCastExpr,
                         ast.UnsafeOverrideExpr, ast.DefuzzyExpr,
                         ast.EmbedExpr)):
        expr.expr = _lower_ops_expr(expr.expr, inlineable)
        return expr
    if isinstance(expr, ast.ArrayLiteral):
        expr.elements = [_lower_ops_expr(e, inlineable) for e in expr.elements]
        return expr
    if isinstance(expr, ast.MapLiteral):
        expr.keys = [_lower_ops_expr(k, inlineable) for k in expr.keys]
        expr.values = [_lower_ops_expr(v, inlineable) for v in expr.values]
        return expr
    if isinstance(expr, ast.InterpolatedString):
        expr.parts = [
            part if isinstance(part, str) else _lower_ops_expr(part, inlineable)
            for part in expr.parts
        ]
        return expr
    if isinstance(expr, ast.LoopCallExpr):
        expr.condition_arg = _lower_ops_expr(expr.condition_arg, inlineable)
        expr.state_args = [
            _lower_ops_expr(a, inlineable) for a in expr.state_args
        ]
        return expr

    # Leaves (Identifier, literals, TypeRef) — no-op.
    return expr
