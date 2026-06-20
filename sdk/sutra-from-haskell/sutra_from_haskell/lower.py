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

# `data` ADTs -> tagged axons (the OCaml/Rust variant pattern). The prepass fills
# `_VARIANTS[constructor] = (type_name, tag, arity)` and `_DATATYPES` (the ADT type
# names, which map to `Axon`). A construction `Lit 7` is statement-shaped (axon
# build), so it is HOISTED to a prelude temp via `_ARG_HOIST[node.id]`, the
# Rust/Elixir/Clojure mechanism. `_AH_COUNTER` numbers temps per body.
_VARIANTS: dict[str, tuple] = {}
_DATATYPES: set = set()
_ARG_HOIST: dict[int, str] = {}
_AH_COUNTER = [0]

# Pattern-equation variable bindings: a clause's variable pattern maps its name
# to the canonical arg slot `_ai` while lowering that clause's body (the OCaml
# `_MATCH_SUBST` / Elixir / Rust shape).
_SUBST: dict[str, str] = {}

# Per-equation destructure prelude: a NESTED `let (a, (b, c)) = t` needs an `Axon` temp
# per non-leaf prefix (chaining `.item()` on a raw tensor fails). The let bind is
# substitution-only, so the temps accumulate here and the equation emitter appends them
# after the hoist prelude. Cleared per equation. (Clojure's `_DESTRUCTURE_PRELUDE` shape.)
_DESTRUCTURE_PRELUDE: list = []
# Monotonic id for naming the int-local prelude of a VARIANT `case` in EXPRESSION
# position (`_c{uid}_vtag` / `_c{uid}_val{i}`), so multiple such cases in one expression
# don't collide. Reset per equation (names only need to be unique within a function).
_CASE_UID: list = [0]


def _text(node, src: bytes) -> str:
    return src[node.start_byte:node.end_byte].decode("utf-8")


def _emit_hs_nested_reads(val_src: str, paths, bound: list) -> None:
    """For each `(path_keys, name)` in `paths`, bind `name` (in `_SUBST`, appending to
    `bound`) to `realvec(<holder>.item("<leaf>"))`, emitting one `Axon` temp per non-leaf
    prefix to `_DESTRUCTURE_PRELUDE` (shared across siblings). Chaining `.item()` on a raw
    tensor fails, so non-leaf hops go through an `Axon` temp. Shared by the nested tuple-
    and constructor-`let`-pattern destructures."""
    prefix_temp = {(): val_src}

    def _temp_for(prefix):
        if prefix in prefix_temp:
            return prefix_temp[prefix]
        parent = _temp_for(prefix[:-1])
        tmp = f"_np{len(_DESTRUCTURE_PRELUDE)}"
        _DESTRUCTURE_PRELUDE.append(f'    Axon {tmp} = {parent}.item("{prefix[-1]}");\n')
        prefix_temp[prefix] = tmp
        return tmp

    for keys, nm in paths:
        holder = _temp_for(keys[:-1])
        _SUBST[nm] = f'realvec({holder}.item("{keys[-1]}"))'
        bound.append(nm)


def _collect_hs_ctor_paths(cpat, src: bytes, prefix: tuple):
    """Flatten a (possibly NESTED, possibly MIXED) constructor pattern `(Ctor p…)` into
    [(path_keys, name), …] over `_val{i}` keys. A `variable` payload is a leaf; a payload
    that is a nested constructor `(Inner a b)` (a `parens`-wrapped `apply`) recurses
    (`(Outer (Inner a b) c)` → `[(("_val0","_val0"),"a"), (("_val0","_val1"),"b"),
    (("_val1",),"c")]`); a payload that is a tuple `(a, b)` recurses via
    `_collect_hs_tuple_paths` (so a ctor wrapping a tuple, `Wrap (a, b)`, mixes). Any other
    payload shape → None. `cpat` is the `apply` spine."""
    chead, pargs = _flatten_apply(cpat, src)
    if chead.type != "constructor" or _text(chead, src) not in _VARIANTS or not pargs:
        return None
    out: list = []
    for i, pv in enumerate(pargs):
        key = f"_val{i}"
        if pv.type == "variable":
            out.append((prefix + (key,), _text(pv, src)))
        else:
            inner = pv
            if inner.type == "parens" and inner.named_children:
                inner = inner.named_children[0]
            if inner.type == "apply":
                sub = _collect_hs_ctor_paths(inner, src, prefix + (key,))
            elif inner.type == "tuple":
                sub = _collect_hs_tuple_paths(inner, src, prefix + (key,))
            else:
                return None
            if sub is None:
                return None
            out.extend(sub)
    return out


def _collect_hs_tuple_paths(tup, src: bytes, prefix: tuple):
    """Flatten a (possibly NESTED, possibly MIXED) Haskell `tuple` pattern into
    [(path_keys, name), …], where `path_keys` is the chain of 0-based positional axon keys
    (`_0`, `_1`, …). A nested `tuple` element recurses (`(a, (b, c))` →
    `[(("_0",),"a"), (("_1","_0"),"b"), (("_1","_1"),"c")]`); a constructor element
    `Box b` (an `apply`, optionally `parens`-wrapped) recurses via `_collect_hs_ctor_paths`
    (so a tuple containing a ctor, `(a, Box b)`, mixes). Any other element → None."""
    out: list = []
    for i, e in enumerate(tup.named_children):
        key = f"_{i}"
        if e.type == "variable":
            out.append((prefix + (key,), _text(e, src)))
        elif e.type == "tuple":
            sub = _collect_hs_tuple_paths(e, src, prefix + (key,))
            if sub is None:
                return None
            out.extend(sub)
        else:
            inner = e
            if inner.type == "parens" and inner.named_children:
                inner = inner.named_children[0]
            if inner.type == "apply":
                sub = _collect_hs_ctor_paths(inner, src, prefix + (key,))
            elif inner.type == "tuple":
                sub = _collect_hs_tuple_paths(inner, src, prefix + (key,))
            else:
                return None
            if sub is None:
                return None
            out.extend(sub)
    return out


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
    if hs_type and hs_type in _DATATYPES:
        return "Axon"  # an ADT value is carried by a tagged axon
    if hs_type:
        t = hs_type.strip()
        if t.startswith("(") and "," in t and t.endswith(")"):
            return "Axon"  # a tuple type `(Int, Int)` is a positional-key axon
    return _TYPE_MAP.get(hs_type, _DEFAULT_TYPE) if hs_type else _DEFAULT_TYPE


