"""Clojure → Sutra lowering pass (MVP).

Models on `sutra-from-ocaml` (the reference frontend) via the MVP shape shared
by the Scala/Elixir/Haskell/Rust/F# frontends. This first cut proves the
toolchain end-to-end for Clojure (the Lisp entry of the roadmap): `defn`
functions lower to Sutra `function`s, compile, and RUN on the substrate.

Grammar loading: there is no PyPI wheel, so `build_grammar.py` compiles the
sogaiu grammar (Emma-authorized source, 2026-06-12) into `_grammar/clojure.dll`
and this module loads it via ctypes.

The s-expression surface makes the lowering a single list dispatch on the head
symbol: arithmetic/comparison/boolean heads lower as (left-folded n-ary) infix;
`if` lowers to the defuzz blend; any other symbol head is a call. Numbers are
the MVP value domain (dynamically typed → Sutra `number`). `let`, `cond`,
maps/vectors-as-data and recursion are later items; recursion surfaces as
`UNSUPPORTED-RECURSION` until the tail/CPS transforms are ported (never a
silent self-call).
"""
from __future__ import annotations

import ctypes
import pathlib
from typing import Optional

_HERE = pathlib.Path(__file__).resolve().parent
_DLL = _HERE.parent / "_grammar" / "clojure.dll"
_TYPE = "number"

# Clojure operator symbol → Sutra operator (n-ary heads left-fold).
_OP_MAP = {
    "+": "+", "-": "-", "*": "*", "/": "/",
    "=": "==", "not=": "!=", "<": "<", ">": ">", "<=": "<=", ">=": ">=",
    "and": "&&", "or": "||",
}


def grammar_available() -> bool:
    return _DLL.exists()


def _load_language():
    import tree_sitter

    lib = ctypes.cdll.LoadLibrary(str(_DLL))
    lib.tree_sitter_clojure.restype = ctypes.c_void_p
    return tree_sitter.Language(lib.tree_sitter_clojure())


def _text(node, src: bytes) -> str:
    return src[node.start_byte:node.end_byte].decode("utf-8")


def _blend(test_src: str, then_src: str, else_src: str) -> str:
    """Sutra strong-defuzz two-way blend — the shared frontend shape."""
    w = f"truth_axis(defuzzy({test_src}))"
    return f"(((1 + {w}) * ({then_src})) + ((1 - {w}) * ({else_src}))) / 2"


def _head_symbol(list_lit, src: bytes) -> Optional[str]:
    kids = list_lit.named_children
    if kids and kids[0].type == "sym_lit":
        return _text(kids[0], src)
    return None


def _contains_self_call(node, name: str, src: bytes) -> bool:
    if node.type == "list_lit" and _head_symbol(node, src) == name:
        return True
    return any(_contains_self_call(c, name, src) for c in node.named_children)


def _lower_expr(node, src: bytes) -> str:
    t = node.type
    if t == "num_lit":
        return _text(node, src)
    if t == "sym_lit":
        return _text(node, src)
    if t == "bool_lit":
        return _text(node, src)
    if t == "list_lit":
        kids = node.named_children
        head = _head_symbol(node, src)
        if head is None:
            return "/* UNSUPPORTED-EXPR: non-symbol list head */"
        args = kids[1:]
        if head == "if":
            if len(args) < 2:
                return "/* UNSUPPORTED-EXPR: malformed if */"
            cond_src = _lower_expr(args[0], src)
            then_src = _lower_expr(args[1], src)
            else_src = _lower_expr(args[2], src) if len(args) >= 3 else "0"
            return _blend(cond_src, then_src, else_src)
        sop = _OP_MAP.get(head)
        if sop is not None:
            if len(args) < 2:
                return f"/* UNSUPPORTED-EXPR: unary ({head} …) — later item */"
            expr = _lower_expr(args[0], src)
            for a in args[1:]:                 # n-ary heads left-fold
                expr = f"({expr} {sop} {_lower_expr(a, src)})"
            return expr
        arg_srcs = [_lower_expr(a, src) for a in args]
        return f"{head}({', '.join(arg_srcs)})"
    return f"/* UNSUPPORTED-EXPR: {t} */"


def _lower_defn(list_lit, src: bytes) -> str:
    """(defn name [p1 p2] body) → a Sutra function."""
    kids = list_lit.named_children
    if len(kids) < 4 and not (len(kids) == 3 and kids[2].type == "list_lit"):
        # (defn name [] body) has 4 kids too (empty vec_lit is named)
        pass
    name_node = kids[1] if len(kids) > 1 else None
    vec = next((c for c in kids if c.type == "vec_lit"), None)
    if name_node is None or name_node.type != "sym_lit" or vec is None:
        return "// UNSUPPORTED-DEFN: unrecognized defn shape\n"
    name = _text(name_node, src)
    params: list[str] = []
    for p in vec.named_children:
        if p.type != "sym_lit":
            return (f"// UNSUPPORTED-DEFN: '{name}' has a non-symbol parameter "
                    f"({p.type}) — destructuring is a later item\n")
        params.append(_text(p, src))
    body_nodes = [c for c in kids[2:] if c is not vec]
    if not body_nodes:
        return f"// UNSUPPORTED-DEFN: '{name}' has no body\n"
    body = body_nodes[-1]  # multi-form bodies (side effects) are later items
    if _contains_self_call(body, name, src):
        return (f"// UNSUPPORTED-RECURSION: '{name}' is recursive "
                f"(transforms not yet ported)\n")
    params_src = ", ".join(f"{_TYPE} {p}" for p in params)
    return (f"function {_TYPE} {name}({params_src}) {{\n"
            f"    return {_lower_expr(body, src)};\n"
            f"}}\n")


def lower(source: str, source_path: Optional[pathlib.Path] = None) -> str:
    """Clojure source string → Sutra source string."""
    import tree_sitter

    if not grammar_available():
        raise RuntimeError(
            f"Clojure grammar DLL missing at {_DLL}; run "
            f"sdk/sutra-from-clojure/build_grammar.py (needs MSVC)."
        )
    parser = tree_sitter.Parser(_load_language())
    src = source.encode("utf-8")
    tree = parser.parse(src)

    out = ["// Generated by sutra-from-clojure. See sdk/sutra-from-clojure/README.md.\n"]
    for child in tree.root_node.named_children:
        if child.type == "list_lit" and _head_symbol(child, src) == "defn":
            out.append(_lower_defn(child, src))
        # ns/def/comment forms are later items
    return "\n".join(out)
