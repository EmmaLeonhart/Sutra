"""Tier-4 native recursion via memoization — shape detection (Phase 5.5, step 4b, part 1).

Sutra has no native runtime recursion; tier 4 makes recursion native by rewriting a multiple-recursive
function into a memoizing loop (`while_loop` → recurrent neurons). This module is the DETECTOR: it
recognizes the tabulable index-structured shape that the loop synthesizer (4b part 2) consumes —

    function int f(int n) {
        if (n <OP> K) { return <base>; }      # base case (no recursive call), e.g. `if (n < 2) return n;`
        return f(n - c1) + f(n - c2) [+ …];    # >= 2 recursive calls of f at constant offsets, summed
    }

This is the `fib`/tribonacci family (overlapping subproblems over an integer index). Detection is
conservative: anything outside this exact shape returns None (left for the general agenda+memo form,
which is a later step). It does NOT match single recursion (that is tier 2) — it requires >= 2
recursive calls.
"""
from __future__ import annotations

from typing import NamedTuple, Optional

_CMP_OPS = {"<", "<=", "==", ">", ">="}


class TabulableShape(NamedTuple):
    param: str                 # the single integer index parameter name
    base_op: str               # comparison op of the base-case condition (`n <op> K`)
    base_k: int                # the base-case threshold K
    base_value: object         # the base-case return expression (an AST node; no recursive call)
    offsets: tuple             # the constant recursive offsets, e.g. (1, 2) for f(n-1)+f(n-2)
    func: object               # the FunctionDecl node


def _name(node) -> str:
    return type(node).__name__


def _contains_call_to(node, fname: str) -> bool:
    """Does the subtree contain a Call to `fname`? (Whole-AST dataclass walk via __dict__ fields.)"""
    if _name(node) == "Call" and _name(node.callee) == "Identifier" and node.callee.name == fname:
        return True
    import dataclasses
    if not dataclasses.is_dataclass(node):
        return False
    for f in dataclasses.fields(node):
        ch = getattr(node, f.name, None)
        if isinstance(ch, (list, tuple)):
            if any(dataclasses.is_dataclass(c) and _contains_call_to(c, fname) for c in ch):
                return True
        elif dataclasses.is_dataclass(ch) and _contains_call_to(ch, fname):
            return True
    return False


def _sum_terms(expr):
    """Flatten a left/right-nested `+` chain into its leaf terms."""
    if _name(expr) == "BinaryOp" and expr.op == "+":
        return _sum_terms(expr.left) + _sum_terms(expr.right)
    return [expr]


def _recursive_offset(term, param: str, fname: str) -> Optional[int]:
    """If `term` is `f(n - C)` with C a positive int literal, return C; else None."""
    if _name(term) != "Call" or _name(term.callee) != "Identifier" or term.callee.name != fname:
        return None
    if len(term.args) != 1:
        return None
    arg = term.args[0]
    if _name(arg) != "BinaryOp" or arg.op != "-":
        return None
    if _name(arg.left) != "Identifier" or arg.left.name != param:
        return None
    if _name(arg.right) != "IntLiteral" or arg.right.value <= 0:
        return None
    return arg.right.value


def detect_tabulable_recursion(fdecl) -> Optional[TabulableShape]:
    """Return a TabulableShape if `fdecl` is the fib-family index-structured multiple recursion,
    else None (conservative — unrecognized shapes are left for other tiers)."""
    if _name(fdecl) != "FunctionDecl" or fdecl.body is None:
        return None
    if len(fdecl.params) != 1:
        return None
    param = fdecl.params[0].name
    fname = fdecl.name
    stmts = fdecl.body.statements
    if len(stmts) != 2:
        return None
    base_if, rec_ret = stmts
    if _name(base_if) != "IfStmt" or _name(rec_ret) != "ReturnStmt":
        return None
    # --- base case: `if (n <op> K) { return <base, no recursion>; }`, no else ---
    if base_if.else_branch is not None:
        return None
    cond = base_if.condition
    if (_name(cond) != "BinaryOp" or cond.op not in _CMP_OPS
            or _name(cond.left) != "Identifier" or cond.left.name != param
            or _name(cond.right) != "IntLiteral"):
        return None
    then_stmts = base_if.then_branch.statements
    if len(then_stmts) != 1 or _name(then_stmts[0]) != "ReturnStmt" or then_stmts[0].value is None:
        return None
    base_value = then_stmts[0].value
    if _contains_call_to(base_value, fname):
        return None
    # --- recursive return: a sum of >= 2 recursive calls f(n - C), all constant positive offsets ---
    if rec_ret.value is None:
        return None
    terms = _sum_terms(rec_ret.value)
    offsets = []
    for t in terms:
        off = _recursive_offset(t, param, fname)
        if off is None:
            return None          # a non-`f(n-C)` term -> not the pure tabulable shape
        offsets.append(off)
    if len(offsets) < 2:
        return None              # single recursion is tier 2, not tier 4
    return TabulableShape(param=param, base_op=cond.op, base_k=cond.right.value,
                          base_value=base_value, offsets=tuple(offsets), func=fdecl)