def _register_data_types(decls, src: bytes) -> None:
    """Prepass: register `data T = C1 a | C2 b c | …` constructors as variants
    (`_VARIANTS[Ci] = (T, tag, arity)`) and `T` as an ADT type (`_DATATYPES`).
    Arity = the number of field-type children after the constructor name."""
    for child in decls.named_children:
        if child.type != "data_type":
            continue
        name_node = next((c for c in child.named_children if c.type == "name"), None)
        ctors = next((c for c in child.named_children
                      if c.type == "data_constructors"), None)
        if name_node is None or ctors is None:
            continue
        tname = _text(name_node, src)
        _DATATYPES.add(tname)
        tag = 0
        for dc in ctors.named_children:
            if dc.type != "data_constructor":
                continue
            prefix = next((c for c in dc.named_children if c.type == "prefix"), None)
            target = prefix if prefix is not None else dc
            cnode = next((c for c in target.named_children
                          if c.type == "constructor"), None)
            if cnode is None:
                continue
            arity = sum(1 for c in target.named_children if c.type != "constructor")
            _VARIANTS[_text(cnode, src)] = (tname, tag, arity)
            tag += 1


def _construction(node, src: bytes):
    """If `node` builds an ADT value — `apply (constructor C) arg…` or a bare
    nullary `constructor C` — return (variant, [arg_nodes]); else None."""
    if node.type == "constructor" and _text(node, src) in _VARIANTS:
        return _text(node, src), []
    if node.type == "apply":
        head, args = _flatten_apply(node, src)
        if head.type == "constructor" and _text(head, src) in _VARIANTS:
            return _text(head, src), args
    return None


def _emit_construction(variant: str, args, src: bytes, var: str, indent: str) -> str:
    """Tagged-axon construction statements for `variant arg…` bound to `var`
    (the Rust `_emit_enum_construction` shape). Stores `_tag` + `_val0`/`_val1`/…"""
    _tname, tag, _arity = _VARIANTS[variant]
    stmts = f'{indent}Axon {var};\n{indent}{var}.add("_tag", {tag});\n'
    for i, a in enumerate(args):
        stmts += f'{indent}{var}.add("_val{i}", {_lower_expr(a, src)});\n'
    return stmts


def _hoist_constructions(node, src: bytes, indent: str = "    ") -> str:
    """Post-order walk: hoist EVERY ADT VALUE construction to a prelude `Axon
    _ahN; …` group and register `node.id → _ahN` in `_ARG_HOIST` (inner before
    outer). The Rust `_hoist_enum_constructions` shape. Skips `case`-alternative
    PATTERNS (a `Lit n` there is a match pattern, not a value) and the head
    `constructor` of an `apply` (it is part of the application, not a nullary
    value). Returns the prelude string."""
    ctor = _construction(node, src)
    if ctor is not None:
        variant, args = ctor
        prelude = ""
        for a in args:  # recurse into ARGS only — not the head constructor
            prelude += _hoist_constructions(a, src, indent)
        tmp = f"_ah{_AH_COUNTER[0]}"
        _AH_COUNTER[0] += 1
        prelude += _emit_construction(variant, args, src, tmp, indent)
        _ARG_HOIST[node.id] = tmp
        return prelude
    if node.type == "tuple" and node.named_children:
        # A VALUE tuple `(a, b)` -> a positional-key axon (`fst`/`snd` read `_0`/`_1`).
        # Reached only in value position: the body hoist never sees signature (type)
        # tuples, and `case`-alternative tuple PATTERNS are skipped above.
        elems = node.named_children
        prelude = ""
        for el in elems:
            prelude += _hoist_constructions(el, src, indent)
        tmp = f"_ah{_AH_COUNTER[0]}"
        _AH_COUNTER[0] += 1
        prelude += f"{indent}Axon {tmp};\n"
        for i, el in enumerate(elems):
            prelude += f'{indent}{tmp}.add("_{i}", {_lower_expr(el, src)});\n'
        _ARG_HOIST[node.id] = tmp
        return prelude
    if node.type == "bind":
        # A `bind`'s first child is the PATTERN (a `variable` or a `tuple`/
        # constructor destructure) — NOT a value. Only its `match` body (the
        # bound value) can carry hoistable constructions; recursing into the
        # pattern would wrongly hoist a tuple PATTERN `(a, b)` as a value axon.
        prelude = ""
        for m in node.named_children:
            if m.type == "match":
                prelude += _hoist_constructions(m, src, indent)
        return prelude
    if node.type == "case":
        # Recurse into the scrutinee and the alternative BODIES, never the
        # alternative patterns (which are constructor-shaped but not values).
        prelude = ""
        kids = node.named_children
        if kids:
            prelude += _hoist_constructions(kids[0], src, indent)  # scrutinee
        alts = next((c for c in kids if c.type == "alternatives"), None)
        if alts is not None:
            for alt in alts.named_children:
                if alt.type != "alternative":
                    continue
                for m in alt.named_children:
                    if m.type == "match":  # the arm body, not the pattern
                        prelude += _hoist_constructions(m, src, indent)
        return prelude
    prelude = ""
    for child in node.named_children:
        prelude += _hoist_constructions(child, src, indent)
    return prelude


