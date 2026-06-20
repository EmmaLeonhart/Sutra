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
    # `<>` is Elixir binary/string concatenation; on the substrate string concat
    # is the same `+` codepoint-array append OCaml's `^` lowers to (the result
    # eq_synthetic-matches the concatenated literal). The compiler routes `+` to
    # substrate concat when the operands are String-typed.
    "<>": "+",
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


def _static_key_field(node, src: bytes):
    """The static axon-field name for an arrow-map key, or None. A plain string `"k"`
    → `k`; a number `1` → `1` (the number's text, so `%{1 => v}` is the same
    named-field axon as a string/atom map and `m[1]` reads it back). Interpolated
    strings and other key shapes have no static field name → None."""
    if node.type == "integer":
        return _text(node, src).strip()
    if node.type != "string":
        return None
    parts = node.named_children
    if len(parts) == 1 and parts[0].type == "quoted_content":
        return _text(parts[0], src)
    if len(parts) == 0:  # empty string "" — degenerate, skip
        return None
    return None  # interpolation / escapes — not a static field name


def _map_fields(node, src: bytes):
    """If `node` is an Elixir map literal whose keys are all static field names,
    return [(field, value_node), …]; else None. Two key forms are supported:
    atom-key shorthand `%{x: a, y: b}` and the string-key arrow form
    `%{"k" => v}` — both lower to the same named-field axon (`.add("k", v)` /
    `.item("k")`), so a string-keyed map and an atom-keyed map are structurally
    identical axons. A struct literal `%Name{x: a, y: b}` also parses as a `map`
    (with an extra `struct` child for the nominal type); it lowers to the same
    named-field axon, the struct alias dropped — the Rust
    `struct`-as-named-field-axon shape. Non-atom/non-string keys (numeric,
    interpolated, variable) are still unsupported and make this return None."""
    if node.type != "map":
        return None
    content = next((c for c in node.named_children if c.type == "map_content"), None)
    if content is None:
        return None
    fields = []
    # Atom-key shorthand: pairs nest inside a `keywords` node.
    kws = next((c for c in content.named_children if c.type == "keywords"), None)
    if kws is not None:
        for pair in kws.named_children:
            if pair.type != "pair" or len(pair.named_children) < 2:
                return None
            key_node, val_node = pair.named_children[0], pair.named_children[-1]
            if key_node.type != "keyword":
                return None
            field = _text(key_node, src).rstrip().rstrip(":")
            fields.append((field, val_node))
        return fields if fields else None
    # Arrow form: `key => value` pairs are `binary_operator` children directly
    # under `map_content`. String and numeric keys give a static field name.
    for child in content.named_children:
        if child.type != "binary_operator" or len(child.named_children) < 2:
            return None
        key_node, val_node = child.named_children[0], child.named_children[-1]
        field = _static_key_field(key_node, src)
        if field is None:
            return None  # non-string/non-numeric arrow key — unsupported
        fields.append((field, val_node))
    return fields if fields else None


def _tuple_fields(node, src: bytes):
    """If `node` is a tuple literal `{a, b, …}`, return [("_0", a), ("_1", b), …] —
    a tuple is a positional-key axon (`elem(t, i)` reads `_i`). Else None."""
    if node.type != "tuple":
        return None
    elems = node.named_children
    if not elems:
        return None
    return [(f"_{i}", el) for i, el in enumerate(elems)]


def _hoist_maps(node, src: bytes, indent: str = "    ") -> str:
    """Post-order walk of a body expression: hoist EVERY map OR tuple literal to a
    prelude `Axon _ahN; _ahN.add("f", v); …` group and register `node.id → _ahN` in
    `_ARG_HOIST` so `_lower_expr` emits the temp name in place. Returns the
    concatenated prelude statements (possibly empty). Mirrors the Rust
    `_hoist_enum_constructions` shape."""
    prelude = ""
    for child in node.named_children:
        prelude += _hoist_maps(child, src, indent)
    fields = _map_fields(node, src)
    if fields is None:
        fields = _tuple_fields(node, src)  # tuples lower to positional-key axons
    if fields is not None:
        tmp = f"_ah{_AH_COUNTER[0]}"
        _AH_COUNTER[0] += 1
        prelude += f"{indent}Axon {tmp};\n"
        for field, val in fields:
            prelude += f'{indent}{tmp}.add("{field}", {_lower_expr(val, src)});\n'
        _ARG_HOIST[node.id] = tmp
    return prelude


def _dot_accessed_params(body, params: set, src: bytes) -> set:
    """Param names read as maps/tuples anywhere in `body` — via atom-key dot-access
    (`p.x`), string-key index-access (`m["k"]`), or `elem(t, i)` tuple access — these
    are axons, so they type as `Axon` rather than the default `number`."""
    found: set = set()

    def walk(n):
        obj = None
        if n.type == "dot" and n.named_children:
            obj = n.named_children[0]
        elif n.type == "access_call" and len(n.named_children) == 2 \
                and _static_key_field(n.named_children[1], src) is not None:
            obj = n.named_children[0]
        elif n.type == "call" and _call_kw(n, src) == "elem":
            args = next((c for c in n.named_children if c.type == "arguments"), None)
            an = list(args.named_children) if args is not None else []
            if len(an) == 2 and an[1].type == "integer":
                obj = an[0]
        if obj is not None and obj.type == "identifier" and _text(obj, src) in params:
            found.add(_text(obj, src))
        for c in n.named_children:
            walk(c)

    walk(body)
    return found


