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
import sys as _sys
# Windows dev builds a `.dll` (MSVC); the Linux CI runner builds a `.so` (gcc).
_DLL = _HERE.parent / "_grammar" / (
    "fsharp.dll" if _sys.platform == "win32" else "fsharp.so")
_DEFAULT_TYPE = "int"

# F# primitive type name → Sutra type (the OCaml `_OCAML_TYPE_TO_SUTRA` set;
# F# shares the same primitive names). Unknown types fall back to the default.
_FSHARP_TYPE_TO_SUTRA = {
    "int": "int",
    "float": "float",
    "double": "float",
    "bool": "bool",
    "string": "String",
    "unit": "void",
}


# Record + discriminated-union types declared in the file. A param/value of such a
# type lowers as a Sutra `Axon` (named-field for records; tag+payload for DUs — the
# OCaml/Rust/Haskell pattern).
_RECORD_TYPES: set = set()

# Discriminated-union variant cases: `variant name → (tag, arity)`, tags assigned in
# declaration order per `type T = | A … | B …`. Construction `A x` → a tagged axon
# (`_tag` + `_val0…`); a `match` pattern `A x` tests `_tag` and binds the payload.
_VARIANTS: dict = {}

# Per-function counter for unique `_vtag{N}` int-locals — a variant `match` binds the
# scrutinee's tag to an `int` local in the prelude BEFORE comparing (`int _vtag0 =
# realvec(s.item("_tag")); … (_vtag0 == k)`). Comparing the tag inline as a raw filler
# (`realvec(...) == 0`) is NOT crisp at 0 (measured: a 0-tag dispatch returned the 50/50
# blend, 32 not 48); the int-local round-trip makes it crisp — the working Haskell shape.
_VTAG_N = [0]

# Per-function counter for hoisted aggregate-argument temps (`_ahN`). A tuple/record/
# DU construction passed DIRECTLY as a call argument (`addPair (5, 8)`) is statement-
# shaped, so it is hoisted to a prelude temp and the temp name used at the call site —
# bringing F# to parity with the other frontends (which all hoist arg constructions).
_AH_N = [0]

# Per-function construction prelude (record `{ … }` literals are statement-shaped, so
# they are emitted as `Axon q; q.add(…)` BEFORE the return) and the set of axon-typed
# names in scope (record params + record-bound locals) for `p.x` field-access dispatch.
_PRELUDE: list = []
_AXON_VARS: set = set()


