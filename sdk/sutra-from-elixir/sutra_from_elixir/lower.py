"""Elixir → Sutra lowering pass (MVP).

Models on `sutra-from-ocaml` (the reference frontend) via the `sutra-from-scala`
MVP shape. This first cut proves the toolchain end-to-end for Elixir (the BEAM
entry of the roadmap): `defmodule` functions lower to Sutra `function`s, compile,
and RUN on the substrate.

tree-sitter-elixir is homogeneous: `defmodule` / `def` / `if` are all `call`
nodes whose first child is the keyword identifier. Supported now: a single
`defmodule` whose `def`s become top-level functions (Elixir module-internal
calls are bare, so no name prefixing is needed at MVP scope); inline
(`, do: expr`) and `do … end` block bodies; integer/float literals; binary
operators (arithmetic / comparison / boolean); `if … do … else … end` → the
defuzz blend; calls; parens. Elixir is dynamically typed — every value lowers
as Sutra `number`. Anything else emits an `UNSUPPORTED-*` marker (surface the
gap rather than mislower); recursion is detected and marked UNSUPPORTED until
the tail/CPS transforms are ported.
"""
from __future__ import annotations

import pathlib
from typing import Optional

_TYPE = "number"  # Elixir is dynamically typed; numbers are the MVP value domain

# Elixir binary operator → Sutra operator.
_OP_MAP = {
    "+": "+", "-": "-", "*": "*", "/": "/",
    "==": "==", "!=": "!=", "<": "<", ">": ">", "<=": "<=", ">=": ">=",
    "and": "&&", "or": "||", "&&": "&&", "||": "||",
}


def _text(node, src: bytes) -> str:
    return src[node.start_byte:node.end_byte].decode("utf-8")


def _blend(test_src: str, then_src: str, else_src: str) -> str:
    """Sutra strong-defuzz two-way blend (no control flow) — the shared frontend
    shape (OCaml/Scala `_blend`). Arms fully parenthesised."""
    w = f"truth_axis(defuzzy({test_src}))"
    return f"(((1 + {w}) * ({then_src})) + ((1 - {w}) * ({else_src}))) / 2"


def _call_kw(node, src: bytes) -> Optional[str]:
    """The keyword identifier of a `call` node (`def`, `defmodule`, `if`, …),
    or None when the call is an ordinary function application."""
    if node.type != "call" or not node.named_children:
        return None
    head = node.named_children[0]
    if head.type == "identifier":
        return _text(head, src)
    return None


def _do_block_value(do_block, src: bytes):
    """Split a `do_block` into (body_exprs, else_exprs|None). Comments and the
    `do`/`end` tokens are unnamed; `else_block` is a named child."""
    body, els = [], None
    for c in do_block.named_children:
        if c.type == "else_block":
            els = list(c.named_children)
        else:
            body.append(c)
    return body, els


def _contains_self_call(node, name: str, src: bytes) -> bool:
    kw = _call_kw(node, src)
    if kw == name:
        return True
    return any(_contains_self_call(c, name, src) for c in node.named_children)


def _lower_expr(node, src: bytes) -> str:
    t = node.type
    if t == "integer":
        return _text(node, src).replace("_", "")
    if t == "float":
        return _text(node, src).replace("_", "")
    if t == "identifier":
        return _text(node, src)
    if t == "boolean":
        return _text(node, src)
    if t == "unary_operator":
        kids = node.named_children
        op = _text(node, src)[:1]
        if kids and op == "-":
            return f"(0 - {_lower_expr(kids[0], src)})"
        return f"/* UNSUPPORTED-UNARY: {_text(node, src)} */"
    if t == "binary_operator":
        op = node.child_by_field_name("operator")
        left = node.child_by_field_name("left")
        right = node.child_by_field_name("right")
        if op is None or left is None or right is None:
            return "/* UNSUPPORTED-EXPR: malformed binary_operator */"
        sop = _OP_MAP.get(_text(op, src))
        if sop is None:
            return f"/* UNSUPPORTED-OP: {_text(op, src)} */"
        return f"({_lower_expr(left, src)} {sop} {_lower_expr(right, src)})"
    if t == "call":
        kw = _call_kw(node, src)
        if kw == "if":
            # call(if, arguments(cond), do_block(then…, else_block(else…)))
            kids = node.named_children
            args = next((c for c in kids if c.type == "arguments"), None)
            do_block = next((c for c in kids if c.type == "do_block"), None)
            if args is None or not args.named_children or do_block is None:
                return "/* UNSUPPORTED-EXPR: malformed if */"
            cond_src = _lower_expr(args.named_children[0], src)
            body, els = _do_block_value(do_block, src)
            then_src = _lower_expr(body[-1], src) if body else "0"
            else_src = _lower_expr(els[-1], src) if els else "0"
            return _blend(cond_src, then_src, else_src)
        if kw is not None:
            # Ordinary application `f(a, b)`.
            args = next((c for c in node.named_children if c.type == "arguments"), None)
            arg_srcs = [_lower_expr(a, src)
                        for a in (args.named_children if args is not None else [])]
            return f"{kw}({', '.join(arg_srcs)})"
        return f"/* UNSUPPORTED-EXPR: non-identifier call */"
    if t == "block" and node.named_children:
        return f"({_lower_expr(node.named_children[-1], src)})"
    return f"/* UNSUPPORTED-EXPR: {t} */"