def _concat_operand_params(body, params: set, src: bytes) -> set:
    """Param names used as an operand of `<>` anywhere in `body`. In Elixir `<>` is
    binary/string concatenation only, so such a param is provably a `String` — it
    types as `String` (not the default `number`) so the compiler routes the `<>`-
    lowered `+` to substrate string concat rather than numeric add."""
    found: set = set()

    def walk(n):
        if n.type == "binary_operator" and len(n.named_children) == 2:
            op = next((c for c in n.children if not c.is_named), None)
            if op is not None and _text(op, src) == "<>":
                for side in n.named_children:
                    if side.type == "identifier" and _text(side, src) in params:
                        found.add(_text(side, src))
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


# Elixir type-test guards that DO lower natively (measured in
# planning/findings/2026-06-18-substrate-type-tests.md). Each maps to a
# substrate-pure truth-returning builtin (`is_string_truth` / `is_axon_truth` /
# `is_number_truth`, codegen_base.BUILTINS) that scatters `2*flag - 1` onto
# AXIS_TRUTH over an existing tag axis, so the guard composes in the `defuzzy`
# clause-dispatch blend. (`is_binary` additionally needs Elixir string-literal-arg
# lowering, which now works.)
_TYPE_TEST_LOWER = {
    "is_binary": "is_string_truth",
    "is_bitstring": "is_string_truth",
    "is_list": "is_axon_truth",
    "is_map": "is_axon_truth",
    "is_tuple": "is_axon_truth",
    "is_number": "is_number_truth",
}

# Elixir type-test guard predicates that still do NOT lower (queue §0.6; same
# finding). Two classes: UNREPRESENTABLE (int and float are the identical real-axis
# vector, so no axis check separates them) and not-yet-built (a clean substrate
# axis exists but the boundary is subtle / no substrate notion yet).
_TYPE_TEST_GUARDS = {
    "is_integer": "unrepresentable: int N and float N are the bit-identical "
                  "real-axis vector on the substrate (measured); no axis check "
                  "separates is_integer from is_float. Needs a core int/float tag.",
    "is_float": "unrepresentable: see is_integer (int and float share the "
                "identical substrate vector).",
    "is_atom": "tag-checkable (atoms lower to string-flag codepoint arrays) but "
               "not yet built; booleans-as-atoms make the boundary subtle.",
    "is_boolean": "tag-checkable (AXIS_TRUTH-only value) but not yet built.",
    "is_nil": "no substrate notion of nil yet.",
    "is_function": "no substrate notion of a first-class function value yet.",
}


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


def _if_parts(body, src: bytes):
    """An Elixir `if COND do THEN else ELSE end` call → (cond_node, then_e, else_e),
    else None. Factored out so both the if-based recursion path and the synthesized
    multi-clause-recursion path feed the transforms uniformly."""
    if body.type != "call" or _call_kw(body, src) != "if":
        return None
    args_node = next((c for c in body.named_children if c.type == "arguments"), None)
    do_block = next((c for c in body.named_children if c.type == "do_block"), None)
    if args_node is None or not args_node.named_children or do_block is None:
        return None
    then_forms, else_forms = _do_block_value(do_block, src)
    if not then_forms or not else_forms:
        return None  # both arms required (the if must have an else)
    return args_node.named_children[0], then_forms[-1], else_forms[-1]


def _try_lower_tail_recursive(name: str, params, cond_src, neg_src, then_e, else_e,
                              src: bytes):
    """Lower a TAIL-recursive `def f(p…) do if COND do BASE else f(a…) end end` to
    a declared Sutra `while_loop` (the OCaml/Scala/F#/Rust/Haskell shape ported).
    `cond_src`/`neg_src` are the lowered base-match test + its negation (passed as
    strings so a multi-clause head can synthesize them). Returns Sutra or None."""
    arity = len(params)
    then_args = _self_call_args(then_e, name, arity, src)
    else_args = _self_call_args(else_e, name, arity, src)
    if (then_args is None) == (else_args is None):
        return None
    if else_args is not None:
        cont = neg_src
        rec_args, base = else_args, then_e
    else:
        cont = cond_src
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
# Multiplicative/additive identity for seeding a non-tail fold accumulator
# (both `_FOLD_OPS` ops are commutative + associative with a known identity, so a
# post-loop `acc OP base` combine reproduces the call-stack order).
_FOLD_IDENTITY = {"+": "0", "*": "1"}


def _foldable_step(node, name: str, src: bytes):
    """For a single non-tail fold step `LEAF <OP> f(REC)` (or `f(REC) <OP> LEAF`),
    with OP in `_FOLD_OPS` and exactly ONE side an arity-1 self-call to `name`:
    return `(op_text, leaf_node, rec_arg_node)`, else None. Shared by the single-base
    `_try_lower_foldable_nontail` and the multibase non-tail fold path."""
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


def _foldable_step_multi(node, name: str, arity: int, src: bytes):
    """Like `_foldable_step` but for an arity-N self-call: `LEAF <OP> f(REC0, REC1, …)`
    (or the call on the left). Returns `(op_text, leaf_node, [rec_arg_nodes])` — the
    full recursion arg list, so a MULTI-arg non-tail fold can carry every arg through
    the trampoline. Else None."""
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
    lc = _self_call_args(left, name, arity, src)
    rc = _self_call_args(right, name, arity, src)
    if (lc is None) == (rc is None):
        return None
    return (op_text, right, lc) if lc is not None else (op_text, left, rc)


