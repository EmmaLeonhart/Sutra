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
    coeffs: tuple              # the per-term coefficients, e.g. (2, 1) for 2*f(n-1)+f(n-2)
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


def _recursive_call_offset(call, param: str, fname: str) -> Optional[int]:
    """If `call` is `f(n - C)` with C a positive int literal, return C; else None."""
    if _name(call) != "Call" or _name(call.callee) != "Identifier" or call.callee.name != fname:
        return None
    if len(call.args) != 1:
        return None
    arg = call.args[0]
    if _name(arg) != "BinaryOp" or arg.op != "-":
        return None
    if _name(arg.left) != "Identifier" or arg.left.name != param:
        return None
    if _name(arg.right) != "IntLiteral" or arg.right.value <= 0:
        return None
    return arg.right.value


def _recursive_term(term, param: str, fname: str):
    """If `term` is a (coefficient * ) recursive call — `f(n-C)`, `K*f(n-C)`, or `f(n-C)*K` with K a
    positive int literal — return (coeff, offset); else None. (General linear-recurrence terms.)"""
    off = _recursive_call_offset(term, param, fname)
    if off is not None:
        return (1, off)
    if _name(term) == "BinaryOp" and term.op == "*":
        for a, b in ((term.left, term.right), (term.right, term.left)):
            if _name(a) == "IntLiteral" and a.value > 0:
                off = _recursive_call_offset(b, param, fname)
                if off is not None:
                    return (a.value, off)
    return None


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
    coeffs, offsets = [], []
    for t in terms:
        ct = _recursive_term(t, param, fname)
        if ct is None:
            return None          # a non-(coeff*)`f(n-C)` term -> not the pure tabulable shape
        coeffs.append(ct[0])
        offsets.append(ct[1])
    if len(offsets) < 2:
        return None              # single recursion is tier 2, not tier 4
    return TabulableShape(param=param, base_op=cond.op, base_k=cond.right.value,
                          base_value=base_value, offsets=tuple(offsets),
                          coeffs=tuple(coeffs), func=fdecl)


def synthesize_tabulation_source(shape: TabulableShape) -> Optional[str]:
    """Generate non-recursive Sutra source for `shape` as a memoizing `while_loop`, or None if the
    shape is outside this MVP's synthesizable subset.

    The loop carries a rolling window of M = max(offsets) accumulators holding f(k), …, f(k+M-1);
    each iteration appends f(k+M) = sum over offsets o of window[M-o] and shifts. After n iterations
    from the base window the head holds f(n) — the verified 4a form (a recurrent-neuron `while_loop`,
    NATIVE, no recursion, no WASM). MVP subset: the base value is the parameter identity (`return n`)
    and the base threshold K equals M (the standard fib-family); then the base window is 0,1,…,M-1.
    Wider base values / K>M are left to a later step."""
    if shape.base_op not in ("<", "<="):
        return None
    m = max(shape.offsets)
    # `if (n < K)` covers indices < K; `if (n <= K)` covers indices <= K (so M = K+1 effectively).
    covers = shape.base_k if shape.base_op == "<" else shape.base_k + 1
    if covers != m:
        return None
    bv = shape.base_value
    if _name(bv) != "Identifier" or bv.name != shape.param:
        return None   # MVP: base value must be the parameter identity (f(j) = j for j < K)

    f = shape.func.name
    n = shape.param
    ti = f"_t_{n}"                      # loop counter (fresh, avoids clashing with the param)
    ws = [f"_w{j}" for j in range(m)]
    # f(i) = sum over terms of coeff * f(i-offset) = coeff * window[M-offset]
    parts = []
    for coeff, o in zip(shape.coeffs, shape.offsets):
        w = ws[m - o]
        parts.append(w if coeff == 1 else f"{coeff} * {w}")
    combine = " + ".join(parts)
    shift = "".join(f"    {ws[j]} = {ws[j + 1]};\n" for j in range(m - 1)) + f"    {ws[m - 1]} = _new;\n"
    loop = f"_tab_{f}"
    decl_state = ", ".join(f"int {w} = 0" for w in ws)
    call_state = ", ".join(f"_s{w}" for w in ws)
    slot_decls = "".join(f"    slot int _s{w} = {w};\n" for w in ws)
    init_window = "".join(f"    int {ws[j]} = {j};\n" for j in range(m))
    return (
        f"while_loop {loop}({ti} < {n}, int {ti} = 0, {decl_state}, int {n} = 0) {{\n"
        f"    int _new = {combine};\n"
        f"{shift}"
        f"    {ti} = {ti} + 1;\n"
        f"}}\n"
        f"function int {f}(int {n}) {{\n"
        f"    int {ti} = 0;\n"
        f"{init_window}"
        f"    slot int _s{ti} = {ti};\n"
        f"{slot_decls}"
        f"    slot int _s{n} = {n};\n"
        f"    loop {loop}({ti} < {n}, _s{ti}, {call_state}, _s{n});\n"
        f"    return _s{ws[0]};\n"
        f"}}\n"
    )


def tabulate_module(module):
    """Rewrite every tabulable multiple-recursive FunctionDecl in `module` into its memoizing
    `while_loop` form (a `while_loop` decl + a non-recursive function), in place. Returns the
    module. Conservative: a function that doesn't detect+synthesize is left untouched."""
    from .lexer import Lexer
    from .parser import Parser

    new_items = []
    for it in module.items:
        if type(it).__name__ == "FunctionDecl":
            shape = detect_tabulable_recursion(it)
            if shape is not None:
                src = synthesize_tabulation_source(shape)
                if src is not None:
                    lx = Lexer(src, file=f"<tabulate:{it.name}>")
                    sub = Parser(lx.tokenize(), file=f"<tabulate:{it.name}>",
                                 diagnostics=lx.diagnostics).parse_module()
                    if not lx.diagnostics.has_errors():
                        new_items.extend(sub.items)   # the while_loop decl + the new function
                        continue
        new_items.append(it)
    module.items = new_items
    return module
