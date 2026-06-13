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

# `let` binding substitutions: a bound name maps to its (parenthesised) value
# expression while lowering the body — the OCaml `let..in` expression-position
# shape. Sequential: each value is lowered with the EARLIER binds already active.
_SUBST: dict[str, str] = {}


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
    if node.type == "list_lit" and _head_symbol(node, src) in (name, "recur"):
        return True
    return any(_contains_self_call(c, name, src) for c in node.named_children)


# Sutra comparison op → its negation (halt condition → loop continue condition).
_NEG_CMP = {"==": "!=", "!=": "==", "<": ">=", ">": "<=", "<=": ">", ">=": "<"}


def _self_call_args(node, name: str, arity: int, src: bytes):
    """If `node` is `(name a…)` or `(recur a…)` at the right arity, return the
    arg nodes; else None. `recur` is Clojure's idiomatic tail-call form."""
    if node.type != "list_lit":
        return None
    if _head_symbol(node, src) not in (name, "recur"):
        return None
    args = node.named_children[1:]
    return args if len(args) == arity else None


def _negate_cond(cond, src: bytes) -> str:
    """Negate a halt condition into the loop's continue condition (the OCaml
    `_negate_cond` shape): a single comparison list `(op a b)` inverts via
    `_NEG_CMP`, else `!(…)`."""
    if cond.type == "list_lit":
        sop = _OP_MAP.get(_head_symbol(cond, src) or "")
        neg = _NEG_CMP.get(sop) if sop else None
        args = cond.named_children[1:]
        if neg is not None and len(args) == 2:
            return f"({_lower_expr(args[0], src)} {neg} {_lower_expr(args[1], src)})"
    return f"!({_lower_expr(cond, src)})"


def _try_lower_tail_recursive(name: str, params: list, body, src: bytes):
    """Lower a TAIL-recursive `(defn f [p…] (if COND BASE (recur a…)))` (or a
    named self-call) to a declared Sutra `while_loop` — the OCaml/Scala/F#/Rust/
    Haskell shape ported. Returns the emitted Sutra or None."""
    if body.type != "list_lit" or _head_symbol(body, src) != "if":
        return None
    args = body.named_children[1:]
    if len(args) < 3:
        return None
    cond, then_e, else_e = args[0], args[1], args[2]
    arity = len(params)
    then_args = _self_call_args(then_e, name, arity, src)
    else_args = _self_call_args(else_e, name, arity, src)
    if (then_args is None) == (else_args is None):
        return None
    if else_args is not None:
        cont = _negate_cond(cond, src)
        rec_args, base = else_args, then_e
    else:
        cont = _lower_expr(cond, src)
        rec_args, base = then_args, else_e

    ty = _TYPE
    loop_name = f"_rec_{name}"
    state_decls = ", ".join(f"{ty} {p} = 0" for p in params)
    temp_decls = "".join(f"    {ty} _t{i} = {_lower_expr(arg, src)};\n"
                         for i, arg in enumerate(rec_args))
    assigns = "".join(f"    {p} = _t{i};\n" for i, p in enumerate(params))
    loop_decl = f"while_loop {loop_name}({cont}, {state_decls}) {{\n{temp_decls}{assigns}}}\n"
    slot_lines = "".join(f"    slot {ty} _{p}_r = {p};\n" for p in params)
    slot_args = ", ".join(f"_{p}_r" for p in params)
    writeback = "".join(f"    {p} = _{p}_r;\n" for p in params)
    params_src = ", ".join(f"{ty} {p}" for p in params)
    base_src = _lower_expr(base, src)
    fn = (
        f"function {ty} {name}({params_src}) {{\n"
        f"{slot_lines}"
        f"    loop {loop_name}({cont}, {slot_args});\n"
        f"{writeback}"
        f"    return {base_src};\n"
        f"}}\n"
    )
    return loop_decl + fn


def _lower_expr(node, src: bytes) -> str:
    t = node.type
    if t == "num_lit":
        return _text(node, src)
    if t == "sym_lit":
        text = _text(node, src)
        return _SUBST.get(text, text)
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
        if head == "let":
            # (let [n1 v1 n2 v2 …] body) — sequential binds substituted into the
            # body (and into later values). Numbers only, so re-evaluation of a
            # substituted value is side-effect-free.
            if not args or args[0].type != "vec_lit":
                return "/* UNSUPPORTED-EXPR: malformed let binding vector */"
            pairs = args[0].named_children
            if len(pairs) % 2 != 0:
                return "/* UNSUPPORTED-EXPR: odd let binding vector */"
            bound: list[str] = []
            for i in range(0, len(pairs), 2):
                if pairs[i].type != "sym_lit":
                    for nm in bound:
                        _SUBST.pop(nm, None)
                    return "/* UNSUPPORTED-EXPR: non-symbol let binding (destructuring later) */"
                nm = _text(pairs[i], src)
                val_src = f"({_lower_expr(pairs[i + 1], src)})"
                _SUBST[nm] = val_src
                bound.append(nm)
            body = args[-1] if len(args) >= 2 else None
            res = _lower_expr(body, src) if body is not None else "0"
            for nm in bound:
                _SUBST.pop(nm, None)
            return res
        if head == "cond":
            # (cond t1 r1 t2 r2 … :else d) — nested defuzz blend; :else (or the
            # final clause) is the base.
            if len(args) < 2 or len(args) % 2 != 0:
                return "/* UNSUPPORTED-EXPR: malformed cond */"
            parsed = []
            for i in range(0, len(args), 2):
                test_node, res_node = args[i], args[i + 1]
                if test_node.type == "kwd_lit":  # :else
                    parsed.append((None, _lower_expr(res_node, src)))
                else:
                    parsed.append((f"({_lower_expr(test_node, src)})",
                                   _lower_expr(res_node, src)))
            expr = parsed[-1][1]
            for test, res in reversed(parsed[:-1]):
                expr = res if test is None else _blend(test, res, expr)
            return expr
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
    if params:
        rec = _try_lower_tail_recursive(name, params, body, src)
        if rec is not None:
            return rec
    if _contains_self_call(body, name, src):
        # Recursion / `recur` outside the supported tail shape — a plain
        # self-call would not terminate through the fuzzy-if blend. Surface it.
        return (f"// UNSUPPORTED-RECURSION: '{name}' is recursive but not the "
                f"tail-accumulator shape\n")
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
    _SUBST.clear()

    out = ["// Generated by sutra-from-clojure. See sdk/sutra-from-clojure/README.md.\n"]
    for child in tree.root_node.named_children:
        if child.type == "list_lit" and _head_symbol(child, src) == "defn":
            out.append(_lower_defn(child, src))
        # ns/def/comment forms are later items
    return "\n".join(out)
