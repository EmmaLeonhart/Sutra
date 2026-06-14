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

# Pattern-equation variable bindings: a clause's variable pattern maps its name
# to the canonical arg slot `_ai` while lowering that clause's body (the OCaml
# `_MATCH_SUBST` / Elixir / Rust shape).
_SUBST: dict[str, str] = {}


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
        text = _text(node, src)
        return _SUBST.get(text, text)
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
    if t == "let_in":
        # `let <binds> in <body>` — substitute the binds into the body (the
        # `local_binds` shape shared with `where`).
        lb = next((c for c in node.named_children if c.type == "local_binds"), None)
        body = next((c for c in node.named_children if c.type != "local_binds"), None)
        if lb is None or body is None:
            return "/* UNSUPPORTED-EXPR: malformed let-in */"
        bound = _apply_local_binds(lb, src)
        try:
            return _lower_expr(body, src)
        finally:
            for nm in bound:
                _SUBST.pop(nm, None)
    return f"/* UNSUPPORTED-EXPR: {t} */"


# Sutra comparison op → its negation (halt condition → loop continue condition).
_NEG_CMP = {"==": "!=", "!=": "==", "<": ">=", ">": "<=", "<=": ">", ">=": "<"}


def _self_call_args(node, name: str, arity: int, src: bytes):
    """If `node` is `name a1 … a{arity}` (a curried self-application), return the
    arg nodes; else None."""
    if node.type != "apply":
        return None
    head, args = _flatten_apply(node, src)
    if head.type != "variable" or _text(head, src) != name or len(args) != arity:
        return None
    return args


def _negate_cond(cond, src: bytes) -> str:
    """Negate a halt condition into the loop's continue condition (the OCaml
    `_negate_cond` shape): a single `infix` comparison inverts via `_NEG_CMP`,
    else `!(…)`."""
    if cond.type == "infix":
        kids = cond.named_children
        op = next((c for c in kids if c.type == "operator"), None)
        operands = [c for c in kids if c.type != "operator"]
        if op is not None and len(operands) == 2:
            sop = _OP_MAP.get(_text(op, src))
            neg = _NEG_CMP.get(sop) if sop else None
            if neg is not None:
                return (f"{_lower_expr(operands[0], src)} {neg} "
                        f"{_lower_expr(operands[1], src)}")
    return f"!({_lower_expr(cond, src)})"


def _try_lower_tail_recursive(name: str, params, ret: str, body, src: bytes):
    """Lower a TAIL-recursive equation `f p… = if COND then BASE else f a…` to a
    declared Sutra `while_loop` (the OCaml/Scala/F#/Rust shape ported). `body` is
    a `conditional`; `params` is a list of (name, type). Returns Sutra or None."""
    if body.type != "conditional" or len(body.named_children) < 3:
        return None
    cond, then_e, else_e = body.named_children[0], body.named_children[1], body.named_children[2]
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

    loop_name = f"_rec_{name}"
    state_decls = ", ".join(f"{ty} {nm} = 0" for nm, ty in params)
    temp_decls = "".join(f"    {ty} _t{i} = {_lower_expr(arg, src)};\n"
                         for i, ((_nm, ty), arg) in enumerate(zip(params, rec_args)))
    assigns = "".join(f"    {nm} = _t{i};\n" for i, (nm, _ty) in enumerate(params))
    loop_decl = f"while_loop {loop_name}({cont}, {state_decls}) {{\n{temp_decls}{assigns}}}\n"
    slot_lines = "".join(f"    slot {ty} _{nm}_r = {nm};\n" for nm, ty in params)
    slot_args = ", ".join(f"_{nm}_r" for nm, _ty in params)
    writeback = "".join(f"    {nm} = _{nm}_r;\n" for nm, _ty in params)
    params_src = ", ".join(f"{ty} {nm}" for nm, ty in params)
    base_src = _lower_expr(base, src)
    fn = (
        f"function {ret} {name}({params_src}) {{\n"
        f"{slot_lines}"
        f"    loop {loop_name}({cont}, {slot_args});\n"
        f"{writeback}"
        f"    return {base_src};\n"
        f"}}\n"
    )
    return loop_decl + fn


# Associative + commutative combine ops for the non-tail fold transform.
_FOLD_OPS = {"+", "*"}


def _contains_variable(node, ident: str, src: bytes) -> bool:
    if node.type == "variable" and _text(node, src) == ident:
        return True
    return any(_contains_variable(c, ident, src) for c in node.named_children)


