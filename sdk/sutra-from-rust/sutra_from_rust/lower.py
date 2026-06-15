"""Rust → Sutra lowering pass (MVP).

Models on `sutra-from-ocaml` (the reference frontend) via the Scala/Elixir/
Haskell MVP shape. This first cut proves the toolchain end-to-end for Rust
(the imperative entry of the roadmap): top-level `fn` items lower to Sutra
`function`s, compile, and RUN on the substrate.

Supported now: `fn` items with typed parameters + return (i8…i64/u8…u64/
usize/isize → int, f32/f64 → number, bool → bool); block bodies with `let`
bindings and a tail expression (bare or statement-wrapped); integer/float
literals (numeric suffixes stripped); binary arithmetic/comparison/boolean
operators; `if/else` expression → the defuzz blend; calls; parens. Ownership/
borrowing never reaches the lowering (the MVP value domain is copies of
numbers); `&`/`mut`, structs/enums/match, loops and recursion are later items —
anything unrecognized emits an `UNSUPPORTED-*` marker, and recursion surfaces
as `UNSUPPORTED-RECURSION` until the tail/CPS transforms are ported (never a
silent self-call).
"""
from __future__ import annotations

import pathlib
from typing import Optional

_TYPE_MAP = {
    "i8": "int", "i16": "int", "i32": "int", "i64": "int", "isize": "int",
    "u8": "int", "u16": "int", "u32": "int", "u64": "int", "usize": "int",
    "f32": "number", "f64": "number",
    "bool": "bool",
}
_DEFAULT_TYPE = "int"

# Rust binary operator → Sutra operator.
_OP_MAP = {
    "+": "+", "-": "-", "*": "*", "/": "/", "%": "%",
    "==": "==", "!=": "!=", "<": "<", ">": ">", "<=": "<=", ">=": ">=",
    "&&": "&&", "||": "||",
}

_NUM_SUFFIXES = ("i8", "i16", "i32", "i64", "isize",
                 "u8", "u16", "u32", "u64", "usize", "f32", "f64")

# Enums → tagged axons (the OCaml variant pattern). Prepass fills
# `_ENUMS[name] = {variant: (tag, arity)}` and `_VARIANTS[variant] =
# (enum, tag, arity)` from `enum E { V0(t), V1(t, t), V2 }`. The enum def is
# erased — the runtime shape is a tagged axon `{_tag, _val0, _val1, …}`.
# Construction `E::V(a, b)` is statement-based (`Axon t; t.add("_tag", tag);
# t.add("_val0", a); …`), so constructions anywhere in an expression tree are
# HOISTED to prelude temps and `_ARG_HOIST[node.id]` carries the temp name to
# the use site. `_SUBST` substitutes a match arm's bound payload names to the
# scrutinee's `_val{i}` reads (the OCaml `_MATCH_SUBST` shape).
_ENUMS: dict[str, dict] = {}
_VARIANTS: dict[str, tuple] = {}
_ARG_HOIST: dict[int, str] = {}
_SUBST: dict[str, str] = {}
# Function-scoped counter for hoisted aggregate temps (`_ahN`), so constructions
# across DIFFERENT statements in one function get unique names (a per-statement
# counter collides — `let a = …` and the tail both restart at _ah0). Reset at
# each function.
_HOIST_N: list = [0]
# Structs -> axons (the OCaml record pattern). `_STRUCTS` is the set of struct
# names (the field set is carried by the named axon keys, so no order needed).
# A struct-typed param maps to `Axon`; construction `S { x: a, y: b }` hoists to
# `Axon t; t.add("x", a); t.add("y", b);`; field access `p.x` -> `realvec(
# p.item("x"))` (a raw axon field read collapses arithmetic to ~0 at low dims —
# finding 2026-06-05). Numeric fields only (strings aren't axon fillers).
_STRUCTS: set = set()


def _text(node, src: bytes) -> str:
    return src[node.start_byte:node.end_byte].decode("utf-8")


def _blend(test_src: str, then_src: str, else_src: str) -> str:
    """Sutra strong-defuzz two-way blend — the shared frontend shape."""
    w = f"truth_axis(defuzzy({test_src}))"
    return f"(((1 + {w}) * ({then_src})) + ((1 - {w}) * ({else_src}))) / 2"


def _map_type(node, src: bytes) -> str:
    if node is None:
        return _DEFAULT_TYPE
    text = _text(node, src)
    if text in _ENUMS or text in _STRUCTS:
        return "Axon"
    return _TYPE_MAP.get(text, _DEFAULT_TYPE)


def _struct_construction(node, src: bytes):
    """If `node` is a struct construction `S { x: a, y: b }` (a `struct_expression`
    whose type names a known struct), return (struct_name, [(field, value), …]);
    else None."""
    if node.type != "struct_expression":
        return None
    tid = next((c for c in node.named_children if c.type == "type_identifier"), None)
    flist = next((c for c in node.named_children
                  if c.type == "field_initializer_list"), None)
    if tid is None or flist is None or _text(tid, src) not in _STRUCTS:
        return None
    fields = []
    for fi in flist.named_children:
        if fi.type == "field_initializer":
            fid = next((c for c in fi.named_children
                        if c.type == "field_identifier"), None)
            val = fi.named_children[-1]
            if fid is None:
                return None
            fields.append((_text(fid, src), val))
        elif fi.type == "shorthand_field_initializer":
            # `S { x }` ≡ `S { x: x }` — the field name and the in-scope value
            # are the same identifier; reuse that identifier node as the value.
            ident = next((c for c in fi.named_children
                          if c.type == "identifier"), None)
            if ident is None:
                return None
            fields.append((_text(ident, src), ident))
        else:
            return None  # base (`..rest`) inits are a later item
    return _text(tid, src), fields