def _map_fsharp_type(simple_type_node, src: bytes) -> str:
    """A `simple_type` (`long_identifier`-wrapped type name) → Sutra type. A declared
    record type name → `Axon` (a record is structurally a named-field axon)."""
    if simple_type_node is None:
        return _DEFAULT_TYPE
    if simple_type_node.type == "compound_type":   # `int * int` — a tuple is an axon
        return "Axon"
    text = _text(simple_type_node, src).strip()
    if text in _RECORD_TYPES:
        return "Axon"
    return _FSHARP_TYPE_TO_SUTRA.get(text, _DEFAULT_TYPE)

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
        # Record field access `p.x` is a `long_identifier` with parts [p, x]; when the
        # head is an axon-typed name in scope, read the field (the Rust/Elixir
        # realvec(item) shape). A long_identifier_or_op wraps a long_identifier.
        ln = node
        if t == "long_identifier_or_op" and node.named_children \
                and node.named_children[0].type == "long_identifier":
            ln = node.named_children[0]
        if ln.type == "long_identifier":
            idents = [c for c in ln.named_children if c.type == "identifier"]
            if len(idents) == 2 and _text(idents[0], src) in _AXON_VARS:
                obj, field = _text(idents[0], src), _text(idents[1], src)
                return f'realvec({obj}.item("{field}"))'
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
        hname = _text(head, src).strip()
        # `fst t` / `snd t` — pair accessors → the positional axon fields _0 / _1.
        if hname in ("fst", "snd") and len(args) == 1:
            field = "_0" if hname == "fst" else "_1"
            return f'realvec({_lower_expr(args[0], src)}.item("{field}"))'
        # A tuple/record/DU construction passed directly as an argument is hoisted to
        # a prelude temp (axon-build statements), then the temp name used here.
        arg_srcs = [(_hoist_construction_arg(a, src) or _lower_expr(a, src))
                    for a in args]
        return f"{hname}({', '.join(arg_srcs)})"
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
        # If any rule is a DU variant pattern, bind the scrutinee's tag to an `int`
        # local FIRST (crisp equality even at tag 0; see _VTAG_N). Emitted to _PRELUDE.
        rule_nodes = [r for r in rules.named_children if r.type == "rule"]
        is_variant_match = any(
            r.named_children and r.named_children[0].type == "identifier_pattern"
            and r.named_children[0].named_children
            and _text(r.named_children[0].named_children[0], src).strip() in _VARIANTS
            for r in rule_nodes)
        tagv = None
        if is_variant_match:
            tagv = f"_vtag{_VTAG_N[0]}"
            _VTAG_N[0] += 1
            _PRELUDE.append(f'    int {tagv} = realvec({scrut_src}.item("_tag"));\n')
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
                pk = pat.named_children
                head_name = _text(pk[0], src).strip() if pk else ""
                if head_name in _VARIANTS:
                    # `| Circle r -> …`: a DU variant pattern. Test the scrutinee's
                    # `_tag` (via the crisp int-local); bind payload names to `_val0…`.
                    tag, _arity = _VARIANTS[head_name]
                    test = f'({tagv} == {tag})'
                    payload = [c for c in pk[1:] if c.type == "identifier_pattern"]
                    binds = [(_text(pp, src).strip(),
                              f'realvec({scrut_src}.item("_val{i}"))')
                             for i, pp in enumerate(payload)]
                    for nm, sub in binds:
                        _SUBST[nm] = sub
                    try:
                        res_src = _lower_expr(res, src)
                    finally:
                        for nm, _sub in binds:
                            _SUBST.pop(nm, None)
                else:
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
        kids = node.named_children
        # let-SEQUENCE body: a value binding `let a = e` followed by a continuation
        # (`let a = e1 \n let b = e2 \n expr` nests as declaration_expressions). Lower
        # it by sequential substitution — the same shape as the Clojure/Haskell `let`:
        # bind `a → (lowered e1)`, lower the continuation, pop. Bindings see earlier
        # ones (F# `let` is sequential), so process in order.
        if len(kids) >= 2 and kids[0].type == "function_or_value_defn":
            tpb = _tuple_pattern_binding(kids[0], src)
            if tpb is not None:
                # `let (a, b) = t` — destructure a tuple axon into named locals.
                # Each element substitutes to the positional axon field read
                # `realvec(t.item("_i"))` (the same projection `fst`/`snd` use). The
                # value must be a bare name (a param or a let-bound temp); a
                # parenthesised `(expr).item(...)` falls through to the tensor op.
                names, val_node = tpb
                val_src = _lower_expr(val_node, src)
                if not val_src.isidentifier():
                    return ("/* UNSUPPORTED-LET: tuple-pattern binding value is "
                            "not a simple name (later item) */")
                subs: list[str] = []
                for i, nm in enumerate(names):
                    _SUBST[nm] = f'realvec({val_src}.item("_{i}"))'
                    subs.append(nm)
                try:
                    return _lower_expr(kids[1], src)
                finally:
                    for nm in subs:
                        _SUBST.pop(nm, None)
            rpb = _record_pattern_binding(kids[0], src)
            if rpb is not None:
                # `let { x = a; y = b } = p` — destructure a record axon: each bound
                # local reads the named axon field `realvec(p.item("x"))` (the `p.x`
                # projection). The value must be a bare name (a record param or a
                # let-bound record temp).
                binds, val_node = rpb
                val_src = _lower_expr(val_node, src)
                if not val_src.isidentifier():
                    return ("/* UNSUPPORTED-LET: record-pattern binding value is "
                            "not a simple name (later item) */")
                subs = []
                for field, local in binds:
                    _SUBST[local] = f'realvec({val_src}.item("{field}"))'
                    subs.append(local)
                try:
                    return _lower_expr(kids[1], src)
                finally:
                    for nm in subs:
                        _SUBST.pop(nm, None)
            dpb = _du_pattern_binding(kids[0], src)
            if dpb is not None:
                # `let (Circle r) = s` — destructure a tagged DU axon: each payload
                # local reads `realvec(s.item("_val{i}"))` (the `match`-arm payload
                # bind). The value must be a bare name (a DU param or a let-bound
                # DU temp).
                variant, locals_, val_node = dpb
                val_src = _lower_expr(val_node, src)
                if not val_src.isidentifier():
                    return ("/* UNSUPPORTED-LET: DU-pattern binding value is not a "
                            "simple name (later item) */")
                subs = []
                for i, local in enumerate(locals_):
                    _SUBST[local] = f'realvec({val_src}.item("_val{i}"))'
                    subs.append(local)
                try:
                    return _lower_expr(kids[1], src)
                finally:
                    for nm in subs:
                        _SUBST.pop(nm, None)
            vb = _value_binding(kids[0], src)
            if vb is not None:
                name, val_node = vb
                tup_fields = _tuple_fields(val_node, src)
                if tup_fields is not None:
                    # `let t = (a, b)` — tuple construction to a positional-key axon.
                    _PRELUDE.append(f"    Axon {name};\n")
                    for field, fval in tup_fields:
                        _PRELUDE.append(f'    {name}.add("{field}", {_lower_expr(fval, src)});\n')
                    _AXON_VARS.add(name)
                    return _lower_expr(kids[1], src)
                rec_fields = _record_fields(val_node, src)
                if rec_fields is not None:
                    # `let q = { x = a; y = b }` — record construction is statement-
                    # shaped (axon `add`s), so emit it to the prelude and keep `q` as a
                    # real axon variable (NOT a substitution). Field access `q.x` then
                    # dispatches via _AXON_VARS. Sutra/Yantra OS: a record is an axon.
                    _PRELUDE.append(f"    Axon {name};\n")
                    for field, fval in rec_fields:
                        _PRELUDE.append(f'    {name}.add("{field}", {_lower_expr(fval, src)});\n')
                    _AXON_VARS.add(name)
                    return _lower_expr(kids[1], src)
                va = _variant_application(val_node, src)
                if va is not None:
                    # `let c = Circle 4` — DU construction to a TAGGED axon (`_tag` +
                    # `_val0…`), the Haskell/Rust variant shape; emitted to the prelude.
                    vname, vargs = va
                    tag, _arity = _VARIANTS[vname]
                    _PRELUDE.append(f"    Axon {name};\n")
                    _PRELUDE.append(f'    {name}.add("_tag", {tag});\n')
                    for i, a in enumerate(vargs):
                        _PRELUDE.append(f'    {name}.add("_val{i}", {_lower_expr(a, src)});\n')
                    _AXON_VARS.add(name)
                    return _lower_expr(kids[1], src)
                val_src = _lower_expr(val_node, src)
                prev = _SUBST.get(name)
                _SUBST[name] = f"({val_src})"
                try:
                    cont_src = _lower_expr(kids[1], src)
                finally:
                    if prev is None:
                        _SUBST.pop(name, None)
                    else:
                        _SUBST[name] = prev
                return cont_src
        # single child (the function-body wrapper) — lower it directly.
        return _lower_expr(kids[0], src)
    return f"/* UNSUPPORTED-EXPR: {t} */"


