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


# `case` name-binding patterns: a bound name maps to the (parenthesised)
# scrutinee while lowering that clause's result (the OCaml `_MATCH_SUBST` shape).
_SUBST: dict[str, str] = {}

# Maps -> axons (the Rust struct / OCaml record pattern). A `%{x: a, y: b}`
# literal cannot be lowered inline (axon construction is statement-shaped), so it
# is HOISTED to a prelude temp and `_ARG_HOIST[node.id]` carries the temp name to
# the position where the map appeared. `_AH_COUNTER` numbers the temps per body.
_ARG_HOIST: dict[int, str] = {}
_AH_COUNTER = [0]


def _blend(test_src: str, then_src: str, else_src: str) -> str:
    """Sutra strong-defuzz two-way blend (no control flow) — the shared frontend
    shape (OCaml/Scala `_blend`). Arms fully parenthesised."""
    w = f"truth_axis(defuzzy({test_src}))"
    return f"(((1 + {w}) * ({then_src})) + ((1 - {w}) * ({else_src}))) / 2"


def _map_fields(node, src: bytes):
    """If `node` is an Elixir `%{x: a, y: b}` map literal with atom-key shorthand
    pairs, return [(field, value_node), …]; else None. The `%{"k" => v}` arrow
    form and non-atom keys are a later item."""
    if node.type != "map":
        return None
    content = next((c for c in node.named_children if c.type == "map_content"), None)
    if content is None:
        return None
    kws = next((c for c in content.named_children if c.type == "keywords"), None)
    if kws is None:
        return None
    fields = []
    for pair in kws.named_children:
        if pair.type != "pair" or len(pair.named_children) < 2:
            return None
        key_node, val_node = pair.named_children[0], pair.named_children[-1]
        if key_node.type != "keyword":
            return None  # `"k" => v` arrow form — later item
        field = _text(key_node, src).rstrip().rstrip(":")
        fields.append((field, val_node))
    return fields if fields else None


def _hoist_maps(node, src: bytes, indent: str = "    ") -> str:
    """Post-order walk of a body expression: hoist EVERY map literal to a prelude
    `Axon _ahN; _ahN.add("f", v); …` group and register `node.id → _ahN` in
    `_ARG_HOIST` so `_lower_expr` emits the temp name in place. Returns the
    concatenated prelude statements (possibly empty). Mirrors the Rust
    `_hoist_enum_constructions` shape."""
    prelude = ""
    for child in node.named_children:
        prelude += _hoist_maps(child, src, indent)
    fields = _map_fields(node, src)
    if fields is not None:
        tmp = f"_ah{_AH_COUNTER[0]}"
        _AH_COUNTER[0] += 1
        prelude += f"{indent}Axon {tmp};\n"
        for field, val in fields:
            prelude += f'{indent}{tmp}.add("{field}", {_lower_expr(val, src)});\n'
        _ARG_HOIST[node.id] = tmp
    return prelude


def _dot_accessed_params(body, params: set, src: bytes) -> set:
    """Param names read via dot-access (`p.x`) anywhere in `body` — these are
    maps, so they type as `Axon` rather than the default `number`."""
    found: set = set()

    def walk(n):
        if n.type == "dot" and n.named_children:
            obj = n.named_children[0]
            if obj.type == "identifier" and _text(obj, src) in params:
                found.add(_text(obj, src))
        for c in n.named_children:
            walk(c)

    walk(body)
    return found


