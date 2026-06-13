"""F# → Sutra lowering pass (MVP).

Models on `sutra-from-ocaml` (the reference frontend) — F# is OCaml's close
cousin and ionide's grammar mirrors the ML shapes (`function_or_value_defn`,
`application_expression`, `infix_expression`). This first cut proves the
toolchain end-to-end for F#: top-level `let` functions lower to Sutra
`function`s, compile, and RUN on the substrate.

Grammar loading: there is no PyPI wheel, so `build_grammar.py` compiles the
ionide grammar (Emma-authorized source, 2026-06-12) into `_grammar/fsharp.dll`
and this module loads it via ctypes.

Supported now: top-level `let f a b = expr` (and `let main () = expr`);
integer/float consts; infix arithmetic/comparison/boolean operators (`<>` →
`!=`, `=` → `==` in expression position); application spines flatten to Sutra
calls (`add 7 9` → `add(7, 9)`); `if/then/else` → the defuzz blend; parens.
Untyped params default to int (F# infers; annotations are a later item).
GRAMMAR QUIRK (measured): unparenthesized application mixed with infix
(`add 7 9 + classify 5`) mis-associates in the ionide grammar — parenthesize
call operands. Anything unrecognized emits an `UNSUPPORTED-*` marker;
recursion surfaces as `UNSUPPORTED-RECURSION` until the tail/CPS transforms
are ported (never a silent self-call).
"""
from __future__ import annotations

import ctypes
import pathlib
from typing import Optional

_HERE = pathlib.Path(__file__).resolve().parent
_DLL = _HERE.parent / "_grammar" / "fsharp.dll"
_DEFAULT_TYPE = "int"

# F# infix operator → Sutra operator (expression position: `=` compares).
_OP_MAP = {
    "+": "+", "-": "-", "*": "*", "/": "/",
    "=": "==", "<>": "!=", "<": "<", ">": ">", "<=": "<=", ">=": ">=",
    "&&": "&&", "||": "||",
}


def grammar_available() -> bool:
    return _DLL.exists()


def _load_language():
    import tree_sitter

    lib = ctypes.cdll.LoadLibrary(str(_DLL))
    lib.tree_sitter_fsharp.restype = ctypes.c_void_p
    return tree_sitter.Language(lib.tree_sitter_fsharp())


def _text(node, src: bytes) -> str:
    return src[node.start_byte:node.end_byte].decode("utf-8")


def _blend(test_src: str, then_src: str, else_src: str) -> str:
    """Sutra strong-defuzz two-way blend — the shared frontend shape."""
    w = f"truth_axis(defuzzy({test_src}))"
    return f"(((1 + {w}) * ({then_src})) + ((1 - {w}) * ({else_src}))) / 2"


def _flatten_apply(node):
    """Left-nested `application_expression` spine → (head_node, [arg_node, …])."""
    args: list = []
    while node.type == "application_expression" and len(node.named_children) == 2:
        head, arg = node.named_children
        args.append(arg)
        node = head
    return node, list(reversed(args))


def _contains_self_call(node, name: str, src: bytes) -> bool:
    if node.type == "identifier" and _text(node, src) == name:
        return True
    return any(_contains_self_call(c, name, src) for c in node.named_children)