def _value_binding(fovd, src: bytes):
    """If `fovd` is a `function_or_value_defn` that is a simple VALUE binding
    (`let a = expr`, a `value_declaration_left` with a plain identifier pattern),
    return (name, value_node); else None (a nested function defn or other shape —
    not a let-bound scalar local, a later item)."""
    kids = fovd.named_children
    if not kids or kids[0].type != "value_declaration_left":
        return None
    ip = next((c for c in kids[0].named_children
               if c.type == "identifier_pattern"), None)
    if ip is None or kids[-1] is kids[0]:
        return None
    return _text(ip, src).strip(), kids[-1]


def _tuple_pattern_binding(fovd, src: bytes):
    """If `fovd` is a tuple-pattern value binding `let (a, b) = expr`
    (`value_declaration_left → paren_pattern → repeat_pattern` of plain
    `identifier_pattern`s), return ([name, …], value_node); else None. A nested /
    non-identifier element is a later item (→ None)."""
    kids = fovd.named_children
    if not kids or kids[0].type != "value_declaration_left":
        return None
    vdl = kids[0]
    if kids[-1] is vdl:
        return None  # no value expression
    paren = next((c for c in vdl.named_children if c.type == "paren_pattern"), None)
    if paren is None:
        return None
    rep = next((c for c in paren.named_children if c.type == "repeat_pattern"), None)
    if rep is None:
        return None
    names: list[str] = []
    for ip in rep.named_children:
        if ip.type != "identifier_pattern" or not ip.named_children:
            return None
        names.append(_text(ip.named_children[0], src).strip())
    return (names, kids[-1]) if names else None