def _lower_pipe(left, right, src: bytes) -> str:
    """Lower `left |> right`: insert the lowered `left` as the FIRST argument of the
    `right` call (`x |> f(a)` → `f(x, a)`; `x |> f` → `f(x)`)."""
    piped = _lower_expr(left, src)
    if right.type == "identifier":
        return f"{_text(right, src)}({piped})"
    if right.type == "call":
        name = _call_kw(right, src)
        if name is None:
            return "/* UNSUPPORTED-PIPE: non-identifier call target */"
        args = next((c for c in right.named_children if c.type == "arguments"), None)
        rest = [_lower_expr(a, src)
                for a in (args.named_children if args is not None else [])]
        return f"{name}({', '.join([piped] + rest)})"
    return "/* UNSUPPORTED-PIPE: target is not a call */"


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
    if _ARG_HOIST and node.id in _ARG_HOIST:
        return _ARG_HOIST[node.id]  # a hoisted map literal — emit its temp name
    t = node.type
    if t == "dot":
        # Map field read `p.x` -> the axon item read, projected to a clean
        # number-vector (realvec — raw fillers carry crosstalk, the Rust pattern).
        kids = node.named_children
        if len(kids) == 2 and kids[1].type == "identifier":
            return f'realvec({_lower_expr(kids[0], src)}.item("{_text(kids[1], src)}"))'
        return "/* UNSUPPORTED-EXPR: dot arity */"
    if t == "map":
        # A map literal reaching here was not hoisted — surface the gap.
        return "/* UNSUPPORTED-CONSTRUCTION: map value outside a hoistable position */"
    if t == "integer":
        return _text(node, src).replace("_", "")
    if t == "float":
        return _text(node, src).replace("_", "")
    if t == "identifier":
        text = _text(node, src)
        return _SUBST.get(text, text)
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
        if _text(op, src) == "|>":
            # Pipe: `x |> f(a, b)` ≡ `f(x, a, b)` — insert the left value as the
            # right call's FIRST argument. Nested pipes recurse via `left`.
            return _lower_pipe(left, right, src)
        sop = _OP_MAP.get(_text(op, src))
        if sop is None:
            return f"/* UNSUPPORTED-OP: {_text(op, src)} */"
        return f"({_lower_expr(left, src)} {sop} {_lower_expr(right, src)})"
    if t == "call":
        # Field access `p.x` parses as a zero-arg `call` wrapping a `dot`.
        dot = next((c for c in node.named_children if c.type == "dot"), None)
        has_args = any(c.type == "arguments" for c in node.named_children)
        if dot is not None and not has_args:
            return _lower_expr(dot, src)
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
                if pat.type == "integer":
                    res_src = _lower_expr(bd.named_children[-1], src)
                    parsed.append((f"({scrut_src} == {_text(pat, src)})", res_src))
                elif pat.type == "identifier":
                    # `_` is an anonymous catch-all; any other name BINDS the
                    # scrutinee (substituted into the clause result) — a catch-all
                    # base either way. The OCaml `_MATCH_SUBST` shape.
                    nm = _text(pat, src)
                    if nm == "_":
                        res_src = _lower_expr(bd.named_children[-1], src)
                    else:
                        _SUBST[nm] = f"({scrut_src})"
                        try:
                            res_src = _lower_expr(bd.named_children[-1], src)
                        finally:
                            _SUBST.pop(nm, None)
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


def _guard_split(head, src: bytes):
    """A guarded clause head is `call(...) when guard` — a `binary_operator` whose
    operator token is `when`, left operand the call/identifier head, right operand
    the guard expression. Return (inner_head, guard_node); else (head, None)."""
    if head.type == "binary_operator" and len(head.named_children) == 2:
        left, right = head.named_children[0], head.named_children[1]
        if src[left.end_byte:right.start_byte].decode("utf-8").strip() == "when":
            return left, right
    return head, None


def _def_head(def_call, src: bytes):
    """Decompose `call(def, arguments(head [, keywords(do: expr)]) [, do_block])`
    into (name, [param_pattern_nodes], body_expr_node, guard_node_or_None) or None.
    `head` is either `call(name, arguments(patterns…))`, a bare `identifier`
    (zero-arg), or a `when`-guarded form of either. Param patterns are returned as
    raw nodes so the multi-clause dispatcher can inspect them; `_def_parts` is the
    bare-param view for the single-clause path (which rejects guards)."""
    kids = def_call.named_children
    args = next((c for c in kids if c.type == "arguments"), None)
    if args is None or not args.named_children:
        return None
    head, guard = _guard_split(args.named_children[0], src)
    param_nodes: list = []
    if head.type == "call":
        name_node = head.named_children[0] if head.named_children else None
        if name_node is None or name_node.type != "identifier":
            return None
        name = _text(name_node, src)
        head_args = next((c for c in head.named_children if c.type == "arguments"), None)
        if head_args is not None:
            param_nodes = list(head_args.named_children)
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
    return name, param_nodes, body, guard


def _def_parts(def_call, src: bytes):
    """Single-clause view: (name, param_names, body) with BARE-identifier params
    only (literal/pattern params → None, handled by the clause dispatcher)."""
    head = _def_head(def_call, src)
    if head is None:
        return None
    name, param_nodes, body, guard = head
    if guard is not None:
        return None  # guarded clause → routes through the clause dispatcher
    params: list[str] = []
    for p in param_nodes:
        if p.type != "identifier":
            return None  # pattern params (literals, tuples) → multi-clause path
        params.append(_text(p, src))
    return name, params, body


