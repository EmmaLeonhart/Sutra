"""Scala → Sutra lowering pass (MVP).

Models on `sutra-from-ocaml/lower.py` (the reference frontend; new frontends model on
it, not `-ts`). This first cut proves the toolchain end-to-end for Scala: a top-level
`def` function lowers to a Sutra `function`, compiles, and RUNS on the substrate.

Supported now: `def f(a: Int, b: Int): Int = <expr>`; Int/Long → int, Double/Float →
number, Boolean → bool, String → String; integer/float literals; infix arithmetic +
comparison + boolean ops; function calls; parenthesized expressions. Anything else
emits an `UNSUPPORTED-*` marker (so partial programs surface the gap rather than mislower).
"""
from __future__ import annotations

import pathlib
from typing import Optional

_TYPE_MAP = {
    "Int": "int", "Long": "int", "Short": "int", "Byte": "int",
    "Double": "number", "Float": "number",
    "Boolean": "bool", "String": "String", "Unit": "int",
}
_DEFAULT_TYPE = "int"

# Scala infix operator → Sutra operator.
_OP_MAP = {
    "+": "+", "-": "-", "*": "*", "/": "/", "%": "%",
    "==": "==", "!=": "!=", "<": "<", ">": ">", "<=": "<=", ">=": ">=",
    "&&": "&&", "||": "||",
}


def _text(node, src: bytes) -> str:
    return src[node.start_byte:node.end_byte].decode("utf-8")


def _blend(test_src: str, then_src: str, else_src: str) -> str:
    """Sutra strong-defuzz two-way blend (no control flow): weight by the test's
    truth. Arms fully parenthesised so a bare `* (atom)` never precedes an infix op
    (the `(atom) <binop>` cast ambiguity). Same shape as the OCaml frontend's _blend."""
    w = f"truth_axis(defuzzy({test_src}))"
    return f"(((1 + {w}) * ({then_src})) + ((1 - {w}) * ({else_src}))) / 2"


def _map_type(node, src: bytes) -> str:
    return _TYPE_MAP.get(_text(node, src), _DEFAULT_TYPE) if node is not None else _DEFAULT_TYPE


def _lower_expr(node, src: bytes) -> str:
    t = node.type
    if t == "integer_literal":
        return _text(node, src).rstrip("Ll")
    if t in ("floating_point_literal", "float_literal"):
        return _text(node, src).rstrip("fFdD")
    if t in ("identifier", "stable_identifier"):
        return _text(node, src)
    if t == "boolean_literal":
        return _text(node, src)
    if t == "parenthesized_expression":
        inner = node.named_children[0] if node.named_children else None
        return f"({_lower_expr(inner, src)})" if inner is not None else "0"
    if t == "infix_expression":
        kids = node.named_children
        op = next((c for c in kids if c.type == "operator_identifier"), None)
        operands = [c for c in kids if c.type != "operator_identifier"]
        if op is None or len(operands) != 2:
            return f"/* UNSUPPORTED-EXPR: malformed infix */"
        sop = _OP_MAP.get(_text(op, src))
        if sop is None:
            return f"/* UNSUPPORTED-OP: {_text(op, src)} */"
        return f"({_lower_expr(operands[0], src)} {sop} {_lower_expr(operands[1], src)})"
    if t == "if_expression":
        # Sutra has no control-flow branch: an if is a defuzz BLEND that weights both
        # arms by the condition's truth (same shape as the OCaml frontend's `_blend`).
        # Every arm fully parenthesised so a bare `* (atom)` never precedes an infix op
        # (the Sutra `(atom) <binop>` cast ambiguity). A missing else is implicit-zero.
        kids = node.named_children
        if len(kids) < 2:
            return "/* UNSUPPORTED-EXPR: malformed if */"
        cond_src = _lower_expr(kids[0], src)
        then_src = _lower_expr(kids[1], src)
        else_src = _lower_expr(kids[2], src) if len(kids) >= 3 else "0"
        return _blend(cond_src, then_src, else_src)
    if t == "match_expression":
        # Literal `n match { case k => …; case _ => … }` → a nested defuzz blend over
        # `n == k` tests (same as the OCaml frontend's literal match). The last case is
        # the base (a trailing `_` wildcard, or the final literal for an exhaustive set).
        kids = node.named_children
        scrut_src = _lower_expr(kids[0], src) if kids else "0"
        case_block = next((c for c in kids if c.type == "case_block"), None)
        if case_block is None:
            return "/* UNSUPPORTED-EXPR: match without cases */"
        parsed = []
        for cc in case_block.named_children:
            if cc.type != "case_clause":
                continue
            ck = cc.named_children
            pat, res = ck[0], ck[-1]
            if pat.type == "wildcard":
                test = None
            elif pat.type == "integer_literal":
                test = f"({scrut_src} == {_text(pat, src)})"
            else:
                return f"/* UNSUPPORTED-MATCH-PATTERN: {pat.type} */"
            parsed.append((test, _lower_expr(res, src)))
        if not parsed:
            return "/* UNSUPPORTED-EXPR: empty match */"
        expr = parsed[-1][1]
        for test, res in reversed(parsed[:-1]):
            expr = res if test is None else _blend(test, res, expr)
        return expr
    if t == "call_expression":
        kids = node.named_children
        if not kids:
            return "/* UNSUPPORTED-EXPR: empty call */"
        fn = _lower_expr(kids[0], src)
        args_node = next((c for c in kids if c.type == "arguments"), None)
        args = [_lower_expr(a, src) for a in (args_node.named_children if args_node else [])]
        return f"{fn}({', '.join(args)})"
    return f"/* UNSUPPORTED-EXPR: {t} */"