def _emit_struct_construction(fields, src: bytes, var: str, indent: str) -> str:
    """Axon-construction statements for a struct bound to `var` (named keys)."""
    stmts = f"{indent}Axon {var};\n"
    for field, val in fields:
        stmts += f'{indent}{var}.add("{field}", {_lower_expr(val, src)});\n'
    return stmts


def _enum_construction(node, src: bytes):
    """If `node` is an enum construction `E::V(a, b)` (a call whose head is a
    `scoped_identifier` naming a known variant), return (variant, [arg_nodes]);
    else None. Detection is call-form only — a BARE `scoped_identifier` is
    ambiguous (it is also a call head and a match-pattern path), and nullary
    variants in value position are a later item, so they are NOT hoisted here."""
    if node.type == "call_expression" and node.named_children:
        head = node.named_children[0]
        if head.type == "scoped_identifier":
            ids = [c for c in head.named_children if c.type == "identifier"]
            if len(ids) == 2 and _text(ids[1], src) in _VARIANTS:
                args_node = next((c for c in node.named_children
                                  if c.type == "arguments"), None)
                args = list(args_node.named_children) if args_node is not None else []
                return _text(ids[1], src), args
    return None


def _emit_enum_construction(variant: str, args, src: bytes, var: str,
                            indent: str) -> str:
    """Tagged-axon construction statements for `variant(args…)` bound to `var`
    (no return — reusable for hoisted temps). Stores `_tag` + `_val0`/`_val1`/…"""
    _enum, tag, _arity = _VARIANTS[variant]
    stmts = f"{indent}Axon {var};\n{indent}{var}.add(\"_tag\", {tag});\n"
    for i, a in enumerate(args):
        stmts += f'{indent}{var}.add("_val{i}", {_lower_expr(a, src)});\n'
    return stmts


def _hoist_enum_constructions(body, src: bytes, indent: str = "    "):
    """Post-order walk: hoist EVERY enum construction to a prelude
    `Axon _ahN; …` group and register `node.id → _ahN` in `_ARG_HOIST` so
    `_lower_expr` emits the temp at the use site (inner constructions resolve
    before outer ones). Returns (prelude, added_ids) or None."""
    prelude: list[str] = []
    added: list[int] = []

    def walk(n):
        for c in n.named_children:
            walk(c)
        ctor = _enum_construction(n, src)
        if ctor is not None:
            variant, args = ctor
            tmp = f"_ah{_HOIST_N[0]}"
            _HOIST_N[0] += 1
            prelude.append(_emit_enum_construction(variant, args, src, tmp, indent))
            _ARG_HOIST[n.id] = tmp
            added.append(n.id)
            return
        sctor = _struct_construction(n, src)
        if sctor is not None:
            _name, fields = sctor
            tmp = f"_ah{_HOIST_N[0]}"
            _HOIST_N[0] += 1
            prelude.append(_emit_struct_construction(fields, src, tmp, indent))
            _ARG_HOIST[n.id] = tmp
            added.append(n.id)

    walk(body)
    if not added:
        return None
    return "".join(prelude), added


def _strip_suffix(lit: str) -> str:
    text = lit.replace("_", "")
    for suf in _NUM_SUFFIXES:
        if text.endswith(suf):
            return text[: -len(suf)]
    return text


def _contains_self_call(node, name: str, src: bytes) -> bool:
    if node.type == "call_expression" and node.named_children:
        fn = node.named_children[0]
        if fn.type == "identifier" and _text(fn, src) == name:
            return True
    return any(_contains_self_call(c, name, src) for c in node.named_children)


# Sutra comparison op → its negation (halt condition → loop continue condition).
_NEG_CMP = {"==": "!=", "!=": "==", "<": ">=", ">": "<=", "<=": ">", ">=": "<"}


def _self_call_args(node, name: str, arity: int, src: bytes):
    """If `node` is `name(a1, …, a{arity})`, return the arg nodes; else None."""
    if node.type != "call_expression" or not node.named_children:
        return None
    fn = node.named_children[0]
    if fn.type != "identifier" or _text(fn, src) != name:
        return None
    args_node = next((c for c in node.named_children if c.type == "arguments"), None)
    args = list(args_node.named_children) if args_node is not None else []
    return args if len(args) == arity else None


def _negate_cond(cond, src: bytes) -> str:
    """Negate a halt condition into the loop's continue condition (the OCaml
    `_negate_cond` shape): a single comparison inverts via `_NEG_CMP`, else `!(…)`."""
    if cond.type == "binary_expression":
        op = cond.child_by_field_name("operator")
        left = cond.child_by_field_name("left")
        right = cond.child_by_field_name("right")
        if op is not None and left is not None and right is not None:
            sop = _OP_MAP.get(_text(op, src))
            neg = _NEG_CMP.get(sop) if sop else None
            if neg is not None:
                return f"{_lower_expr(left, src)} {neg} {_lower_expr(right, src)}"
    return f"!({_lower_expr(cond, src)})"