def _try_lower_foldable_nontail(name: str, params, ret: str, body, src: bytes):
    """CPS / accumulator transform for a FOLDABLE non-tail equation
    `f n = if COND then BASE else LEAF <OP> f REC` (single param, OP in
    `_FOLD_OPS`): the pending call-stack work is reified as an accumulator carried
    by a Sutra `while_loop` trampoline — the OCaml/Scala/Rust shape ported. BASE is
    evaluated pre-loop at the INITIAL param, so a param-dependent BASE is rejected
    (→ None). Returns loop decl + function, or None."""
    if body.type != "conditional" or len(body.named_children) < 3 or len(params) != 1:
        return None
    cond, then_e, else_e = body.named_children[0], body.named_children[1], body.named_children[2]

    def foldable(node):
        if node.type != "infix":
            return None
        kids = node.named_children
        op = next((c for c in kids if c.type == "operator"), None)
        operands = [c for c in kids if c.type != "operator"]
        if op is None or len(operands) != 2:
            return None
        op_text = _text(op, src)
        if op_text not in _FOLD_OPS:
            return None
        lc = _self_call_args(operands[0], name, 1, src)
        rc = _self_call_args(operands[1], name, 1, src)
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

    pname, pty = params[0][0], params[0][1]
    if _contains_variable(base, pname, src):
        return None  # param-dependent base — the transform would mis-evaluate it
    sutra_op = _OP_MAP.get(op_text, op_text)
    loop_name = f"_rec_{name}"
    leaf_src = _lower_expr(leaf, src)
    rec_src = _lower_expr(rec_arg, src)
    base_src = _lower_expr(base, src)
    if any("UNSUPPORTED" in s for s in (leaf_src, rec_src, base_src, cont)):
        return None
    loop_decl = (
        f"while_loop {loop_name}({cont}, {pty} {pname} = 0, {pty} _acc = 0) {{\n"
        f"    {pty} _t_n = {rec_src};\n"
        f"    {pty} _t_acc = _acc {sutra_op} {leaf_src};\n"
        f"    {pname} = _t_n;\n"
        f"    _acc = _t_acc;\n"
        f"}}\n"
    )
    fn = (
        f"function {ret} {name}({pty} {pname}) {{\n"
        f"    {pty} _acc = {base_src};\n"
        f"    slot {pty} _{pname}_r = {pname};\n"
        f"    slot {pty} _acc_r = _acc;\n"
        f"    loop {loop_name}({cont}, _{pname}_r, _acc_r);\n"
        f"    return _acc_r;\n"
        f"}}\n"
    )
    return loop_decl + fn


def _match_body(decl, src: bytes):
    """The expression node of a declaration's `match` (`= expr`), or None.
    Guarded matches (multiple `match` children / guards) are later items."""
    matches = [c for c in decl.named_children if c.type == "match"]
    if len(matches) != 1:
        return None
    m = matches[0]
    return m.named_children[-1] if m.named_children else None


def _apply_local_binds(local_binds, src: bytes) -> list[str]:
    """Add each `bind` in a `local_binds` node (a `where` clause or `let` group) to
    `_SUBST` as name → its parenthesised lowered value, processed in order so a
    later binding sees the earlier ones (the OCaml `let..in` / Clojure `let` shape;
    numbers, so re-evaluating a substituted value is side-effect-free). Mutually-
    recursive / forward where-bindings are a later item. Returns the bound names
    (for cleanup by the caller)."""
    bound: list[str] = []
    for b in local_binds.named_children:
        if b.type != "bind":
            continue
        name_node = next((c for c in b.named_children if c.type == "variable"), None)
        val = _match_body(b, src)  # the bind's `match` (= expr) body
        if name_node is None or val is None:
            continue
        _SUBST[_text(name_node, src)] = f"({_lower_expr(val, src)})"
        bound.append(_text(name_node, src))
    return bound


def _resolve_types(name: str, arity: int):
    """(param_types, return_type) from the signature prepass, defaulting to int."""
    sig = _SIGNATURES.get(name)
    if sig is not None and len(sig) == arity + 1:
        return [_map_type(s) for s in sig[:-1]], _map_type(sig[-1])
    return [_DEFAULT_TYPE] * arity, _DEFAULT_TYPE