def _lower_block(node, src: bytes) -> str:
    """A `{ val a = …; val b = …; finalExpr }` block body → Sutra local declarations
    + a `return` of the final expression. `val a = e` → `<ty> a = <e>;` (ty from a
    `val a: T = e` annotation, else the int default)."""
    stmts = ""
    final = None
    for c in node.named_children:
        if c.type == "val_definition":
            kids = c.named_children
            if len(kids) < 2:
                continue
            name = _text(kids[0], src)
            ty_node = next((k for k in kids if k.type == "type_identifier"), None)
            ty = _map_type(ty_node, src) if ty_node is not None else _DEFAULT_TYPE
            stmts += f"    {ty} {name} = {_lower_expr(kids[-1], src)};\n"
        else:
            final = c  # the block's value is its last non-val expression
    final_src = _lower_expr(final, src) if final is not None else "0"
    return stmts + f"    return {final_src};\n"


def _lower_function(node, src: bytes) -> str:
    kids = node.named_children
    name_node = next((c for c in kids if c.type == "identifier"), None)
    if name_node is None:
        return "// UNSUPPORTED-DEF: no name\n"
    name = _text(name_node, src)
    params: list[tuple[str, str]] = []
    params_node = next((c for c in kids if c.type == "parameters"), None)
    if params_node is not None:
        for pnode in params_node.named_children:
            if pnode.type != "parameter":
                continue
            pid = next((c for c in pnode.named_children if c.type == "identifier"), None)
            ptype = next((c for c in pnode.named_children if c.type == "type_identifier"), None)
            if pid is not None:
                params.append((_text(pid, src), _map_type(ptype, src)))
    ret_node = next((c for c in kids if c.type == "type_identifier"), None)
    ret = _map_type(ret_node, src)
    body = kids[-1] if kids else None
    if body is None or body.type in ("identifier", "parameters", "type_identifier"):
        return f"// UNSUPPORTED-DEF: '{name}' has no expression body\n"
    params_src = ", ".join(f"{ty} {nm}" for nm, ty in params)
    inner = _lower_block(body, src) if body.type == "block" \
        else f"    return {_lower_expr(body, src)};\n"
    return f"function {ret} {name}({params_src}) {{\n{inner}}}\n"


def lower(source: str, source_path: Optional[pathlib.Path] = None) -> str:
    """Scala source string → Sutra source string. `source_path` accepted for harness
    parity with the other frontends (unused in this MVP)."""
    import tree_sitter
    import tree_sitter_scala as tss

    lang = tree_sitter.Language(tss.language())
    parser = tree_sitter.Parser(lang)
    src = source.encode("utf-8")
    tree = parser.parse(src)

    out = ["// Generated by sutra-from-scala. See sdk/sutra-from-scala/README.md.\n"]
    for child in tree.root_node.named_children:
        if child.type == "function_definition":
            out.append(_lower_function(child, src))
        # other top-level forms (objects, classes, vals) are later items
    return "\n".join(out)