def _record_pattern_binding(fovd, src: bytes):
    """If `fovd` is a record-pattern value binding `let { x = a; y = b } = expr`
    (`value_declaration_left → record_pattern → field_pattern[long_identifier field,
    identifier_pattern local]`), return ([(field, local), …], value_node); else None.
    A field pattern that is not a plain `field = local-name` is a later item (→ None)."""
    kids = fovd.named_children
    if not kids or kids[0].type != "value_declaration_left":
        return None
    vdl = kids[0]
    if kids[-1] is vdl:
        return None  # no value expression
    rp = next((c for c in vdl.named_children if c.type == "record_pattern"), None)
    if rp is None:
        return None
    binds: list[tuple[str, str]] = []
    for fp in rp.named_children:
        if fp.type != "field_pattern":
            continue
        field_node = next((c for c in fp.named_children
                           if c.type == "long_identifier"), None)
        local_pat = next((c for c in fp.named_children
                          if c.type == "identifier_pattern"), None)
        if field_node is None or local_pat is None or not local_pat.named_children:
            return None
        binds.append((_text(field_node, src).strip(),
                      _text(local_pat.named_children[0], src).strip()))
    return (binds, kids[-1]) if binds else None


def _du_pattern_binding(fovd, src: bytes):
    """If `fovd` is a DU-case value binding `let (Circle r) = s`
    (`value_declaration_left → paren_pattern → identifier_pattern[variant head,
    payload identifier_patterns]`), return (variant, [payload_local, …], value_node);
    else None. The head `long_identifier_or_op` must name a known variant; only plain
    identifier payloads are in scope (the `match` DU-pattern shape, lifted to a let)."""
    kids = fovd.named_children
    if not kids or kids[0].type != "value_declaration_left":
        return None
    vdl = kids[0]
    if kids[-1] is vdl:
        return None  # no value expression
    paren = next((c for c in vdl.named_children if c.type == "paren_pattern"), None)
    if paren is None:
        return None
    ip = next((c for c in paren.named_children
               if c.type == "identifier_pattern"), None)
    if ip is None or not ip.named_children:
        return None
    variant = _text(ip.named_children[0], src).strip()
    if variant not in _VARIANTS:
        return None
    locals_: list[str] = []
    for pp in ip.named_children[1:]:
        if pp.type != "identifier_pattern" or not pp.named_children:
            return None
        locals_.append(_text(pp.named_children[0], src).strip())
    return (variant, locals_, kids[-1]) if locals_ else None


def _tuple_fields(node, src: bytes):
    """If `node` is a tuple literal `(a, b, …)`, return [("_0", a), ("_1", b), …] — a
    tuple is a positional-key axon (`fst`/`snd` read `_0`/`_1`). The tuple parses as a
    `paren_expression` wrapping a `tuple_expression` (the parens ARE the tuple syntax),
    so unwrap a single paren layer. Else None."""
    if node.type == "paren_expression" and len(node.named_children) == 1:
        node = node.named_children[0]
    if node.type != "tuple_expression":
        return None
    elems = node.named_children
    if not elems:
        return None
    return [(f"_{i}", el) for i, el in enumerate(elems)]


