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

# Case classes → axons (the OCaml record pattern). Prepass fills
# `_CASE_CLASSES[name] = [field, …]` from `case class Name(f: T, …)` defs (the def
# itself is erased — an axon is the runtime shape). Construction `Name(a, b)` is
# statement-based (`Axon t; t.add("f", a); …`), so constructions anywhere in an
# expression tree are HOISTED to prelude temps and `_ARG_HOIST[node.id]` carries the
# temp name to the call site — the OCaml `_hoist_aggregate_args_deep` machinery.
_CASE_CLASSES: dict[str, list[str]] = {}
_ARG_HOIST: dict[int, str] = {}

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
    if node is None:
        return _DEFAULT_TYPE
    text = _text(node, src)
    if text in _CASE_CLASSES:
        return "Axon"
    return _TYPE_MAP.get(text, _DEFAULT_TYPE)


def _case_class_call(node, src: bytes) -> Optional[str]:
    """The case-class name if `node` is a construction call (`Point(7, 9)`), else None."""
    if node.type != "call_expression" or not node.named_children:
        return None
    fn = node.named_children[0]
    if fn.type in ("identifier", "stable_identifier"):
        name = _text(fn, src)
        if name in _CASE_CLASSES:
            return name
    return None


def _emit_construction(cname: str, node, src: bytes, var: str, indent: str) -> str:
    """Axon-construction statements for `cname(args…)` bound to `var` (no return —
    reusable for hoisted temps, val bindings, and return-position bodies)."""
    args_node = next((c for c in node.named_children if c.type == "arguments"), None)
    args = [_lower_expr(a, src) for a in (args_node.named_children if args_node else [])]
    fields = _CASE_CLASSES[cname]
    stmts = f"{indent}Axon {var};\n"
    for field, arg in zip(fields, args):
        stmts += f'{indent}{var}.add("{field}", {arg});\n'
    return stmts


def _hoist_constructions(body, src: bytes, indent: str = "    "):
    """Post-order walk of an expression tree: hoist EVERY case-class construction to
    a prelude `Axon _ahN; …` group and register `node.id → _ahN` in `_ARG_HOIST` so
    `_lower_expr` emits the temp at the call site (inner constructions resolve before
    the outer ones that reference them). Returns (prelude, added_ids) or None."""
    prelude: list[str] = []
    added: list[int] = []

    def walk(n):
        for c in n.named_children:
            walk(c)
        cname = _case_class_call(n, src)
        if cname is not None:
            tmp = f"_ah{len(added)}"
            prelude.append(_emit_construction(cname, n, src, tmp, indent))
            _ARG_HOIST[n.id] = tmp
            added.append(n.id)

    walk(body)
    if not added:
        return None
    return "".join(prelude), added


def _stmt_with_hoist(node, src: bytes, template: str, indent: str = "    ") -> str:
    """Lower `node` as the expression of a statement (`template` has one `{expr}`
    slot), hoisting any case-class constructions inside it to a prelude first."""
    deep = _hoist_constructions(node, src, indent)
    if deep is None:
        return template.format(expr=_lower_expr(node, src))
    prelude, added = deep
    try:
        expr = _lower_expr(node, src)
    finally:
        for nid in added:
            _ARG_HOIST.pop(nid, None)
    return prelude + template.format(expr=expr)