def _lower_case_stmts(node, src: bytes, indent: str = "    ", inline: bool = False):
    """`case scrut of (C x) -> r; …` → (binding statements, result expr), the Rust
    `_lower_match_stmts` shape. Binds `int _vtag = realvec(scrut.item("_tag"))` and
    `int _val{i} = realvec(scrut.item("_val{i}"))` to clean number-vector LOCALS,
    then a nested defuzz blend tests `_vtag == tag`; constructor-payload names
    substitute to the `_val{i}` locals. Last constructor arm is the base; a bare
    `variable`/`_` pattern is also a base. Returns (stmts, expr) or (None, marker).

    `inline=True` (for a VARIANT `case` in EXPRESSION position, which can't emit its own
    statements): the `int _vtag`/`int _val{i}` declarations are HOISTED to the equation's
    `_DESTRUCTURE_PRELUDE` under unique `_c{uid}_…` names (so the `int` type-snap still
    happens — an inline raw `realvec(scrut.item(…))` read is NOT equivalent, measured: it
    skips the snap and the tag/payload compare wrong), and `stmts == ""` is returned. The
    expression references those prelude locals. Nested constructor payloads still need
    `Axon` statement temps, so they stay unsupported in inline mode (UNSUPPORTED marker)."""
    kids = node.named_children
    if not kids or kids[0].type != "variable":
        return None, "/* UNSUPPORTED-CASE: non-variable scrutinee (later item) */"
    scrut_src = _text(kids[0], src)
    # In inline mode the int-locals get unique `_c{uid}_…` names (hoisted to the prelude);
    # at the function tail they keep the plain `_vtag` / `_val{i}` names.
    _pfx = ""
    if inline:
        _pfx = f"_c{_CASE_UID[0]}"
        _CASE_UID[0] += 1
    vtag_ref = f"{_pfx}_vtag" if inline else "_vtag"

    def _val_ref(i: int) -> str:
        return f"{_pfx}_val{i}" if inline else f"_val{i}"
    alts_node = next((c for c in kids if c.type == "alternatives"), None)
    if alts_node is None:
        return None, "/* UNSUPPORTED-CASE: no alternatives */"
    parsed = []
    max_arity = 0
    uses_variant = False
    uses_literal = False
    # NESTED constructor payloads (`Outer (Inner a b) c -> …`) read through an `Axon`
    # temp per non-leaf prefix, emitted into the case prelude (reading from the
    # scrutinee). Shared across arms (a `_np` counter keeps names unique).
    case_axon_temps: list = []
    prefix_temp = {(): scrut_src}

    def _case_axon_temp_for(prefix):
        if prefix in prefix_temp:
            return prefix_temp[prefix]
        parent = _case_axon_temp_for(prefix[:-1])
        tmp = f"_np{len(case_axon_temps)}"
        case_axon_temps.append(
            f'{indent}Axon {tmp} = {parent}.item("{prefix[-1]}");\n')
        prefix_temp[prefix] = tmp
        return tmp

    for alt in alts_node.named_children:
        if alt.type != "alternative":
            continue
        pat = alt.named_children[0]
        body_m = next((c for c in alt.named_children if c.type == "match"), None)
        if body_m is None or not body_m.named_children:
            return None, "/* UNSUPPORTED-CASE: malformed alternative */"
        res = body_m.named_children[-1]
        binds: list[tuple[str, str]] = []
        if pat.type == "apply":
            head, pargs = _flatten_apply(pat, src)
            if head.type != "constructor" or _text(head, src) not in _VARIANTS:
                return None, "/* UNSUPPORTED-CASE: non-variant constructor pattern */"
            tag = _VARIANTS[_text(head, src)][1]
            test = f"({vtag_ref} == {tag})"
            uses_variant = True
            if all(p.type == "variable" for p in pargs):
                max_arity = max(max_arity, len(pargs))
                for i, p in enumerate(pargs):
                    binds.append((_text(p, src), _val_ref(i)))
            else:
                # NESTED ctor payload (`Outer (Inner a b) c`): read each leaf through an
                # `Axon` temp per non-leaf prefix (`_collect_hs_ctor_paths` flattens the
                # whole pattern to `_val{i}` key-paths; the test is still the OUTER tag).
                if inline:
                    # Nested payloads need `Axon` statement temps — not emittable in an
                    # expression slot; leave on the WASM fallback.
                    return None, ("/* UNSUPPORTED-CASE: nested variant payload in "
                                  "expression position (later item) */")
                paths = _collect_hs_ctor_paths(pat, src, ())
                if paths is None:
                    return None, "/* UNSUPPORTED-CASE: non-variable payload pattern */"
                for keys, nm in paths:
                    holder = _case_axon_temp_for(keys[:-1])
                    binds.append((nm, f'realvec({holder}.item("{keys[-1]}"))'))
        elif pat.type == "constructor" and _text(pat, src) in _VARIANTS:
            test = f"({vtag_ref} == {_VARIANTS[_text(pat, src)][1]})"
            uses_variant = True
        elif pat.type == "constructor" and _text(pat, src) in ("True", "False"):
            # Bool literal pattern (`case b of True -> …; False -> …`): test the bool
            # scrutinee directly (`b == true` / `b == false`) — no `_tag` read, the
            # number/literal dispatch shape.
            lit = "true" if _text(pat, src) == "True" else "false"
            test = f"({scrut_src} == {lit})"
            uses_literal = True
        elif pat.type == "literal":
            # Integer/float literal pattern (`case n of 0 -> …`): dispatch the
            # scrutinee value DIRECTLY — the Clojure/Elixir `case` equality-blend
            # shape — not via a variant `_tag`. scrut is a plain number here.
            test = f"({scrut_src} == {_lower_expr(pat, src)})"
            uses_literal = True
        elif pat.type in ("variable", "wildcard"):  # `_` or catch-all name — base
            test = None
            # A named catch-all binds the scrutinee value (`m -> m+1` ⇒ m = scrut).
            if pat.type == "variable":
                binds.append((_text(pat, src), scrut_src))
        else:
            return None, f"/* UNSUPPORTED-CASE: pattern {pat.type} */"
        for nm, sub in binds:
            _SUBST[nm] = sub
        try:
            res_src = _lower_expr(res, src)
        finally:
            for nm, _sub in binds:
                _SUBST.pop(nm, None)
        parsed.append((test, res_src))
    if not parsed:
        return None, "/* UNSUPPORTED-CASE: no arms */"
    if uses_variant and uses_literal:
        # A scrutinee is either an ADT or a number, never both — mixing is
        # ill-typed; surface it rather than emit a half-variant blend.
        return None, "/* UNSUPPORTED-CASE: mixed variant + literal patterns */"
    # The `_tag`/`_val` locals are only meaningful for variant scrutinees; a
    # literal/number case dispatches the scrutinee directly with no prelude.
    stmts = ""
    if uses_variant:
        decls = f'{indent}int {vtag_ref} = realvec({scrut_src}.item("_tag"));\n'
        for i in range(max_arity):
            decls += f'{indent}int {_val_ref(i)} = realvec({scrut_src}.item("_val{i}"));\n'
        decls += "".join(case_axon_temps)   # NESTED-payload `Axon` temps (read from scrut)
        if inline:
            # Hoist to the equation prelude (flushed before the return) — an expression
            # slot can't carry the declarations itself.
            _DESTRUCTURE_PRELUDE.append(decls)
        else:
            stmts = decls
    expr = parsed[-1][1]  # last arm = base (exhaustive ADT match / catch-all)
    for test, res in reversed(parsed[:-1]):
        expr = res if test is None else _blend(test, res, expr)
    return stmts, expr


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
    if _ARG_HOIST and node.id in _ARG_HOIST:
        return _ARG_HOIST[node.id]  # a hoisted ADT construction — emit its temp
    t = node.type
    if t == "constructor" and _text(node, src) in ("True", "False"):
        # Bool literal value `True`/`False` → the Sutra `true`/`false` literal.
        return "true" if _text(node, src) == "True" else "false"
    if t == "constructor" and _text(node, src) in _VARIANTS:
        # A construction reaching here was not hoisted — surface the gap.
        return "/* UNSUPPORTED-CONSTRUCTION: ADT value outside a hoistable position */"
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
        hname = _text(head, src).strip()
        # `fst t` / `snd t` — pair accessors → the positional axon fields _0 / _1.
        if hname in ("fst", "snd") and len(args) == 1:
            field = "_0" if hname == "fst" else "_1"
            return f'realvec({_lower_expr(args[0], src)}.item("{field}"))'
        arg_srcs = [_lower_expr(a, src) for a in args]
        return f"{hname}({', '.join(arg_srcs)})"
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
    if t == "case":
        # `case` in NON-TAIL expression position (`1 + (case n of 0 -> 100; _ -> 200)`).
        # A LITERAL/wildcard case is a pure nested blend (`_lower_case_stmts` returns no
        # prelude — a plain-number scrutinee `n == 0` is crisp), so it inlines. A VARIANT
        # case is lowered in INLINE mode: the `_tag`/`_val{i}` reads splice in as
        # `realvec(scrut.item(…))` directly, so no `int _vtag` prelude is needed and the
        # whole case is one pure expression. Nested-payload variant cases still need
        # statement temps and stay on the fallback (an UNSUPPORTED-CASE marker).
        stmts, expr = _lower_case_stmts(node, src, inline=True)
        if stmts is None:
            return expr  # an UNSUPPORTED-CASE marker
        return f"({expr})"
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