def _try_lower_tail_recursive(name: str, params, ret: str, body, src: bytes):
    """Lower a TAIL-recursive `fn f(p…) { if COND { BASE } else { f(a…) } }` to a
    declared Sutra `while_loop` (the OCaml/Scala/F# shape ported). Each arm must
    be a single tail expression. Returns the emitted Sutra or None."""
    if body.type != "if_expression":
        return None
    kids = body.named_children
    if len(kids) < 2:
        return None
    cond = kids[0]
    then_blk = kids[1]
    else_clause = next((c for c in kids if c.type == "else_clause"), None)
    if else_clause is None or not else_clause.named_children:
        return None
    then_lets, then_tail = _block_value(then_blk, src)
    else_lets, else_tail = _block_value(else_clause.named_children[0], src)
    if then_lets or else_lets or then_tail is None or else_tail is None:
        return None
    arity = len(params)
    then_args = _self_call_args(then_tail, name, arity, src)
    else_args = _self_call_args(else_tail, name, arity, src)
    if (then_args is None) == (else_args is None):
        return None
    if else_args is not None:
        cont = _negate_cond(cond, src)
        rec_args, base = else_args, then_tail
    else:
        cont = _lower_expr(cond, src)
        rec_args, base = then_args, else_tail

    loop_name = f"_rec_{name}"
    state_decls = ", ".join(f"{ty} {nm} = 0" for nm, ty in params)
    temp_decls = "".join(f"    {ty} _t{i} = {_lower_expr(arg, src)};\n"
                         for i, ((_nm, ty), arg) in enumerate(zip(params, rec_args)))
    assigns = "".join(f"    {nm} = _t{i};\n" for i, (nm, _ty) in enumerate(params))
    loop_decl = f"while_loop {loop_name}({cont}, {state_decls}) {{\n{temp_decls}{assigns}}}\n"
    slot_lines = "".join(f"    slot {ty} _{nm}_r = {nm};\n" for nm, ty in params)
    slot_args = ", ".join(f"_{nm}_r" for nm, _ty in params)
    writeback = "".join(f"    {nm} = _{nm}_r;\n" for nm, _ty in params)
    params_src = ", ".join(f"{ty} {nm}" for nm, ty in params)
    base_src = _lower_expr(base, src)
    fn = (
        f"function {ret} {name}({params_src}) {{\n"
        f"{slot_lines}"
        f"    loop {loop_name}({cont}, {slot_args});\n"
        f"{writeback}"
        f"    return {base_src};\n"
        f"}}\n"
    )
    return loop_decl + fn


# Associative + commutative combine ops for the non-tail fold transform.
_FOLD_OPS = {"+", "*"}


def _contains_identifier(node, ident: str, src: bytes) -> bool:
    if node.type == "identifier" and _text(node, src) == ident:
        return True
    return any(_contains_identifier(c, ident, src) for c in node.named_children)


def _try_lower_foldable_nontail(name: str, params, ret: str, body, src: bytes):
    """CPS / accumulator transform for a FOLDABLE non-tail recursion
    `fn f(n) { if COND { BASE } else { LEAF <OP> f(REC) } }` (single param, OP in
    `_FOLD_OPS`): the pending call-stack work is reified as an accumulator carried
    by a Sutra `while_loop` trampoline — the OCaml/Scala shape ported. BASE is
    evaluated before the loop at the INITIAL param, so a param-dependent BASE is
    rejected (→ None). Returns loop decl + function, or None."""
    if body.type != "if_expression" or len(params) != 1:
        return None
    kids = body.named_children
    if len(kids) < 2:
        return None
    cond = kids[0]
    then_blk = kids[1]
    else_clause = next((c for c in kids if c.type == "else_clause"), None)
    if else_clause is None or not else_clause.named_children:
        return None
    then_lets, then_tail = _block_value(then_blk, src)
    else_lets, else_tail = _block_value(else_clause.named_children[0], src)
    if then_lets or else_lets or then_tail is None or else_tail is None:
        return None

    def foldable(node):
        if node.type != "binary_expression":
            return None
        op = node.child_by_field_name("operator")
        left = node.child_by_field_name("left")
        right = node.child_by_field_name("right")
        if op is None or left is None or right is None:
            return None
        if _text(op, src) not in _FOLD_OPS:
            return None
        lc = _self_call_args(left, name, 1, src)
        rc = _self_call_args(right, name, 1, src)
        if (lc is None) == (rc is None):
            return None  # exactly one operand must be the self-call
        return (_text(op, src), right, lc[0]) if lc is not None \
            else (_text(op, src), left, rc[0])

    fold_then, fold_else = foldable(then_tail), foldable(else_tail)
    if (fold_else is None) == (fold_then is None):
        return None
    if fold_else is not None:
        cont = _negate_cond(cond, src)
        op_text, leaf, rec_arg = fold_else
        base = then_tail
    else:
        cont = _lower_expr(cond, src)
        op_text, leaf, rec_arg = fold_then
        base = else_tail

    pname, pty = params[0][0], params[0][1]
    if _contains_identifier(base, pname, src):
        return None  # param-dependent base — the transform would mis-evaluate it
    sutra_op = _OP_MAP.get(op_text, op_text)
    loop_name = f"_rec_{name}"
    leaf_src = _lower_expr(leaf, src)
    rec_src = _lower_expr(rec_arg, src)
    base_src = _lower_expr(base, src)
    if any("UNSUPPORTED" in s for s in (leaf_src, rec_src, base_src, cont)):
        return None
    loop_decl = (
        f"while_loop {loop_name}({cont}, {pty} {pname} = 0, {pty} _acc = 0) {{\n"
        f"    {pty} _t_n = {rec_src};\n"
        f"    {pty} _t_acc = _acc {sutra_op} {leaf_src};\n"
        f"    {pname} = _t_n;\n"
        f"    _acc = _t_acc;\n"
        f"}}\n"
    )
    fn = (
        f"function {ret} {name}({pty} {pname}) {{\n"
        f"    {pty} _acc = {base_src};\n"
        f"    slot {pty} _{pname}_r = {pname};\n"
        f"    slot {pty} _acc_r = _acc;\n"
        f"    loop {loop_name}({cont}, _{pname}_r, _acc_r);\n"
        f"    return _acc_r;\n"
        f"}}\n"
    )
    return loop_decl + fn


