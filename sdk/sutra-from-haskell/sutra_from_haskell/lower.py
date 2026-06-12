"""Haskell → Sutra lowering pass (MVP).

Models on `sutra-from-ocaml` (the reference frontend) via the Scala/Elixir MVP
shape. This first cut proves the toolchain end-to-end for Haskell: top-level
function equations lower to Sutra `function`s, compile, and RUN on the substrate.

Supported now: top-level `function` equations (`add a b = a + b`) and zero-arg
`bind`s (`main = …`); `signature` declarations supply param/return types (the
arrow chain flattens; Int/Integer → int, Double/Float → number, Bool → bool;
unsignatured names default to int); integer/float literals; `infix` operators
(arithmetic / comparison / boolean); curried `apply` spines flatten to Sutra
calls (`add 7 9` → `add(7, 9)`); `if/then/else` (`conditional`) → the defuzz
blend; parens. Laziness is NOT modeled: Sutra is strict, and the MVP scope
(total arithmetic programs) is insensitive to evaluation order — programs
relying on laziness are out of scope. Guards/where/let, pattern equations and
typeclasses are later items; anything unrecognized emits an `UNSUPPORTED-*`
marker, and recursion surfaces as `UNSUPPORTED-RECURSION` until the tail/CPS
transforms are ported (never a silent self-call).
"""
from __future__ import annotations

import pathlib
from typing import Optional

_TYPE_MAP = {
    "Int": "int", "Integer": "int",
    "Double": "number", "Float": "number",
    "Bool": "bool",
}
_DEFAULT_TYPE = "int"

# Haskell infix operator → Sutra operator.
_OP_MAP = {
    "+": "+", "-": "-", "*": "*", "/": "/",
    "==": "==", "/=": "!=", "<": "<", ">": ">", "<=": "<=", ">=": ">=",
    "&&": "&&", "||": "||",
}

# signature name → flattened arrow-chain type texts ([param…, return]).
_SIGNATURES: dict[str, list[str]] = {}


def _text(node, src: bytes) -> str:
    return src[node.start_byte:node.end_byte].decode("utf-8")


def _blend(test_src: str, then_src: str, else_src: str) -> str:
    """Sutra strong-defuzz two-way blend — the shared frontend shape."""
    w = f"truth_axis(defuzzy({test_src}))"
    return f"(((1 + {w}) * ({then_src})) + ((1 - {w}) * ({else_src}))) / 2"


def _flatten_arrow(type_node, src: bytes) -> list[str]:
    """`function(name Int, function(name Int, name Int))` → ["Int","Int","Int"]."""
    if type_node.type == "function":
        kids = type_node.named_children
        if len(kids) == 2:
            return [_text(kids[0], src)] + _flatten_arrow(kids[1], src)
    return [_text(type_node, src)]


def _map_type(hs_type: Optional[str]) -> str:
    return _TYPE_MAP.get(hs_type, _DEFAULT_TYPE) if hs_type else _DEFAULT_TYPE


def _flatten_apply(node, src: bytes):
    """Left-nested `apply` spine → (head_node, [arg_node, …])."""
    args: list = []
    while node.type == "apply" and len(node.named_children) == 2:
        head, arg = node.named_children
        args.append(arg)
        node = head
    return node, list(reversed(args))


def _contains_self_call(node, name: str, src: bytes) -> bool:
    if node.type == "variable" and _text(node, src) == name:
        return True
    return any(_contains_self_call(c, name, src) for c in node.named_children)