def _record_fields(node, src: bytes):
    """If `node` is a record literal `{ x = a; y = b }` (`brace_expression` →
    `field_initializers`), return [(field, value_node), …]; else None. Record-update
    syntax (`{ r with … }`) and computed field names are a later item → None."""
    if node.type != "brace_expression":
        return None
    fis = next((c for c in node.named_children
                if c.type == "field_initializers"), None)
    if fis is None:
        return None
    fields = []
    for fi in fis.named_children:
        if fi.type != "field_initializer" or len(fi.named_children) < 2:
            return None
        field = _text(fi.named_children[0], src).strip()
        fields.append((field, fi.named_children[-1]))
    return fields if fields else None


def _record_type_names(root, src: bytes) -> set:
    """All record type names declared in the file (`type Point = { … }` →
    `type_definition` → `record_type_defn` → `type_name`)."""
    names: set = set()

    def walk(n):
        if n.type == "record_type_defn":
            tn = next((c for c in n.named_children if c.type == "type_name"), None)
            if tn is not None:
                ident = next((c for c in tn.named_children
                              if c.type == "identifier"), None)
                if ident is not None:
                    names.add(_text(ident, src).strip())
        for c in n.named_children:
            walk(c)

    walk(root)
    return names


def _union_info(root, src: bytes):
    """Scan `union_type_defn`s. Returns (type_names, variants): the DU type names (for
    `Axon` param typing) and `variant → (tag, arity)` (tags per-DU in declaration
    order; arity = number of `union_type_field`s)."""
    type_names: set = set()
    variants: dict = {}

    def walk(n):
        if n.type == "union_type_defn":
            tn = next((c for c in n.named_children if c.type == "type_name"), None)
            if tn is not None:
                ti = next((c for c in tn.named_children if c.type == "identifier"), None)
                if ti is not None:
                    type_names.add(_text(ti, src).strip())
            cases = next((c for c in n.named_children
                          if c.type == "union_type_cases"), None)
            tag = 0
            for case in (cases.named_children if cases is not None else []):
                if case.type != "union_type_case":
                    continue
                ci = next((c for c in case.named_children
                           if c.type == "identifier"), None)
                if ci is None:
                    continue
                fields = next((c for c in case.named_children
                               if c.type == "union_type_fields"), None)
                arity = len([c for c in fields.named_children
                             if c.type == "union_type_field"]) if fields else 0
                variants[_text(ci, src).strip()] = (tag, arity)
                tag += 1
        for c in n.named_children:
            walk(c)

    walk(root)
    return type_names, variants


def _variant_application(node, src: bytes):
    """If `node` is a DU construction `Circle 4` (an `application_expression` whose head
    names a known variant), return (variant_name, [arg_nodes]); else None. A bare
    nullary variant in value position is a later item (ambiguous with a plain name)."""
    if node.type != "application_expression":
        return None
    head, args = _flatten_apply(node)
    if head.type in ("identifier", "long_identifier_or_op", "long_identifier"):
        name = _text(head, src).strip()
        if name in _VARIANTS:
            return name, args
    return None