def _collect_used_names(node, src: bytes, names: set) -> list:
    """Identifiers from `names` used anywhere in `node`, in first-seen order.
    Used to pick the `while`-loop state: the in-scope locals/params the loop's
    condition and body touch (which must be threaded as Sutra loop state, since
    the hoisted `while_loop` is a top-level decl and sees only its params)."""
    found: list = []

    def walk(n):
        if n.type == "identifier":
            t = _text(n, src)
            if t in names and t not in found:
                found.append(t)
        for c in n.named_children:
            walk(c)

    walk(node)
    return found


def _lower_assign(a, src: bytes, mutable: set):
    """Lower a Rust assignment statement to a Sutra `lhs = rhs` body expression
    (no indent/semicolon). Handles plain `x = rhs` (`assignment_expression`) and
    compound `x op= rhs` (`compound_assignment_expr`, desugared to `x = (x op
    rhs)`). The target must be a `mut` identifier. Returns the string or None if
    the node is not a (compound-)assignment to a mutable local."""
    if a.type not in ("assignment_expression", "compound_assignment_expr"):
        return None
    akids = a.named_children
    if len(akids) < 2 or akids[0].type != "identifier":
        return None
    lhs = _text(akids[0], src)
    if lhs not in mutable:
        return None  # assigning a non-`mut` binding — out of shape
    rhs = _lower_expr(akids[-1], src)
    if "UNSUPPORTED" in rhs:
        return None
    if a.type == "assignment_expression":
        return f"{lhs} = {rhs}"
    op = a.child_by_field_name("operator")
    if op is None:
        return None
    sop = _OP_MAP.get(_text(op, src)[:-1])  # `+=` -> `+`
    if sop is None:
        return None
    return f"{lhs} = ({lhs} {sop} {rhs})"


def _lower_while_rust(node, src: bytes, scope_ty: dict, mutable: set, idx: int):
    """Lower a Rust `while COND { BODY }` to a hoisted Sutra `while_loop` + the
    `slot`/`loop`/write-back call sequence — the OCaml `_lower_while` shape. State
    = the in-scope names (locals + params) the cond/body touch, cond-first; only
    `mut` locals are written back (params/immutable locals are read-only). The
    body is a sequence of `lhs = rhs;` / `lhs op= rhs;` assignments (sequential
    update, the OCaml while-body shape). Returns (loop_decl, call_block) or None
    if outside this shape."""
    cond = node.child_by_field_name("condition")
    body = node.child_by_field_name("body")
    if cond is None:
        cond = node.named_children[0] if node.named_children else None
    if body is None:
        body = next((c for c in node.named_children if c.type == "block"), None)
    if cond is None or body is None:
        return None
    in_scope = set(scope_ty)
    used_cond = _collect_used_names(cond, src, in_scope)
    used_body = _collect_used_names(body, src, in_scope)
    state = used_cond + [v for v in used_body if v not in used_cond]
    if not state:
        return None
    cond_src = _lower_expr(cond, src)
    if "UNSUPPORTED" in cond_src:
        return None
    body_lines = ""
    for st in body.named_children:
        if st.type != "expression_statement" or not st.named_children:
            return None
        line = _lower_assign(st.named_children[0], src, mutable)
        if line is None:
            return None
        body_lines += f"    {line};\n"
    loop_name = f"_while{idx}"
    state_decls = ", ".join(f"{scope_ty[v]} {v} = 0" for v in state)
    loop_decl = (f"while_loop {loop_name}({cond_src}, {state_decls}) {{\n"
                 f"{body_lines}}}\n")
    slot_lines = "".join(f"    slot {scope_ty[v]} _{v}_r = {v};\n" for v in state)
    slot_args = ", ".join(f"_{v}_r" for v in state)
    writeback = "".join(f"    {v} = _{v}_r;\n" for v in state if v in mutable)
    call = (f"{slot_lines}"
            f"    loop {loop_name}({cond_src}, {slot_args});\n"
            f"{writeback}")
    return loop_decl, call


