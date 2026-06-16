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
import sys as _sys
# Windows dev builds a `.dll` (MSVC); the Linux CI runner builds a `.so` (gcc).
_DLL = _HERE.parent / "_grammar" / (
    "clojure.dll" if _sys.platform == "win32" else "clojure.so")
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

# Maps -> axons (the Rust-struct / OCaml-record / Elixir-map pattern). A `{:x a
# :y b}` literal cannot lower inline (axon construction is statement-shaped), so
# it is HOISTED to a prelude temp and `_ARG_HOIST[node.id]` carries the temp name
# to the position where the map appeared. `_AH_COUNTER` numbers temps per body.
_ARG_HOIST: dict[int, str] = {}
_AH_COUNTER = [0]

# Node ids of let/loop BINDING vectors in the current body — a `vec_lit` there is
# structural (the binding form), NOT a data vector, so it must not be hoisted as a
# positional-key axon. Data vectors `[a b]` (in value position) lower to axons.
_BINDING_VECS: set = set()


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


def _kwd_name(kwd_lit, src: bytes) -> Optional[str]:
    """The clean key of a `kwd_lit` (`:x` → `x`), read from its `kwd_name` child."""
    nm = next((c for c in kwd_lit.named_children if c.type == "kwd_name"), None)
    return _text(nm, src) if nm is not None else None


def _map_key_name(node, src: bytes) -> Optional[str]:
    """The axon-field name for a map key: a `kwd_lit` (`:x` → `x`), a `str_lit`
    (`"x"` → `x`), or a `num_lit` (`1` → `1`, the number's text used as the field
    name, so `{1 a 2 b}` is the same named-field axon as a keyword map and `(get m 1)`
    reads it back). Other key shapes (symbols, expressions) are a later item → None."""
    if node.type == "kwd_lit":
        return _kwd_name(node, src)
    if node.type == "str_lit":
        return _text(node, src).strip().strip('"')
    if node.type == "num_lit":
        return _text(node, src).strip()
    return None


def _map_fields(node, src: bytes):
    """If `node` is a Clojure `{:x a "y" b}` map literal whose keys are all static
    field names (keyword, string, or number), return [(field, value_node), …]; else
    None. Symbol/expression keys are a later item."""
    if node.type != "map_lit":
        return None
    kids = node.named_children
    if len(kids) % 2 != 0 or not kids:
        return None
    fields = []
    for i in range(0, len(kids), 2):
        key_node, val_node = kids[i], kids[i + 1]
        key = _map_key_name(key_node, src)
        if key is None:
            return None  # non-keyword/string key — later item
        fields.append((key, val_node))
    return fields if fields else None


def _vec_fields(node, src: bytes):
    """If `node` is a DATA vector `[a b …]` (a `vec_lit` NOT in let/loop binding
    position), return [("_0", a), ("_1", b), …] — a vector is a positional-key axon
    (`(nth v i)` reads `_i`). Binding vectors (`_BINDING_VECS`) and empty vectors → None."""
    if node.type != "vec_lit" or node.id in _BINDING_VECS:
        return None
    elems = node.named_children
    if not elems:
        return None
    return [(f"_{i}", el) for i, el in enumerate(elems)]


def _collect_binding_vecs(node, src: bytes) -> None:
    """Populate `_BINDING_VECS` with the node ids of let/loop binding vectors in
    `node` (the first `vec_lit` arg of a `(let […] …)` / `(loop […] …)` form), so the
    hoist treats only DATA vectors as positional axons."""
    if node.type == "list_lit":
        head = _head_symbol(node, src)
        if head in ("let", "loop"):
            args = node.named_children[1:]
            bvec = next((a for a in args if a.type == "vec_lit"), None)
            if bvec is not None:
                _BINDING_VECS.add(bvec.id)
                # A destructuring PATTERN vector `[a b]` sits at an even (binding)
                # position inside the binding vector — it is structural, not data,
                # so mark it too (else `_hoist_maps` would hoist it as an axon).
                bkids = bvec.named_children
                for i in range(0, len(bkids) - 1, 2):
                    if bkids[i].type == "vec_lit":
                        _BINDING_VECS.add(bkids[i].id)
    for c in node.named_children:
        _collect_binding_vecs(c, src)


def _hoist_maps(node, src: bytes, indent: str = "    ") -> str:
    """Post-order walk: hoist EVERY map OR data-vector literal to a prelude `Axon
    _ahN; …` group and register `node.id → _ahN` in `_ARG_HOIST`. Mirrors the
    Elixir/Rust shape."""
    prelude = ""
    for child in node.named_children:
        prelude += _hoist_maps(child, src, indent)
    fields = _map_fields(node, src)
    if fields is None:
        fields = _vec_fields(node, src)   # data vectors -> positional-key axons
    if fields is not None:
        tmp = f"_ah{_AH_COUNTER[0]}"
        _AH_COUNTER[0] += 1
        prelude += f"{indent}Axon {tmp};\n"
        for field, val in fields:
            prelude += f'{indent}{tmp}.add("{field}", {_lower_expr(val, src)});\n'
        _ARG_HOIST[node.id] = tmp
    return prelude


