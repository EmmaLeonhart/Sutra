"""Erlang → Sutra lowering pass (MVP).

Models on `sutra-from-ocaml` / `sutra-from-elixir`. Erlang groups all clauses of a
function in ONE `fun_decl` (clauses separated by `;`, terminated by `.`), so the
multi-clause dispatcher reads a single `fun_decl`'s `function_clause` children
directly — no grouping across declarations.

Grammar loading: no PyPI wheel, so `build_grammar.py` compiles the WhatsApp
tree-sitter-erlang grammar (parser.c + scanner.c) into `_grammar/erlang.dll` and
this module loads it via ctypes (same pattern as `sutra-from-clojure`).

Shapes (shared with the other frontends): functions → Sutra `function`s; binary
ops → infix; `if`/`case` → defuzz blend; multi-clause heads with literal/var
patterns + `when` guards → a nested dispatch blend; single-clause `if`-based tail
recursion → a declared `while_loop`; foldable non-tail recursion → a CPS
accumulator trampoline. Multi-clause recursion (Erlang's other idiom) and
maps/records/tuples are later items (surface as `UNSUPPORTED-*`, never a silent
self-call).
"""
from __future__ import annotations

import ctypes
import pathlib
from typing import Optional

_HERE = pathlib.Path(__file__).resolve().parent
_DLL = _HERE.parent / "_grammar" / "erlang.dll"
_TYPE = "number"

# Erlang operator → Sutra operator. Erlang spells some comparisons differently
# (`=<` not `<=`, `/=` not `!=`, `=:=` exact-equal). `div`/`rem` omitted (rem would
# need Math.mod, which is forbidden — a later item via complex rotation).
_OP_MAP = {
    "+": "+", "-": "-", "*": "*",
    "==": "==", "=:=": "==", "/=": "!=", "=/=": "!=",
    "<": "<", ">": ">", "=<": "<=", ">=": ">=",
    "andalso": "&&", "orelse": "||", "and": "&&", "or": "||",
}

# Bound names (params / case-binds) → their Sutra substitution (the `_SUBST` shape
# shared with the Elixir/Clojure/Haskell frontends).
_SUBST: dict[str, str] = {}

# Maps → axons (the Elixir/Clojure pattern). A `#{K => V}` `map_expr` is
# statement-shaped (axon construction), so it is HOISTED to a prelude temp and
# `_ARG_HOIST[node.id]` carries the temp name to the use site. `_AH` numbers temps.
_ARG_HOIST: dict[int, str] = {}
_AH = [0]


def _map_key_name(node, src: bytes):
    """The static axon-field name for an Erlang map key: an `integer` (`1` → `1`),
    an `atom` (`a` → `a`), or a `string` (`"k"` → `k`). Other key shapes (variables,
    expressions) have no static field name → None."""
    if node.type == "integer":
        return _text(node, src).strip()
    if node.type == "atom":
        return _text(node, src).strip()
    if node.type == "string":
        return _text(node, src).strip().strip('"')
    return None


def _map_fields(node, src: bytes):
    """If `node` is a `map_expr` (`#{k1 => v1, …}`) whose keys are all static field
    names, return [(field, value_node), …]; else None. Each `map_field` child holds
    a key node then a value node. Update syntax (`M#{…}`) and non-static keys → None."""
    if node.type != "map_expr":
        return None
    fields = []
    for mf in node.named_children:
        if mf.type != "map_field" or len(mf.named_children) < 2:
            return None
        key = _map_key_name(mf.named_children[0], src)
        if key is None:
            return None
        fields.append((key, mf.named_children[-1]))
    return fields if fields else None


