"""Compile-time pre-evaluation of bounded pure recursion (Phase 5.5 tier 3, step 3a).

Scoped in `planning/exploratory/2026-06-17-phase5.5-tier3-preeval-scoping.md`. For a call
`f(args)` to a pure function whose controlling arguments are compile-time literals and whose
recursion is provably bounded within `max_depth`, this evaluates `f` symbolically on the AST at
compile time and replaces the call with the resulting literal. Naive `fib(5)` thereby folds to `5`
at compile time instead of running on the substrate.

This is **host-side, PURE compile-time evaluation** of the integer/arithmetic subset of Sutra — the
same category as the arithmetic constant-folding already in `simplify.py`. It is NOT runtime
substrate execution: there is no running program to read from, so it does not touch the substrate
runtime or the no-host-readout rule. Referential transparency (Sutra functions are pure) is what
makes it always sound (per `planning/sutra-spec/recursion-execution-model.md`).

**OPT-IN.** This pass is NOT wired into the default compile pipeline — a caller invokes
`preeval_bounded_recursion(module, max_depth=...)` explicitly. (The *automatic* default policy —
"when NOT to pre-evaluate", which Emma flagged unsolved — is a separate downstream decision; see the
scoping doc step 3c.) The supported subset is deliberately conservative: any construct outside
{IntLiteral, FloatLiteral, Identifier(param), BinaryOp(+ - * and the six comparisons), IfStmt,
ReturnStmt, Call(known pure fn)} makes the evaluator abort that call site (leaving it for the runtime
path), so it never mis-folds.
"""
from __future__ import annotations

import dataclasses

from . import ast_nodes as ast


class _NotFoldable(Exception):
    """Raised when a call site cannot be safely evaluated at compile time."""


_NO_RETURN = object()   # sentinel: a block fell off the end without returning


def _walk(node, fn):
    """Visit `node` and every dataclass-AST descendant (all fields, list-valued included),
    so call collection cannot miss a reference (safety: missing a call would wrongly prune a
    live function)."""
    fn(node)
    if not dataclasses.is_dataclass(node):
        return
    for f in dataclasses.fields(node):
        ch = getattr(node, f.name, None)
        if isinstance(ch, (list, tuple)):
            for c in ch:
                if dataclasses.is_dataclass(c):
                    _walk(c, fn)
        elif dataclasses.is_dataclass(ch):
            _walk(ch, fn)


def _prune_dead_recursive(module):
    """Remove DIRECTLY-self-recursive functions that became unreferenced after folding.

    Pre-eval is now on by default (shallow), so pruning must be conservative — it is NOT
    general dead-code elimination. It removes ONLY a function that (a) directly calls itself
    (so pre-eval is what made it dead and its body typically uses constructs the V1 codegen
    lowers elsewhere, e.g. recursive if/else) AND (b) is not called from any OTHER item
    (self-calls don't count). Non-recursive helpers, operator/conversion functions, and any
    function still referenced elsewhere are NEVER pruned, so this can't surprise a program.
    (Mutually-recursive dead groups are left intact — a documented limitation.)"""
    def _self_recursive(fd):
        hit = [False]

        def v(n):
            if (type(n).__name__ == "Call" and type(n.callee).__name__ == "Identifier"
                    and n.callee.name == fd.name):
                hit[0] = True
        _walk(fd, v)
        return hit[0]

    # Names referenced from some OTHER item (a function's self-calls are excluded).
    ext_refs: set = set()
    for it in module.items:
        own = it.name if type(it).__name__ == "FunctionDecl" else None

        def visit(n, own=own):
            if (type(n).__name__ == "Call" and type(n.callee).__name__ == "Identifier"
                    and n.callee.name != own):
                ext_refs.add(n.callee.name)
        _walk(it, visit)

    module.items = [
        it for it in module.items
        if type(it).__name__ != "FunctionDecl"
        or it.name in ext_refs
        or not _self_recursive(it)
    ]
    return module


# Default recursion-depth cap for AUTOMATIC pre-evaluation (Emma 2026-06-17: "default
# max precalculated depth should not be zero but around 2-3"). A small default folds
# the cheap shallow cases automatically without binary-bloat risk; deeper recursion
# cleanly falls through to the runtime path unless the user opts into a higher cap
# (`--preeval` raises it, `--max-preeval-depth N` / atman.toml set it explicitly).
DEFAULT_MAX_PREEVAL_DEPTH = 3

# Cap used by the explicit `--preeval` "deep" opt-in. Kept within the host evaluator's
# own stack limit (CPython ~1000 frames, several per logical level) so compile-time
# evaluation cannot overflow (3b finding 2026-06-17).
DEEP_MAX_PREEVAL_DEPTH = 128