def _contains_identifier_node(node, ident: str, src: bytes) -> bool:
    if node.type == "identifier" and _text(node, src) == ident:
        return True
    return any(_contains_identifier_node(c, ident, src) for c in node.named_children)


def _try_lower_foldable_nontail(name: str, params, cond_src, neg_src, then_e, else_e,
                                src: bytes):
    """CPS / accumulator transform for a FOLDABLE non-tail
    `def f(n) do if COND do BASE else LEAF <OP> f(REC) end end` (single param, OP
    in `_FOLD_OPS`): the pending call-stack work is reified as an accumulator
    carried by a Sutra `while_loop` trampoline — the OCaml/Scala/F#/Rust/Haskell/
    Clojure shape ported. BASE is evaluated pre-loop at the INITIAL param, so a
    param-dependent BASE is rejected (→ None). `cond_src`/`neg_src` are the lowered
    base-match test + negation (strings, so a multi-clause head can synthesize
    them). Returns loop decl + function, or None."""
    if len(params) != 1:
        return None

    fold_then = _foldable_step(then_e, name, src)
    fold_else = _foldable_step(else_e, name, src)
    if (fold_else is None) == (fold_then is None):
        return None
    if fold_else is not None:
        cont = neg_src
        op_text, leaf, rec_arg = fold_else
        base = then_e
    else:
        cont = cond_src
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
    if t == "access_call":
        # String-key map read `m["k"]` -> the axon item read, same projection as
        # the atom-key `p.x` path (a string-keyed map is the same named-field axon).
        kids = node.named_children
        if len(kids) == 2:
            field = _static_key_field(kids[1], src)
            if field is not None:
                return f'realvec({_lower_expr(kids[0], src)}.item("{field}"))'
        return "/* UNSUPPORTED-EXPR: access_call (non-string key) */"
    if t == "map":
        # A map literal reaching here was not hoisted — surface the gap.
        return "/* UNSUPPORTED-CONSTRUCTION: map value outside a hoistable position */"
    if t == "integer":
        return _text(node, src).replace("_", "")
    if t == "float":
        return _text(node, src).replace("_", "")
    if t == "string":
        # A plain Elixir string literal `"…"` → a Sutra string literal (string-flag
        # codepoint array); `_text` keeps the quotes. `==` / a `case`/`when` string
        # pattern routes to eq_synthetic. Interpolated strings (`"#{x}"`) carry an
        # `interpolation` child and are a later item — they fall through.
        if not any(c.type == "interpolation" for c in node.named_children):
            return _text(node, src)
        return "/* UNSUPPORTED-EXPR: interpolated string */"
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
                if pat.type in ("integer", "boolean", "string"):
                    # `0 -> …` / `true -> …` / `"foo" -> …` literal pattern: dispatch the
                    # scrutinee directly (`scrut == k`). For a string, `==` routes to
                    # eq_synthetic (Euclidean on the codepoint array), which separates
                    # strings cleanly; `_text` keeps the quotes (the Sutra literal form).
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
            args = next((c for c in node.named_children if c.type == "arguments"), None)
            arg_nodes = list(args.named_children) if args is not None else []
            # `elem(t, i)` — tuple read at a STATIC index → the positional axon field
            # `_i` (the map/struct field-read shape). `i` must be an integer literal.
            if kw == "elem" and len(arg_nodes) == 2 and arg_nodes[1].type == "integer":
                idx = _text(arg_nodes[1], src).strip()
                return f'realvec({_lower_expr(arg_nodes[0], src)}.item("_{idx}"))'
            # Type-test guards (`is_binary(s)`, `is_list(x)`, `is_number(n)`, …). On a
            # substrate where every value is a vector, a type test means an axis/tag
            # check. The tag-checkable subset lowers to a substrate-pure truth-builtin
            # over its tag axis (AXIS_STRING_FLAG / AXIS_AXON_POPULATED / neither). See
            # planning/findings/2026-06-18-substrate-type-tests.md. (queue §0.6)
            if kw in _TYPE_TEST_LOWER and len(arg_nodes) == 1:
                return f"{_TYPE_TEST_LOWER[kw]}({_lower_expr(arg_nodes[0], src)})"
            # The rest still don't lower: `is_integer` vs `is_float` is FUNDAMENTALLY
            # UNREPRESENTABLE (int 2 and float 2.0 are the bit-identical real-axis
            # vector, measured ||diff||=0); is_atom/is_boolean/is_nil/is_function are
            # not yet built. Emit an UNSUPPORTED-GUARD marker (routes the clause to the
            # WASM fallback) rather than a call to a nonexistent runtime function.
            if kw in _TYPE_TEST_GUARDS:
                reason = _TYPE_TEST_GUARDS[kw]
                return f"/* UNSUPPORTED-GUARD: {kw} — {reason} */"
            # Ordinary application `f(a, b)`.
            arg_srcs = [_lower_expr(a, src) for a in arg_nodes]
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
    into (name, [param_pattern_nodes], body_expr_node, guard_node_or_None,
    prelude_stmts) or None. `head` is either `call(name, arguments(patterns…))`, a
    bare `identifier` (zero-arg), or a `when`-guarded form of either. `prelude_stmts`
    is the do-block statements BEFORE the final value expression (leading `=`
    pattern-match bindings); empty for an inline `, do: expr` body. Param patterns
    are returned as raw nodes so the multi-clause dispatcher can inspect them;
    `_def_parts` is the bare-param view for the single-clause path (rejects guards)."""
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
    # Body: inline `, do: expr` (a keywords pair) or a do_block. For a do_block, the
    # final statement is the value; the leading statements are `=` binding prelude.
    body = None
    prelude_stmts: list = []
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
                body = stmts[-1]
                prelude_stmts = stmts[:-1]
    if body is None:
        return None
    return name, param_nodes, body, guard, prelude_stmts


def _def_parts(def_call, src: bytes):
    """Single-clause view: (name, param_names, body, prelude_stmts) with
    BARE-identifier params only (literal/pattern params → None, handled by the
    clause dispatcher). `prelude_stmts` carries leading `=` binding statements."""
    head = _def_head(def_call, src)
    if head is None:
        return None
    name, param_nodes, body, guard, prelude_stmts = head
    if guard is not None:
        return None  # guarded clause → routes through the clause dispatcher
    params: list[str] = []
    for p in param_nodes:
        if p.type != "identifier":
            return None  # pattern params (literals, tuples) → multi-clause path
        params.append(_text(p, src))
    return name, params, body, prelude_stmts


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
    is a list of (param_pattern_nodes, body_node, guard_node_or_None, prelude_stmts).
    `prelude_stmts` are leading `=` destructure bindings in the clause body (`{a, b} =
    t`, `%{x: a} = m`, `x = name`) — applied per clause via `_apply_match_binding`."""
    arity = len(clauses[0][0])
    for _pn, body, _gd, _pre in clauses:
        if _contains_self_call(body, name, src):
            return (f"// UNSUPPORTED-RECURSION: '{name}' multi-clause dispatch with "
                    f"recursion (later item)\n")
    argnames = [f"_a{i}" for i in range(arity)]
    axon_args: set = set()  # argnames bound by a tuple PATTERN param (axon-typed)
    parsed = []  # (test_src_or_None, result_src)
    for param_nodes, body, guard, prelude_stmts in clauses:
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
            elif (p.type == "tuple" and p.named_children
                  and all(e.type == "identifier" for e in p.named_children)):
                # `{a, b}` tuple-PATTERN param — the arg is a positional-key axon;
                # each element binds to the field read `realvec(_ai.item("_j"))`
                # (the same projection `elem(t, j)` uses). Nested / non-identifier
                # elements are a later item (fall through to UNSUPPORTED below).
                axon_args.add(argnames[i])
                for j, e in enumerate(p.named_children):
                    binds.append((_text(e, src),
                                  f'realvec({argnames[i]}.item("_{j}"))'))
            elif p.type == "map":
                # `%{x: a}` (atom shorthand) OR `%{"x" => a}` (string-key arrow) map-PATTERN
                # param — the arg is a named-field axon; each pair binds its identifier local
                # to the field read `realvec(_ai.item("x"))` (the `p.x` projection). Both key
                # forms reuse `_map_fields` (atom and string keys give the same named-field
                # axon); only identifier locals are in scope (a nested/non-identifier value
                # is a later item).
                mf = _map_fields(p, src)
                if mf is None or any(vn.type != "identifier" for _f, vn in mf):
                    return (f"// UNSUPPORTED-DEF: '{name}' map-pattern param is not an "
                            f"atom-/string-key map of identifier locals (later item)\n")
                axon_args.add(argnames[i])
                for field, local_node in mf:
                    binds.append((_text(local_node, src),
                                  f'realvec({argnames[i]}.item("{field}"))'))
            else:
                return (f"// UNSUPPORTED-DEF: '{name}' clause has pattern param "
                        f"{p.type} (later item)\n")
        for nm, sub in binds:
            _SUBST[nm] = sub
        # Leading `=` destructure bindings in this clause body (`{a, b} = t`, …) bind
        # via `_SUBST` on top of the param binds (so a destructure of a param resolves
        # through `_ai`). The RHS param is typed `Axon` (added to `axon_args`).
        pre_names: list = []
        pre_ok = all(_apply_match_binding(st, src, pre_names, axon_args)
                     for st in prelude_stmts)
        try:
            if not pre_ok:
                return (f"// UNSUPPORTED-DEF: '{name}' clause body binding statement "
                        f"is not a supported `=` destructure (later item)\n")
            res_src = _lower_expr(body, src)
            guard_src = _lower_expr(guard, src) if guard is not None else None
        finally:
            for nm in pre_names:
                _SUBST.pop(nm, None)
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
    params_src = ", ".join(
        f"{'Axon' if a in axon_args else _TYPE} {a}" for a in argnames)
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
        name, param_nodes, body, guard, prelude_stmts = head
        key = (name, len(param_nodes))
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append((dc, param_nodes, body, guard, prelude_stmts))
    for key in order:
        members = groups[key]
        bare_single = (len(members) == 1
                       and members[0][3] is None  # no guard
                       and all(p.type == "identifier" for p in members[0][1]))
        if bare_single:
            out.append(_lower_def(members[0][0], src))
        else:
            multi_rec = _try_lower_multiclause_recursion(key[0], members, src)
            if multi_rec is not None:
                out.append(multi_rec)
            elif (mb := _try_lower_multibase_multiclause_recursion(
                    key[0], members, src)) is not None:
                out.append(mb)
            else:
                # Clause bodies may carry leading `=` destructure bindings (m[4]);
                # `_lower_def_clauses` applies them per clause via `_apply_match_binding`.
                out.append(_lower_def_clauses(
                    key[0], [(pn, bd, gd, pre) for _dc, pn, bd, gd, pre in members], src))
    return out


