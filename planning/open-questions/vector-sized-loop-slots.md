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

## Recommendation

**Option C**, unless Emma specifically wants by-reference symmetry for vector state. Rungs 1-2
already deliver a correct, measured value-returning path for both single- and multi-state vector
loops; Options A/B spend real substrate-redesign effort (and, for B, risk the paper-cited scalar
path) to buy a surface the language is already steering people away from. C closes the SUT0206
crush cleanly and cheaply. But this reverses the letter of Emma's "Both" pick (made before
rungs 1-2 proved the value path), so it needs her confirmation — same as the rung-1 measurement
reshaped that decision.

## Migration (whichever path)

- SUT0206: warning → error (C) or delete entirely (A/B, once by-reference vector state works).
- `do_while.su` (corpus valid, `slot vector`, not paper-cited): convert to the expression form
  (C) or leave working (A/B).
- Do NOT touch `do_while_adder.su` (paper-cited, scalar — unaffected by C; re-verify under B).