def _lower_expr(node, src: bytes) -> str:
    t = node.type
    if t == "literal":
        inner = node.named_children[0] if node.named_children else None
        return _text(inner if inner is not None else node, src)
    if t in ("integer", "float"):
        return _text(node, src)
    if t == "variable":
        return _text(node, src)
    if t == "parens":
        inner = node.named_children[0] if node.named_children else None
        return f"({_lower_expr(inner, src)})" if inner is not None else "0"
    if t == "infix":
        kids = node.named_children
        op = next((c for c in kids if c.type == "operator"), None)
        operands = [c for c in kids if c.type != "operator"]
        if op is None or len(operands) != 2:
            return "/* UNSUPPORTED-EXPR: malformed infix */"
        sop = _OP_MAP.get(_text(op, src))
        if sop is None:
            return f"/* UNSUPPORTED-OP: {_text(op, src)} */"
        return f"({_lower_expr(operands[0], src)} {sop} {_lower_expr(operands[1], src)})"
    if t == "conditional":
        kids = node.named_children
        if len(kids) < 3:
            return "/* UNSUPPORTED-EXPR: malformed conditional */"
        return _blend(_lower_expr(kids[0], src),
                      _lower_expr(kids[1], src),
                      _lower_expr(kids[2], src))
    if t == "apply":
        head, args = _flatten_apply(node, src)
        if head.type != "variable":
            return "/* UNSUPPORTED-EXPR: non-variable application head */"
        arg_srcs = [_lower_expr(a, src) for a in args]
        return f"{_text(head, src)}({', '.join(arg_srcs)})"
    return f"/* UNSUPPORTED-EXPR: {t} */"


def _match_body(decl, src: bytes):
    """The expression node of a declaration's `match` (`= expr`), or None.
    Guarded matches (multiple `match` children / guards) are later items."""
    matches = [c for c in decl.named_children if c.type == "match"]
    if len(matches) != 1:
        return None
    m = matches[0]
    return m.named_children[-1] if m.named_children else None


def _lower_equation(decl, src: bytes) -> str:
    """A `function` equation (`add a b = …`) or zero-arg `bind` (`main = …`)."""
    kids = decl.named_children
    name_node = next((c for c in kids if c.type == "variable"), None)
    if name_node is None:
        return "// UNSUPPORTED-DECL: no name\n"
    name = _text(name_node, src)
    patterns = next((c for c in kids if c.type == "patterns"), None)
    params: list[str] = []
    if patterns is not None:
        for p in patterns.named_children:
            if p.type != "variable":
                return (f"// UNSUPPORTED-DECL: '{name}' has a pattern parameter "
                        f"({p.type}) — pattern equations are a later item\n")
            params.append(_text(p, src))
    body = _match_body(decl, src)
    if body is None:
        return f"// UNSUPPORTED-DECL: '{name}' has no single plain `= expr` body\n"
    if _contains_self_call(body, name, src):
        return (f"// UNSUPPORTED-RECURSION: '{name}' is recursive "
                f"(transforms not yet ported)\n")
    sig = _SIGNATURES.get(name)
    if sig is not None and len(sig) == len(params) + 1:
        ptypes = [_map_type(s) for s in sig[:-1]]
        ret = _map_type(sig[-1])
    else:
        ptypes = [_DEFAULT_TYPE] * len(params)
        ret = _DEFAULT_TYPE
    params_src = ", ".join(f"{ty} {nm}" for ty, nm in zip(ptypes, params))
    return (f"function {ret} {name}({params_src}) {{\n"
            f"    return {_lower_expr(body, src)};\n"
            f"}}\n")


def lower(source: str, source_path: Optional[pathlib.Path] = None) -> str:
    """Haskell source string → Sutra source string."""
    import tree_sitter
    import tree_sitter_haskell as tsh

    lang = tree_sitter.Language(tsh.language())
    parser = tree_sitter.Parser(lang)
    src = source.encode("utf-8")
    tree = parser.parse(src)

    root = tree.root_node
    decls = next((c for c in root.named_children if c.type == "declarations"), root)

    # Prepass: signatures supply the types for their equations.
    _SIGNATURES.clear()
    for child in decls.named_children:
        if child.type == "signature" and len(child.named_children) == 2:
            var, ty = child.named_children
            if var.type == "variable":
                _SIGNATURES[_text(var, src)] = _flatten_arrow(ty, src)

    out = ["// Generated by sutra-from-haskell. See sdk/sutra-from-haskell/README.md.\n"]
    for child in decls.named_children:
        if child.type in ("function", "bind"):
            out.append(_lower_equation(child, src))
        # signatures are consumed by the prepass; data/class/instance are later items
    return "\n".join(out)