def _loop_break_guard(body, src: bytes):
    """If `body` (a loop's `block`) opens with `if COND { break; }`, return
    (break_cond_node, [remaining body statements]); else None. Only the single
    leading-break shape is in scope (`loop { if C { break; } REST }` ≡
    `while !C { REST }`) — a `break` anywhere else stays out of shape."""
    stmts = list(body.named_children)
    if not stmts or stmts[0].type != "expression_statement" or not stmts[0].named_children:
        return None
    head = stmts[0].named_children[0]
    if head.type != "if_expression":
        return None
    kids = head.named_children
    if len(kids) < 2:
        return None
    cond = kids[0]
    cons = next((c for c in kids if c.type == "block"), None)
    # No `else` arm, and the consequence is exactly one bare `break;`.
    if any(c.type == "else_clause" for c in kids) or cons is None:
        return None
    cstmts = cons.named_children
    if (len(cstmts) != 1 or cstmts[0].type != "expression_statement"
            or not cstmts[0].named_children
            or cstmts[0].named_children[0].type != "break_expression"):
        return None
    # A `break` surviving in the remaining body would be unsupported.
    rest = stmts[1:]
    if any(_contains_break(s) for s in rest):
        return None
    return cond, rest


def _contains_break(node) -> bool:
    if node.type == "break_expression":
        return True
    return any(_contains_break(c) for c in node.named_children)


def _lower_loop_rust(node, src: bytes, scope_ty: dict, mutable: set, idx: int):
    """Lower a Rust `loop { if COND { break; } BODY }` to a Sutra `while_loop`
    on the continue condition `!COND` — the `_lower_while_rust` shape with the
    halt-guard hoisted out of the body. Returns (loop_decl, call_block) or None
    if outside the single-leading-break shape."""
    body = next((c for c in node.named_children if c.type == "block"), None)
    if body is None:
        return None
    guard = _loop_break_guard(body, src)
    if guard is None:
        return None
    break_cond, rest = guard
    cont_src = _negate_cond(break_cond, src)
    if "UNSUPPORTED" in cont_src:
        return None
    in_scope = set(scope_ty)
    used_cond = _collect_used_names(break_cond, src, in_scope)
    used_body = []
    for st in rest:
        for v in _collect_used_names(st, src, in_scope):
            if v not in used_body:
                used_body.append(v)
    state = used_cond + [v for v in used_body if v not in used_cond]
    if not state:
        return None
    body_lines = ""
    for st in rest:
        if st.type != "expression_statement" or not st.named_children:
            return None
        line = _lower_assign(st.named_children[0], src, mutable)
        if line is None:
            return None
        body_lines += f"    {line};\n"
    loop_name = f"_loop{idx}"
    state_decls = ", ".join(f"{scope_ty[v]} {v} = 0" for v in state)
    loop_decl = (f"while_loop {loop_name}({cont_src}, {state_decls}) {{\n"
                 f"{body_lines}}}\n")
    slot_lines = "".join(f"    slot {scope_ty[v]} _{v}_r = {v};\n" for v in state)
    slot_args = ", ".join(f"_{v}_r" for v in state)
    writeback = "".join(f"    {v} = _{v}_r;\n" for v in state if v in mutable)
    call = (f"{slot_lines}"
            f"    loop {loop_name}({cont_src}, {slot_args});\n"
            f"{writeback}")
    return loop_decl, call


def _try_lower_imperative(name: str, params, ret: str, block, src: bytes):
    """Lower an imperative `fn` body — leading `let [mut]` bindings, `while`
    loops (-> hoisted Sutra `while_loop`), top-level `lhs = rhs;` reassignments,
    and a bare tail expression. Fires only when the block contains a `while`
    (so the recursion/expression paths still own the functional shapes). Returns
    loop decls + the function source, or None if any part is out of shape."""
    children = list(block.named_children)
    has_loop = any(
        c.type == "expression_statement" and c.named_children
        and c.named_children[0].type in ("while_expression", "loop_expression")
        for c in children)
    if not has_loop:
        return None
    if not children or children[-1].type in ("let_declaration", "expression_statement"):
        return None  # needs a bare tail value expression
    tail_node = children[-1]
    scope_ty = {nm: ty for nm, ty in params}
    mutable: set = set()
    body = ""
    loop_decls = ""
    idx = 0
    for c in children[:-1]:
        if c.type == "let_declaration":
            kids = c.named_children
            ident = next((k for k in kids if k.type == "identifier"), None)
            if ident is None:
                return None  # pattern let — later item
            nm = _text(ident, src)
            ty_node = next((k for k in kids if k.type == "primitive_type"), None)
            ty = _map_type(ty_node, src) if ty_node is not None else _DEFAULT_TYPE
            value = kids[-1]
            val_src = _lower_expr(value, src)
            if "UNSUPPORTED" in val_src:
                return None
            body += f"    {ty} {nm} = {val_src};\n"
            scope_ty[nm] = ty
            if any(k.type == "mutable_specifier" for k in kids):
                mutable.add(nm)
        elif c.type == "expression_statement" and c.named_children:
            inner = c.named_children[0]
            if inner.type in ("while_expression", "loop_expression"):
                if inner.type == "while_expression":
                    res = _lower_while_rust(inner, src, scope_ty, mutable, idx)
                else:
                    res = _lower_loop_rust(inner, src, scope_ty, mutable, idx)
                if res is None:
                    return None
                decl, call = res
                loop_decls += decl
                body += call
                idx += 1
            elif inner.type in ("assignment_expression", "compound_assignment_expr"):
                line = _lower_assign(inner, src, mutable)
                if line is None:
                    return None
                body += f"    {line};\n"
            else:
                return None
        else:
            return None
    tail_src = _lower_expr(tail_node, src)
    if "UNSUPPORTED" in tail_src:
        return None
    params_src = ", ".join(f"{ty} {nm}" for nm, ty in params)
    fn = (f"function {ret} {name}({params_src}) {{\n"
          f"{body}"
          f"    return {tail_src};\n"
          f"}}\n")
    return loop_decls + fn