def _maps_get(node, src: bytes):
    """If `node` is `maps:get(Key, Map)` (a `remote` to module `maps`, fun `get`,
    with a static key), return (field_name, map_node); else None."""
    if node.type != "remote":
        return None
    mod = next((c for c in node.named_children if c.type == "remote_module"), None)
    call = next((c for c in node.named_children if c.type == "call"), None)
    if mod is None or call is None:
        return None
    mod_atom = next((c for c in mod.named_children if c.type == "atom"), None)
    if mod_atom is None or _text(mod_atom, src) != "maps":
        return None
    fn = call.named_children[0] if call.named_children else None
    if fn is None or fn.type != "atom" or _text(fn, src) != "get":
        return None
    args_node = next((c for c in call.named_children if c.type == "expr_args"), None)
    args = list(args_node.named_children) if args_node is not None else []
    if len(args) != 2:
        return None
    field = _map_key_name(args[0], src)
    if field is None:
        return None
    return field, args[1]


def _hoist_maps(node, src: bytes, indent: str = "    ") -> str:
    """Post-order walk: hoist every `map_expr` to a prelude `Axon _ahN; …` group and
    register `node.id → _ahN`. Mirrors the Elixir `_hoist_maps`."""
    prelude = ""
    for child in node.named_children:
        prelude += _hoist_maps(child, src, indent)
    fields = _map_fields(node, src)
    if fields is not None:
        tmp = f"_ah{_AH[0]}"
        _AH[0] += 1
        prelude += f"{indent}Axon {tmp};\n"
        for field, val in fields:
            prelude += f'{indent}{tmp}.add("{field}", {_lower_expr(val, src)});\n'
        _ARG_HOIST[node.id] = tmp
    return prelude


def _maps_get_params(body, params: set, src: bytes) -> set:
    """Param names read as maps via `maps:get(K, P)` — these type as `Axon`."""
    found: set = set()

    def walk(n):
        mg = _maps_get(n, src)
        if mg is not None and mg[1].type == "var" and _text(mg[1], src) in params:
            found.add(_text(mg[1], src))
        for c in n.named_children:
            walk(c)

    walk(body)
    return found


def grammar_available() -> bool:
    return _DLL.exists()


def _load_language():
    import tree_sitter

    lib = ctypes.cdll.LoadLibrary(str(_DLL))
    lib.tree_sitter_erlang.restype = ctypes.c_void_p
    return tree_sitter.Language(lib.tree_sitter_erlang())


def _text(node, src: bytes) -> str:
    return src[node.start_byte:node.end_byte].decode("utf-8")


def _blend(test_src: str, then_src: str, else_src: str) -> str:
    """Sutra strong-defuzz two-way blend — the shared frontend shape."""
    w = f"truth_axis(defuzzy({test_src}))"
    return f"(((1 + {w}) * ({then_src})) + ((1 - {w}) * ({else_src}))) / 2"


def _binop(node, src: bytes):
    """`binary_op_expr` → (left, op_text, right); the operator token sits between
    the two named operands."""
    kids = node.named_children
    if len(kids) != 2:
        return None
    left, right = kids[0], kids[1]
    op = src[left.end_byte:right.start_byte].decode("utf-8").strip()
    return left, op, right


def _clause_body_expr(clause_body, src: bytes):
    """The expression of a `clause_body` (`-> expr`) — its last named child."""
    kids = clause_body.named_children
    return kids[-1] if kids else None


def _call_name_args(node, src: bytes):
    """`call` → (function-name-atom-text, [arg_nodes]) or None for a non-atom head."""
    if node.type != "call":
        return None
    name_node = node.named_children[0] if node.named_children else None
    if name_node is None or name_node.type != "atom":
        return None
    args_node = next((c for c in node.named_children if c.type == "expr_args"), None)
    args = list(args_node.named_children) if args_node is not None else []
    return _text(name_node, src), args