def _try_lower_multiclause_recursion(name: str, members, src: bytes):
    """The idiomatic pattern-matched recursion `def f(0), do: BASE` + `def f(n), do:
    … f(n-1)` (and the multi-arg accumulator `def sum(0, acc), do: acc; def sum(n,
    acc), do: sum(n-1, acc+n)`, and the GUARDED form `def fac(n) when n == 0, do: 1;
    def fac(n), do: n*fac(n-1)`) is semantically identical to the single-clause
    `if`-form, so derive the base-match condition and reuse the recursion transforms
    (fed source strings). Scope: exactly 2 same-arity clauses — a recursive clause
    with ALL IDENTIFIER params, no guard, and a self-call, plus a BASE clause (no
    self-call) distinguished EITHER by exactly one INTEGER-literal param (Mode A:
    cond `(V == K)`) OR by a `when` guard with all-identifier params (Mode B: cond =
    the lowered guard). The recursive clause's names are the synthesized params; the
    base clause's identifier params are renamed to them by position (via `_SUBST`),
    applied to both the base body and (Mode B) the guard. `members` are the
    `_lower_defs` tuples `(dc, param_nodes, body, guard, prelude)`. Returns Sutra or
    None."""
    if len(members) != 2:
        return None
    parsed = []
    for _dc, param_nodes, body, guard, prelude in members:
        if prelude or not param_nodes:
            return None
        parsed.append((param_nodes, body, guard))
    arity = len(parsed[0][0])
    if any(len(p[0]) != arity for p in parsed):
        return None
    base = rec = None
    rec_guard = None
    for params, body, guard in parsed:
        sc = _contains_self_call(body, name, src)
        if all(p.type == "identifier" for p in params) and sc:
            # The recursive clause: all-identifier params + a self-call. Its guard
            # may be None (the catch-all recursive of Mode A/B) OR an explicit
            # `when` guard (Mode C — a guarded recursive clause).
            rec = (params, body)
            rec_guard = guard
        elif not sc:
            base = (params, body, guard)
    if base is None or rec is None:
        return None
    rec_params, else_e = rec
    base_params, then_e, base_guard = base
    rec_names = [_text(p, src) for p in rec_params]
    lit_positions = [i for i, p in enumerate(base_params) if p.type == "integer"]
    renames: list = []

    def _rename(positions):
        for i in positions:
            bn = _text(base_params[i], src)
            if bn != rec_names[i]:
                _SUBST[bn] = rec_names[i]
                renames.append(bn)

    try:
        if (base_guard is None and len(lit_positions) == 1
                and all(base_params[i].type == "identifier"
                        for i in range(arity) if i != lit_positions[0])):
            # Mode A — integer-literal base param.
            li = lit_positions[0]
            k = _text(base_params[li], src).replace("_", "")
            cond_src, neg_src = f"({rec_names[li]} == {k})", f"({rec_names[li]} != {k})"
            _rename([i for i in range(arity) if i != li])
        elif (rec_guard is None and base_guard is not None
                and all(p.type == "identifier" for p in base_params)):
            # Mode B — guarded base + catch-all recursive; the base guard is the
            # base-match condition (the loop halts when it holds).
            _rename(range(arity))
            cond_src = _lower_expr(base_guard, src)
            neg_src = _negate_cond(base_guard, src)
            if "UNSUPPORTED" in cond_src or "UNSUPPORTED" in neg_src:
                return None
        elif (rec_guard is not None and base_guard is None
                and all(p.type == "identifier" for p in base_params)):
            # Mode C — guarded RECURSIVE clause + catch-all base
            # (`def f(n, acc) when n > 0, do: f(n-1, acc+n)` + `def f(_, acc), do: acc`).
            # The continue is the recursive guard directly; the catch-all base is the
            # post-loop value. The Haskell explicit-recursive-guard analog. The guard
            # references the recursive clause's param names (= the synthesized
            # `rec_names`), so it lowers without rename; only the base body is renamed.
            _rename(range(arity))
            neg_src = _lower_expr(rec_guard, src)        # continue = recursive guard
            cond_src = _negate_cond(rec_guard, src)
            if "UNSUPPORTED" in cond_src or "UNSUPPORTED" in neg_src:
                return None
        else:
            return None
        out = _try_lower_tail_recursive(name, rec_names, cond_src, neg_src,
                                        then_e, else_e, src)
        if out is None:
            out = _try_lower_foldable_nontail(name, rec_names, cond_src, neg_src,
                                              then_e, else_e, src)
    finally:
        for bn in renames:
            _SUBST.pop(bn, None)
    return out