def _block_value(block, src: bytes):
    """Split a `block` into (let_declarations, tail_expr_node). The tail
    expression may be bare or wrapped in an `expression_statement`."""
    lets, tail = [], None
    for c in block.named_children:
        if c.type == "let_declaration":
            lets.append(c)
        elif c.type == "expression_statement":
            tail = c.named_children[0] if c.named_children else None
        else:
            tail = c
    return lets, tail


def _lower_expr(node, src: bytes) -> str:
    if _ARG_HOIST and node.id in _ARG_HOIST:
        return _ARG_HOIST[node.id]
    t = node.type
    if t == "integer_literal":
        return _strip_suffix(_text(node, src))
    if t == "float_literal":
        return _strip_suffix(_text(node, src))
    if t == "identifier":
        text = _text(node, src)
        return _SUBST.get(text, text)
    if t == "boolean_literal":
        return _text(node, src)
    if t == "parenthesized_expression":
        inner = node.named_children[0] if node.named_children else None
        return f"({_lower_expr(inner, src)})" if inner is not None else "0"
    if t == "unary_expression":
        kids = node.named_children
        if kids and _text(node, src).startswith("-"):
            return f"(0 - {_lower_expr(kids[0], src)})"
        return f"/* UNSUPPORTED-UNARY: {_text(node, src)} */"
    if t == "binary_expression":
        op = node.child_by_field_name("operator")
        left = node.child_by_field_name("left")
        right = node.child_by_field_name("right")
        if op is None or left is None or right is None:
            return "/* UNSUPPORTED-EXPR: malformed binary_expression */"
        sop = _OP_MAP.get(_text(op, src))
        if sop is None:
            return f"/* UNSUPPORTED-OP: {_text(op, src)} */"
        return f"({_lower_expr(left, src)} {sop} {_lower_expr(right, src)})"
    if t == "if_expression":
        kids = node.named_children
        if len(kids) < 2:
            return "/* UNSUPPORTED-EXPR: malformed if */"
        cond_src = _lower_expr(kids[0], src)
        then_blk = kids[1]
        else_clause = next((c for c in kids if c.type == "else_clause"), None)
        _lets_t, then_tail = _block_value(then_blk, src)
        if _lets_t or then_tail is None:
            return "/* UNSUPPORTED-EXPR: if-arm with statements (later item) */"
        then_src = _lower_expr(then_tail, src)
        else_src = "0"
        if else_clause is not None and else_clause.named_children:
            _lets_e, else_tail = _block_value(else_clause.named_children[0], src)
            if _lets_e or else_tail is None:
                return "/* UNSUPPORTED-EXPR: else-arm with statements (later item) */"
            else_src = _lower_expr(else_tail, src)
        return _blend(cond_src, then_src, else_src)
    if t == "call_expression":
        kids = node.named_children
        if not kids:
            return "/* UNSUPPORTED-EXPR: empty call */"
        if _enum_construction(node, src) is not None:
            # A construction reaching here was not hoisted — emitting `E::V(…)`
            # would mislower (no such Sutra function). Surface the gap.
            return "/* UNSUPPORTED-CONSTRUCTION: enum value outside a hoistable position */"
        fn = kids[0]
        if fn.type != "identifier":
            return f"/* UNSUPPORTED-EXPR: non-identifier callee ({fn.type}) */"
        args_node = next((c for c in kids if c.type == "arguments"), None)
        args = [_lower_expr(a, src)
                for a in (args_node.named_children if args_node is not None else [])]
        return f"{_text(fn, src)}({', '.join(args)})"
    if t == "match_expression":
        # A match only lowers as a function-body tail (it needs the `_vtag` /
        # `_val{i}` binding statements — see `_lower_match_stmts`). Nested in a
        # larger expression it would need those bindings hoisted: a later item.
        return "/* UNSUPPORTED-MATCH: match nested in an expression (use as the function tail) */"
    if t == "field_expression":
        # Struct field read `p.x` -> the axon item read, projected to a clean
        # number-vector (realvec — raw fillers carry crosstalk, finding 2026-06-05).
        kids = node.named_children
        if len(kids) == 2 and kids[1].type == "field_identifier":
            return f'realvec({_lower_expr(kids[0], src)}.item("{_text(kids[1], src)}"))'
        return "/* UNSUPPORTED-EXPR: field_expression arity */"
    if t == "struct_expression" and _struct_construction(node, src) is not None:
        # A construction reaching here was not hoisted — surface the gap.
        return "/* UNSUPPORTED-CONSTRUCTION: struct value outside a hoistable position */"
    return f"/* UNSUPPORTED-EXPR: {t} */"