def _lower_expr(node, src: bytes) -> str:
    if _ARG_HOIST and node.id in _ARG_HOIST:
        return _ARG_HOIST[node.id]            # a hoisted map literal — emit its temp
    t = node.type
    mg = _maps_get(node, src)
    if mg is not None:
        # `maps:get(K, P)` → the axon item read, projected to a clean number-vector
        # (the Elixir/Clojure `m[k]` shape).
        field, map_node = mg
        return f'realvec({_lower_expr(map_node, src)}.item("{field}"))'
    if t == "map_expr":
        # A map literal reaching here was not hoisted — surface the gap.
        return "/* UNSUPPORTED-CONSTRUCTION: map outside a hoistable position */"
    if t == "integer":
        return _text(node, src)
    if t == "var":
        text = _text(node, src)
        return _SUBST.get(text, text)
    if t == "atom":
        # A bare atom in expression position: `true`/`false` map to truth values;
        # other atoms have no numeric meaning in the MVP.
        a = _text(node, src)
        if a in ("true", "false"):
            return a
        return f"/* UNSUPPORTED-EXPR: atom {a} */"
    if t in ("paren_expr", "block_expr"):
        inner = node.named_children[-1] if node.named_children else None
        return f"({_lower_expr(inner, src)})" if inner is not None else "0"
    if t == "binary_op_expr":
        b = _binop(node, src)
        if b is None:
            return "/* UNSUPPORTED-EXPR: malformed binary op */"
        left, op, right = b
        sop = _OP_MAP.get(op)
        if sop is None:
            return f"/* UNSUPPORTED-OP: {op} */"
        return f"({_lower_expr(left, src)} {sop} {_lower_expr(right, src)})"
    if t == "call":
        na = _call_name_args(node, src)
        if na is None:
            return "/* UNSUPPORTED-EXPR: non-atom call head */"
        name, args = na
        return f"{name}({', '.join(_lower_expr(a, src) for a in args)})"
    if t == "if_expr":
        # `if G1 -> R1; G2 -> R2; ... ; true -> D end` — nested guard blend, the
        # `true` clause (or the last) as base.
        clauses = [c for c in node.named_children if c.type == "if_clause"]
        return _lower_if_clauses(clauses, src)
    if t == "case_expr":
        # `case E of P1 -> R1; ... ; _ -> D end` — nested equality blend on E; an
        # integer pattern → `(E == k)`, a var pattern binds (catch-all base).
        kids = node.named_children
        subject = kids[0] if kids else None
        clauses = [c for c in kids if c.type == "cr_clause"]
        if subject is None or not clauses:
            return "/* UNSUPPORTED-EXPR: malformed case */"
        return _lower_case_clauses(subject, clauses, src)
    return f"/* UNSUPPORTED-EXPR: {t} */"


def _lower_if_clauses(clauses, src: bytes) -> str:
    """Nested blend over `if_clause`s; a guard of `true` (or the last clause) is
    the base."""
    parsed = []  # (test_src_or_None, result_src)
    for c in clauses:
        guard = next((g for g in c.named_children if g.type == "guard"), None)
        body = next((b for b in c.named_children if b.type == "clause_body"), None)
        if body is None:
            return "/* UNSUPPORTED-EXPR: if-clause without body */"
        res = _lower_expr(_clause_body_expr(body, src), src)
        gtext = _text(guard, src).strip() if guard is not None else "true"
        if gtext == "true":
            parsed.append((None, res))
        else:
            gexpr = guard.named_children[0] if guard.named_children else None
            inner = gexpr.named_children[0] if (gexpr is not None
                                                and gexpr.named_children) else None
            parsed.append((f"({_lower_expr(inner, src)})" if inner is not None
                           else "true", res))
    expr = parsed[-1][1]
    for test, res in reversed(parsed[:-1]):
        expr = res if test is None else _blend(test, res, expr)
    return expr


def _lower_case_clauses(subject, clauses, src: bytes) -> str:
    """Nested equality blend on `subject` over `cr_clause`s; integer pattern → an
    equality test, var pattern binds the name (catch-all base)."""
    e_src = f"({_lower_expr(subject, src)})"
    parsed = []  # (test_src_or_None, result_src)
    for c in clauses:
        kids = c.named_children
        pat = kids[0] if kids else None
        body = next((b for b in kids if b.type == "clause_body"), None)
        if pat is None or body is None:
            return "/* UNSUPPORTED-EXPR: malformed case clause */"
        bind = None
        if pat.type == "integer":
            test = f"({e_src} == {_text(pat, src)})"
        elif pat.type == "var":
            nm = _text(pat, src)
            test = None  # variable / `_` pattern is a catch-all
            if nm != "_":
                bind = (nm, e_src)
        else:
            return "/* UNSUPPORTED-EXPR: case pattern (literals/vars only) */"
        if bind is not None:
            _SUBST[bind[0]] = bind[1]
        try:
            res = _lower_expr(_clause_body_expr(body, src), src)
        finally:
            if bind is not None:
                _SUBST.pop(bind[0], None)
        parsed.append((test, res))
    expr = parsed[-1][1]
    for test, res in reversed(parsed[:-1]):
        expr = res if test is None else _blend(test, res, expr)
    return expr


