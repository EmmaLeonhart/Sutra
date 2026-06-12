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


def _text(node, src: bytes) -> str:
    return src[node.start_byte:node.end_byte].decode("utf-8")


def _blend(test_src: str, then_src: str, else_src: str) -> str:
    """Sutra strong-defuzz two-way blend — the shared frontend shape."""
    w = f"truth_axis(defuzzy({test_src}))"
    return f"(((1 + {w}) * ({then_src})) + ((1 - {w}) * ({else_src}))) / 2"


def _map_type(node, src: bytes) -> str:
    if node is None:
        return _DEFAULT_TYPE
    return _TYPE_MAP.get(_text(node, src), _DEFAULT_TYPE)


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
    t = node.type
    if t == "integer_literal":
        return _strip_suffix(_text(node, src))
    if t == "float_literal":
        return _strip_suffix(_text(node, src))
    if t == "identifier":
        return _text(node, src)
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
        fn = kids[0]
        if fn.type != "identifier":
            return f"/* UNSUPPORTED-EXPR: non-identifier callee ({fn.type}) */"
        args_node = next((c for c in kids if c.type == "arguments"), None)
        args = [_lower_expr(a, src)
                for a in (args_node.named_children if args_node is not None else [])]
        return f"{_text(fn, src)}({', '.join(args)})"
    return f"/* UNSUPPORTED-EXPR: {t} */"


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
            pty = next((c for c in p.named_children if c.type == "primitive_type"), None)
            if pid is None:
                return f"// UNSUPPORTED-FN: '{name}' has a pattern parameter\n"
            params.append((_text(pid, src), _map_type(pty, src)))
    ret_node = next((c for c in kids if c.type == "primitive_type"), None)
    ret = _map_type(ret_node, src)
    block = next((c for c in kids if c.type == "block"), None)
    if block is None:
        return f"// UNSUPPORTED-FN: '{name}' has no body\n"
    if _contains_self_call(block, name, src):
        return (f"// UNSUPPORTED-RECURSION: '{name}' is recursive "
                f"(transforms not yet ported)\n")
    lets, tail = _block_value(block, src)
    if tail is None:
        return f"// UNSUPPORTED-FN: '{name}' has no tail expression\n"
    stmts = ""
    for ld in lets:
        ld_kids = ld.named_children
        if len(ld_kids) < 2 or ld_kids[0].type != "identifier":
            return f"// UNSUPPORTED-FN: '{name}' has a pattern let (later item)\n"
        ty_node = next((c for c in ld_kids if c.type == "primitive_type"), None)
        ty = _map_type(ty_node, src) if ty_node is not None else _DEFAULT_TYPE
        stmts += f"    {ty} {_text(ld_kids[0], src)} = {_lower_expr(ld_kids[-1], src)};\n"
    params_src = ", ".join(f"{ty} {nm}" for nm, ty in params)
    return (f"function {ret} {name}({params_src}) {{\n"
            f"{stmts}"
            f"    return {_lower_expr(tail, src)};\n"
            f"}}\n")


def lower(source: str, source_path: Optional[pathlib.Path] = None) -> str:
    """Rust source string → Sutra source string."""
    import tree_sitter
    import tree_sitter_rust as tsr

    lang = tree_sitter.Language(tsr.language())
    parser = tree_sitter.Parser(lang)
    src = source.encode("utf-8")
    tree = parser.parse(src)

    out = ["// Generated by sutra-from-rust. See sdk/sutra-from-rust/README.md.\n"]
    for child in tree.root_node.named_children:
        if child.type == "function_item":
            out.append(_lower_function(child, src))
        # structs/enums/impls/use are later items
    return "\n".join(out)