def _lower_def_clauses(name: str, clauses, src: bytes) -> str:
    """Lower a group of same-name/arity `def` heads into ONE dispatching Sutra
    function — a nested defuzz blend over the clauses (the `case`/`_MATCH` shape
    lifted to function heads). Each clause's params are matched positionally:
    an integer-literal pattern becomes an `(_ai == k)` test; an identifier
    pattern binds that name to `_ai` (the `_SUBST` shape) and contributes no
    test. A clause with no literal patterns and no guard is a catch-all; the LAST
    clause is the base (Elixir's first-match-wins, lifted to the blend). A `when`
    GUARD lowers to a test ANDed with the clause's pattern tests (the guard
    references the params, which are bound to `_ai` while it is lowered). `clauses`
    is a list of (param_pattern_nodes, body_node, guard_node_or_None)."""
    arity = len(clauses[0][0])
    for _pn, body, _gd in clauses:
        if _contains_self_call(body, name, src):
            return (f"// UNSUPPORTED-RECURSION: '{name}' multi-clause dispatch with "
                    f"recursion (later item)\n")
    argnames = [f"_a{i}" for i in range(arity)]
    parsed = []  # (test_src_or_None, result_src)
    for param_nodes, body, guard in clauses:
        if len(param_nodes) != arity:
            return f"// UNSUPPORTED-DEF: '{name}' clause arity mismatch\n"
        tests: list[str] = []
        binds: list[tuple[str, str]] = []
        for i, p in enumerate(param_nodes):
            if p.type == "integer":
                tests.append(f"({argnames[i]} == {_text(p, src).replace('_', '')})")
            elif p.type == "identifier":
                nm = _text(p, src)
                if nm != "_":
                    binds.append((nm, argnames[i]))
            else:
                return (f"// UNSUPPORTED-DEF: '{name}' clause has pattern param "
                        f"{p.type} (later item)\n")
        for nm, sub in binds:
            _SUBST[nm] = sub
        try:
            res_src = _lower_expr(body, src)
            guard_src = _lower_expr(guard, src) if guard is not None else None
        finally:
            for nm, _sub in binds:
                _SUBST.pop(nm, None)
        if "UNSUPPORTED" in res_src or (guard_src and "UNSUPPORTED" in guard_src):
            return f"// UNSUPPORTED-DEF: '{name}' clause body not lowerable\n"
        if guard_src is not None:
            tests.append(f"({guard_src})")
        test = " && ".join(tests) if tests else None
        parsed.append((test, res_src))
    expr = parsed[-1][1]  # last clause = base
    for test, res in reversed(parsed[:-1]):
        expr = res if test is None else _blend(test, res, expr)
    params_src = ", ".join(f"{_TYPE} {a}" for a in argnames)
    return (f"function {_TYPE} {name}({params_src}) {{\n"
            f"    return {expr};\n"
            f"}}\n")


def _lower_defs(def_calls, src: bytes) -> list:
    """Group `def`s by (name, arity); a single-clause bare-param group routes
    through `_lower_def` (so the tail/fold recursion transforms still own it),
    while a multi-clause group — or any group with a literal/pattern param —
    becomes one dispatching function via `_lower_def_clauses`."""
    groups: dict = {}
    order: list = []
    out: list = []
    for dc in def_calls:
        head = _def_head(dc, src)
        if head is None:
            out.append(_lower_def(dc, src))  # surfaces UNSUPPORTED-DEF
            continue
        name, param_nodes, body, guard = head
        key = (name, len(param_nodes))
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append((dc, param_nodes, body, guard))
    for key in order:
        members = groups[key]
        bare_single = (len(members) == 1
                       and members[0][3] is None  # no guard
                       and all(p.type == "identifier" for p in members[0][1]))
        if bare_single:
            out.append(_lower_def(members[0][0], src))
        else:
            out.append(_lower_def_clauses(
                key[0], [(pn, bd, gd) for _dc, pn, bd, gd in members], src))
    return out


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
    # Maps -> axons: hoist any `%{…}` literals in the body to prelude temps, and
    # type any dot-accessed param as `Axon` (it is a map, not a number).
    _ARG_HOIST.clear()
    prelude = _hoist_maps(body, src)
    axon_params = _dot_accessed_params(body, set(params), src)
    params_src = ", ".join(
        f"{'Axon' if p in axon_params else _TYPE} {p}" for p in params)
    body_src = _lower_expr(body, src)
    _ARG_HOIST.clear()
    return (f"function {_TYPE} {name}({params_src}) {{\n"
            f"{prelude}"
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
    _SUBST.clear()
    _ARG_HOIST.clear()
    _AH_COUNTER[0] = 0

    out = ["// Generated by sutra-from-elixir. See sdk/sutra-from-elixir/README.md.\n"]
    for child in tree.root_node.named_children:
        kw = _call_kw(child, src)
        if kw == "defmodule":
            do_block = next((c for c in child.named_children if c.type == "do_block"),
                            None)
            if do_block is None:
                out.append("// UNSUPPORTED-MODULE: defmodule without body\n")
                continue
            # Collect `def` members and group by (name, arity) so multi-clause
            # heads lower to ONE dispatching function (defp/defstruct/use/alias
            # are later items).
            defs = [m for m in do_block.named_children if _call_kw(m, src) == "def"]
            out.extend(_lower_defs(defs, src))
        elif kw == "def":
            out.extend(_lower_defs([child], src))
    return "\n".join(out)