def _lower_guards(matches, src: bytes):
    """Lower a guarded equation's `match` list (`| COND = expr`, … `| otherwise =
    expr`) to a nested defuzz blend — the shared blend shape, guards as the tests.
    Each `match` carries a `guards` node (its `boolean` children are the guard
    conditions, AND-combined; `otherwise` marks the catch-all base) and a result.
    The params are real Sutra params, so guard exprs reference them directly (no
    `_SUBST`). Returns the blend expr, or None if any match is not guarded."""
    parsed = []  # (test_src_or_None, result_src)
    for m in matches:
        guards = next((c for c in m.named_children if c.type == "guards"), None)
        if guards is None or not m.named_children:
            return None
        result = m.named_children[-1]
        conds = [c for c in guards.named_children if c.type == "boolean"]
        if not conds:
            return None
        test_srcs: list[str] = []
        is_base = False
        for b in conds:
            inner = b.named_children[0] if b.named_children else None
            if inner is None:
                return None
            if inner.type == "variable" and _text(inner, src) == "otherwise":
                is_base = True
            else:
                ts = _lower_expr(inner, src)
                if "UNSUPPORTED" in ts:
                    return None
                test_srcs.append(ts)
        res_src = _lower_expr(result, src)
        if "UNSUPPORTED" in res_src:
            return None
        test = None if is_base else (" && ".join(test_srcs) if test_srcs else None)
        parsed.append((test, res_src))
    if not parsed:
        return None
    expr = parsed[-1][1]  # last guard = base (typically `otherwise`)
    for test, res in reversed(parsed[:-1]):
        expr = res if test is None else _blend(test, res, expr)
    return expr


def _decl_name_arity(decl, src: bytes):
    """(name, arity) for a `function`/`bind` decl; (None, 0) if unnamed."""
    name_node = next((c for c in decl.named_children if c.type == "variable"), None)
    if name_node is None:
        return None, 0
    patterns = next((c for c in decl.named_children if c.type == "patterns"), None)
    arity = len(patterns.named_children) if patterns is not None else 0
    return _text(name_node, src), arity


def _lower_pattern_equations(name: str, decls, src: bytes) -> str:
    """Group same-name/arity equations (`classify 0 = …`, `classify 1 = …`,
    `classify n = …`) into ONE dispatching Sutra function — the Elixir multi-
    clause shape ported. An integer-literal pattern → an `(_ai == k)` test; a
    variable pattern binds that name to `_ai` (via `_SUBST`); the last equation
    is the base. Each equation must have a single plain `= expr` body (guarded
    pattern equations are a later item)."""
    arity = _decl_name_arity(decls[0], src)[1]
    clauses = []  # (pattern_nodes, body_node)
    for d in decls:
        patterns = next((c for c in d.named_children if c.type == "patterns"), None)
        pnodes = list(patterns.named_children) if patterns is not None else []
        if len(pnodes) != arity:
            return f"// UNSUPPORTED-DECL: '{name}' equation arity mismatch\n"
        body = _match_body(d, src)
        if body is None:
            return (f"// UNSUPPORTED-DECL: '{name}' has a guarded pattern equation "
                    f"(later item)\n")
        clauses.append((pnodes, body))
    for _pn, body in clauses:
        if _contains_self_call(body, name, src):
            return (f"// UNSUPPORTED-RECURSION: '{name}' multi-equation dispatch with "
                    f"recursion (later item)\n")
    ptypes, ret = _resolve_types(name, arity)
    argnames = [f"_a{i}" for i in range(arity)]
    parsed = []  # (test_src_or_None, result_src)
    for pnodes, body in clauses:
        tests: list[str] = []
        binds: list[tuple[str, str]] = []
        for i, p in enumerate(pnodes):
            if p.type == "literal":
                inner = p.named_children[0] if p.named_children else None
                if inner is None or inner.type != "integer":
                    return (f"// UNSUPPORTED-DECL: '{name}' non-integer literal "
                            f"pattern (later item)\n")
                tests.append(f"({argnames[i]} == {_text(inner, src)})")
            elif p.type == "variable":
                nm = _text(p, src)
                if nm != "_":
                    binds.append((nm, argnames[i]))
            else:
                return f"// UNSUPPORTED-DECL: '{name}' pattern {p.type} (later item)\n"
        for nm, sub in binds:
            _SUBST[nm] = sub
        try:
            res_src = _lower_expr(body, src)
        finally:
            for nm, _sub in binds:
                _SUBST.pop(nm, None)
        if "UNSUPPORTED" in res_src:
            return f"// UNSUPPORTED-DECL: '{name}' equation body not lowerable\n"
        test = " && ".join(tests) if tests else None
        parsed.append((test, res_src))
    expr = parsed[-1][1]  # last equation = base
    for test, res in reversed(parsed[:-1]):
        expr = res if test is None else _blend(test, res, expr)
    params_src = ", ".join(f"{ty} {a}" for ty, a in zip(ptypes, argnames))
    return (f"function {ret} {name}({params_src}) {{\n"
            f"    return {expr};\n"
            f"}}\n")