def _lower_expr(node, src: bytes) -> str:
    if _ARG_HOIST and node.id in _ARG_HOIST:
        return _ARG_HOIST[node.id]
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
        if _case_class_call(node, src) is not None:
            # A construction reaching here was not hoisted — emitting `Point(…)`
            # would silently mislower (no such Sutra function). Surface the gap.
            return "/* UNSUPPORTED-CONSTRUCTION: case-class call outside a hoistable position */"
        fn = _lower_expr(kids[0], src)
        args_node = next((c for c in kids if c.type == "arguments"), None)
        args = [_lower_expr(a, src) for a in (args_node.named_children if args_node else [])]
        return f"{fn}({', '.join(args)})"
    if t == "field_expression":
        # Case-class field read `p.x` → the axon item read, projected to a clean
        # number-vector (realvec — the substrate-pure projection; raw axon fillers
        # carry crosstalk and collapse arithmetic to ~0, finding 2026-06-05).
        kids = node.named_children
        if len(kids) == 2:
            obj = _lower_expr(kids[0], src)
            field = _text(kids[1], src)
            return f'realvec({obj}.item("{field}"))'
        return "/* UNSUPPORTED-EXPR: field_expression arity */"
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
            val_expr = kids[-1]
            cname = _case_class_call(val_expr, src)
            if cname is not None:
                # `val p = Point(7, 9)` — the construction binds the name directly.
                stmts += _emit_construction(cname, val_expr, src, name, "    ")
                continue
            ty_node = next((k for k in kids if k.type == "type_identifier"), None)
            ty = _map_type(ty_node, src) if ty_node is not None else _DEFAULT_TYPE
            stmts += _stmt_with_hoist(val_expr, src, f"    {ty} {name} = {{expr}};\n")
        else:
            final = c  # the block's value is its last non-val expression
    if final is None:
        return stmts + "    return 0;\n"
    return stmts + _stmt_with_hoist(final, src, "    return {expr};\n")


# Sutra comparison operator → its logical negation: turns a halt condition
# (`if (n == 0) base else recurse`) into the loop's *continue* condition.
_NEG_CMP = {"==": "!=", "!=": "==", "<": ">=", ">": "<=", "<=": ">", ">=": "<"}


def _peel_parens(node):
    while node is not None and node.type == "parenthesized_expression" \
            and node.named_children:
        node = node.named_children[0]
    return node


def _self_call_args(node, name: str, arity: int, src: bytes):
    """If `node` is exactly `name(arg1, …, arg{arity})`, return the arg nodes; else None."""
    node = _peel_parens(node)
    if node is None or node.type != "call_expression" or not node.named_children:
        return None
    fn = node.named_children[0]
    if fn.type not in ("identifier", "stable_identifier") or _text(fn, src) != name:
        return None
    args_node = next((c for c in node.named_children if c.type == "arguments"), None)
    args = list(args_node.named_children) if args_node is not None else []
    if len(args) != arity:
        return None
    return args


def _negate_cond(cond, src: bytes) -> str:
    """Negate a halt condition into the loop's continue condition: a single infix
    comparison inverts precisely via `_NEG_CMP`; any other boolean condition negates
    generally with Sutra `!(…)` (the OCaml frontend's `_negate_cond` shape)."""
    cond = _peel_parens(cond)
    if cond.type == "infix_expression":
        kids = cond.named_children
        op = next((c for c in kids if c.type == "operator_identifier"), None)
        operands = [c for c in kids if c.type != "operator_identifier"]
        if op is not None and len(operands) == 2:
            sutra_op = _OP_MAP.get(_text(op, src))
            neg = _NEG_CMP.get(sutra_op) if sutra_op else None
            if neg is not None:
                return (f"{_lower_expr(operands[0], src)} {neg} "
                        f"{_lower_expr(operands[1], src)}")
    return f"!({_lower_expr(cond, src)})"


def _contains_self_call(node, name: str, src: bytes) -> bool:
    """True if any call in the tree invokes `name` (recursion detector)."""
    if node.type == "call_expression" and node.named_children:
        fn = node.named_children[0]
        if fn.type in ("identifier", "stable_identifier") and _text(fn, src) == name:
            return True
    return any(_contains_self_call(c, name, src) for c in node.named_children)


