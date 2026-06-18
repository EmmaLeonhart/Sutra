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
    each iteration appends f(k+M) = Σ coeff·window[M-offset] and shifts. After n iterations from the
    base window the head holds f(n) — the verified 4a form (a recurrent-neuron `while_loop`, NATIVE,
    no recursion, no WASM). Subset: the base threshold K equals M (the standard family), and the base
    value is either the parameter identity (`return n` → f(j)=j) or an integer literal (`return L` →
    f(j)=L for all j<K); so the base window is computable. Wider base expressions / K>M are later."""
    if shape.base_op not in ("<", "<="):
        return None
    m = max(shape.offsets)
    # `if (n < K)` covers indices < K; `if (n <= K)` covers indices <= K (so M = K+1 effectively).
    covers = shape.base_k if shape.base_op == "<" else shape.base_k + 1
    if covers != m:
        return None
    bv = shape.base_value
    if _name(bv) == "Identifier" and bv.name == shape.param:
        base_vals = list(range(m))            # f(j) = j  (`return n`)
    elif _name(bv) == "IntLiteral":
        base_vals = [bv.value] * m            # f(j) = L  (`return L`)
    else:
        return None   # wider base expressions left to a later step

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
    init_window = "".join(f"    int {ws[j]} = {base_vals[j]};\n" for j in range(m))
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


def synthesize_ram_memo_source(shape: TabulableShape) -> Optional[str]:
    """Generate non-recursive Sutra source for `shape` as a RAM-MEMO `while_loop` — the general
    single-index DP form (RAM-device-backed memo, finding `2026-06-17-tier4-ram-memo-in-loop.md`).

    Seeds `ramWrite(j, base(j))` for j < K, then loops `ramWrite(i, Σ coeff·ramRead(i-offset))` for i
    in [K, n], returning `ramRead(n)`. Unlike the rolling-window form this uses a true memo TABLE (the
    RAM device persists across loop iterations), so it handles ANY offsets — including large ones a
    fixed scalar window would make unwieldy. (Uses low RAM addresses 0..n, so it must NOT be combined
    with a program that also uses low-address arrays; the rolling-window form, with no RAM, stays the
    default for the cases it covers — this RAM-memo backend is for the wider single-index family.)
    Requires K >= max(offset) (so every f(i-offset) is already in the memo) and base = identity/literal."""
    m = max(shape.offsets)
    covers = shape.base_k if shape.base_op in ("<",) else (shape.base_k + 1 if shape.base_op == "<=" else None)
    if covers is None or covers < m:
        return None
    bv = shape.base_value
    if _name(bv) == "Identifier" and bv.name == shape.param:
        base_vals = [str(j) for j in range(covers)]      # f(j) = j
    elif _name(bv) == "IntLiteral":
        base_vals = [str(bv.value)] * covers             # f(j) = L
    else:
        return None

    f = shape.func.name
    n = shape.param
    ti = f"_t_{n}"
    bound = f"_b_{n}"
    parts = []
    for coeff, o in zip(shape.coeffs, shape.offsets):
        r = f"ramRead({ti} - {o})"
        parts.append(r if coeff == 1 else f"{coeff} * {r}")
    combine = " + ".join(parts)
    seed = "".join(f"    ramWrite({j}, {base_vals[j]});\n" for j in range(covers))
    return (
        f"while_loop _ramtab_{f}({ti} < {bound}, int {ti} = {covers}, int {bound} = 0) {{\n"
        f"    int _v = {combine};\n"
        f"    ramWrite({ti}, _v);\n"
        f"    {ti} = {ti} + 1;\n"
        f"}}\n"
        f"function int {f}(int {n}) {{\n"
        f"{seed}"
        f"    int {bound} = {n} + 1;\n"
        f"    int {ti} = {covers};\n"
        f"    slot int _s{ti} = {ti};\n"
        f"    slot int _s{bound} = {bound};\n"
        f"    loop _ramtab_{f}({ti} < {bound}, _s{ti}, _s{bound});\n"
        f"    return ramRead({n});\n"
        f"}}\n"
    )


# ----------------------------------------------------------------------------------------------
# Multi-argument DP (the "complicated form", v0.8.0 serious attempt). A 2-argument recurrence
#
#     function int f(int a, int b) {
#         if (<b == 0>)  { return C0; }       # >= 1 boundary `if (cond) return <int const>;` (no else)
#         if (<b == a>)  { return C1; }
#         return f(a-1, b-1) + f(a-1, b) [+ …];   # >= 1 recursive term, EVERY term decreasing `a`
#     }
#
# is the binomial / Pascal family. It compiles to a single RAM-memo `while_loop` that fills a
# (n+1)x(n+1) row-major table (base address 100, cell (row,col) at 100 + row*(n+1) + col), row
# outer / col inner, the col counter wrapped by a substrate blend (no Math.mod), each boundary
# applied by a nested blend `(((1+flag)*const) + ((1-flag)*else))/2`, and the recurrence terms read
# from RAM. This is the hand-proven Pascal loop (test_native_recursion.py, 2026-06-17) generalized
# over the detected boundaries + offsets + coeffs. Conservative: every recursive term MUST decrease
# the first param by >= 1 (so row i depends only on rows < i, making the row-major fill well-founded)
# and the second-param offsets MUST be >= 0; anything else returns None (left to the agenda+memo
# form or to WASM). Cap: the fill is (n+1)^2 cells, so practical to the `loop_max_iterations` budget
# (default 50 -> n <= 6); larger n needs `[project.compile] loop_max_iterations` raised.

class Tabulable2DShape(NamedTuple):
    p0: str                    # first (outer / row) integer param — decreased by every term
    p1: str                    # second (inner / col) integer param
    boundaries: tuple          # ((flag_su_expr:str, const:int), …) — base cases, applied as blends
    coeffs: tuple              # per-term coefficients
    offsets: tuple             # per-term (da, db): f(p0-da, p1-db), da>=1, db>=0
    func: object               # the FunctionDecl node


def _recursive_call_offset_2d(call, p0: str, p1: str, fname: str):
    """If `call` is `f(p0 - DA, p1 - DB)` with DA>=1, DB>=0 constant int literals (a bare `p` counts
    as offset 0), return (DA, DB); else None."""
    if _name(call) != "Call" or _name(call.callee) != "Identifier" or call.callee.name != fname:
        return None
    if len(call.args) != 2:
        return None

    def _axis_offset(arg, param):
        # `param`            -> offset 0
        if _name(arg) == "Identifier" and arg.name == param:
            return 0
        # `param - C`        -> offset C (C a non-negative int literal)
        if (_name(arg) == "BinaryOp" and arg.op == "-"
                and _name(arg.left) == "Identifier" and arg.left.name == param
                and _name(arg.right) == "IntLiteral" and arg.right.value >= 0):
            return arg.right.value
        return None

    da = _axis_offset(call.args[0], p0)
    db = _axis_offset(call.args[1], p1)
    if da is None or db is None or da < 1 or db < 0:
        return None
    return (da, db)


def _recursive_term_2d(term, p0: str, p1: str, fname: str):
    """`f(p0-DA,p1-DB)`, `K*f(…)`, or `f(…)*K` -> (coeff, da, db); else None."""
    off = _recursive_call_offset_2d(term, p0, p1, fname)
    if off is not None:
        return (1, off[0], off[1])
    if _name(term) == "BinaryOp" and term.op == "*":
        for a, b in ((term.left, term.right), (term.right, term.left)):
            if _name(a) == "IntLiteral" and a.value > 0:
                off = _recursive_call_offset_2d(b, p0, p1, fname)
                if off is not None:
                    return (a.value, off[0], off[1])
    return None


def _boundary_flag(cond, p0: str, p1: str):
    """Map a base-case condition to a substrate flag-expr over the loop's `_row`/`_col` counters
    (row<->p0, col<->p1). Returns the Sutra expr string (a ±1 `truth_axis(defuzzy(...))` flag) or
    None if the condition is outside the recognized set. Boundary-clean comparisons only:
    `col == 0` via the even/odd `(2*col) < 1`; `col == row`/`row == col` via crisp `==` (the proven
    loop uses crisp `==` for the diagonal); a literal `col == K` via crisp `==`."""
    if _name(cond) != "BinaryOp":
        return None
    op, L, R = cond.op, cond.left, cond.right

    def is_id(x, nm):
        return _name(x) == "Identifier" and x.name == nm
    def is_int(x, v=None):
        return _name(x) == "IntLiteral" and (v is None or x.value == v)

    # col == 0  /  col < 1  /  col <= 0   (the second param hits its low edge)
    if op == "==" and is_id(L, p1) and is_int(R, 0):
        return "truth_axis(defuzzy((2 * _dp_col) < 1))"
    if op == "<" and is_id(L, p1) and is_int(R, 1):
        return "truth_axis(defuzzy((2 * _dp_col) < 1))"
    if op == "<=" and is_id(L, p1) and is_int(R, 0):
        return "truth_axis(defuzzy((2 * _dp_col) < 1))"
    # col == row / row == col  (the diagonal)
    if op == "==" and ((is_id(L, p1) and is_id(R, p0)) or (is_id(L, p0) and is_id(R, p1))):
        return "truth_axis(defuzzy(_dp_col == _dp_row))"
    # col == K  (a constant diagonal/edge)
    if op == "==" and is_id(L, p1) and is_int(R):
        return f"truth_axis(defuzzy(_dp_col == {R.value}))"
    return None


def detect_2arg_dp(fdecl):
    """Return a Tabulable2DShape if `fdecl` is the 2-arg binomial/Pascal-family DP, else None.
    Shape: 2 int params; >= 1 leading boundary `if (cond) return <int const>;` (no else, each cond
    recognized by `_boundary_flag`); then a final `return` summing >= 1 recursive term, EVERY term
    decreasing the first param by >= 1. Conservative — unrecognized shapes return None."""
    if _name(fdecl) != "FunctionDecl" or fdecl.body is None:
        return None
    if len(fdecl.params) != 2:
        return None
    p0, p1 = fdecl.params[0].name, fdecl.params[1].name
    fname = fdecl.name
    stmts = fdecl.body.statements
    if len(stmts) < 2:
        return None
    *bnd_ifs, rec_ret = stmts
    if _name(rec_ret) != "ReturnStmt" or rec_ret.value is None:
        return None
    boundaries = []
    for s in bnd_ifs:
        if _name(s) != "IfStmt" or s.else_branch is not None:
            return None
        then = s.then_branch.statements
        if len(then) != 1 or _name(then[0]) != "ReturnStmt" or then[0].value is None:
            return None
        cval = then[0].value
        if _name(cval) != "IntLiteral" or _contains_call_to(cval, fname):
            return None
        flag = _boundary_flag(s.condition, p0, p1)
        if flag is None:
            return None
        boundaries.append((flag, cval.value))
    if not boundaries:
        return None  # no base case -> not a well-founded DP we can seed
    terms = _sum_terms(rec_ret.value)
    coeffs, offsets = [], []
    for t in terms:
        ct = _recursive_term_2d(t, p0, p1, fname)
        if ct is None:
            return None  # a non-recursive / non-decreasing term -> not this shape
        coeffs.append(ct[0])
        offsets.append((ct[1], ct[2]))
    if not offsets:
        return None
    return Tabulable2DShape(p0=p0, p1=p1, boundaries=tuple(boundaries),
                            coeffs=tuple(coeffs), offsets=tuple(offsets), func=fdecl)


def synthesize_2arg_dp_source(shape: Tabulable2DShape):
    """Emit non-recursive Sutra source for `shape` as a RAM-memo `while_loop` filling a (n+1)x(n+1)
    row-major table (base 100), row outer / col inner, col wrapped by an even/odd blend (no
    Math.mod), each boundary applied by a nested blend, the recurrence read from RAM. The proven
    Pascal loop generalized over the detected boundaries/coeffs/offsets. Returns the source string."""
    p0, p1 = shape.p0, shape.p1
    f = shape.func.name
    # All synthesized loop vars use a `_dp_` prefix: it dodges the codegen's reserved single-letter
    # underscore names (the unroll counter `_t`, `_step`, …) AND is distinctive enough not to collide
    # with the user's param names p0/p1.
    # interior recurrence: Σ coeff * ramRead(100 + (row-da)*W + (col-db))
    parts = []
    for coeff, (da, db) in zip(shape.coeffs, shape.offsets):
        addr = f"100 + (_dp_row - {da}) * _dp_w + (_dp_col - {db})"
        r = f"ramRead({addr})"
        parts.append(r if coeff == 1 else f"{coeff} * {r}")
    interior = " + ".join(parts)
    # boundary blend chain: cval = b0 ? c0 : (b1 ? c1 : interior)  (innermost = interior)
    expr = "_dp_interior"
    blend_lines = [f"    int _dp_interior = {interior};\n"]
    for idx, (flag, const) in enumerate(reversed(shape.boundaries)):
        fv = f"_dp_bf{len(shape.boundaries) - 1 - idx}"
        blend_lines.append(f"    int {fv} = {flag};\n")
        expr = f"(((1 + {fv}) * {const}) + ((1 - {fv}) * ({expr}))) / 2"
    blend_lines.append(f"    int _dp_cval = {expr};\n")
    body = "".join(blend_lines)
    loop = f"_dploop_{f}"
    return (
        f"while_loop {loop}(_dp_i < _dp_t, int _dp_i = 0, int _dp_row = 0, int _dp_col = 0, "
        f"int _dp_t = 0, int _dp_n = 0, int _dp_w = 0) {{\n"
        f"{body}"
        f"    ramWrite(100 + _dp_row * _dp_w + _dp_col, _dp_cval);\n"
        f"    int _dp_atend = truth_axis(defuzzy((2 * _dp_col) > (2 * _dp_n - 1)));\n"
        f"    int _dp_newcol = (((1 + _dp_atend) * 0) + ((1 - _dp_atend) * (_dp_col + 1))) / 2;\n"
        f"    int _dp_winc = (_dp_atend + 1) / 2;\n"
        f"    _dp_col = _dp_newcol;\n"
        f"    _dp_row = _dp_row + _dp_winc;\n"
        f"    _dp_i = _dp_i + 1;\n"
        f"}}\n"
        f"function int {f}(int {p0}, int {p1}) {{\n"
        f"    int _dp_i = 0; int _dp_row = 0; int _dp_col = 0;\n"
        f"    int _dp_w = {p0} + 1;\n"
        f"    int _dp_t = ({p0} + 1) * ({p0} + 1);\n"
        f"    int _dp_n = {p0};\n"
        f"    slot int _dp_si = _dp_i; slot int _dp_sr = _dp_row; slot int _dp_sc = _dp_col;\n"
        f"    slot int _dp_st = _dp_t; slot int _dp_sn = _dp_n; slot int _dp_sw = _dp_w;\n"
        f"    loop {loop}(_dp_i < _dp_t, _dp_si, _dp_sr, _dp_sc, _dp_st, _dp_sn, _dp_sw);\n"
        f"    return ramRead(100 + {p0} * _dp_w + {p1});\n"
        f"}}\n"
    )


def tabulate_module(module):
    """Rewrite every tabulable recursive FunctionDecl in `module` into its memoizing `while_loop`
    form (a `while_loop` decl + a non-recursive function), in place. Returns the module. Handles
    both the single-index fib family (`detect_tabulable_recursion`) and the 2-arg binomial/Pascal
    DP family (`detect_2arg_dp`). Conservative: a function that doesn't detect+synthesize is left
    untouched."""
    from .lexer import Lexer
    from .parser import Parser

    def _parse_replacement(src, tag):
        lx = Lexer(src, file=tag)
        sub = Parser(lx.tokenize(), file=tag, diagnostics=lx.diagnostics).parse_module()
        return None if lx.diagnostics.has_errors() else sub.items

    new_items = []
    for it in module.items:
        if type(it).__name__ == "FunctionDecl":
            shape = detect_tabulable_recursion(it)
            if shape is not None:
                src = synthesize_tabulation_source(shape)
                if src is not None:
                    items = _parse_replacement(src, f"<tabulate:{it.name}>")
                    if items is not None:
                        new_items.extend(items)   # the while_loop decl + the new function
                        continue
            shape2 = detect_2arg_dp(it)
            if shape2 is not None:
                src = synthesize_2arg_dp_source(shape2)
                if src is not None:
                    items = _parse_replacement(src, f"<tabulate2d:{it.name}>")
                    if items is not None:
                        new_items.extend(items)
                        continue
        new_items.append(it)
    module.items = new_items
    return module