def _conditional_parts(body, src: bytes):
    """A Haskell `if COND then THEN else ELSE` (`conditional`) → (cond, then_e,
    else_e) nodes, else None. Factored out so both the if-based recursion path and
    the synthesized multi-equation path feed the transforms uniformly."""
    if body.type != "conditional" or len(body.named_children) < 3:
        return None
    return body.named_children[0], body.named_children[1], body.named_children[2]


def _try_lower_tail_recursive(name: str, params, ret: str, cond_src, neg_src,
                              then_e, else_e, src: bytes):
    """Lower a TAIL-recursive equation `f p… = if COND then BASE else f a…` to a
    declared Sutra `while_loop` (the OCaml/Scala/F#/Rust shape ported). `cond_src`/
    `neg_src` are the lowered base-match test + negation (strings, so a multi-equation
    head can synthesize them); `params` is a list of (name, type). Returns Sutra or
    None."""
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
# Identity element for seeding a non-tail fold accumulator (both `_FOLD_OPS` ops are
# commutative + associative with a known identity, so a post-loop `acc OP base` combine
# reproduces the call-stack order).
_FOLD_IDENTITY = {"+": "0", "*": "1"}


def _foldable_step_multi(node, name: str, arity: int, src: bytes):
    """`LEAF <OP> f a1 … aN` (or the self-call on the left), OP in `_FOLD_OPS`, the call
    at arity N: return `(op_text, leaf_node, [rec_arg_nodes])` — the full recursion arg
    list, for the MULTI-arg / multibase non-tail fold path. Else None."""
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
    lc = _self_call_args(operands[0], name, arity, src)
    rc = _self_call_args(operands[1], name, arity, src)
    if (lc is None) == (rc is None):
        return None
    return (op_text, operands[1], lc) if lc is not None else (op_text, operands[0], rc)


