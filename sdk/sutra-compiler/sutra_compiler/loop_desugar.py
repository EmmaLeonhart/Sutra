"""Implicit tail-recursive loop desugar (Emma's model; queue.md item 0).

`loop(expr){ body }` (the bare, condition-based form — currently
parsed-but-rejected) is sugar for a tail-recursive loop function
whose recurrent state is the **implicit axon**: the variables the
body mutates, plus the loop bound's free variables (threaded
invariant). This pass rewrites it, before codegen, into the
already-working explicit machinery:

  - the captured vars' `VarDecl`s are flipped to `slot` (slot
    storage is transparently routed everywhere by codegen — reads
    `codegen_base.py:2620-2624`, writes `:1937-1945`, decl
    `:800-819`, loop-call thread `:1628-1664`), so doing the flip
    at the declaration makes every use consistent by construction;
  - a synthesized `iterative_loop` `LoopFunctionDecl` (count =
    the loop's condition expression; body = the original body +
    a `pass` yielding the new mutated values and `replace` for the
    invariant bound vars) is inserted into `module.items`
    immediately before the function it came from (top-level loop
    functions live in `module.items`, not on `Module`; codegen
    translates items strictly in order — `codegen_base.py:643` —
    so the decl must precede the caller for `_loop_decls`
    registration);
  - the `LoopStmt` is replaced by a `LoopCallStmt`.

Inside the emitted loop function `_slot_vars` is reset to empty
(`codegen_base.py:1081`), so the state params are plain locals
there — the `iterative_loop` count expression (e.g. bare `x`)
resolves to the in-scope state local (`codegen_base.py:1422`).
That is exactly why the bound's free vars must be threaded as
state. The slot-ness only matters in the caller, where the
`LoopCallStmt` slot-loads/stores them.

Literal-bound `loop(N){...}` is untouched: it has `count != None`
and the codegen dispatches it to the compile-time unroll before
this form is ever reached. This pass only fires for
`count is None`.

Scope of this first attempt (documented, not faked as complete):
  - Top-level `FunctionDecl` bodies and nested blocks within them.
    Class-method bodies are a follow-on.
  - A captured/bound name must have a `VarDecl` (with an explicit
    `type_ref`) in the enclosing function. Missing decl, no type,
    or a parameter-only name → `CodegenNotSupported` with a clear
    message. Never guess a type or silently miscompile.
  - First VarDecl of a given name in the function is the one
    flipped (no scope-shadowing analysis yet).
"""
from __future__ import annotations

import copy
import dataclasses
from typing import Dict, List, Optional

from . import ast_nodes as ast
from .codegen_base import CodegenNotSupported
from .loop_capture import captured_state, free_identifiers


_BOOL_BINOPS = frozenset(
    {"<", ">", "<=", ">=", "==", "!=", "&&", "||"}
)


def _loop_kind(cond: object) -> str:
    """Pick the loop kind from the bound expression's *shape*.

    `loop(n < 11){…}` / `loop(!done){…}` — a relational/logical
    bound — is a `while_loop` (condition re-checked before each
    tick). `loop(x){…}` / `loop(n + 1){…}` — an integer count — is
    an `iterative_loop` (run that many ticks; `iterator` = tick).

    Syntactic heuristic only (no type inference in this pass).
    Known, documented limitations (wrong iteration count at worst,
    never a miscompile/crash):
      - A bare boolean variable as the whole bound —
        `loop(done){…}` — is read as a *count* (`int(done)` ⇒ 0/1
        ticks). Write `loop(done == true){…}` for while semantics.
      - **Relational bounds (`<` `>` `<=` `>=`) are verified to
        work** on both backends. Equality / negation bounds
        (`==` `!=` `!`) inherit the pre-existing *fuzzy* numeric-
        equality truth-axis lowering (numeric `==` → Euclidean +
        tanh on the truth axis, not a crisp boolean — see
        `planning/sutra-spec/equality-and-defuzzification.md`).
        That lowering is unchanged by this pass and is out of
        scope here; such a `loop(!(n==k)){…}` may not terminate
        crisply. Tracked under equality-and-defuzzification, NOT a
        desugar bug."""
    while isinstance(cond, ast.Parenthesized):
        cond = cond.inner
    if isinstance(cond, ast.BinaryOp) and cond.op in _BOOL_BINOPS:
        return "while_loop"
    if isinstance(cond, ast.UnaryOp) and cond.op == "!":
        return "while_loop"
    return "iterative_loop"