# ----- recursion transforms (ported from the Elixir/Clojure frontends) -----

_NEG_CMP = {"==": "!=", "!=": "==", "<": ">=", ">": "<=", "<=": ">", ">=": "<"}
_FOLD_OPS = {"+", "*"}


def _contains_self_call(node, name: str, src: bytes) -> bool:
    na = _call_name_args(node, src)
    if na is not None and na[0] == name:
        return True
    return any(_contains_self_call(c, name, src) for c in node.named_children)


def _self_call_args(node, name: str, arity: int, src: bytes):
    na = _call_name_args(node, src)
    if na is None or na[0] != name or len(na[1]) != arity:
        return None
    return na[1]


def _if_as_conditional(body, src: bytes):
    """A 2-clause `if_expr` `[COND -> THEN, true -> ELSE]` → (cond, then, else)
    nodes (the conditional shape the recursion transforms expect). Else None."""
    if body.type != "if_expr":
        return None
    clauses = [c for c in body.named_children if c.type == "if_clause"]
    if len(clauses) != 2:
        return None
    def parts(c):
        g = next((x for x in c.named_children if x.type == "guard"), None)
        b = next((x for x in c.named_children if x.type == "clause_body"), None)
        return g, (_clause_body_expr(b, src) if b is not None else None)
    g0, then_e = parts(clauses[0])
    g1, else_e = parts(clauses[1])
    if g1 is None or _text(g1, src).strip() != "true" or then_e is None or else_e is None:
        return None
    gexpr = g0.named_children[0] if (g0 is not None and g0.named_children) else None
    cond = gexpr.named_children[0] if (gexpr is not None and gexpr.named_children) else None
    return (cond, then_e, else_e) if cond is not None else None


def _negate_cond(cond, src: bytes) -> str:
    b = _binop(cond, src) if cond.type == "binary_op_expr" else None
    if b is not None:
        left, op, right = b
        neg = _NEG_CMP.get(_OP_MAP.get(op, ""))
        if neg is not None:
            return f"({_lower_expr(left, src)} {neg} {_lower_expr(right, src)})"
    return f"!({_lower_expr(cond, src)})"


def _try_lower_tail_recursive(name: str, params, cond, then_e, else_e, src: bytes):
    """`f(p…) -> if COND -> BASE; true -> f(a…) end.` → a declared `while_loop`."""
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
    temp_decls = "".join(f"    {ty} _t{i} = {_lower_expr(a, src)};\n"
                         for i, a in enumerate(rec_args))
    assigns = "".join(f"    {p} = _t{i};\n" for i, p in enumerate(params))
    loop_decl = f"while_loop {loop_name}({cont}, {state_decls}) {{\n{temp_decls}{assigns}}}\n"
    slot_lines = "".join(f"    slot {ty} _{p}_r = {p};\n" for p in params)
    slot_args = ", ".join(f"_{p}_r" for p in params)
    writeback = "".join(f"    {p} = _{p}_r;\n" for p in params)
    params_src = ", ".join(f"{ty} {p}" for p in params)
    fn = (f"function {ty} {name}({params_src}) {{\n{slot_lines}"
          f"    loop {loop_name}({cont}, {slot_args});\n{writeback}"
          f"    return {_lower_expr(base, src)};\n}}\n")
    return loop_decl + fn


