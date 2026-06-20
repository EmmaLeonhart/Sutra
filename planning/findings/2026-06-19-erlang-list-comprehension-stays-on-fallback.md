# Erlang list comprehensions stay on the WASM fallback (2026-06-19)

**Status:** assessed — STAYS on the WASM fallback. Negative/blocked result (integrity rule #4).
**Branch:** `wasm-fallback-edge-cases-native` (Emma's edge-case-clearing pass over
`planning/wasm-fallback-edge-cases.md`).

## What was attempted

The edge-case catalogue listed Erlang list comprehensions (`[ X*2 || X <- L ]`) as the last open
Elixir/Erlang frontend item, with the note "needs a list abstraction the substrate lacks." Lowering
a comprehension today emits `UNSUPPORTED-EXPR: list_comprehension`.

## What the substrate actually has (the note was wrong)

The premise is partly incorrect. The substrate **does** have a list abstraction — Sutra
*binding-arrays* (`docs/loops.md`, `planning/sutra-spec/control-flow.md`): `arr[0]` is the length,
`arr[1..length]` the elements. The wired primitives:

- `array_from_literal(*values)` — construct a fixed-size array from compile-time-known element exprs
  (`codegen_pytorch.py`; `codegen_base.py` routes array literals through it).
- `array_get(arr, i)`, `array_length(arr)` — read ops.
- `foreach_loop NAME(arr, state…)` — walk a binding-array, body sees `element` per tick.

The TS transpiler already uses these for array handling.

## Why it still stays on the fallback

1. **Runtime-list comprehension** (`f(L) -> [X*2 || X <- L]`, `L` a parameter): building the RESULT
   list needs an `array_map` / append / set primitive. None exists — only `array_from_literal`
   (compile-time elements). `foreach_loop` can *reduce* a binding-array to a scalar accumulator, but
   it cannot *build a new list* of the same length. Genuinely blocked on a missing builder primitive.

2. **Compile-time-literal-list comprehension** (`[X*2 || X <- [1,2,3]]`): the elements are known, so
   this could unroll to `array_from_literal(1*2, 2*2, 3*2)`. But the result is a list value, and
   Sutra has **no readout** — to verify RUN == ground truth the program must reduce to a scalar, which
   needs a list-consumer (`lists:sum` / `hd` / `lists:nth`). None of those are wired in the Erlang
   frontend. Per the integrity rules, an untested list-valued lowering cannot be claimed as working,
   so there is nothing to ship that is verifiable end-to-end.

## Re-attempt condition

Pick this up only when there is either:
- (a) an array-builder primitive (`array_map` / append) for the runtime-list case, **or**
- (b) a concrete `lists:*` reducer consumer wired in the Erlang frontend so a compile-time-literal
  comprehension has a RUN==ground-truth scalar path.

Until then it correctly rides the tier-5 WASM fallback (covers correctness).
