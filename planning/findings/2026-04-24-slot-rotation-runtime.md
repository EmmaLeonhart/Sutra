# 2D-Givens-per-slot rotation binding — runtime landing

**Date:** 2026-04-24.
**Script:** `experiments/slot_rotation_reversibility.py`.
**Design:**
`planning/findings/2026-04-21-extended-state-and-rotation-binding.md`.
**Reference-impl validation:**
`planning/findings/2026-04-24-synthetic-subspace-validation.md`.

## What landed

Three runtime methods added to `_VSA` in
`sdk/sutra-compiler/sutra_compiler/codegen.py`, generated in every
compiled Sutra module:

| method | signature | purpose |
|--------|-----------|---------|
| `slot_store` | `(state, slot_idx, scalar) -> state'` | Assign scalar to slot's 2D plane (real leg); zero imaginary leg. Overwrites prior slot content. |
| `slot_load`  | `(state, slot_idx) -> float` | Read scalar from slot's real leg. |
| `rotate_slot`| `(state, slot_idx, angle) -> state'` | 2D Givens rotation by `angle` within the slot's plane. Inverse = same call with `-angle`. |

Layout: each slot is a disjoint 2D plane in the synthetic block,
starting at `semantic_dim + SLOT_BASE` with `SLOT_BASE = 4` (past
AXIS_REAL, AXIS_IMAG, AXIS_TRUTH, AXIS_CHAR_FLAG). Slot `s` occupies
synthetic indices `SLOT_BASE + 2s` and `SLOT_BASE + 2s + 1`. With
the current `synthetic_dim = 100`, the runtime supports **48 disjoint
slots** before wrap-around.

## Test results (on the compiled runtime, not a reference reimpl)

Ran against the actual compiled `_VSA` loaded from `hello_world.su`:

| test | measurement | threshold | verdict |
|------|-------------|-----------|---------|
| Slot independence (48 slots) | max load error = 0.0 | 1e-14 | **PASS** |
| Reassignment = single assign  | state diff = 0.0 (both slot and full vector) | 1e-14 | **PASS** |
| Rotation roundtrip (100 ops) | L2 error = 9.06e-16 | 1e-10 | **PASS** |
| Semantic isolation           | semantic drift = 0.0 | 1e-14 | **PASS** |

All four tests pass. The primitive behaves exactly as the
2026-04-21 design specified and the 2026-04-24 validation predicted.

## What this means

The extended-state-vector design graduates from "pending
experimental validation" to "runtime-supported primitive":

- Reversible imperative state is now a first-class property of the
  substrate. `x = a; x = b; x = a` produces a state
  byte-identical to `x = a` — the sequence of assignments is a
  sequence of plane-writes with no accumulating drift, no residual
  phase, no semantic coupling.
- The synthetic subspace is a real computational resource, not a
  placeholder. 48 independent slots per program is a meaningful
  capacity for the kinds of demos Sutra ships today (hello world,
  fuzzy branching, role-filler record all fit comfortably).
- `slot_store` / `slot_load` can back a compile-time-allocated
  `var x : int` style slot without touching `bind` / `unbind` /
  `bundle`. The two binding systems now coexist cleanly: rotation
  binding in the synthetic subspace for positional / variable-slot
  content, Haar-in-semantic binding for role-filler content on
  LLM embeddings.

## What is explicitly not yet done

1. **No Sutra-language surface syntax.** `slot_store` / `slot_load` /
   `rotate_slot` are runtime methods callable from Python; no `.su`
   source yet compiles down to them. A surface like
   `var[N] slots : fuzzy` or `slot x = ...` would need parser +
   validator + codegen changes that this sprint scoped out.
2. **No compile-time slot allocator.** Every user of the slot
   primitives today picks their own `slot_idx`. A compiler pass
   that maps named variables to slot indices is the next step once
   the surface syntax is chosen.
3. **No spec text update.** The runtime ships ahead of the spec
   commitment. `planning/sutra-spec/binding.md` still says the
   synthetic-subspace rotation-binding design is a design target,
   not a committed primitive; that text needs a refresh in a
   follow-up pass.
4. **No demo `.su` program exercises it yet.** The only executor is
   the Python experiment above. A real demo where the compiler
   allocates slots for `int` / `fuzzy` variables and the user writes
   imperative-looking code that is provably reversible is the
   pedagogical win this unlocks.

## Pre-Anthropic-grant-app sprint closeout

This is the last item of the three-item sprint (queue.md,
2026-04-24). All three closed:

1. **Capacity experiments** — all 5 passed.
   `planning/findings/2026-04-24-synthetic-subspace-validation.md`
2. **Cross-substrate embedding sweep** — 5/5 on all three substrates
   with comfortable margins.
   `planning/findings/2026-04-24-capital-country-across-substrates.md`
3. **Extended-state runtime primitive** — 4/4 on compiled runtime.
   (This doc.)