def preeval_bounded_recursion(module, max_depth: int = DEFAULT_MAX_PREEVAL_DEPTH,
                              prune: bool = True):
    """Fold compile-time-constant calls to bounded pure recursive functions into literals,
    in place, and return the module. With `prune=True`, also strip functions left unreachable
    from `main` by the folding (so the folded program compiles). Conservative: anything
    unsupported is left untouched."""
    funcs = {it.name: it for it in module.items
             if type(it).__name__ == "FunctionDecl" and it.body is not None}
    memo: dict = {}

    def eval_expr(e, env, depth):
        t = type(e).__name__
        if t == "IntLiteral" or t == "FloatLiteral":
            return e.value
        if t == "Identifier":
            if e.name in env:
                return env[e.name]
            raise _NotFoldable()
        if t == "BinaryOp":
            lo = eval_expr(e.left, env, depth)
            ro = eval_expr(e.right, env, depth)
            op = e.op
            if op == "+":
                return lo + ro
            if op == "-":
                return lo - ro
            if op == "*":
                return lo * ro
            if op == "<":
                return 1 if lo < ro else 0
            if op == ">":
                return 1 if lo > ro else 0
            if op == "<=":
                return 1 if lo <= ro else 0
            if op == ">=":
                return 1 if lo >= ro else 0
            if op == "==":
                return 1 if lo == ro else 0
            if op == "!=":
                return 1 if lo != ro else 0
            raise _NotFoldable()
        if t == "Call":
            if type(e.callee).__name__ != "Identifier":
                raise _NotFoldable()
            argvals = tuple(eval_expr(a, env, depth) for a in e.args)
            return eval_call(e.callee.name, argvals, depth + 1)
        raise _NotFoldable()

    def run_block(block, env, depth):
        """Evaluate a block's statements until a return; return the value, or _NO_RETURN."""
        for st in block.statements:
            t = type(st).__name__
            if t == "ReturnStmt":
                if st.value is None:
                    raise _NotFoldable()
                return eval_expr(st.value, env, depth)
            elif t == "IfStmt":
                cond = eval_expr(st.condition, env, depth)
                branch = st.then_branch if cond != 0 else st.else_branch
                if branch is not None:
                    r = run_block(branch, env, depth)
                    if r is not _NO_RETURN:
                        return r
                # not returned: fall through to the next statement
            else:
                raise _NotFoldable()   # unsupported statement -> abort this site
        return _NO_RETURN

    def eval_call(fname, argvals, depth):
        if depth > max_depth:
            raise _NotFoldable()
        key = (fname, argvals)
        if key in memo:
            return memo[key]
        f = funcs.get(fname)
        if f is None or len(f.params) != len(argvals):
            raise _NotFoldable()
        env = {p.name: v for p, v in zip(f.params, argvals)}
        r = run_block(f.body, env, depth)
        if r is _NO_RETURN:
            raise _NotFoldable()
        memo[key] = r
        return r

    def lit(value, span):
        if isinstance(value, bool):
            value = int(value)
        if isinstance(value, int):
            return ast.IntLiteral(span=span, value=value)
        return ast.FloatLiteral(span=span, value=float(value))

    def rewrite_expr(e):
        t = type(e).__name__
        if (t == "Call" and type(e.callee).__name__ == "Identifier"
                and e.callee.name in funcs):
            try:
                return lit(eval_expr(e, {}, 0), e.span)
            except (_NotFoldable, RecursionError):
                # RecursionError: the host evaluator's own stack would overflow before
                # `max_depth` is hit (a `max_depth` set above the host recursion limit).
                # Treat as not-foldable — leave the call for the runtime path. The default
                # `max_depth` is kept well within the host limit so this is the rare case.
                pass
        if t == "BinaryOp":
            e.left = rewrite_expr(e.left)
            e.right = rewrite_expr(e.right)
        elif t == "Call":
            e.args = [rewrite_expr(a) for a in e.args]
        return e

    def rewrite_stmt(s):
        t = type(s).__name__
        if t == "ReturnStmt" and s.value is not None:
            s.value = rewrite_expr(s.value)
        elif t == "IfStmt":
            s.condition = rewrite_expr(s.condition)
            for st in s.then_branch.statements:
                rewrite_stmt(st)
            if s.else_branch is not None:
                for st in s.else_branch.statements:
                    rewrite_stmt(st)
        elif t == "Block":
            for st in s.statements:
                rewrite_stmt(st)
        elif getattr(s, "initializer", None) is not None:
            s.initializer = rewrite_expr(s.initializer)

    for it in module.items:
        if type(it).__name__ == "FunctionDecl" and it.body is not None:
            for st in it.body.statements:
                rewrite_stmt(st)
    if prune:
        _prune_dead_recursive(module)
    return module