def _contains_variable(node, ident: str, src: bytes) -> bool:
    if node.type == "variable" and _text(node, src) == ident:
        return True
    return any(_contains_variable(c, ident, src) for c in node.named_children)


def _try_lower_foldable_nontail(name: str, params, ret: str, cond_src, neg_src,
                                then_e, else_e, src: bytes):
    """CPS / accumulator transform for a FOLDABLE non-tail equation
    `f n = if COND then BASE else LEAF <OP> f REC` (single param, OP in
    `_FOLD_OPS`): the pending call-stack work is reified as an accumulator carried
    by a Sutra `while_loop` trampoline — the OCaml/Scala/Rust shape ported. BASE is
    evaluated pre-loop at the INITIAL param, so a param-dependent BASE is rejected
    (→ None). `cond_src`/`neg_src` are the lowered base-match test + negation
    (strings). Returns loop decl + function, or None."""
    if len(params) != 1:
        return None

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
        cont = neg_src
        op_text, leaf, rec_arg = fold_else
        base = then_e
    else:
        cont = cond_src
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


def _collect_var_names(node, src: bytes, out: set) -> None:
    """Collect every `variable` identifier text in a subtree (for the dependency scan)."""
    if node is None:
        return
    if node.type == "variable":
        out.add(_text(node, src))
    for c in node.named_children:
        _collect_var_names(c, src, out)


def _bind_defines(b, src: bytes) -> set:
    """The name(s) a `bind` introduces — from its PATTERN (first child), not its value.
    Simple `a = …` → {a}; destructure `(a,b) = t` / `(Wrap a b) = w` → the pattern vars."""
    names: set = set()
    first = b.named_children[0] if b.named_children else None
    if first is not None and first.type in ("tuple", "parens", "apply"):
        _collect_var_names(first, src, names)
    else:
        nm = next((c for c in b.named_children if c.type == "variable"), None)
        if nm is not None:
            names.add(_text(nm, src))
    return names


def _order_binds(binds: list, src: bytes) -> list:
    """Dependency-order a `where`/`let` group so each bind is lowered AFTER the local
    binds whose names it references — the substitution is single-level, so a forward
    (out-of-order) reference would otherwise leak the referenced name as a bare
    identifier (finding: forward `where` reference). Acyclic forward references are
    handled here; a true mutual-recursion CYCLE makes no progress and the remaining
    binds keep source order (it stays on the WASM fallback — laziness/fixpoint is out
    of scope, not faked)."""
    defs = [_bind_defines(b, src) for b in binds]
    all_local: set = set().union(*defs) if defs else set()
    uses = []
    for i, b in enumerate(binds):
        u: set = set()
        _collect_var_names(_match_body(b, src), src, u)
        uses.append((u & all_local) - defs[i])
    ordered, emitted, remaining = [], set(), list(range(len(binds)))
    progress = True
    while remaining and progress:
        progress, still = False, []
        for i in remaining:
            if uses[i] <= emitted:
                ordered.append(binds[i]); emitted |= defs[i]; progress = True
            else:
                still.append(i)
        remaining = still
    ordered.extend(binds[i] for i in remaining)  # cycle: keep source order
    return ordered


def _apply_local_binds(local_binds, src: bytes) -> list[str]:
    """Add each `bind` in a `local_binds` node (a `where` clause or `let` group) to
    `_SUBST` as name → its parenthesised lowered value. Binds are dependency-ordered
    (`_order_binds`) so a later binding sees the earlier ones — including FORWARD
    (out-of-order) references within the group (the OCaml `let..in` / Clojure `let`
    shape; numbers, so re-evaluating a substituted value is side-effect-free). A true
    mutual-recursion cycle stays on the WASM fallback. Returns the bound names (for
    cleanup by the caller)."""
    bound: list[str] = []
    for b in _order_binds([b for b in local_binds.named_children if b.type == "bind"], src):
        if b.type != "bind":
            continue
        first = b.named_children[0] if b.named_children else None
        if first is not None and first.type == "tuple":
            # `(a, b) = t` — tuple-pattern destructure: each element reads the positional
            # axon field of the bound value via `realvec` (the same projection `fst`/`snd`
            # use). NESTED patterns (`(a, (b, c)) = t`) read through an `Axon` temp per
            # non-leaf prefix (appended to `_DESTRUCTURE_PRELUDE`) — chaining `.item()` on
            # a raw tensor fails.
            paths = _collect_hs_tuple_paths(first, src, ())
            val = _match_body(b, src)
            if paths is None or val is None:
                continue
            val_src = _lower_expr(val, src)
            # The bound value must be a bare name (a variable, or a hoisted tuple temp);
            # `name.item(...)` is the axon-method form the compiler dispatches.
            if not val_src.isidentifier():
                continue
            _emit_hs_nested_reads(val_src, paths, bound)
            continue
        # `(Ctor a b) = w` — single-constructor ADT destructure: each payload variable
        # reads the tagged-axon field `realvec(w.item("_val{i}"))` (the `case`-arm
        # payload-bind shape). NESTED constructor patterns (`(Outer (Inner a b) c) = w`)
        # read through an `Axon` temp per non-leaf prefix. The pattern is a `parens`
        # wrapping the constructor `apply` spine.
        cpat = first
        if cpat is not None and cpat.type == "parens" and cpat.named_children:
            cpat = cpat.named_children[0]
        if cpat is not None and cpat.type == "apply":
            cpaths = _collect_hs_ctor_paths(cpat, src, ())
            if cpaths is not None:
                val = _match_body(b, src)
                val_src = _lower_expr(val, src) if val is not None else ""
                if val is not None and val_src.isidentifier():
                    _emit_hs_nested_reads(val_src, cpaths, bound)
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


