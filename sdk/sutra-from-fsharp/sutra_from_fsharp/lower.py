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


# `match` name-binding patterns: a bound name maps to the (parenthesised)
# scrutinee while lowering that rule's result (the OCaml `_MATCH_SUBST` shape,
# shared with the Elixir/Rust/Haskell frontends).
_SUBST: dict[str, str] = {}


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


# Sutra comparison op → its negation: a halt condition becomes the loop's
# *continue* condition.
_NEG_CMP = {"==": "!=", "!=": "==", "<": ">=", ">": "<=", "<=": ">", ">=": "<"}


def _self_call_args(node, name: str, arity: int, src: bytes):
    """If `node` is `name arg1 … arg{arity}` (a curried self-application at the
    right arity), return the arg nodes; else None."""
    if node.type != "application_expression":
        return None
    head, args = _flatten_apply(node)
    if head.type not in ("identifier", "long_identifier_or_op", "long_identifier"):
        return None
    if _text(head, src) != name or len(args) != arity:
        return None
    return args


def _negate_cond(cond, src: bytes) -> str:
    """Negate a halt condition into the loop's continue condition: a single infix
    comparison inverts precisely via `_NEG_CMP`; any other boolean negates with
    Sutra `!(…)` (the OCaml frontend's `_negate_cond` shape)."""
    if cond.type == "infix_expression":
        kids = cond.named_children
        op = next((c for c in kids if c.type == "infix_op"), None)
        operands = [c for c in kids if c.type != "infix_op"]
        if op is not None and len(operands) == 2:
            sop = _OP_MAP.get(_text(op, src))
            neg = _NEG_CMP.get(sop) if sop else None
            if neg is not None:
                return (f"{_lower_expr(operands[0], src)} {neg} "
                        f"{_lower_expr(operands[1], src)}")
    return f"!({_lower_expr(cond, src)})"


def _try_lower_tail_recursive(name: str, params: list, body, src: bytes):
    """Lower a TAIL-recursive accumulator `let rec f p… = if COND then BASE else
    f a…` (self-call in either arm) to a Sutra declared `while_loop` — bounded
    substrate iteration, no self-calling function (which would not terminate
    through the fuzzy-if blend). The OCaml/Scala `_try_lower_tail_recursive`
    shape, ported. Returns the emitted Sutra or None."""
    if body.type != "if_expression" or len(body.named_children) < 3:
        return None
    kids = body.named_children
    cond, then_e, else_e = kids[0], kids[1], kids[2]
    arity = len(params)
    then_args = _self_call_args(then_e, name, arity, src)
    else_args = _self_call_args(else_e, name, arity, src)
    if (then_args is None) == (else_args is None):
        return None  # exactly one branch must be the self-call
    if else_args is not None:
        cont = _negate_cond(cond, src)            # halt when COND, loop while not
        rec_args, base = else_args, then_e
    else:
        cont = _lower_expr(cond, src)             # loop while COND
        rec_args, base = then_args, else_e

    ty = _DEFAULT_TYPE
    loop_name = f"_rec_{name}"
    state_decls = ", ".join(f"{ty} {p} = 0" for p in params)
    # Simultaneous update via temporaries (the swaploop lesson).
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


# Associative + commutative combine ops for the non-tail fold transform.
_FOLD_OPS = {"+", "*"}


def _contains_identifier(node, ident: str, src: bytes) -> bool:
    if node.type == "identifier" and _text(node, src) == ident:
        return True
    return any(_contains_identifier(c, ident, src) for c in node.named_children)