def _lower_expr(node, src: bytes) -> str:
    t = node.type
    if t == "const":
        inner = node.named_children[0] if node.named_children else None
        if inner is not None and inner.type in ("int", "float", "int32", "int64"):
            return _text(inner, src).rstrip("LlmMfF")
        return f"/* UNSUPPORTED-CONST: {inner.type if inner else 'empty'} */"
    if t in ("identifier", "long_identifier", "long_identifier_or_op"):
        return _text(node, src)
    if t == "paren_expression":
        inner = node.named_children[0] if node.named_children else None
        return f"({_lower_expr(inner, src)})" if inner is not None else "0"
    if t == "infix_expression":
        kids = node.named_children
        op = next((c for c in kids if c.type == "infix_op"), None)
        operands = [c for c in kids if c.type != "infix_op"]
        if op is None or len(operands) != 2:
            return "/* UNSUPPORTED-EXPR: malformed infix */"
        sop = _OP_MAP.get(_text(op, src))
        if sop is None:
            return f"/* UNSUPPORTED-OP: {_text(op, src)} */"
        return f"({_lower_expr(operands[0], src)} {sop} {_lower_expr(operands[1], src)})"
    if t == "if_expression":
        kids = node.named_children
        if len(kids) < 2:
            return "/* UNSUPPORTED-EXPR: malformed if */"
        cond_src = _lower_expr(kids[0], src)
        then_src = _lower_expr(kids[1], src)
        else_src = _lower_expr(kids[2], src) if len(kids) >= 3 else "0"
        return _blend(cond_src, then_src, else_src)
    if t == "application_expression":
        head, args = _flatten_apply(node)
        if head.type not in ("identifier", "long_identifier_or_op", "long_identifier"):
            return f"/* UNSUPPORTED-EXPR: application head {head.type} */"
        arg_srcs = [_lower_expr(a, src) for a in args]
        return f"{_text(head, src)}({', '.join(arg_srcs)})"
    if t == "match_expression":
        # `match scrut with | k1 -> r1 | … | _ -> base` → a nested defuzz blend
        # over `scrut == k` tests (the OCaml/Scala literal-match shape). The last
        # rule is the base (a trailing `_`, or the final literal for an
        # exhaustive set). Literal patterns only — variant/record patterns are a
        # later item.
        kids = node.named_children
        scrut_src = _lower_expr(kids[0], src) if kids else "0"
        rules = next((c for c in kids if c.type == "rules"), None)
        if rules is None:
            return "/* UNSUPPORTED-EXPR: match without rules */"
        parsed = []
        for rule in rules.named_children:
            if rule.type != "rule":
                continue
            rk = rule.named_children
            pat, res = rk[0], rk[-1]
            if pat.type == "wildcard_pattern":
                test = None
            elif pat.type == "const":
                test = f"({scrut_src} == {_lower_expr(pat, src)})"
            else:
                return f"/* UNSUPPORTED-MATCH-PATTERN: {pat.type} */"
            parsed.append((test, _lower_expr(res, src)))
        if not parsed:
            return "/* UNSUPPORTED-EXPR: empty match */"
        expr = parsed[-1][1]
        for test, res in reversed(parsed[:-1]):
            expr = res if test is None else _blend(test, res, expr)
        return expr
    if t == "declaration_expression" and node.named_children:
        return _lower_expr(node.named_children[0], src)
    return f"/* UNSUPPORTED-EXPR: {t} */"


def _lower_defn(defn, src: bytes) -> str:
    """A `function_or_value_defn`: [function_declaration_left, body_expr]."""
    kids = defn.named_children
    left = next((c for c in kids if c.type == "function_declaration_left"), None)
    if left is None or len(kids) < 2:
        return "// UNSUPPORTED-LET: not a function definition shape\n"
    body = kids[-1]
    lk = left.named_children
    name_node = next((c for c in lk if c.type == "identifier"), None)
    if name_node is None:
        return "// UNSUPPORTED-LET: no name\n"
    name = _text(name_node, src)
    params: list[str] = []
    arg_pats = next((c for c in lk if c.type == "argument_patterns"), None)
    if arg_pats is not None:
        for p in arg_pats.named_children:
            if p.type == "long_identifier" and p.named_children:
                params.append(_text(p.named_children[0], src))
            elif p.type == "const" and p.named_children \
                    and p.named_children[0].type == "unit":
                continue  # `()` — the zero-arg marker
            else:
                return (f"// UNSUPPORTED-LET: '{name}' has a pattern parameter "
                        f"({p.type}) — later item\n")
    if _contains_self_call(body, name, src):
        return (f"// UNSUPPORTED-RECURSION: '{name}' is recursive "
                f"(transforms not yet ported)\n")
    params_src = ", ".join(f"{_DEFAULT_TYPE} {p}" for p in params)
    return (f"function {_DEFAULT_TYPE} {name}({params_src}) {{\n"
            f"    return {_lower_expr(body, src)};\n"
            f"}}\n")


def lower(source: str, source_path: Optional[pathlib.Path] = None) -> str:
    """F# source string → Sutra source string."""
    import tree_sitter

    if not grammar_available():
        raise RuntimeError(
            f"F# grammar DLL missing at {_DLL}; run "
            f"sdk/sutra-from-fsharp/build_grammar.py (needs MSVC)."
        )
    parser = tree_sitter.Parser(_load_language())
    src = source.encode("utf-8")
    tree = parser.parse(src)

    out = ["// Generated by sutra-from-fsharp. See sdk/sutra-from-fsharp/README.md.\n"]
    for child in tree.root_node.named_children:
        if child.type == "declaration_expression":
            defn = next((c for c in child.named_children
                         if c.type == "function_or_value_defn"), None)
            if defn is not None:
                out.append(_lower_defn(defn, src))
        # modules/types/namespaces are later items
    return "\n".join(out)