def _is_int_literal_pat(p) -> bool:
    """A Haskell integer-literal pattern `0` is a `literal` wrapping an `integer`."""
    return (p.type == "literal" and bool(p.named_children)
            and p.named_children[0].type == "integer")


def _try_lower_multiclause_recursion(name: str, clauses, src: bytes):
    """The idiomatic equation-matched recursion `f 0 = BASE` + `f n = … f (n-1)`
    (and the multi-arg accumulator form `sum 0 acc = acc; sum n acc = sum (n-1)
    (acc+n)`) is semantically identical to the single-clause `if`-form, so synthesize
    the base-match condition `(V == K)` from the equation patterns and reuse the
    recursion transforms (fed source strings). Scope: exactly 2 same-arity equations —
    a BASE equation with exactly one INTEGER-literal pattern (rest variables) and no
    self-call, and a recursive equation with ALL VARIABLE patterns and a self-call.
    The recursive equation's names are the synthesized params; the base equation's
    variable patterns are renamed to them by position (via `_SUBST`). `clauses` is the
    `[(pattern_nodes, body), …]` list. Returns Sutra or None."""
    if len(clauses) != 2:
        return None
    arity = len(clauses[0][0])
    if arity == 0 or any(len(pn) != arity for pn, _b in clauses):
        return None
    base = rec = None
    for pn, body in clauses:
        if (any(_is_int_literal_pat(p) for p in pn)
                and not _contains_self_call(body, name, src)):
            base = (pn, body)
        elif (all(p.type == "variable" for p in pn)
                and _contains_self_call(body, name, src)):
            rec = (pn, body)
    if base is None or rec is None:
        return None
    base_pats, then_e = base
    rec_pats, else_e = rec
    lit_positions = [i for i, p in enumerate(base_pats) if _is_int_literal_pat(p)]
    if len(lit_positions) != 1:
        return None
    li = lit_positions[0]
    if any(base_pats[i].type != "variable" for i in range(arity) if i != li):
        return None
    rec_names = [_text(p, src) for p in rec_pats]
    k = _text(base_pats[li].named_children[0], src)
    v = rec_names[li]
    ptypes, ret = _resolve_types(name, arity)
    typed_params = list(zip(rec_names, ptypes))
    cond_src, neg_src = f"({v} == {k})", f"({v} != {k})"
    renames: list = []
    for i in range(arity):
        if i == li:
            continue
        bn = _text(base_pats[i], src)
        if bn != rec_names[i]:
            _SUBST[bn] = rec_names[i]
            renames.append(bn)
    try:
        out = _try_lower_tail_recursive(name, typed_params, ret, cond_src, neg_src,
                                        then_e, else_e, src)
        if out is None:
            out = _try_lower_foldable_nontail(name, typed_params, ret, cond_src,
                                              neg_src, then_e, else_e, src)
    finally:
        for bn in renames:
            _SUBST.pop(bn, None)
    return out


def _try_lower_guarded_recursion(name: str, typed_params, ret: str, matches, src: bytes):
    """A guarded recursive equation `f n | n == 0 = BASE | otherwise = … f (n-1)`
    is the `if`-form with the condition stated explicitly in the guard, so lower the
    cond-guard's condition directly and reuse the recursion transforms. Scope: exactly
    2 single-condition guards — a real-condition guard whose result has no self-call,
    and an `otherwise` guard whose result has the self-call. (The params are real
    Sutra params, so guard/body exprs reference them directly.) Returns Sutra or None."""
    if len(matches) != 2:
        return None

    def guard_parts(m):
        guards = next((c for c in m.named_children if c.type == "guards"), None)
        if guards is None or not m.named_children:
            return None
        conds = [c for c in guards.named_children if c.type == "boolean"]
        if len(conds) != 1 or not conds[0].named_children:
            return None
        return conds[0].named_children[0], m.named_children[-1]  # (cond_inner, result)

    parts = [guard_parts(m) for m in matches]
    if any(p is None for p in parts):
        return None
    # One non-recursive BASE guard + one recursive guard. The recursive guard may
    # be `otherwise` OR an explicit condition (`| n > 0 = f …`). The base guard is
    # always an explicit condition.
    base_m = rec_m = None
    for inner, result in parts:
        is_otherwise = inner.type == "variable" and _text(inner, src) == "otherwise"
        if _contains_self_call(result, name, src):
            rec_m = (None if is_otherwise else inner, result)  # cond None ⇒ otherwise
        elif not is_otherwise:
            base_m = (inner, result)
    if base_m is None or rec_m is None:
        return None
    cond_node, then_e = base_m  # base (non-recursive): condition + result
    rec_cond, else_e = rec_m    # recursive: result, + explicit cond or None (otherwise)
    if rec_cond is None:
        # Recursive = `otherwise`: continue while NOT the base condition.
        cond_src = _lower_expr(cond_node, src)
        neg_src = _negate_cond(cond_node, src)
    else:
        # Explicit recursive condition (`| n > 0 = f …`): continue = that condition.
        # `_try_lower_tail_recursive`/`_try_lower_foldable_nontail` take then_e=base,
        # else_e=rec, so the recursive branch is `else` and the continue is `neg_src`
        # — feed the recursive condition there (cond_src is unused for an else-recursive
        # call but must be non-UNSUPPORTED). Strict `<`/`>` halt crisply at the
        # boundary (tie → heaviside 0); the base guard matches at exit.
        cond_src = _negate_cond(rec_cond, src)
        neg_src = _lower_expr(rec_cond, src)
    if "UNSUPPORTED" in cond_src or "UNSUPPORTED" in neg_src:
        return None
    rec = _try_lower_tail_recursive(name, typed_params, ret, cond_src, neg_src,
                                    then_e, else_e, src)
    if rec is not None:
        return rec
    return _try_lower_foldable_nontail(name, typed_params, ret, cond_src, neg_src,
                                       then_e, else_e, src)


