# Vector-sized loop slots — the by-reference statement form and vector state

**Status:** design doc for vector-loop-state rung 3 (queued; Emma directed "Both,
expression-first" 2026-07-12). Rungs 1-2 shipped a complete *value-returning* path for
vector loop state (the loop expression form + multi-state tuple-destructure). This doc
scopes the remaining rung — making the *by-reference statement form* carry vector state
too — and surfaces the option that rungs 1-2 make viable: **not building it at all.**

## The problem

The by-reference loop-call statement form crushes vector/String state to a scalar:

```sutra
slot String acc = make_string("");
loop build(15, acc);       // acc is silently reduced to its real-axis scalar → runtime crash
```

Warned at compile time by SUT0206; measured to crash on the corpus's own `do_while.su`
(finding 2026-07-08).

## Current representation (ground truth, `codegen_pytorch.py`)

- `_slot_state = _VSA.zero_vector()` — ONE `dim`-length tensor per function
  (`dim = semantic_dim + synthetic_dim`).
- `_slot_plane(slot_idx)` → `(base, base+1)` where `base = semantic_dim + SLOT_BASE + 2*s`,
  `SLOT_BASE = 8`, `n_planes = (synthetic_dim - SLOT_BASE) // 2`. **Each slot owns exactly 2
  synthetic axes.**
- `slot_store(state, idx, v)` writes `_slot_cell(v)` (a 0-d real-axis projection — this is the
  crush) into axis `base`; zeroes `base+1`.
- `slot_load(state, idx)` returns `state[base]` — a 0-d scalar.

**Why 2 axes can't hold a vector:** a slot has 2 synthetic axes inside the SAME `dim`-length
state vector; a `String`/`vector` value is itself `dim`-length. You cannot pack a `dim`-vector
into 2 components of a `dim`-vector. So carrying vector state by reference requires a different
storage representation, not a bigger `_slot_cell`.

## Options

### Option C — DON'T build it; the value-returning path already covers vector state
Keep the by-reference slot form **scalar-only**, permanently. Promote SUT0206 from warning to
**error** for `String`/`vector`/`complex` loop state, steering to the expression form
(single-state) or destructure (multi-state) — both shipped and proven (rungs 1-2). Convert the
corpus's `do_while.su` (the known-broken `slot vector` case) to the expression form.
- **Cost:** small — a diagnostic severity flip + one corpus rewrite + doc.
- **Substrate purity:** unaffected (no new mechanism).
- **Risk:** low. The only thing lost is by-reference *symmetry* for vector state — but the
  value-returning forms are the idiomatic direction anyway (loops.md already frames them so).
- **Downside:** `slot String acc; loop f(N, acc);` never works; users must write
  `String acc = loop f(N, make_string(""));`. That is arguably better style, not a real loss.

### Option A — parallel vector-slot store (scalar plane untouched)
Add a second structure `_vslot_state` (a Python list of `dim`-vectors, or a `[n_vslots, dim]`
tensor) alongside the scalar `_slot_state`. A `slot`-declared var of a multi-axis type routes to
`vslot_store`/`vslot_load` (full-vector write/read); scalar slots keep the existing plane.
- **Cost:** medium — new store/load ops, type-dispatched `_translate_var_decl` + loop-call
  writeback, driver threads a second state object.
- **Substrate purity:** OK — the store is a container of tensors (same category as `_slot_state`
  today); read/write is indexing/assignment, no host readout. Must confirm the loop driver
  passes/returns the full vector without any `_re`/`.item()` on the path.
- **Risk:** medium. Two parallel slot mechanisms is exactly the kind of redundant affordance
  CLAUDE.md warns agents latch onto; needs clear canonicalisation.

### Option B — unify: all slots become `dim`-sized
`_slot_state` becomes `[n_slots, dim]` (or a list of `dim`-vectors). Scalars are stored as their
number-vector form (a scalar is already a `dim`-vector on AXIS_REAL). `slot_store` sets row
`idx`; `slot_load` returns row `idx` (full vector). One representation for all slot types.
- **Cost:** large — touches every scalar-slot program's lowering; `slot_load` no longer returns
  a 0-d value, so any code assuming that must be re-audited.
- **Substrate purity:** OK in principle (rows are vectors), but the re-verification surface is
  the whole scalar-slot corpus (`do_while_adder` is paper-cited — durability).
- **Risk:** high. Biggest blast radius; most re-measurement.

## Recommendation → DECIDED: Option B (Emma, 2026-07-12)

The doc recommended **C** (cheapest; rungs 1-2 already cover vector state). Shown all three,
**Emma chose B — unify all slots to `dim`-sized.** She wants by-reference symmetry under a
single representation, accepting the larger blast radius and the re-verification of the
paper-cited scalar path. Build it carefully and incrementally, keeping every scalar-slot program
measured-correct at each step; do NOT retire the scalar path until the unified path reproduces it.

### Option B build plan (staged; each sub-rung bounded + measured)

- **B1 — storage representation.** `_slot_state` from one `dim`-vector to a per-slot collection of
  `dim`-vectors. n_slots isn't known until a function is fully scanned, so either pre-scan the
  body for `slot` decls to size a `[n_slots, dim]` tensor, or use a growable list-of-vectors
  (append on declare). `slot_store(state, idx, v)` sets slot `idx` to the full vector (scalars via
  `make_real`/number-vector, NOT `_slot_cell`/`_re`); `slot_load(state, idx)` returns the full
  `dim`-vector. Substrate-purity gate: no `_re`/`.item()` on the store/load path.
- **B2 — loop-call by-reference path.** `_translate_loop_call` init args (`slot_load`) + writeback
  (`slot_store`) thread full vectors; the driver already threads state as plain locals, so it needs
  no change beyond receiving/returning vectors.
- **B3 — re-verify the scalar path FIRST (before retiring anything).** Every scalar-slot program —
  `do_while_adder` (paper-cited), the counter/toggle demos, corpus scalar-slot files — must decode
  to the same ground-truth value. Measure, don't assume. This is the durability gate.
- **B4 — String/vector by-reference works.** The finding's FizzBuzz `slot String acc` case now
  runs by reference; add the end-to-end test (decoded ground truth).
- **B5 — retire the SUT0206 crush** (the by-reference form no longer crushes vector state) and
  keep `do_while.su` (the `slot vector` case) working by reference.
- Throughout: `slot_load` no longer returns 0-d — audit every consumer (the slot-load call sites
  outside loops, e.g. a bare `slot int x` read) so none assumed a scalar.

## Migration (whichever path)

- SUT0206: warning → error (C) or delete entirely (A/B, once by-reference vector state works).
- `do_while.su` (corpus valid, `slot vector`, not paper-cited): convert to the expression form
  (C) or leave working (A/B).
- Do NOT touch `do_while_adder.su` (paper-cited, scalar — unaffected by C; re-verify under B).