def _kwd_accessed_params(body, params: set, src: bytes) -> set:
    """Param names read via keyword access `(:k p)` or `(get p :k)` — these are
    maps, so they type as `Axon` rather than the default `number`."""
    found: set = set()

    def walk(n):
        if n.type == "list_lit":
            kids = n.named_children
            # `(:k p)` — keyword in head position
            if (len(kids) == 2 and kids[0].type == "kwd_lit"
                    and kids[1].type == "sym_lit"
                    and _text(kids[1], src) in params):
                found.add(_text(kids[1], src))
            # `(get p :k)` — get with a map-param first argument
            elif (len(kids) == 3 and kids[0].type == "sym_lit"
                    and _text(kids[0], src) == "get"
                    and kids[1].type == "sym_lit"
                    and _text(kids[1], src) in params):
                found.add(_text(kids[1], src))
            # `(nth v i)` — vector-param positional access types `v` as Axon
            elif (len(kids) == 3 and kids[0].type == "sym_lit"
                    and _text(kids[0], src) == "nth"
                    and kids[1].type == "sym_lit"
                    and _text(kids[1], src) in params):
                found.add(_text(kids[1], src))
            # `(first v)` / `(second v)` — vector-param accessors type `v` as Axon
            elif (len(kids) == 2 and kids[0].type == "sym_lit"
                    and _text(kids[0], src) in ("first", "second")
                    and kids[1].type == "sym_lit"
                    and _text(kids[1], src) in params):
                found.add(_text(kids[1], src))
        for c in n.named_children:
            walk(c)

    walk(body)
    return found


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


# Associative + commutative combine ops for the non-tail fold transform.
_FOLD_OPS = {"+", "*"}


def _contains_symbol(node, ident: str, src: bytes) -> bool:
    if node.type == "sym_lit" and _text(node, src) == ident:
        return True
    return any(_contains_symbol(c, ident, src) for c in node.named_children)


def _try_lower_foldable_nontail(name: str, params: list, body, src: bytes):
    """CPS / accumulator transform for a FOLDABLE non-tail
    `(defn f [n] (if COND BASE (OP LEAF (f REC))))` (single param, OP in
    `_FOLD_OPS`): the pending call-stack work is reified as an accumulator carried
    by a Sutra `while_loop` trampoline — the OCaml/Scala/Rust/Haskell/F# shape
    ported. BASE is evaluated pre-loop at the INITIAL param, so a param-dependent
    BASE is rejected (→ None). Returns loop decl + function, or None."""
    if body.type != "list_lit" or _head_symbol(body, src) != "if" \
            or len(params) != 1:
        return None
    args = body.named_children[1:]
    if len(args) < 3:
        return None
    cond, then_e, else_e = args[0], args[1], args[2]

    def foldable(node):
        if node.type != "list_lit":
            return None
        op = _head_symbol(node, src)
        if op not in _FOLD_OPS:
            return None
        operands = node.named_children[1:]
        if len(operands) != 2:
            return None  # the binary LEAF <OP> f(REC) shape
        lc = _self_call_args(operands[0], name, 1, src)
        rc = _self_call_args(operands[1], name, 1, src)
        if (lc is None) == (rc is None):
            return None
        return (op, operands[1], lc[0]) if lc is not None \
            else (op, operands[0], rc[0])

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
    if _contains_symbol(base, pname, src):
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