def _try_lower_foldable_nontail(name: str, params, cond, then_e, else_e, src: bytes):
    """`f(n) -> if COND -> BASE; true -> LEAF <OP> f(REC) end.` → an accumulator
    `while_loop` trampoline (single param, OP in `_FOLD_OPS`)."""
    if len(params) != 1:
        return None

    def foldable(node):
        if node.type != "binary_op_expr":
            return None
        b = _binop(node, src)
        if b is None:
            return None
        left, op, right = b
        if op not in _FOLD_OPS:
            return None
        lc = _self_call_args(left, name, 1, src)
        rc = _self_call_args(right, name, 1, src)
        if (lc is None) == (rc is None):
            return None
        return (op, right, lc[0]) if lc is not None else (op, left, rc[0])

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
    ty = _TYPE
    sutra_op = _OP_MAP.get(op_text, op_text)
    loop_name = f"_rec_{name}"
    loop_decl = (f"while_loop {loop_name}({cont}, {ty} {pname} = 0, {ty} _acc = 0) {{\n"
                 f"    {ty} _t_n = {_lower_expr(rec_arg, src)};\n"
                 f"    {ty} _t_acc = _acc {sutra_op} {_lower_expr(leaf, src)};\n"
                 f"    {pname} = _t_n;\n    _acc = _t_acc;\n}}\n")
    fn = (f"function {ty} {name}({ty} {pname}) {{\n"
          f"    {ty} _acc = {_lower_expr(base, src)};\n"
          f"    slot {ty} _{pname}_r = {pname};\n    slot {ty} _acc_r = _acc;\n"
          f"    loop {loop_name}({cont}, _{pname}_r, _acc_r);\n"
          f"    return _acc_r;\n}}\n")
    return loop_decl + fn


# ----- function declarations -----

def _clause_parts(fc, src: bytes):
    """`function_clause` → (name, [param_nodes], guard_or_None, body_expr_node)."""
    name_node = next((c for c in fc.named_children if c.type == "atom"), None)
    args = next((c for c in fc.named_children if c.type == "expr_args"), None)
    guard = next((c for c in fc.named_children if c.type == "guard"), None)
    cbody = next((c for c in fc.named_children if c.type == "clause_body"), None)
    if name_node is None or cbody is None:
        return None
    params = list(args.named_children) if args is not None else []
    return _text(name_node, src), params, guard, _clause_body_expr(cbody, src)


def _guard_test(guard, src: bytes) -> str:
    """Lower a `when` guard to a Sutra test (its `guard_clause` expression)."""
    gc = guard.named_children[0] if guard.named_children else None
    expr = gc.named_children[0] if (gc is not None and gc.named_children) else None
    return f"({_lower_expr(expr, src)})" if expr is not None else "true"


def _lower_dispatch(name: str, clauses, src: bytes) -> str:
    """Multi-clause head → one dispatching function (the Elixir `_lower_def_clauses`
    shape): integer pattern → `(_ai == k)`, var pattern binds `_ai`, `when` guard →
    a test ANDed in; the last clause is the base. Recursion here is a later item."""
    parts0 = _clause_parts(clauses[0], src)
    arity = len(parts0[1])
    argnames = [f"_a{i}" for i in range(arity)]
    parsed = []  # (test_or_None, result_src)
    for fc in clauses:
        cp = _clause_parts(fc, src)
        if cp is None:
            return f"// UNSUPPORTED-DECL: '{name}' malformed clause\n"
        _nm, params, guard, body = cp
        if len(params) != arity:
            return f"// UNSUPPORTED-DECL: '{name}' clause arity mismatch\n"
        if _contains_self_call(body, name, src):
            return (f"// UNSUPPORTED-RECURSION: '{name}' multi-clause dispatch with "
                    f"recursion (later item)\n")
        tests, binds = [], []
        for i, p in enumerate(params):
            if p.type == "integer":
                tests.append(f"({argnames[i]} == {_text(p, src)})")
            elif p.type == "var":
                nm = _text(p, src)
                if nm != "_":
                    binds.append((nm, argnames[i]))
            else:
                return (f"// UNSUPPORTED-DECL: '{name}' clause pattern param "
                        f"{p.type} (later item)\n")
        for nm, sub in binds:
            _SUBST[nm] = sub
        try:
            res = _lower_expr(body, src)
            gtest = _guard_test(guard, src) if guard is not None else None
        finally:
            for nm, _s in binds:
                _SUBST.pop(nm, None)
        if "UNSUPPORTED" in res or (gtest and "UNSUPPORTED" in gtest):
            return f"// UNSUPPORTED-DECL: '{name}' clause body not lowerable\n"
        if gtest is not None:
            tests.append(gtest)
        parsed.append((" && ".join(tests) if tests else None, res))
    expr = parsed[-1][1]
    for test, res in reversed(parsed[:-1]):
        expr = res if test is None else _blend(test, res, expr)
    params_src = ", ".join(f"{_TYPE} {a}" for a in argnames)
    return f"function {_TYPE} {name}({params_src}) {{\n    return {expr};\n}}\n"