def _try_lower_multibase_multiclause_recursion(name: str, members, src: bytes):
    """N >= 2 base clauses + one recursive clause — the >2-clause generalisation of
    `_try_lower_multiclause_recursion` Modes A/B. Each base is either an integer-literal
    base (one literal param at the recursion position) OR a `when`-guarded base
    (all-identifier params), and the two MAY be mixed:

        def f(0, acc), do: acc
        def f(1, acc), do: acc + 100
        def f(n, acc) when n > 50, do: acc + 9000   # guarded base (early exit)
        def f(n, acc), do: f(n - 1, acc + n)

    lowers to a `while_loop` whose continue is the `&&` of each base's negated condition
    (`(n != 0) && (n != 1) && (n <= 50)` — the substrate compound halt §0.3, 2026-06-18,
    which made a compound `&&` halt actually fire — verified to still fire with a guard
    comparison term mixed in, 2026-06-19); the body is the recursive step; and the
    post-loop value is a nested defuzz-blend of the base bodies keyed by their conditions
    (`(n == k)` for a literal base, the lowered guard for a guarded base) on the FINAL
    loop state, in source order (first-match priority). The recursive clause is
    all-identifier with a TAIL self-call. Haskell `_try_lower_multibase_tail_recursion`
    is the family reference.

    A NON-TAIL recursive clause (arity 1) — `def f(n), do: n * f(n - 1)` with two
    literal bases — is also handled: it lowers via a CPS fold (seed acc = OP identity,
    fold the leaf each step, combine `acc OP base_blend` on the final state). See the
    `if rec_args is None` branch below; the single-base analog is
    `_try_lower_foldable_nontail`.

    Caveat: bases are integer-literal patterns, so the `(n == k)` tests are crisp
    (eq_synthetic, §0.3). Returns Sutra or None (not this shape)."""
    if len(members) <= 2:
        return None  # 0/1 base is the existing 2-clause path
    parsed = []
    for _dc, param_nodes, body, guard, prelude in members:
        if prelude or not param_nodes:
            return None  # prelude (leading destructure) out of scope for multibase
        parsed.append((param_nodes, body, guard))
    arity = len(parsed[0][0])
    if any(len(p[0]) != arity for p in parsed):
        return None
    rec = None
    # Bases in SOURCE ORDER (first-match priority drives the post-loop blend nesting).
    # Each base is ("lit", params, body, (li, k)) — exactly one integer-literal param at
    # position li — or ("guard", params, body, guard_node) — all-identifier params + a
    # `when` guard. The two kinds may be mixed (mixed literal + guarded multibase).
    bases: list = []
    for params, body, guard in parsed:
        sc = _contains_self_call(body, name, src)
        if guard is None and all(p.type == "identifier" for p in params) and sc:
            if rec is not None:
                return None  # more than one recursive clause — out of scope
            rec = (params, body)
        elif not sc and guard is None:
            lit_positions = [i for i, p in enumerate(params) if p.type == "integer"]
            if len(lit_positions) != 1:
                return None  # literal base must distinguish by exactly one literal param
            li = lit_positions[0]
            if any(params[i].type != "identifier" for i in range(arity) if i != li):
                return None
            bases.append(("lit", params, body,
                          (li, _text(params[li], src).replace("_", ""))))
        elif not sc and guard is not None and all(p.type == "identifier" for p in params):
            bases.append(("guard", params, body, guard))  # `when`-guarded base
        else:
            return None
    if rec is None or len(bases) < 2:
        return None
    if len({extra[0] for kind, _p, _b, extra in bases if kind == "lit"}) > 1:
        return None  # all LITERAL bases must distinguish at the same recursion position
    rec_params, rec_body = rec
    rec_names = [_text(p, src) for p in rec_params]
    # TAIL self-call → accumulator loop; non-tail → CPS fold (handled below).
    rec_args = _self_call_args(rec_body, name, arity, src)

    # Render each base → (cont_test, blend_cond, body_src). A literal base contributes
    # `(n != k)` / `(n == k)`; a guard base contributes negate(guard) / guard. The base
    # clause's identifier params are renamed to the loop-state names by position so the
    # body, guard and tests all reference the loop state.
    def _render_base(kind, base_params, body, extra):
        skip = extra[0] if kind == "lit" else None
        renames: list = []
        for i in range(arity):
            if i == skip:
                continue
            bn = _text(base_params[i], src)
            if bn != rec_names[i]:
                _SUBST[bn] = rec_names[i]
                renames.append(bn)
        try:
            bsrc = _lower_expr(body, src)
            if kind == "lit":
                li_, k = extra
                cont_test, blend_cond = f"({rec_names[li_]} != {k})", f"({rec_names[li_]} == {k})"
            else:
                cont_test, blend_cond = _negate_cond(extra, src), _lower_expr(extra, src)
        finally:
            for bn in renames:
                _SUBST.pop(bn, None)
        if any("UNSUPPORTED" in s for s in (bsrc, cont_test, blend_cond)):
            return None
        return (cont_test, blend_cond, bsrc)

    rendered = []
    for kind, base_params, body, extra in bases:
        r = _render_base(kind, base_params, body, extra)
        if r is None:
            return None
        rendered.append(r)
    # continue = halt unless SOME base condition holds (compound `&&` halt, §0.3).
    cont = " && ".join(ct for ct, _bc, _bs in rendered)
    # Post-loop blend keyed by each base condition on the FINAL loop state, in source
    # order; the last base is the bare else (innermost).
    base_src = rendered[-1][2]
    for _ct, bc, bs in reversed(rendered[:-1]):
        base_src = _blend(bc, bs, base_src)
    ty = _TYPE
    loop_name = f"_rec_{name}"
    if rec_args is None:
        # Non-tail multibase fold (arity 1 only): the recursive clause is a fold step
        # `LEAF <OP> f(REC)` rather than a tail call. Seed `_acc` with the OP identity,
        # fold the leaf each iteration, then combine with the base blend keyed on the
        # FINAL loop state (`acc OP base`). `_FOLD_OPS` are commutative + associative,
        # so this reproduces the call-stack order. Single-base analog:
        # `_try_lower_foldable_nontail`. Multi-arg non-tail folds carry every recursion
        # arg AND the accumulator through the trampoline (commutative+associative OP, so
        # folding the leaf at each step's CURRENT state reproduces the call-stack order);
        # the base blend is keyed on the FINAL multi-arg loop state.
        if arity != 1:
            mstep = _foldable_step_multi(rec_body, name, arity, src)
            if mstep is None:
                return None
            op_text, leaf, rec_arg_nodes = mstep
            sutra_op = _OP_MAP.get(op_text, op_text)
            identity = _FOLD_IDENTITY[op_text]
            leaf_src = _lower_expr(leaf, src)
            rec_srcs = [_lower_expr(a, src) for a in rec_arg_nodes]
            if "UNSUPPORTED" in leaf_src or any("UNSUPPORTED" in s for s in rec_srcs):
                return None
            state_decls = ", ".join(f"{ty} {p} = 0" for p in rec_names)
            temp_decls = "".join(f"    {ty} _t{i} = {rec_srcs[i]};\n" for i in range(arity))
            assigns = "".join(f"    {p} = _t{i};\n" for i, p in enumerate(rec_names))
            slot_lines = "".join(f"    slot {ty} _{p}_r = {p};\n" for p in rec_names)
            slot_args = ", ".join(f"_{p}_r" for p in rec_names)
            writeback = "".join(f"    {p} = _{p}_r;\n" for p in rec_names)
            params_src = ", ".join(f"{ty} {p}" for p in rec_names)
            loop_decl = (
                f"while_loop {loop_name}({cont}, {state_decls}, {ty} _acc = 0) {{\n"
                f"{temp_decls}"
                f"    {ty} _t_acc = _acc {sutra_op} {leaf_src};\n"
                f"{assigns}"
                f"    _acc = _t_acc;\n"
                f"}}\n"
            )
            fn = (
                f"function {ty} {name}({params_src}) {{\n"
                f"    {ty} _acc = {identity};\n"
                f"{slot_lines}"
                f"    slot {ty} _acc_r = _acc;\n"
                f"    loop {loop_name}({cont}, {slot_args}, _acc_r);\n"
                f"{writeback}"
                f"    return _acc_r {sutra_op} {base_src};\n"
                f"}}\n"
            )
            return loop_decl + fn
        step = _foldable_step(rec_body, name, src)
        if step is None:
            return None
        op_text, leaf, rec_arg = step
        sutra_op = _OP_MAP.get(op_text, op_text)
        identity = _FOLD_IDENTITY[op_text]
        leaf_src = _lower_expr(leaf, src)
        rec_src = _lower_expr(rec_arg, src)
        if "UNSUPPORTED" in leaf_src or "UNSUPPORTED" in rec_src:
            return None
        n = rec_names[0]
        loop_decl = (
            f"while_loop {loop_name}({cont}, {ty} {n} = 0, {ty} _acc = 0) {{\n"
            f"    {ty} _t_n = {rec_src};\n"
            f"    {ty} _t_acc = _acc {sutra_op} {leaf_src};\n"
            f"    {n} = _t_n;\n"
            f"    _acc = _t_acc;\n"
            f"}}\n"
        )
        fn = (
            f"function {ty} {name}({ty} {n}) {{\n"
            f"    {ty} _acc = {identity};\n"
            f"    slot {ty} _{n}_r = {n};\n"
            f"    slot {ty} _acc_r = _acc;\n"
            f"    loop {loop_name}({cont}, _{n}_r, _acc_r);\n"
            f"    {n} = _{n}_r;\n"
            f"    return _acc_r {sutra_op} {base_src};\n"
            f"}}\n"
        )
        return loop_decl + fn
    state_decls = ", ".join(f"{ty} {p} = 0" for p in rec_names)
    temp_decls = "".join(f"    {ty} _t{i} = {_lower_expr(arg, src)};\n"
                         for i, arg in enumerate(rec_args))
    assigns = "".join(f"    {p} = _t{i};\n" for i, p in enumerate(rec_names))
    loop_decl = (f"while_loop {loop_name}({cont}, {state_decls}) "
                 f"{{\n{temp_decls}{assigns}}}\n")
    slot_lines = "".join(f"    slot {ty} _{p}_r = {p};\n" for p in rec_names)
    slot_args = ", ".join(f"_{p}_r" for p in rec_names)
    writeback = "".join(f"    {p} = _{p}_r;\n" for p in rec_names)
    params_src = ", ".join(f"{ty} {p}" for p in rec_names)
    fn = (
        f"function {ty} {name}({params_src}) {{\n"
        f"{slot_lines}"
        f"    loop {loop_name}({cont}, {slot_args});\n"
        f"{writeback}"
        f"    return {base_src};\n"
        f"}}\n"
    )
    return loop_decl + fn


