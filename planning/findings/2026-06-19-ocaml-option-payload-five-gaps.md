# OCaml `option`/variant payload support — the five precise gaps

**Date:** 2026-06-19
**Status:** root-caused, NOT fixed — stays on the tier-5 WASM fallback (a substantial
rework, not a few-cycles edge case; logged so a future dedicated session starts from
the precise gaps rather than the catalogue's vague "2-sided rework").

## Symptom

`Some <payload>` does not work end-to-end in `sutra-from-ocaml` (the reference
frontend), for either a scalar payload (`Some 5`) or an aggregate payload
(`Some { x; y }`). User-defined parameterised variants DO work (`Circle of int`;
`area (Circle 4)` RUN-passes) — they go through the `_VARIANT_CTORS` tagged-axon path.
The built-in `option` type is half-wired to that path.

## The five gaps (measured 2026-06-19)

1. **Option-matched param is typed `int`, not `Axon`.** `let f s = match s with Some v
   -> … | None -> …` emits `function int f(int s) { int _otag = realvec(s.item("_tag")); … }`.
   `s.item("_tag")` then fails (`TensorBase.item() takes no arguments`) because `s` is an
   int-typed tensor, not an Axon. User axon-variant params get `Axon` because the type
   constructor is added to `record_types` (lower.py ~2283); built-in `option` has no
   `type_binding`, so an unannotated option-matched param is never typed `Axon`. Fix: infer
   "param is the scrutinee of an option/variant match" → type it `Axon`.

2. **Arg-position option construction is not hoisted.** `_aggregate_arg_emitter`
   (lower.py ~1224) emits hoist code for `record_expression`, `tuple_expression`, and
   `_variant_value_kind` (user variants), but NOT `_option_kind`. So `f (Some 5)` falls
   through to `_lower_expression` → `constructor_path` → "only nullary variants lower".
   Fix: add an `_option_kind` branch that emits the `{_tag,_val}` construction into the temp
   (mirror `_lower_option_body` minus the `return`).

3. **Unit-arg call `mk ()` → `UNSUPPORTED-EXPR: unit`.** Calling a unit-param function as
   `f (mk ())` lowers the inner `mk ()`'s `()` argument to UNSUPPORTED. (Separate small gap,
   surfaced while testing body-position construction.)

4. **Aggregate payload descent (the catalogue item).** `Some { x; y }` needs `_val` to be a
   NESTED axon (the record), and the match arm `Some { x; y } -> …` must descend it to bind
   `x`/`y` — like the variant-`let` aggregate descent, but on the option/variant MATCH path.
   `_lower_option_body` currently lowers `_val` as a single scalar expression.

5. **`.real()` in `_lower_option_body` docstring (lower.py ~1317).** "MVP: numeric Some
   payloads (read via `.real()`)" — `.real()` is a removed NO-introspection accessor. Any
   reliance on it is a substrate-purity violation to excise during the rework.

## Why it is not a few-cycles fix

The gaps interlock: you cannot RUN-verify gap 2 (construction) without gap 1 (param typing)
+ the match read; the aggregate case (gap 4) needs both plus nested descent; gap 5 must be
removed not preserved. That is five coordinated edits + an emitter + fixtures across the
construction path, the match path, the param-typer, and the arg-hoist — a deliberate session,
not a work-loop tick. Until then the construct runs via the WASM fallback. The `.item()`-on-a-
call-result limit (finding `2026-06-18-axon-item-on-call-result-not-supported.md`) compounds
it for any inline field read off an option-returning call.
