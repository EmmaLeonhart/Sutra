# Axon numeric field reads need a `.real()` projection — and the TS path was silently broken

**Date:** 2026-06-05
**Context:** Building the OCaml records → Sutra axon lowering (`sutra-from-ocaml`),
modeled on the TS `interface` → axon path.

## What was measured

Records lower to Sutra axons: `Axon r; r.add("x", a); …` for construction and
`r.item("x")` for field access (the structural-typing carrier, same as the TS
interface mapping). Running the canonical TS fixture
`sutra-from-ts/tests/fixtures/interface_pass` (`distance_squared(p) = p.x*p.x +
p.y*p.y` with `{x:3, y:4}`, ground truth **25**) on the real substrate via
`sutrac --run`:

- `p.item("x")` (no projection) → the result is a **zero vector**, not 25.
  Arithmetic on the raw axon filler vectors collapses to ~0.
- `p.item("x").real()` (project the number off the axon's number-axis) →
  **25.0**. A single-field read `getx(p) = p.item("x").real()` returns **7.0**
  for `x = 7`.

So axon field reads of **numeric** fields must be decoded with `.real()`; without
it the value is unusable.

## The latent bug this exposed

`interface_pass`'s own `expected.su` comment already hinted at it ("end-to-end the
return value is a vector approximation; a `.real()` projection … would clean it
up"), but the TS fixture harness only ever **compile-tests** (parse → codegen →
Python-syntax) — it never runs the emitted program. So the TS interface → axon
path has been emitting `p.item("x")` (no `.real()`) and **returning zeros at
runtime** without any test catching it. Compile-only testing masked a path that
does not actually work.

## What we did

The OCaml records frontend emits the **correct, substrate-verified** form —
`p.item("x").real()` for numeric field access — and its fixture `record`
(`getx (mk 7 9)`) is checked end-to-end with `sutrac --run` (= 7.0), making it
the first axon path verified to actually run rather than just compile.

The TS frontend should get the same `.real()` fix on its interface field reads,
plus an actually-runs test (not just compile). Tracked in the work queue.

## Scope / open

- Current OCaml records cover **numeric fields** (always `.real()`). Non-numeric
  fields (string / nested-axon) need field-type-aware projection (read the field
  types off the record declaration) — not yet done.
- Record literals only lower in function-body position (axon construction is
  multi-statement); a record literal as a function argument is UNSUPPORTED.