def _lower_def(def_call, src: bytes) -> str:
    parts = _def_parts(def_call, src)
    if parts is None:
        return "// UNSUPPORTED-DEF: unrecognized def shape\n"
    name, params, body, prelude_stmts = parts
    if params and not prelude_stmts:
        ifp = _if_parts(body, src)
        if ifp is not None:
            cond, then_e, else_e = ifp
            cond_src = _lower_expr(cond, src)
            neg_src = _negate_cond(cond, src)
            rec = _try_lower_tail_recursive(name, params, cond_src, neg_src,
                                            then_e, else_e, src)
            if rec is not None:
                return rec
            fold = _try_lower_foldable_nontail(name, params, cond_src, neg_src,
                                               then_e, else_e, src)
            if fold is not None:
                return fold
    if _contains_self_call(body, name, src):
        # Recursion outside the supported tail/foldable shapes — a plain
        # self-calling Sutra function would not terminate through the fuzzy-if
        # blend. Surface the gap rather than mislower.
        return f"// UNSUPPORTED-RECURSION: '{name}' is recursive but not the tail-accumulator or foldable non-tail shape\n"
    # Leading `=` pattern-match bindings (`{a, b} = t`, `%{x: a} = m`, `x = e`) are
    # the idiomatic Elixir destructure. Each binds names via `_SUBST` (numbers, so
    # re-evaluating a substituted value is side-effect-free); a tuple/map LHS reads
    # the positional/named axon fields (`realvec(t.item("_0"))`), typing the RHS
    # param as `Axon`. The RHS must be a bare name (a param or earlier binding).
    _ARG_HOIST.clear()
    sub_names: list[str] = []
    axon_destructured: set = set()
    for st in prelude_stmts:
        bind = _apply_match_binding(st, src, sub_names, axon_destructured)
        if not bind:
            for nm in sub_names:
                _SUBST.pop(nm, None)
            return (f"// UNSUPPORTED-DEF: '{name}' body binding statement not a "
                    f"supported `=` destructure (later item)\n")
    # Maps -> axons: hoist any `%{…}` literals in the body to prelude temps, and
    # type any dot-accessed param as `Axon` (it is a map, not a number).
    prelude = _hoist_maps(body, src)
    axon_params = _dot_accessed_params(body, set(params), src) | (
        axon_destructured & set(params))
    # `<>`-operand params are Strings (Elixir `<>` is string concat only).
    string_params = _concat_operand_params(body, set(params), src) - axon_params
    params_src = ", ".join(
        f"{'Axon' if p in axon_params else 'String' if p in string_params else _TYPE} {p}"
        for p in params)
    body_src = _lower_expr(body, src)
    for nm in sub_names:
        _SUBST.pop(nm, None)
    _ARG_HOIST.clear()
    return (f"function {_TYPE} {name}({params_src}) {{\n"
            f"{prelude}"
            f"    return {body_src};\n"
            f"}}\n")