def _try_lower_loop_form(name: str, params: list, body, src: bytes):
    """Lower `(defn f [p…] (loop [v0 i0 v1 i1 …] (if COND (recur a…) BASE)))` to a
    declared Sutra `while_loop`. The loop bindings become the recurrent state
    (initialised from their init exprs, not 0); `recur` updates them simultaneously
    via temps (the tail-recursion shape); any defn param the cond/recur-args/base
    reference is threaded read-only (the Rust `while`-loop param shape, since the
    hoisted loop is top-level). The base is returned after write-back. Returns the
    emitted Sutra or None when the body is not this loop shape."""
    if body.type != "list_lit" or _head_symbol(body, src) != "loop":
        return None
    bargs = body.named_children[1:]
    if len(bargs) < 2 or bargs[0].type != "vec_lit":
        return None
    bvec = bargs[0].named_children
    if len(bvec) == 0 or len(bvec) % 2 != 0:
        return None
    loop_vars: list[str] = []
    inits: list = []
    for i in range(0, len(bvec), 2):
        if bvec[i].type != "sym_lit":
            return None  # destructuring bind — a later item
        loop_vars.append(_text(bvec[i], src))
        inits.append(bvec[i + 1])
    loop_body = bargs[-1]
    if loop_body.type != "list_lit" or _head_symbol(loop_body, src) != "if":
        return None
    iargs = loop_body.named_children[1:]
    if len(iargs) < 3:
        return None
    cond, then_e, else_e = iargs[0], iargs[1], iargs[2]
    arity = len(loop_vars)

    def recur_args(node):
        if node.type == "list_lit" and _head_symbol(node, src) == "recur":
            a = node.named_children[1:]
            return a if len(a) == arity else None
        return None

    then_r, else_r = recur_args(then_e), recur_args(else_e)
    if (then_r is None) == (else_r is None):
        return None  # exactly one branch must be the `recur`
    if then_r is not None:
        cont, rec_args, base = _lower_expr(cond, src), then_r, else_e
    else:
        cont, rec_args, base = _negate_cond(cond, src), else_r, then_e

    # Defn params referenced by cond/recur-args/base (not loop vars) — threaded
    # read-only so the hoisted top-level loop sees them.
    extra: list[str] = []

    def collect(node):
        if node.type == "sym_lit":
            t = _text(node, src)
            if t in params and t not in loop_vars and t not in extra:
                extra.append(t)
        for c in node.named_children:
            collect(c)

    collect(cond)
    for a in rec_args:
        collect(a)
    collect(base)

    ty = _TYPE
    state = loop_vars + extra
    loop_name = f"_loop_{name}"
    state_decls = ", ".join(f"{ty} {v} = 0" for v in state)
    temp_decls = "".join(f"    {ty} _t{i} = {_lower_expr(a, src)};\n"
                         for i, a in enumerate(rec_args))
    assigns = "".join(f"    {loop_vars[i]} = _t{i};\n" for i in range(arity))
    init_lines = "".join(f"    {ty} {v} = {_lower_expr(init, src)};\n"
                         for v, init in zip(loop_vars, inits))
    base_src = _lower_expr(base, src)
    if any("UNSUPPORTED" in s for s in (cont, base_src, temp_decls, init_lines)):
        return None
    loop_decl = (f"while_loop {loop_name}({cont}, {state_decls}) {{\n"
                 f"{temp_decls}{assigns}}}\n")
    slot_lines = "".join(f"    slot {ty} _{v}_r = {v};\n" for v in state)
    slot_args = ", ".join(f"_{v}_r" for v in state)
    writeback = "".join(f"    {v} = _{v}_r;\n" for v in loop_vars)
    params_src = ", ".join(f"{ty} {p}" for p in params)
    fn = (
        f"function {ty} {name}({params_src}) {{\n"
        f"{init_lines}"
        f"{slot_lines}"
        f"    loop {loop_name}({cont}, {slot_args});\n"
        f"{writeback}"
        f"    return {base_src};\n"
        f"}}\n"
    )
    return loop_decl + fn