def _try_lower_tail_recursive(
    name: str, params: list[tuple[str, str]], ret: str, body, src: bytes,
):
    """Lower a TAIL-recursive accumulator shape `def f(p1, …, pk) = if (COND) BASE
    else f(a1, …, ak)` (or with the self-call in the then-arm) to a Sutra declared
    `while_loop` — bounded substrate iteration, no self-calling function (which
    would not terminate through the fuzzy-if blend). The OCaml frontend's
    substrate-verified `_try_lower_tail_recursive` shape, ported. Returns the
    emitted Sutra (loop decl + function) or None if the body is not this shape."""
    if body.type != "if_expression" or len(body.named_children) < 3:
        return None
    kids = body.named_children
    cond, then_e, else_e = kids[0], kids[1], kids[2]
    arity = len(params)
    then_args = _self_call_args(then_e, name, arity, src)
    else_args = _self_call_args(else_e, name, arity, src)
    # Exactly ONE branch must be the self-call (the other is the base).
    if (then_args is None) == (else_args is None):
        return None
    if else_args is not None:
        cont = _negate_cond(cond, src)        # halt when COND, loop while not
        rec_args, base = else_args, then_e
    else:
        cont = _lower_expr(_peel_parens(cond), src)  # loop while COND
        rec_args, base = then_args, else_e

    loop_name = f"_rec_{name}"
    state_decls = ", ".join(f"{ty} {nm} = 0" for nm, ty in params)
    # Simultaneous state update via temporaries: every new value computed from the
    # OLD params first, then all assigned — a sequential update is wrong for swaps
    # (the OCaml frontend measured `swaploop 7 9 2` giving 9 instead of 7).
    temp_decls = "".join(
        f"    {ty} _t{i} = {_lower_expr(arg, src)};\n"
        for i, ((_nm, ty), arg) in enumerate(zip(params, rec_args))
    )
    assigns = "".join(f"    {nm} = _t{i};\n" for i, (nm, _ty) in enumerate(params))
    loop_decl = f"while_loop {loop_name}({cont}, {state_decls}) {{\n{temp_decls}{assigns}}}\n"

    slot_lines = "".join(f"    slot {ty} _{nm}_r = {nm};\n" for nm, ty in params)
    slot_args = ", ".join(f"_{nm}_r" for nm, _ty in params)
    writeback = "".join(f"    {nm} = _{nm}_r;\n" for nm, _ty in params)
    params_src = ", ".join(f"{ty} {nm}" for nm, ty in params)
    base_src = _lower_expr(_peel_parens(base), src)
    fn = (
        f"function {ret} {name}({params_src}) {{\n"
        f"{slot_lines}"
        f"    loop {loop_name}({cont}, {slot_args});\n"
        f"{writeback}"
        f"    return {base_src};\n"
        f"}}\n"
    )
    return loop_decl + fn


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
    # A self-recursive tail-accumulator body becomes a declared while_loop
    # (a direct self-call would not terminate through the fuzzy-if blend).
    if body.type == "if_expression" and params:
        tail = _try_lower_tail_recursive(name, params, ret, body, src)
        if tail is not None:
            return tail
    if _contains_self_call(body, name, src):
        # Recursion that is NOT the tail-accumulator shape — a plain self-calling
        # Sutra function would not terminate through the fuzzy-if blend. Surface
        # the gap rather than mislower (the OCaml frontend's rule; its foldable
        # non-tail CPS transform is the model when this is needed).
        return f"// UNSUPPORTED-RECURSION: '{name}' is recursive but not the tail-accumulator shape\n"
    params_src = ", ".join(f"{ty} {nm}" for nm, ty in params)
    if body.type == "block":
        inner = _lower_block(body, src)
    else:
        inner = _stmt_with_hoist(body, src, "    return {expr};\n")
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

    # Prepass: collect case classes (name → ordered field list); their defs are
    # erased — the runtime shape is an axon (the OCaml record-type erasure).
    _CASE_CLASSES.clear()
    _ARG_HOIST.clear()
    for child in tree.root_node.named_children:
        if child.type == "class_definition" \
                and _text(child, src).lstrip().startswith("case class"):
            kids = child.named_children
            name_node = next((c for c in kids if c.type == "identifier"), None)
            params = next((c for c in kids if c.type == "class_parameters"), None)
            fields = []
            if params is not None:
                for p in params.named_children:
                    if p.type != "class_parameter":
                        continue
                    pid = next((c for c in p.named_children if c.type == "identifier"), None)
                    if pid is not None:
                        fields.append(_text(pid, src))
            if name_node is not None:
                _CASE_CLASSES[_text(name_node, src)] = fields

    out = ["// Generated by sutra-from-scala. See sdk/sutra-from-scala/README.md.\n"]
    for child in tree.root_node.named_children:
        if child.type == "function_definition":
            out.append(_lower_function(child, src))
        # other top-level forms (objects, non-case classes, vals) are later items
    return "\n".join(out)