def _def_parts(def_call, src: bytes):
    """Decompose `call(def, arguments(head [, keywords(do: expr)]) [, do_block])`
    into (name, param_names, body_expr_node) or None. `head` is either
    `call(name, arguments(params…))` or a bare `identifier` (zero-arg, no parens)."""
    kids = def_call.named_children
    args = next((c for c in kids if c.type == "arguments"), None)
    if args is None or not args.named_children:
        return None
    head = args.named_children[0]
    params: list[str] = []
    if head.type == "call":
        name_node = head.named_children[0] if head.named_children else None
        if name_node is None or name_node.type != "identifier":
            return None
        name = _text(name_node, src)
        head_args = next((c for c in head.named_children if c.type == "arguments"), None)
        if head_args is not None:
            for p in head_args.named_children:
                if p.type != "identifier":
                    return None  # pattern params (tuples, literals) are later items
                params.append(_text(p, src))
    elif head.type == "identifier":
        name = _text(head, src)
    else:
        return None
    # Body: inline `, do: expr` (a keywords pair) or a do_block.
    body = None
    kw_node = next((c for c in args.named_children if c.type == "keywords"), None)
    if kw_node is not None:
        pair = next((c for c in kw_node.named_children if c.type == "pair"), None)
        if pair is not None and pair.named_children:
            body = pair.named_children[-1]
    if body is None:
        do_block = next((c for c in kids if c.type == "do_block"), None)
        if do_block is not None:
            stmts, _els = _do_block_value(do_block, src)
            if stmts:
                body = stmts[-1]  # multi-statement bodies (bindings) are later items
    if body is None:
        return None
    return name, params, body


def _lower_def(def_call, src: bytes) -> str:
    parts = _def_parts(def_call, src)
    if parts is None:
        return "// UNSUPPORTED-DEF: unrecognized def shape\n"
    name, params, body = parts
    if _contains_self_call(body, name, src):
        # The tail/CPS recursion transforms are not ported yet; a plain
        # self-calling Sutra function would not terminate through the fuzzy-if
        # blend. Surface the gap rather than mislower.
        return f"// UNSUPPORTED-RECURSION: '{name}' is recursive (transforms not yet ported)\n"
    params_src = ", ".join(f"{_TYPE} {p}" for p in params)
    body_src = _lower_expr(body, src)
    return (f"function {_TYPE} {name}({params_src}) {{\n"
            f"    return {body_src};\n"
            f"}}\n")


def lower(source: str, source_path: Optional[pathlib.Path] = None) -> str:
    """Elixir source string → Sutra source string."""
    import tree_sitter
    import tree_sitter_elixir as tse

    lang = tree_sitter.Language(tse.language())
    parser = tree_sitter.Parser(lang)
    src = source.encode("utf-8")
    tree = parser.parse(src)

    out = ["// Generated by sutra-from-elixir. See sdk/sutra-from-elixir/README.md.\n"]
    for child in tree.root_node.named_children:
        kw = _call_kw(child, src)
        if kw == "defmodule":
            do_block = next((c for c in child.named_children if c.type == "do_block"),
                            None)
            if do_block is None:
                out.append("// UNSUPPORTED-MODULE: defmodule without body\n")
                continue
            for member in do_block.named_children:
                if _call_kw(member, src) == "def":
                    out.append(_lower_def(member, src))
                # defp/defstruct/use/alias are later items
        elif kw == "def":
            out.append(_lower_def(child, src))
    return "\n".join(out)