def _lower_expr(node, src: bytes) -> str:
    if _ARG_HOIST and node.id in _ARG_HOIST:
        return _ARG_HOIST[node.id]  # a hoisted map literal — emit its temp name
    t = node.type
    if t == "map_lit":
        # A map literal reaching here was not hoisted — surface the gap.
        return "/* UNSUPPORTED-CONSTRUCTION: map value outside a hoistable position */"
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
            # `(:key m)` — a keyword in head position is an accessor: get :key
            # from the map m, projected to a clean number-vector (the Rust/Elixir
            # field-read shape).
            if (len(kids) == 2 and kids[0].type == "kwd_lit"):
                key = _kwd_name(kids[0], src)
                if key is not None:
                    return f'realvec({_lower_expr(kids[1], src)}.item("{key}"))'
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
                pat = pairs[i]
                if pat.type == "vec_lit":
                    # `[a b]` vector destructuring: each element substitutes to the
                    # positional axon field read `realvec(val.item("_j"))` (the same
                    # projection `(nth v j)` uses). The value must be a bare name (a
                    # vector param or a hoisted data-vector temp); only plain-symbol
                    # elements are in scope (nested destructure is a later item).
                    elems = pat.named_children
                    val_src = _lower_expr(pairs[i + 1], src)
                    if (not elems or any(e.type != "sym_lit" for e in elems)
                            or not val_src.isidentifier()):
                        for nm in bound:
                            _SUBST.pop(nm, None)
                        return ("/* UNSUPPORTED-EXPR: vector destructuring shape "
                                "(nested pattern / non-name value — later item) */")
                    for j, e in enumerate(elems):
                        nm = _text(e, src)
                        _SUBST[nm] = f'realvec({val_src}.item("_{j}"))'
                        bound.append(nm)
                    continue
                if pat.type != "sym_lit":
                    for nm in bound:
                        _SUBST.pop(nm, None)
                    return "/* UNSUPPORTED-EXPR: non-symbol let binding (destructuring later) */"
                nm = _text(pat, src)
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
        if head == "case":
            # (case E c1 r1 c2 r2 … [default]) — dispatch E against literal
            # constants; lowers to a nested equality defuzz-blend (the `cond`
            # shape with an implicit (= E ci) test per clause). A trailing lone
            # arg is the default (Clojure throws on no match; we use it as the
            # base, or 0 if absent). E is lowered once and reused per clause —
            # MVP value domain is numbers, so re-evaluation is side-effect-free.
            # A clause test may be a single constant `c` or a multi-constant
            # LIST `(c1 c2 …)` — the latter matches if E equals any member
            # (Clojure's list-test semantics), lowered to an OR of `(E == ci)`.
            if len(args) < 3:
                return "/* UNSUPPORTED-EXPR: malformed case */"
            e_src = f"({_lower_expr(args[0], src)})"
            clauses = args[1:]
            has_default = (len(clauses) % 2 == 1)
            default_src = _lower_expr(clauses[-1], src) if has_default else "0"
            pair_clauses = clauses[:-1] if has_default else clauses
            parsed = []
            for i in range(0, len(pair_clauses), 2):
                const_node, res_node = pair_clauses[i], pair_clauses[i + 1]
                if const_node.type in ("num_lit", "bool_lit"):
                    test = f"({e_src} == {_lower_expr(const_node, src)})"
                elif const_node.type == "list_lit":
                    consts = const_node.named_children
                    if not consts or any(
                            c.type not in ("num_lit", "bool_lit") for c in consts):
                        return ("/* UNSUPPORTED-EXPR: case test list "
                                "(number/bool literal members only) */")
                    ors = " || ".join(
                        f"({e_src} == {_lower_expr(c, src)})" for c in consts)
                    test = f"({ors})"
                else:
                    return ("/* UNSUPPORTED-EXPR: case test constant "
                            "(number/bool literals or a literal list — symbols later) */")
                parsed.append((test, _lower_expr(res_node, src)))
            expr = default_src
            for test, res in reversed(parsed):
                expr = _blend(test, res, expr)
            return expr
        if head == "get" and len(args) == 2:
            # `(get m :k)` / `(get m "k")` — map field read, the function-call
            # form of the `(:k m)` accessor; both lower to `realvec(m.item("k"))`.
            key = _map_key_name(args[1], src)
            if key is not None:
                return f'realvec({_lower_expr(args[0], src)}.item("{key}"))'
        if head == "nth" and len(args) == 2 and args[1].type == "num_lit":
            # `(nth v i)` — vector read at a static index → the positional axon
            # field `_i` (the tuple/map field-read shape).
            idx = _text(args[1], src).strip()
            return f'realvec({_lower_expr(args[0], src)}.item("_{idx}"))'
        if head in ("first", "second") and len(args) == 1:
            # `(first v)` / `(second v)` — the positional axon fields _0 / _1.
            field = "_0" if head == "first" else "_1"
            return f'realvec({_lower_expr(args[0], src)}.item("{field}"))'
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
        fold = _try_lower_foldable_nontail(name, params, body, src)
        if fold is not None:
            return fold
    loop_form = _try_lower_loop_form(name, params, body, src)
    if loop_form is not None:
        return loop_form
    if _contains_self_call(body, name, src):
        # Recursion / `recur` outside the supported tail/foldable shapes — a
        # plain self-call would not terminate through the fuzzy-if blend.
        return (f"// UNSUPPORTED-RECURSION: '{name}' is recursive but not the "
                f"tail-accumulator or foldable non-tail shape\n")
    # Maps -> axons: hoist any `{:k v}` literals to prelude temps, and type any
    # keyword-accessed param as `Axon` (it is a map, not a number).
    _ARG_HOIST.clear()
    _BINDING_VECS.clear()
    _collect_binding_vecs(body, src)   # mark let/loop binding vecs (not data vectors)
    prelude = _hoist_maps(body, src)
    axon_params = _kwd_accessed_params(body, set(params), src)
    params_src = ", ".join(
        f"{'Axon' if p in axon_params else _TYPE} {p}" for p in params)
    body_src = _lower_expr(body, src)
    _ARG_HOIST.clear()
    return (f"function {_TYPE} {name}({params_src}) {{\n"
            f"{prelude}"
            f"    return {body_src};\n"
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
    _ARG_HOIST.clear()
    _AH_COUNTER[0] = 0

    out = ["// Generated by sutra-from-clojure. See sdk/sutra-from-clojure/README.md.\n"]
    for child in tree.root_node.named_children:
        if child.type == "list_lit" and _head_symbol(child, src) == "defn":
            out.append(_lower_defn(child, src))
        # ns/def/comment forms are later items
    return "\n".join(out)
