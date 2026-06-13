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
    if text in _ENUMS:
        return "Axon"
    return _TYPE_MAP.get(text, _DEFAULT_TYPE)


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
            tmp = f"_ah{len(added)}"
            prelude.append(_emit_enum_construction(variant, args, src, tmp, indent))
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
    if _contains_self_call(block, name, src):
        # Recursion outside the supported tail shape — a plain self-call would
        # not terminate through the fuzzy-if blend. Surface the gap.
        return (f"// UNSUPPORTED-RECURSION: '{name}' is recursive but not the "
                f"tail-accumulator shape\n")
    stmts = ""
    for ld in lets:
        ld_kids = ld.named_children
        if len(ld_kids) < 2 or ld_kids[0].type != "identifier":
            return f"// UNSUPPORTED-FN: '{name}' has a pattern let (later item)\n"
        value = ld_kids[-1]
        # An enum-construction let binds an Axon; otherwise the annotated /
        # default scalar type.
        if _enum_construction(value, src) is not None:
            ty = "Axon"
        else:
            ty_node = next((c for c in ld_kids if c.type == "primitive_type"), None)
            ty = _map_type(ty_node, src) if ty_node is not None else _DEFAULT_TYPE
        stmts += _stmt_with_hoist(value, src, f"    {ty} {_text(ld_kids[0], src)} = {{expr}};\n")
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
    for child in tree.root_node.named_children:
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