def _lower_function(name: str, clauses, src: bytes) -> str:
    """Lower a function (its list of `function_clause` nodes — the WhatsApp grammar
    emits one `fun_decl` per clause, so the driver groups same-name/arity clauses
    and hands them here)."""
    parts0 = _clause_parts(clauses[0], src)
    if parts0 is None:
        return "// UNSUPPORTED-DECL: malformed function clause\n"
    _name, params, guard, body = parts0
    # Single bare-var clause with no guard: the recursion-aware path (if-based
    # tail / foldable non-tail), else a plain function.
    bare_single = (len(clauses) == 1 and guard is None
                   and all(p.type == "var" and _text(p, src) != "_" for p in params))
    if bare_single:
        pnames = [_text(p, src) for p in params]
        cond_triple = _if_as_conditional(body, src) if params else None
        if cond_triple is not None:
            cond, then_e, else_e = cond_triple
            rec = _try_lower_tail_recursive(name, pnames, cond, then_e, else_e, src)
            if rec is not None:
                return rec
            fold = _try_lower_foldable_nontail(name, pnames, cond, then_e, else_e, src)
            if fold is not None:
                return fold
        if _contains_self_call(body, name, src):
            return (f"// UNSUPPORTED-RECURSION: '{name}' is recursive but not the "
                    f"tail-accumulator or foldable non-tail shape\n")
        # Maps → axons: hoist any `#{…}` in the body to prelude temps, and type any
        # param read via `maps:get(K, P)` as `Axon` (it is a map, not a number).
        _ARG_HOIST.clear()
        prelude = _hoist_maps(body, src)
        axon_params = _maps_get_params(body, set(pnames), src)
        params_src = ", ".join(
            f"{'Axon' if p in axon_params else _TYPE} {p}" for p in pnames)
        body_src = (f"function {_TYPE} {name}({params_src}) {{\n"
                    f"{prelude}    return {_lower_expr(body, src)};\n}}\n")
        _ARG_HOIST.clear()
        return body_src
    return _lower_dispatch(name, clauses, src)


def lower(source: str, source_path: Optional[pathlib.Path] = None) -> str:
    """Erlang source string → Sutra source string."""
    import tree_sitter

    if not grammar_available():
        raise RuntimeError(
            f"Erlang grammar DLL missing at {_DLL}; run "
            f"sdk/sutra-from-erlang/build_grammar.py (needs MSVC)."
        )
    parser = tree_sitter.Parser(_load_language())
    src = source.encode("utf-8")
    tree = parser.parse(src)
    _SUBST.clear()

    # The WhatsApp grammar emits ONE `fun_decl` per clause, so group clauses by
    # (name, arity) — preserving first-seen order — into one dispatching function.
    groups: dict = {}
    order: list = []
    for child in tree.root_node.named_children:
        if child.type != "fun_decl":
            continue  # module/export/other attributes carry no runtime meaning
        fc = next((c for c in child.named_children if c.type == "function_clause"), None)
        if fc is None:
            continue
        cp = _clause_parts(fc, src)
        if cp is None:
            continue
        key = (cp[0], len(cp[1]))
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(fc)

    out = ["// Generated by sutra-from-erlang. See sdk/sutra-from-erlang/README.md.\n"]
    for key in order:
        out.append(_lower_function(key[0], groups[key], src))
    return "\n".join(out)
