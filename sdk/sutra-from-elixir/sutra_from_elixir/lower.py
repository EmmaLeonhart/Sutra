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


# Sutra comparison op → its negation (halt condition → loop continue condition).
_NEG_CMP = {"==": "!=", "!=": "==", "<": ">=", ">": "<=", "<=": ">", ">=": "<"}


def _self_call_args(node, name: str, arity: int, src: bytes):
    """If `node` is `name(a…)` at the right arity, return the arg nodes; else None."""
    if node.type != "call" or _call_kw(node, src) != name:
        return None
    args_node = next((c for c in node.named_children if c.type == "arguments"), None)
    args = list(args_node.named_children) if args_node is not None else []
    return args if len(args) == arity else None


def _negate_cond(cond, src: bytes) -> str:
    """Negate a halt condition into the loop's continue condition (the OCaml
    `_negate_cond` shape): a single `binary_operator` comparison inverts via
    `_NEG_CMP`, else `!(…)`."""
    if cond.type == "binary_operator":
        op = cond.child_by_field_name("operator")
        left = cond.child_by_field_name("left")
        right = cond.child_by_field_name("right")
        if op is not None and left is not None and right is not None:
            sop = _OP_MAP.get(_text(op, src))
            neg = _NEG_CMP.get(sop) if sop else None
            if neg is not None:
                return f"{_lower_expr(left, src)} {neg} {_lower_expr(right, src)}"
    return f"!({_lower_expr(cond, src)})"


def _try_lower_tail_recursive(name: str, params, body, src: bytes):
    """Lower a TAIL-recursive `def f(p…) do if COND do BASE else f(a…) end end` to
    a declared Sutra `while_loop` (the OCaml/Scala/F#/Rust/Haskell shape ported).
    `body` is the `if` call; `params` is a list of names. Returns Sutra or None."""
    if body.type != "call" or _call_kw(body, src) != "if":
        return None
    args_node = next((c for c in body.named_children if c.type == "arguments"), None)
    do_block = next((c for c in body.named_children if c.type == "do_block"), None)
    if args_node is None or not args_node.named_children or do_block is None:
        return None
    cond = args_node.named_children[0]
    then_forms, else_forms = _do_block_value(do_block, src)
    if not then_forms or not else_forms:
        return None  # both arms required (the if must have an else)
    then_e, else_e = then_forms[-1], else_forms[-1]
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


# Associative + commutative combine ops for the non-tail fold transform.
_FOLD_OPS = {"+", "*"}


def _contains_identifier_node(node, ident: str, src: bytes) -> bool:
    if node.type == "identifier" and _text(node, src) == ident:
        return True
    return any(_contains_identifier_node(c, ident, src) for c in node.named_children)


def _try_lower_foldable_nontail(name: str, params, body, src: bytes):
    """CPS / accumulator transform for a FOLDABLE non-tail
    `def f(n) do if COND do BASE else LEAF <OP> f(REC) end end` (single param, OP
    in `_FOLD_OPS`): the pending call-stack work is reified as an accumulator
    carried by a Sutra `while_loop` trampoline — the OCaml/Scala/F#/Rust/Haskell/
    Clojure shape ported. BASE is evaluated pre-loop at the INITIAL param, so a
    param-dependent BASE is rejected (→ None). Returns loop decl + function, or
    None."""
    if body.type != "call" or _call_kw(body, src) != "if" or len(params) != 1:
        return None
    args_node = next((c for c in body.named_children if c.type == "arguments"), None)
    do_block = next((c for c in body.named_children if c.type == "do_block"), None)
    if args_node is None or not args_node.named_children or do_block is None:
        return None
    cond = args_node.named_children[0]
    then_forms, else_forms = _do_block_value(do_block, src)
    if not then_forms or not else_forms:
        return None
    then_e, else_e = then_forms[-1], else_forms[-1]

    def foldable(node):
        if node.type != "binary_operator":
            return None
        op = node.child_by_field_name("operator")
        left = node.child_by_field_name("left")
        right = node.child_by_field_name("right")
        if op is None or left is None or right is None:
            return None
        op_text = _text(op, src)
        if op_text not in _FOLD_OPS:
            return None
        lc = _self_call_args(left, name, 1, src)
        rc = _self_call_args(right, name, 1, src)
        if (lc is None) == (rc is None):
            return None
        return (op_text, right, lc[0]) if lc is not None else (op_text, left, rc[0])

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
    if _contains_identifier_node(base, pname, src):
        return None  # param-dependent base — the transform would mis-evaluate it
    ty = _TYPE
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
        if kw == "case":
            # case(scrut, do_block(stab_clause(arguments(pat), body(res)), …)) →
            # a nested defuzz blend over `scrut == k` tests; the last clause is
            # the base (`_` catch-all, or the final literal). Literal patterns
            # only — a name-binding pattern needs substitution (a later item).
            kids = node.named_children
            args = next((c for c in kids if c.type == "arguments"), None)
            do_block = next((c for c in kids if c.type == "do_block"), None)
            if args is None or not args.named_children or do_block is None:
                return "/* UNSUPPORTED-EXPR: malformed case */"
            scrut_src = _lower_expr(args.named_children[0], src)
            parsed = []
            for cl in do_block.named_children:
                if cl.type != "stab_clause":
                    continue
                pa = next((c for c in cl.named_children if c.type == "arguments"), None)
                bd = next((c for c in cl.named_children if c.type == "body"), None)
                if pa is None or not pa.named_children or bd is None \
                        or not bd.named_children:
                    return "/* UNSUPPORTED-CASE: malformed clause */"
                pat = pa.named_children[0]
                res_src = _lower_expr(bd.named_children[-1], src)
                if pat.type == "integer":
                    parsed.append((f"({scrut_src} == {_text(pat, src)})", res_src))
                elif pat.type == "identifier" and _text(pat, src) == "_":
                    parsed.append((None, res_src))  # catch-all base
                else:
                    return f"/* UNSUPPORTED-CASE-PATTERN: {pat.type} */"
            if not parsed:
                return "/* UNSUPPORTED-EXPR: empty case */"
            expr = parsed[-1][1]
            for test, res in reversed(parsed[:-1]):
                expr = res if test is None else _blend(test, res, expr)
            return expr
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
    if params:
        rec = _try_lower_tail_recursive(name, params, body, src)
        if rec is not None:
            return rec
        fold = _try_lower_foldable_nontail(name, params, body, src)
        if fold is not None:
            return fold
    if _contains_self_call(body, name, src):
        # Recursion outside the supported tail/foldable shapes — a plain
        # self-calling Sutra function would not terminate through the fuzzy-if
        # blend. Surface the gap rather than mislower.
        return f"// UNSUPPORTED-RECURSION: '{name}' is recursive but not the tail-accumulator or foldable non-tail shape\n"
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