def _hoist_construction_arg(node, src: bytes):
    """If `node` is a tuple/record/DU construction in ARGUMENT position, emit its
    axon-build statements to `_PRELUDE` and return the temp name (`_ahN`); else None.
    The let-bound construction path stays separate (it builds into the bound name);
    this is only for constructions passed directly as a call argument."""
    tf = _tuple_fields(node, src)            # `(a, b)` — paren-wrapped tuple
    if tf is not None:
        tmp = f"_ah{_AH_N[0]}"
        _AH_N[0] += 1
        _PRELUDE.append(f"    Axon {tmp};\n")
        for field, val in tf:
            _PRELUDE.append(f'    {tmp}.add("{field}", {_lower_expr(val, src)});\n')
        return tmp
    inner = node
    if inner.type == "paren_expression" and inner.named_children:
        inner = inner.named_children[0]
    rf = _record_fields(inner, src)          # `{ x = a }`
    if rf is not None:
        tmp = f"_ah{_AH_N[0]}"
        _AH_N[0] += 1
        _PRELUDE.append(f"    Axon {tmp};\n")
        for field, val in rf:
            _PRELUDE.append(f'    {tmp}.add("{field}", {_lower_expr(val, src)});\n')
        return tmp
    va = _variant_application(inner, src)     # `Circle 4`
    if va is not None:
        vname, vargs = va
        tag, _arity = _VARIANTS[vname]
        tmp = f"_ah{_AH_N[0]}"
        _AH_N[0] += 1
        _PRELUDE.append(f"    Axon {tmp};\n")
        _PRELUDE.append(f'    {tmp}.add("_tag", {tag});\n')
        for i, a in enumerate(vargs):
            _PRELUDE.append(f'    {tmp}.add("_val{i}", {_lower_expr(a, src)});\n')
        return tmp
    return None


def _typed_paren_param(paren, src: bytes):
    """A `paren_pattern` wrapping `(x: T)` → (name, sutra_type) or None. Shape:
    `paren_pattern → typed_pattern → [identifier_pattern, simple_type]`."""
    tp = next((c for c in paren.named_children if c.type == "typed_pattern"), None)
    if tp is None:
        return None
    ident_pat = next((c for c in tp.named_children
                      if c.type == "identifier_pattern"), None)
    simple_ty = next((c for c in tp.named_children if c.type == "simple_type"), None)
    if ident_pat is None or not ident_pat.named_children:
        return None
    return _text(ident_pat.named_children[0], src), _map_fsharp_type(simple_ty, src)


def _extract_value_decl_left(left, src: bytes):
    """The return-type-annotated form `let f (a: T) … : R = …` parses as a
    `value_declaration_left`. The curried-type grammar nests the params + return
    annotation differently per arity, so this walks the subtree structurally:
    every `paren_pattern` (in document order) is one `(x: T)` param, and the
    return type is the `simple_type` inside a `typed_pattern` that also has a
    `paren_pattern` child (the param-and-return wrapper) — or, for a bare value
    `let x : R = …`, a direct `simple_type` child. Returns
    (name, params, param_ty, ret_type) or None if outside this shape."""
    kids = left.named_children
    idp = kids[0] if kids and kids[0].type == "identifier_pattern" else None
    if idp is None:
        return None
    loi = next((c for c in idp.named_children
                if c.type == "long_identifier_or_op"), None)
    if loi is None:
        return None
    name = _text(loi, src)

    parens: list = []

    def collect_parens(n):
        for c in n.named_children:
            if c.type == "paren_pattern":
                parens.append(c)        # a param — do NOT recurse into it (its
                                        # inner typed_pattern is the PARAM type)
            else:
                collect_parens(c)

    collect_parens(left)
    params: list[str] = []
    param_ty: dict[str, str] = {}
    for pp in parens:
        r = _typed_paren_param(pp, src)
        if r is None:
            return None
        params.append(r[0])
        param_ty[r[0]] = r[1]

    ret = [_DEFAULT_TYPE]

    def find_ret(n):
        if n.type == "typed_pattern" and any(
                c.type == "paren_pattern" for c in n.named_children):
            sty = next((c for c in n.named_children
                        if c.type == "simple_type"), None)
            if sty is not None:
                ret[0] = _map_fsharp_type(sty, src)  # the param-and-return wrapper
        for c in n.named_children:
            find_ret(c)

    find_ret(left)
    if not params:                      # bare value: `let x : R = …`
        sty = (next((c for c in idp.named_children
                     if c.type == "simple_type"), None)
               or next((c for c in kids if c.type == "simple_type"), None))
        if sty is not None:
            ret[0] = _map_fsharp_type(sty, src)
    return name, params, param_ty, ret[0]


