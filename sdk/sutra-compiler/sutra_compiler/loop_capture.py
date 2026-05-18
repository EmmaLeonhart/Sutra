"""Variable-capture analysis for the implicit `loop(expr){ body }`
desugar (queue.md item 0; Emma's implicit-tail-recursion model).

Given a loop body, the **implicit axon** the loop threads tick to
tick is exactly the set of variables the body mutates that are NOT
declared inside the body itself (those are per-iteration locals,
fresh each tick — not recurrent state). This module computes that
set; later units synthesize the tail-recursive loop-function and
auto-slot these names.

Definition (deliberately the *minimal* axon — queue item 0 step
1b "minimize it to mutated-only"):

  captured = { v : body mutates v }  −  { v : body declares v }

where "mutates" = `v` is the `Identifier` target of an `Assignment`
(any op: `=`, `+=`, `-=`, `*=`, `/=`) or the `Identifier` operand
of a `++`/`--` `PostfixOp`, anywhere in the body including nested
control flow. Order is first-mutation order so codegen is
deterministic.

Known, documented simplifications for this first unit (refined in
later units, not faked as complete):
  - A name declared *anywhere* in the body (any nesting) is treated
    as local. Inner-shadowing of an outer name of the same
    identifier therefore conservatively drops it from the axon;
    real shadowing is rare and handled in the scope-aware refinement.
  - Only simple `Identifier` mutation targets are captured. Mutating
    `arr[i]` / `obj.f` does not enter the scalar implicit axon here.
"""
from __future__ import annotations

import dataclasses
from typing import List

from . import ast_nodes as ast


def _children(node: object):
    """Yield the dataclass-typed children of an AST node (single
    values and items of list/tuple fields). Generic over the AST so
    new node types need no change here."""
    if not dataclasses.is_dataclass(node):
        return
    for f in dataclasses.fields(node):
        v = getattr(node, f.name, None)
        if dataclasses.is_dataclass(v):
            yield v
        elif isinstance(v, (list, tuple)):
            for item in v:
                if dataclasses.is_dataclass(item):
                    yield item


def captured_state(body: ast.Block) -> List[str]:
    """Return the ordered list of identifier names `body`
    assigns/mutates that are not declared within `body` — the
    implicit-axon recurrent state for `loop(expr){ body }`.

    Pure analysis: no AST mutation, no side effects.
    """
    mutated: List[str] = []
    seen: set[str] = set()
    declared: set[str] = set()

    def _record_mutation(name: str) -> None:
        if name not in seen:
            seen.add(name)
            mutated.append(name)

    def _visit(node: object) -> None:
        if isinstance(node, ast.Assignment):
            if isinstance(node.target, ast.Identifier):
                _record_mutation(node.target.name)
        elif isinstance(node, ast.PostfixOp):
            if node.op in ("++", "--") and isinstance(
                node.operand, ast.Identifier
            ):
                _record_mutation(node.operand.name)
        elif isinstance(node, ast.VarDecl):
            declared.add(node.name)
        for child in _children(node):
            _visit(child)

    _visit(body)
    return [n for n in mutated if n not in declared]


def free_identifiers(expr: object) -> List[str]:
    """Return the ordered, de-duplicated identifier names referenced
    in `expr` in value position.

    Used to find the loop bound's free variables: for
    `loop(x){ body }` the count expression `x` must be threaded as
    an invariant state param (it is evaluated *inside* the emitted
    loop function — `codegen_base.py:1422`), so the desugar needs
    these names.

    A `Call`'s callee identifier (a function name, not a value var)
    is excluded so `loop(f(n)){...}` does not try to slot `f`. This
    is conservative: any name returned that has no caller `VarDecl`
    is rejected by the desugar with a clear `CodegenNotSupported`
    (fail-safe — never a miscompile)."""
    names: List[str] = []
    seen: set[str] = set()

    def _visit(node: object) -> None:
        if isinstance(node, ast.Identifier):
            if node.name not in seen:
                seen.add(node.name)
                names.append(node.name)
            return
        if isinstance(node, ast.Call):
            # Skip the callee when it is a bare function-name
            # Identifier; still visit its argument expressions.
            callee = getattr(node, "callee", None)
            for child in _children(node):
                if child is callee and isinstance(callee, ast.Identifier):
                    continue
                _visit(child)
            return
        for child in _children(node):
            _visit(child)

    _visit(expr)
    return names