def _lower_match_stmts(node, src: bytes, indent: str = "    "):
    """`match scrut { E::V(x) => r, … }` → (binding statements, result expr),
    the OCaml variant-match shape. Binds `int _vtag = realvec(scrut.item("_tag"))`
    and `int _val{i} = realvec(scrut.item("_val{i}"))` (i over the max arity) to
    clean number-vector LOCALS first — the inline repeated `realvec(...)` reads
    do not project crisply (measured: inline gave 3.5, bound locals give 2.0).
    Then a nested defuzz blend tests `_vtag == tag`; payload names substitute to
    the `_val{i}` locals. Last arm = base (exhaustive enum match); a trailing
    `_` is also a base. Returns (stmts, expr) or (None, marker) on UNSUPPORTED.
    Numeric payloads only."""
    kids = node.named_children
    scrut = kids[0]
    if scrut.type != "identifier":
        return None, "/* UNSUPPORTED-MATCH: non-identifier scrutinee (later item) */"
    scrut_src = _text(scrut, src)
    block = next((c for c in kids if c.type == "match_block"), None)
    if block is None:
        return None, "/* UNSUPPORTED-MATCH: no match block */"
    parsed = []
    max_arity = 0
    for arm in block.named_children:
        if arm.type != "match_arm":
            continue
        pat = next((c for c in arm.named_children if c.type == "match_pattern"), None)
        res = arm.named_children[-1]
        if pat is None or not pat.named_children:
            return None, "/* UNSUPPORTED-MATCH: malformed arm */"
        inner = pat.named_children[0]
        binds: list[tuple[str, str]] = []
        if inner.type == "tuple_struct_pattern":
            scoped = next((c for c in inner.named_children
                           if c.type == "scoped_identifier"), None)
            if scoped is None:
                return None, "/* UNSUPPORTED-MATCH: non-scoped variant pattern */"
            ids = [c for c in scoped.named_children if c.type == "identifier"]
            variant = _text(ids[-1], src) if ids else None
            if variant not in _VARIANTS:
                return None, f"/* UNSUPPORTED-MATCH: unknown variant {variant} */"
            tag = _VARIANTS[variant][1]
            payload = [c for c in inner.named_children if c.type == "identifier"]
            max_arity = max(max_arity, len(payload))
            for i, p in enumerate(payload):
                binds.append((_text(p, src), f"_val{i}"))
            test = f"(_vtag == {tag})"
        elif inner.type == "identifier" and _text(inner, src) in _VARIANTS:
            test = f"(_vtag == {_VARIANTS[_text(inner, src)][1]})"
        elif inner.type in ("wildcard_pattern", "identifier"):
            test = None  # `_` (or a catch-all binding) — the base
        else:
            return None, f"/* UNSUPPORTED-MATCH: pattern {inner.type} */"
        for nm, sub in binds:
            _SUBST[nm] = sub
        try:
            res_src = _lower_expr(res, src)
        finally:
            for nm, _sub in binds:
                _SUBST.pop(nm, None)
        parsed.append((test, res_src))
    if not parsed:
        return None, "/* UNSUPPORTED-MATCH: no arms */"
    stmts = f'{indent}int _vtag = realvec({scrut_src}.item("_tag"));\n'
    for i in range(max_arity):
        stmts += f'{indent}int _val{i} = realvec({scrut_src}.item("_val{i}"));\n'
    expr = parsed[-1][1]  # last arm = base (exhaustive)
    for test, res in reversed(parsed[:-1]):
        expr = res if test is None else _blend(test, res, expr)
    return stmts, expr