def _lower_defn(defn, src: bytes) -> str:
    """A `function_or_value_defn`: a `function_declaration_left` (untyped/typed
    params, default `int` return) or a `value_declaration_left` (return-type
    annotated `let f (…) : R = …`), then the body expr."""
    kids = defn.named_children
    body = kids[-1] if len(kids) >= 2 else None
    name: str = ""
    params: list[str] = []
    param_ty: dict[str, str] = {}
    ret = _DEFAULT_TYPE
    fdl = next((c for c in kids if c.type == "function_declaration_left"), None)
    vdl = next((c for c in kids if c.type == "value_declaration_left"), None)
    if fdl is not None and body is not None:
        lk = fdl.named_children
        name_node = next((c for c in lk if c.type == "identifier"), None)
        if name_node is None:
            return "// UNSUPPORTED-LET: no name\n"
        name = _text(name_node, src)
        arg_pats = next((c for c in lk if c.type == "argument_patterns"), None)
        if arg_pats is not None:
            for p in arg_pats.named_children:
                if p.type == "long_identifier" and p.named_children:
                    params.append(_text(p.named_children[0], src))
                elif p.type == "typed_pattern":
                    # `(x: int)` — a parameter with a type annotation. The pattern
                    # is `[identifier_pattern, simple_type]`; map the annotated type.
                    ident_pat = next((c for c in p.named_children
                                      if c.type == "identifier_pattern"), None)
                    simple_ty = next((c for c in p.named_children
                                      if c.type in ("simple_type", "compound_type")), None)
                    if ident_pat is None or not ident_pat.named_children:
                        return (f"// UNSUPPORTED-LET: '{name}' typed parameter is "
                                f"not a simple identifier — later item\n")
                    pname = _text(ident_pat.named_children[0], src)
                    params.append(pname)
                    param_ty[pname] = _map_fsharp_type(simple_ty, src)
                elif p.type == "const" and p.named_children \
                        and p.named_children[0].type == "unit":
                    continue  # `()` — the zero-arg marker
                else:
                    return (f"// UNSUPPORTED-LET: '{name}' has a pattern parameter "
                            f"({p.type}) — later item\n")
    elif vdl is not None and body is not None:
        extracted = _extract_value_decl_left(vdl, src)
        if extracted is None:
            return "// UNSUPPORTED-LET: return-annotated form not lowerable\n"
        name, params, param_ty, ret = extracted
    else:
        return "// UNSUPPORTED-LET: not a function definition shape\n"
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
    params_src = ", ".join(
        f"{param_ty.get(p, _DEFAULT_TYPE)} {p}" for p in params)
    # Record support: axon-typed params are field-accessible (`p.x`), and let-bound
    # record literals emit construction statements to _PRELUDE before the return.
    _PRELUDE.clear()
    _AXON_VARS.clear()
    _VTAG_N[0] = 0
    _AH_N[0] = 0
    for p in params:
        if param_ty.get(p) == "Axon":
            _AXON_VARS.add(p)
    body_src = _lower_expr(body, src)
    prelude_src = "".join(_PRELUDE)
    _PRELUDE.clear()
    _AXON_VARS.clear()
    return (f"function {ret} {name}({params_src}) {{\n"
            f"{prelude_src}    return {body_src};\n"
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
    # Prepass: register record type names so `(p: Point)` params type as `Axon` and
    # record literals lower to named-field axons. `type Point = { … }` defs emit no
    # runtime code themselves (they declare the shape).
    _RECORD_TYPES.clear()
    _RECORD_TYPES.update(_record_type_names(tree.root_node, src))
    _VARIANTS.clear()
    _union_type_names, _union_variants = _union_info(tree.root_node, src)
    _RECORD_TYPES.update(_union_type_names)   # DU type names are also Axon-typed
    _VARIANTS.update(_union_variants)

    out = ["// Generated by sutra-from-fsharp. See sdk/sutra-from-fsharp/README.md.\n"]
    for child in tree.root_node.named_children:
        if child.type == "declaration_expression":
            defn = next((c for c in child.named_children
                         if c.type == "function_or_value_defn"), None)
            if defn is not None:
                out.append(_lower_defn(defn, src))
        # record/type defs are registered in the prepass; modules/namespaces are later items
    return "\n".join(out)