def _collect_var_decls(
    node: object,
    out: Dict[str, ast.VarDecl],
    dups: "set[str]",
) -> None:
    """First-seen `name -> VarDecl` over the subtree, AND record into
    `dups` any name declared more than once. The pass is not yet
    lexical-scope-aware (first-decl-wins); a duplicated captured name
    is therefore ambiguous, so the desugar refuses it with a clear
    error rather than silently flipping the wrong declaration to
    slot — fail-safe, never a silent miscompile (queue item 0 (b))."""
    if isinstance(node, ast.VarDecl):
        if node.name in out:
            dups.add(node.name)
        else:
            out[node.name] = node
    if not dataclasses.is_dataclass(node):
        return
    for f in dataclasses.fields(node):
        v = getattr(node, f.name, None)
        if dataclasses.is_dataclass(v):
            _collect_var_decls(v, out, dups)
        elif isinstance(v, (list, tuple)):
            for item in v:
                if dataclasses.is_dataclass(item):
                    _collect_var_decls(item, out, dups)


def _references_this(node: object) -> bool:
    """True iff the subtree references `this` (a `ThisExpr` anywhere).

    A loop inside a class method whose body/bound touches `this`
    (i.e. instance state / fields) cannot be lowered to a top-level
    synthesized loop function — that function has no receiver. We
    detect it and reject with a clear error rather than emit code
    that references an undefined `this` (queue item 0 (a))."""
    if isinstance(node, ast.ThisExpr):
        return True
    if not dataclasses.is_dataclass(node):
        return False
    for f in dataclasses.fields(node):
        v = getattr(node, f.name, None)
        if dataclasses.is_dataclass(v):
            if _references_this(v):
                return True
        elif isinstance(v, (list, tuple)):
            for item in v:
                if dataclasses.is_dataclass(item) and _references_this(item):
                    return True
    return False