def _try_lower_foldable_nontail(name: str, params: list, body, src: bytes):
    """CPS / accumulator transform for a FOLDABLE non-tail `let rec f n = if COND
    then BASE else LEAF <OP> f REC` (single param, OP in `_FOLD_OPS`): the pending
    call-stack work is reified as an accumulator carried by a Sutra `while_loop`
    trampoline — the OCaml/Scala/Rust/Haskell shape ported. BASE is evaluated
    pre-loop at the INITIAL param, so a param-dependent BASE is rejected (→ None).
    Returns loop decl + function, or None."""
    if body.type != "if_expression" or len(body.named_children) < 3 \
            or len(params) != 1:
        return None
    kids = body.named_children
    cond, then_e, else_e = kids[0], kids[1], kids[2]

    def foldable(node):
        if node.type != "infix_expression":
            return None
        nk = node.named_children
        op = next((c for c in nk if c.type == "infix_op"), None)
        operands = [c for c in nk if c.type != "infix_op"]
        if op is None or len(operands) != 2:
            return None
        op_text = _text(op, src)
        if op_text not in _FOLD_OPS:
            return None

        def peel(n):
            while (n is not None and n.type == "paren_expression"
                   and n.named_children):
                n = n.named_children[0]
            return n

        # The self-call is parenthesised (`n * (fact (n-1))`) per the F# grammar
        # quirk — peel the parens before matching the application spine.
        lc = _self_call_args(peel(operands[0]), name, 1, src)
        rc = _self_call_args(peel(operands[1]), name, 1, src)
        if (lc is None) == (rc is None):
            return None
        return (op_text, operands[1], lc[0]) if lc is not None \
            else (op_text, operands[0], rc[0])

    fold_then, fold_else = foldable(then_e), foldable(else_e)
    if (fold_else is None) == (fold_then is None):
        return None
    if fold_else is not None:
        cont = _negate_cond(cond, src)
        op_text, leaf, rec_arg = fold_else
        base = then_e
    else:
        cont = _lower_expr(cond, src)
        op_text, leaf, rec_arg = fold_then
        base = else_e

    pname = params[0]
    if _contains_identifier(base, pname, src):
        return None  # param-dependent base — the transform would mis-evaluate it
    ty = _DEFAULT_TYPE
    sutra_op = _OP_MAP.get(op_text, op_text)
    loop_name = f"_rec_{name}"
    leaf_src = _lower_expr(leaf, src)
    rec_src = _lower_expr(rec_arg, src)
    base_src = _lower_expr(base, src)
    if any("UNSUPPORTED" in s for s in (leaf_src, rec_src, base_src, cont)):
        return None
    loop_decl = (
        f"while_loop {loop_name}({cont}, {ty} {pname} = 0, {ty} _acc = 0) {{\n"
        f"    {ty} _t_n = {rec_src};\n"
        f"    {ty} _t_acc = _acc {sutra_op} {leaf_src};\n"
        f"    {pname} = _t_n;\n"
        f"    _acc = _t_acc;\n"
        f"}}\n"
    )
    fn = (
        f"function {ty} {name}({ty} {pname}) {{\n"
        f"    {ty} _acc = {base_src};\n"
        f"    slot {ty} _{pname}_r = {pname};\n"
        f"    slot {ty} _acc_r = _acc;\n"
        f"    loop {loop_name}({cont}, _{pname}_r, _acc_r);\n"
        f"    return _acc_r;\n"
        f"}}\n"
    )
    return loop_decl + fn


def _lower_expr(node, src: bytes) -> str:
    t = node.type
    if t == "const":
        inner = node.named_children[0] if node.named_children else None
        if inner is not None and inner.type in ("int", "float", "int32", "int64"):
            return _text(inner, src).rstrip("LlmMfF")
        return f"/* UNSUPPORTED-CONST: {inner.type if inner else 'empty'} */"
    if t in ("identifier", "long_identifier", "long_identifier_or_op"):
        return _SUBST.get(_text(node, src), _text(node, src))
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
        # `match scrut with | k1 -> r1 | … | x -> base` → a nested defuzz blend
        # over `scrut == k` tests (the OCaml/Scala literal-match shape). The last
        # rule is the base: a trailing `_`, the final literal for an exhaustive
        # set, or a NAME-BINDING pattern (`| x -> …`) that binds the scrutinee to
        # the name (substituted into the result, the `_MATCH_SUBST` shape).
        # Variant/record patterns are still a later item.
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
                res_src = _lower_expr(res, src)
            elif pat.type == "const":
                test = f"({scrut_src} == {_lower_expr(pat, src)})"
                res_src = _lower_expr(res, src)
            elif pat.type == "identifier_pattern":
                # `| x -> …`: bind the name to the scrutinee, a catch-all base.
                nm = _text(pat, src).strip()
                _SUBST[nm] = f"({scrut_src})"
                try:
                    res_src = _lower_expr(res, src)
                finally:
                    _SUBST.pop(nm, None)
                test = None
            else:
                return f"/* UNSUPPORTED-MATCH-PATTERN: {pat.type} */"
            parsed.append((test, res_src))
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
    if body.type == "if_expression" and params:
        tail = _try_lower_tail_recursive(name, params, body, src)
        if tail is not None:
            return tail
        fold = _try_lower_foldable_nontail(name, params, body, src)
        if fold is not None:
            return fold
    if _contains_self_call(body, name, src):
        # Recursion outside the supported tail/foldable shapes — a plain
        # self-call would not terminate through the fuzzy-if blend. Surface it.
        return (f"// UNSUPPORTED-RECURSION: '{name}' is recursive but not the "
                f"tail-accumulator or foldable non-tail shape\n")
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
    _SUBST.clear()

    out = ["// Generated by sutra-from-fsharp. See sdk/sutra-from-fsharp/README.md.\n"]
    for child in tree.root_node.named_children:
        if child.type == "declaration_expression":
            defn = next((c for c in child.named_children
                         if c.type == "function_or_value_defn"), None)
            if defn is not None:
                out.append(_lower_defn(defn, src))
        # modules/types/namespaces are later items
    return "\n".join(out)