def _lower_decls(decl_nodes, src: bytes) -> list:
    """Group `function`/`bind` decls by (name, arity); a single-decl group routes
    through `_lower_equation` (guards / recursion transforms), a multi-decl group
    becomes one dispatching function via `_lower_pattern_equations`."""
    groups: dict = {}
    order: list = []
    out: list = []
    for d in decl_nodes:
        name, arity = _decl_name_arity(d, src)
        if name is None:
            out.append(_lower_equation(d, src))
            continue
        key = (name, arity)
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(d)
    for key in order:
        members = groups[key]
        if len(members) == 1:
            out.append(_lower_equation(members[0], src))
        else:
            out.append(_lower_pattern_equations(key[0], members, src))
    return out


def _lower_equation(decl, src: bytes) -> str:
    """A `function` equation (`add a b = …`) or zero-arg `bind` (`main = …`).
    A guarded equation (multiple `match` clauses / a `guards` child) lowers via
    `_lower_guards`."""
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
    ptypes, ret = _resolve_types(name, len(params))
    # `where` clause: apply its local binds (substitutions) around the whole
    # equation, then clean them up so they do not leak to sibling declarations.
    # The binds reference params by their source names, which the plain path keeps.
    where_lb = next((c for c in kids if c.type == "local_binds"), None)
    where_bound = _apply_local_binds(where_lb, src) if where_lb is not None else []
    try:
        # Guarded equation: one or more `match` clauses each with a `guards` child.
        matches = [c for c in kids if c.type == "match"]
        guarded = len(matches) > 1 or (
            len(matches) == 1 and any(c.type == "guards" for c in matches[0].named_children))
        if guarded:
            gbody = _lower_guards(matches, src)
            if gbody is None:
                return f"// UNSUPPORTED-DECL: '{name}' has a guard shape not yet lowerable\n"
            if any(_contains_self_call(m.named_children[-1], name, src)
                   for m in matches if m.named_children):
                return (f"// UNSUPPORTED-RECURSION: '{name}' guarded equation with "
                        f"recursion (later item)\n")
            params_src = ", ".join(f"{ty} {nm}" for ty, nm in zip(ptypes, params))
            return (f"function {ret} {name}({params_src}) {{\n"
                    f"    return {gbody};\n"
                    f"}}\n")
        body = _match_body(decl, src)
        if body is None:
            return f"// UNSUPPORTED-DECL: '{name}' has no single plain `= expr` body\n"
        typed_params = list(zip(params, ptypes))
        if body.type == "conditional" and params:
            rec = _try_lower_tail_recursive(name, typed_params, ret, body, src)
            if rec is not None:
                return rec
            fold = _try_lower_foldable_nontail(name, typed_params, ret, body, src)
            if fold is not None:
                return fold
        if _contains_self_call(body, name, src):
            # Recursion outside the supported tail/foldable shapes — a plain
            # self-call would not terminate through the fuzzy-if blend. Surface it.
            return (f"// UNSUPPORTED-RECURSION: '{name}' is recursive but not the "
                    f"tail-accumulator or foldable non-tail shape\n")
        params_src = ", ".join(f"{ty} {nm}" for ty, nm in zip(ptypes, params))
        return (f"function {ret} {name}({params_src}) {{\n"
                f"    return {_lower_expr(body, src)};\n"
                f"}}\n")
    finally:
        for nm in where_bound:
            _SUBST.pop(nm, None)


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
    _SUBST.clear()
    for child in decls.named_children:
        if child.type == "signature" and len(child.named_children) == 2:
            var, ty = child.named_children
            if var.type == "variable":
                _SIGNATURES[_text(var, src)] = _flatten_arrow(ty, src)

    out = ["// Generated by sutra-from-haskell. See sdk/sutra-from-haskell/README.md.\n"]
    # Collect `function`/`bind` decls and group by (name, arity) so multi-equation
    # pattern dispatch lowers to ONE function (signatures are consumed by the
    # prepass; data/class/instance are later items).
    decl_nodes = [c for c in decls.named_children if c.type in ("function", "bind")]
    out.extend(_lower_decls(decl_nodes, src))
    return "\n".join(out)