class _Desugarer:
    def __init__(self, module: ast.Module) -> None:
        self._module = module
        self._counter = 0
        # Loop functions synthesized while rewriting the *current*
        # function; flushed into module.items right before it.
        self._pending: List[ast.LoopFunctionDecl] = []
        # Names declared >1× in the current callable body — captured
        # ones are refused (not lexical-scope-aware yet); see (b).
        self._dups: "set[str]" = set()

    def _unique_name(self, fn_name: str) -> str:
        self._counter += 1
        return f"__implicit_loop_{fn_name}_{self._counter}"

    def _rewrite_block(
        self,
        block: ast.Block,
        var_decls: Dict[str, ast.VarDecl],
        fn_name: str,
    ) -> None:
        new_statements: List[ast.Stmt] = []
        for stmt in block.statements:
            # Recurse into nested control flow first so a loop inside
            # an `if`/nested block is handled too.
            for f in dataclasses.fields(stmt):
                v = getattr(stmt, f.name, None)
                if isinstance(v, ast.Block):
                    self._rewrite_block(v, var_decls, fn_name)
                elif isinstance(v, ast.IfStmt):
                    self._rewrite_block_holder(v, var_decls, fn_name)

            if isinstance(stmt, ast.LoopStmt) and stmt.count is None:
                new_statements.append(
                    self._desugar_loop(stmt, var_decls, fn_name)
                )
            else:
                new_statements.append(stmt)
        block.statements = new_statements

    def _rewrite_block_holder(
        self, node: object, var_decls: Dict[str, ast.VarDecl], fn_name: str
    ) -> None:
        """Recurse into a node that holds Block(s) (IfStmt chain)."""
        for f in dataclasses.fields(node):
            v = getattr(node, f.name, None)
            if isinstance(v, ast.Block):
                self._rewrite_block(v, var_decls, fn_name)
            elif isinstance(v, ast.IfStmt):
                self._rewrite_block_holder(v, var_decls, fn_name)

    def _desugar_loop(
        self,
        loop: ast.LoopStmt,
        var_decls: Dict[str, ast.VarDecl],
        fn_name: str,
    ) -> ast.LoopCallStmt:
        sp = loop.span
        cond = loop.condition
        if cond is None:
            raise CodegenNotSupported(
                loop, "implicit `loop(expr){body}` requires a bound/"
                "condition expression."
            )
        # (a) class-method guard: a synthesized implicit loop function
        # is top-level (no receiver). A loop that touches `this` /
        # instance state cannot be lowered that way — clear error,
        # never undefined-`this` emitted code.
        if _references_this(loop.body) or _references_this(cond):
            raise CodegenNotSupported(
                loop,
                "implicit `loop(expr){body}` inside a class method may "
                "not (yet) reference `this` / instance fields — its "
                "lowered loop function is top-level and has no "
                "receiver. Lift the loop state into local variables, "
                "or use an explicit declared loop function.",
            )
        mutated = captured_state(loop.body)
        bound = [n for n in free_identifiers(cond) if n not in mutated]
        state = mutated + bound
        if not state:
            raise CodegenNotSupported(
                loop, "implicit `loop(expr){body}` has no recurrent "
                "state (body mutates nothing and the bound has no "
                "variables) — it would be a no-op or non-terminating; "
                "use `loop[N]{...}` for a fixed unroll instead."
            )

        state_params: List[ast.LoopStateParam] = []
        for name in state:
            if name in self._dups:
                raise CodegenNotSupported(
                    loop,
                    f"implicit loop captures `{name}`, which is "
                    f"declared more than once in this function — the "
                    f"desugar is not yet lexical-scope-aware and will "
                    f"not guess which declaration is the loop's state. "
                    f"Rename one, or use an explicit declared loop "
                    f"function. (Fail-safe — never a silent miscompile.)",
                )
            decl = var_decls.get(name)
            if decl is None:
                raise CodegenNotSupported(
                    loop,
                    f"implicit loop captures `{name}` but it has no "
                    f"`VarDecl` in the enclosing function (a parameter "
                    f"or outer-scope name); declare it locally before "
                    f"the loop so it can be the implicit axon's state.",
                )
            if decl.type_ref is None:
                raise CodegenNotSupported(
                    loop,
                    f"implicit loop captures `{name}` but its "
                    f"declaration is `var`-inferred (no explicit "
                    f"type); give it an explicit type so the loop "
                    f"state parameter has a known type.",
                )
            decl.is_slot = True
            state_params.append(
                ast.LoopStateParam(
                    span=sp,
                    type_ref=copy.deepcopy(decl.type_ref),
                    name=name,
                    default=None,
                )
            )

        pass_values: List[object] = [
            ast.Identifier(span=sp, name=n) for n in mutated
        ] + [ast.ReplaceMarker(span=sp) for _ in bound]
        loop_fn_body = ast.Block(
            span=sp,
            statements=list(loop.body.statements)
            + [ast.PassStmt(span=sp, values=pass_values)],
        )
        name = self._unique_name(fn_name)
        kind = _loop_kind(cond)
        decl = ast.LoopFunctionDecl(
            span=sp,
            kind=kind,
            name=name,
            # iterative_loop: count expr. while_loop: boolean checked
            # before each tick. Either way bound vars are now state
            # params so the expr resolves inside the loop fn.
            condition=cond,
            state_params=state_params,
            body=loop_fn_body,
        )
        self._pending.append(decl)
        return ast.LoopCallStmt(
            span=sp,
            name=name,
            condition_arg=copy.deepcopy(cond),
            state_arg_names=list(state),
        )

    def _rewrite_callable(
        self, body: ast.Block, name: str
    ) -> List[ast.LoopFunctionDecl]:
        """Rewrite one function/method body; return its synthesized
        loop functions (caller inserts them before the enclosing
        top-level item so codegen registers them first)."""
        var_decls: Dict[str, ast.VarDecl] = {}
        self._dups = set()
        # params are not VarDecls; a param-captured name therefore
        # hits the clear CodegenNotSupported in _desugar_loop (by
        # design — not slottable here).
        _collect_var_decls(body, var_decls, self._dups)
        self._pending = []
        self._rewrite_block(body, var_decls, name)
        pend = self._pending
        self._pending = []
        return pend

    def run(self) -> None:
        new_items: List[ast.TopLevel] = []
        for item in self._module.items:
            if isinstance(item, ast.FunctionDecl):
                body = getattr(item, "body", None)
                if isinstance(body, ast.Block):
                    # Synthesized loop fns must precede the caller so
                    # codegen registers them first (items run in order).
                    new_items.extend(
                        self._rewrite_callable(body, item.name)
                    )
            elif isinstance(item, ast.ClassDecl):
                # (a) class-method bodies. The synthesized loop
                # functions are TOP-LEVEL (no receiver) and inserted
                # before the ClassDecl, so codegen registers them
                # before translating the class's methods. Loops that
                # touch `this` are refused in _desugar_loop with a
                # clear error (top-level fn has no receiver).
                for method in getattr(item, "methods", []):
                    mbody = getattr(method, "body", None)
                    if isinstance(mbody, ast.Block):
                        new_items.extend(
                            self._rewrite_callable(
                                mbody, f"{item.name}_{method.name}"
                            )
                        )
            new_items.append(item)
        self._module.items = new_items


def desugar_implicit_loops(module: ast.Module) -> ast.Module:
    """Rewrite every `loop(expr){body}` (count is None) into the
    explicit tail-recursive loop-function machinery, in place."""
    _Desugarer(module).run()
    return module