def _lower_function(item, src: bytes) -> str:
    _HOIST_N[0] = 0  # per-function unique aggregate-temp counter
    kids = item.named_children
    name_node = next((c for c in kids if c.type == "identifier"), None)
    if name_node is None:
        return "// UNSUPPORTED-FN: no name\n"
    name = _text(name_node, src)
    params: list[tuple[str, str]] = []
    params_node = next((c for c in kids if c.type == "parameters"), None)
    if params_node is not None:
        for p in params_node.named_children:
            if p.type != "parameter":
                return f"// UNSUPPORTED-FN: '{name}' has a non-plain parameter ({p.type})\n"
            pid = next((c for c in p.named_children if c.type == "identifier"), None)
            pty = next((c for c in p.named_children
                        if c.type in ("primitive_type", "type_identifier")), None)
            if pid is None:
                return f"// UNSUPPORTED-FN: '{name}' has a pattern parameter\n"
            params.append((_text(pid, src), _map_type(pty, src)))
    ret_node = next((c for c in kids
                     if c.type in ("primitive_type", "type_identifier")), None)
    ret = _map_type(ret_node, src)
    block = next((c for c in kids if c.type == "block"), None)
    if block is None:
        return f"// UNSUPPORTED-FN: '{name}' has no body\n"
    lets, tail = _block_value(block, src)
    if tail is None:
        return f"// UNSUPPORTED-FN: '{name}' has no tail expression\n"
    if not lets and params and tail.type == "if_expression":
        rec = _try_lower_tail_recursive(name, params, ret, tail, src)
        if rec is not None:
            return rec
        fold = _try_lower_foldable_nontail(name, params, ret, tail, src)
        if fold is not None:
            return fold
    imperative = _try_lower_imperative(name, params, ret, block, src)
    if imperative is not None:
        return imperative
    if _contains_self_call(block, name, src):
        # Recursion outside the supported tail/foldable shapes — a plain
        # self-call would not terminate through the fuzzy-if blend. Surface it.
        return (f"// UNSUPPORTED-RECURSION: '{name}' is recursive but not the "
                f"tail-accumulator or foldable non-tail shape\n")
    stmts = ""
    for ld in lets:
        ld_kids = ld.named_children
        if len(ld_kids) < 2 or ld_kids[0].type != "identifier":
            return f"// UNSUPPORTED-FN: '{name}' has a pattern let (later item)\n"
        value = ld_kids[-1]
        nm = _text(ld_kids[0], src)
        # A struct/enum construction let constructs DIRECTLY into the bound name
        # (no redundant temp), the OCaml record-let shape.
        sctor = _struct_construction(value, src)
        if sctor is not None:
            stmts += _emit_struct_construction(sctor[1], src, nm, "    ")
            continue
        ector = _enum_construction(value, src)
        if ector is not None:
            stmts += _emit_enum_construction(ector[0], ector[1], src, nm, "    ")
            continue
        ty_node = next((c for c in ld_kids if c.type == "primitive_type"), None)
        ty = _map_type(ty_node, src) if ty_node is not None else _DEFAULT_TYPE
        stmts += _stmt_with_hoist(value, src, f"    {ty} {nm} = {{expr}};\n")
    params_src = ", ".join(f"{ty} {nm}" for nm, ty in params)
    if tail.type == "match_expression":
        # A variant match as the function tail emits its `_vtag` / `_val{i}`
        # binding statements before the blend (the OCaml shape).
        match_stmts, match_expr = _lower_match_stmts(tail, src)
        if match_stmts is None:
            body_tail = f"    return {match_expr};\n"  # UNSUPPORTED marker
        else:
            body_tail = match_stmts + f"    return {match_expr};\n"
    else:
        body_tail = _stmt_with_hoist(tail, src, "    return {expr};\n")
    return (f"function {ret} {name}({params_src}) {{\n"
            f"{stmts}"
            f"{body_tail}"
            f"}}\n")


def _stmt_with_hoist(node, src: bytes, template: str, indent: str = "    ") -> str:
    """Lower `node` as a statement (`template` has one `{expr}` slot), hoisting
    any enum constructions inside it to a prelude first."""
    deep = _hoist_enum_constructions(node, src, indent)
    if deep is None:
        return template.format(expr=_lower_expr(node, src))
    prelude, added = deep
    try:
        expr = _lower_expr(node, src)
    finally:
        for nid in added:
            _ARG_HOIST.pop(nid, None)
    return prelude + template.format(expr=expr)


def lower(source: str, source_path: Optional[pathlib.Path] = None) -> str:
    """Rust source string → Sutra source string."""
    import tree_sitter
    import tree_sitter_rust as tsr

    lang = tree_sitter.Language(tsr.language())
    parser = tree_sitter.Parser(lang)
    src = source.encode("utf-8")
    tree = parser.parse(src)

    # Prepass: collect enums (name → {variant: (tag, arity)}) and the inverse
    # variant map. Enum defs are erased — the runtime shape is a tagged axon.
    _ENUMS.clear()
    _VARIANTS.clear()
    _ARG_HOIST.clear()
    _SUBST.clear()
    _STRUCTS.clear()
    for child in tree.root_node.named_children:
        if child.type == "struct_item":
            tid = next((c for c in child.named_children
                        if c.type == "type_identifier"), None)
            if tid is not None:
                _STRUCTS.add(_text(tid, src))
        if child.type == "enum_item":
            name_node = next((c for c in child.named_children
                              if c.type == "type_identifier"), None)
            vlist = next((c for c in child.named_children
                          if c.type == "enum_variant_list"), None)
            if name_node is None or vlist is None:
                continue
            ename = _text(name_node, src)
            variants: dict = {}
            tag = 0
            for v in vlist.named_children:
                if v.type != "enum_variant":
                    continue
                vid = next((c for c in v.named_children
                            if c.type == "identifier"), None)
                fields = next((c for c in v.named_children
                               if c.type == "ordered_field_declaration_list"), None)
                arity = len([c for c in fields.named_children]) if fields else 0
                if vid is not None:
                    variants[_text(vid, src)] = (tag, arity)
                    _VARIANTS[_text(vid, src)] = (ename, tag, arity)
                    tag += 1
            _ENUMS[ename] = variants

    out = ["// Generated by sutra-from-rust. See sdk/sutra-from-rust/README.md.\n"]
    for child in tree.root_node.named_children:
        if child.type == "function_item":
            out.append(_lower_function(child, src))
        # structs/impls/use are later items
    return "\n".join(out)