def _try_lower_multibase_tail_recursion(name: str, typed_params, ret: str, matches, src: bytes):
    """N >= 2 non-recursive base guards (each a SINGLE comparison) + one `otherwise`
    guard whose result is a TAIL self-call:

        f n acc | n <= 0 = acc | n == 1 = acc+100 | otherwise = f (n-1) (acc+n)

    lowers to a `while_loop` whose continue is the `&&` of the NEGATED base
    conditions — the substrate compound halt (§0.3, 2026-06-18, which made a
    compound `&&`/`||` halt and equality halts actually fire); the body is the
    recursive step; and the post-loop value is a nested defuzz-blend of the base
    RHSs keyed by their conditions, evaluated on the FINAL loop state (at exit the
    continue is false, so exactly one base condition holds). The 2-guard case
    (one base + one `otherwise`) is the existing `_try_lower_guarded_recursion`;
    this is the >2-guard generalisation. Scope (anything else → None, a later
    item): single-comparison base guards (so each negates cleanly); the recursive
    guard is a TAIL call whose guard is `otherwise` (continue = `&&` of negated
    bases) OR an explicit condition (continue = that condition). Returns Sutra/None.

    Caveat — base conditions should be CRISP at their boundary. Equality bases
    (`n == 0`, `n == 1`) are crisp (§0.3 made `==`/`!=` halts crisp), and a strict
    `<`/`>` away from its boundary is fine. A `<=`/`>=` base is correct in the
    loop's *continue* (the tie rounds to halt via heaviside) but reads as a
    half-blend in the *post-loop value* at its exact boundary — the pre-existing
    `<=` boundary-fuzziness limitation (finding 2026-06-13-while-loop-le-boundary-
    equality-defuzz), orthogonal to this transform. Use `==` for an exact base."""
    if len(matches) <= 2:
        return None  # 0/1 base is the existing 2-guard path
    arity = len(typed_params)
    bases: list = []   # (cond_inner_node, result_node) — explicit-condition bases
    rec_result = None
    rec_cond = None    # the recursive guard's explicit condition node, or None (otherwise)
    for m in matches:
        guards = next((c for c in m.named_children if c.type == "guards"), None)
        if guards is None or not m.named_children:
            return None
        conds = [c for c in guards.named_children if c.type == "boolean"]
        if len(conds) != 1 or not conds[0].named_children:
            return None  # compound/zero guard — out of scope
        inner = conds[0].named_children[0]
        result = m.named_children[-1]
        is_otherwise = inner.type == "variable" and _text(inner, src) == "otherwise"
        has_rec = _contains_self_call(result, name, src)
        if has_rec:
            # The single recursive step — its guard may be `otherwise` OR an
            # explicit condition (`| n > 1 = f …`).
            if rec_result is not None:
                return None
            rec_result = result
            rec_cond = None if is_otherwise else inner
        elif not is_otherwise:
            bases.append((inner, result))
        else:
            return None  # an `otherwise` base with no recursion is not this shape
    if rec_result is None or len(bases) < 2:
        return None
    rec_args = _self_call_args(rec_result, name, arity, src)
    # A TAIL recursive guard → accumulator loop (`rec_args` are the next-state values).
    # A NON-tail recursive guard (`a + f (a-1) b`) → CPS fold: carry every recursion arg
    # plus a synthetic `_acc`, fold the leaf each step, post-combine `_acc OP base_blend`
    # keyed on the FINAL state (the base the recursion bottoms out at — the seed select).
    fold_step = None
    if rec_args is None:
        fold_step = _foldable_step_multi(rec_result, name, arity, src)
        if fold_step is None:
            return None  # non-tail but not a foldable step — later item
    # Continue condition: an explicit recursive guard IS the continue
    # (`| n > 1 = f …` → continue while `n > 1`); an `otherwise` recursive guard
    # continues while NO base matches (the `&&` of the negated base conditions).
    if rec_cond is not None:
        cont = _lower_expr(rec_cond, src)
        if "UNSUPPORTED" in cont:
            return None
    else:
        neg_terms: list = []
        for cond_inner, _r in bases:
            neg = _negate_cond(cond_inner, src)
            if "UNSUPPORTED" in neg:
                return None
            neg_terms.append(f"({neg})")
        cont = " && ".join(neg_terms)
    # Post-loop value: nested blend of base RHSs keyed by their conditions on the
    # final state, in source order. The last base is the bare `else` (at loop exit
    # exactly one base condition holds, so if no earlier one matched the last does).
    rendered: list = []
    for cond_inner, result in bases:
        csrc = _lower_expr(cond_inner, src)
        rsrc = _lower_expr(result, src)
        if "UNSUPPORTED" in csrc or "UNSUPPORTED" in rsrc:
            return None
        rendered.append((csrc, rsrc))
    base_src = rendered[-1][1]
    for csrc, rsrc in reversed(rendered[:-1]):
        base_src = _blend(csrc, rsrc, base_src)
    # Emit — the `_try_lower_tail_recursive` shape, multibase continue + base.
    loop_name = f"_rec_{name}"
    state_decls = ", ".join(f"{ty} {nm} = 0" for nm, ty in typed_params)
    slot_lines = "".join(f"    slot {ty} _{nm}_r = {nm};\n" for nm, ty in typed_params)
    slot_args = ", ".join(f"_{nm}_r" for nm, _ty in typed_params)
    writeback = "".join(f"    {nm} = _{nm}_r;\n" for nm, _ty in typed_params)
    params_src = ", ".join(f"{ty} {nm}" for nm, ty in typed_params)
    if fold_step is not None:
        # NON-tail multibase fold: carry every recursion arg AND a synthetic `_acc`.
        op_text, leaf, rec_arg_nodes = fold_step
        sutra_op = _OP_MAP.get(op_text, op_text)
        identity = _FOLD_IDENTITY[op_text]
        leaf_src = _lower_expr(leaf, src)
        rec_srcs = [_lower_expr(a, src) for a in rec_arg_nodes]
        if "UNSUPPORTED" in leaf_src or any("UNSUPPORTED" in s for s in rec_srcs):
            return None
        temp_decls = "".join(f"    {ty} _t{i} = {rec_srcs[i]};\n"
                             for i, (_nm, ty) in enumerate(typed_params))
        assigns = "".join(f"    {nm} = _t{i};\n" for i, (nm, _ty) in enumerate(typed_params))
        loop_decl = (
            f"while_loop {loop_name}({cont}, {state_decls}, {ret} _acc = 0) {{\n"
            f"{temp_decls}"
            f"    {ret} _t_acc = _acc {sutra_op} {leaf_src};\n"
            f"{assigns}"
            f"    _acc = _t_acc;\n"
            f"}}\n"
        )
        fn = (
            f"function {ret} {name}({params_src}) {{\n"
            f"    {ret} _acc = {identity};\n"
            f"{slot_lines}"
            f"    slot {ret} _acc_r = _acc;\n"
            f"    loop {loop_name}({cont}, {slot_args}, _acc_r);\n"
            f"{writeback}"
            f"    return _acc_r {sutra_op} {base_src};\n"
            f"}}\n"
        )
        return loop_decl + fn
    temp_decls = "".join(f"    {ty} _t{i} = {_lower_expr(arg, src)};\n"
                         for i, ((_nm, ty), arg) in enumerate(zip(typed_params, rec_args)))
    assigns = "".join(f"    {nm} = _t{i};\n" for i, (nm, _ty) in enumerate(typed_params))
    loop_decl = (f"while_loop {loop_name}({cont}, {state_decls}) "
                 f"{{\n{temp_decls}{assigns}}}\n")
    fn = (
        f"function {ret} {name}({params_src}) {{\n"
        f"{slot_lines}"
        f"    loop {loop_name}({cont}, {slot_args});\n"
        f"{writeback}"
        f"    return {base_src};\n"
        f"}}\n"
    )
    return loop_decl + fn


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
    multi_rec = _try_lower_multiclause_recursion(name, clauses, src)
    if multi_rec is not None:
        return multi_rec
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
            if params:
                grec = _try_lower_guarded_recursion(
                    name, list(zip(params, ptypes)), ret, matches, src)
                if grec is not None:
                    return grec
                mrec = _try_lower_multibase_tail_recursion(
                    name, list(zip(params, ptypes)), ret, matches, src)
                if mrec is not None:
                    return mrec
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
        cparts = _conditional_parts(body, src) if params else None
        if cparts is not None:
            cond, then_e, else_e = cparts
            cond_src = _lower_expr(cond, src)
            neg_src = _negate_cond(cond, src)
            rec = _try_lower_tail_recursive(name, typed_params, ret, cond_src,
                                            neg_src, then_e, else_e, src)
            if rec is not None:
                return rec
            fold = _try_lower_foldable_nontail(name, typed_params, ret, cond_src,
                                               neg_src, then_e, else_e, src)
            if fold is not None:
                return fold
        if _contains_self_call(body, name, src):
            # Recursion outside the supported tail/foldable shapes — a plain
            # self-call would not terminate through the fuzzy-if blend. Surface it.
            return (f"// UNSUPPORTED-RECURSION: '{name}' is recursive but not the "
                    f"tail-accumulator or foldable non-tail shape\n")
        params_src = ", ".join(f"{ty} {nm}" for ty, nm in zip(ptypes, params))
        # ADTs -> tagged axons: hoist any constructions in the body to prelude
        # temps, then lower. A `case` body lowers to binding statements + a nested
        # blend (the Rust match-at-tail shape).
        _ARG_HOIST.clear()
        _DESTRUCTURE_PRELUDE.clear()
        _CASE_UID[0] = 0  # unique case-prelude names start fresh per equation
        prelude = _hoist_constructions(body, src)
        if body.type == "case":
            case_stmts, case_expr = _lower_case_stmts(body, src)
            if case_stmts is None:
                _ARG_HOIST.clear()
                return f"// UNSUPPORTED-DECL: '{name}' {case_expr}\n"
            _ARG_HOIST.clear()
            return (f"function {ret} {name}({params_src}) {{\n"
                    f"{prelude}{case_stmts}"
                    f"    return {case_expr};\n"
                    f"}}\n")
        body_src = _lower_expr(body, src)
        # NESTED-destructure `Axon` temps (e.g. `let (a, (b, c)) = t`) emitted during
        # lowering, after the hoist prelude (they may read a hoisted tuple) and before the
        # return.
        destr_prelude = "".join(_DESTRUCTURE_PRELUDE)
        _ARG_HOIST.clear()
        _DESTRUCTURE_PRELUDE.clear()
        return (f"function {ret} {name}({params_src}) {{\n"
                f"{prelude}"
                f"{destr_prelude}"
                f"    return {body_src};\n"
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

    # Prepass: signatures supply the types for their equations; `data` decls
    # register their constructors as tagged-axon variants.
    _SIGNATURES.clear()
    _SUBST.clear()
    _VARIANTS.clear()
    _DATATYPES.clear()
    _ARG_HOIST.clear()
    _AH_COUNTER[0] = 0
    _register_data_types(decls, src)
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