def _apply_match_binding(stmt, src: bytes, sub_names: list, axon_set: set) -> bool:
    """Lower a leading `=` pattern-match statement into `_SUBST` entries (appended to
    `sub_names` for cleanup; any tuple/map RHS param added to `axon_set`). Supported
    LHS: a `{a, b}` tuple pattern, a `%{x: a}` atom-key map pattern, or a bare
    `identifier` rebinding. The RHS must lower to a bare name. Returns True on
    success, False if the statement is outside this shape."""
    if stmt.type != "binary_operator":
        return False
    op = stmt.child_by_field_name("operator")
    if op is None or _text(op, src) != "=":
        return False
    lhs = stmt.child_by_field_name("left")
    rhs = stmt.child_by_field_name("right")
    if lhs is None or rhs is None:
        return False
    rhs_src = _lower_expr(rhs, src)
    if not rhs_src.isidentifier():
        return False  # a complex RHS (`name.item(...)` only dispatches on a name)
    if lhs.type == "identifier":
        nm = _text(lhs, src)
        _SUBST[nm] = f"({rhs_src})"
        sub_names.append(nm)
        return True
    if lhs.type == "tuple" and lhs.named_children \
            and all(e.type == "identifier" for e in lhs.named_children):
        axon_set.add(rhs_src)
        for j, e in enumerate(lhs.named_children):
            nm = _text(e, src)
            _SUBST[nm] = f'realvec({rhs_src}.item("_{j}"))'
            sub_names.append(nm)
        return True
    if lhs.type == "map":
        content = next((c for c in lhs.named_children
                        if c.type == "map_content"), None)
        kws = next((c for c in content.named_children
                    if c.type == "keywords"), None) if content else None
        if kws is None:
            return False
        pairs = []
        for pair in kws.named_children:
            if pair.type != "pair" or len(pair.named_children) < 2:
                return False
            key_node, val_node = pair.named_children[0], pair.named_children[-1]
            if key_node.type != "keyword" or val_node.type != "identifier":
                return False
            pairs.append((_text(key_node, src).rstrip().rstrip(":"),
                          _text(val_node, src)))
        if not pairs:
            return False
        axon_set.add(rhs_src)
        for field, local in pairs:
            _SUBST[local] = f'realvec({rhs_src}.item("{field}"))'
            sub_names.append(local)
        return True
    return False


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
