# Sutra spec — open questions

One-stop index of every open question sitting in the spec right now.
Each section in the spec carries its own open questions inline; this
file is the rolled-up view so a reader can see the whole set of
decisions the language has not yet made without walking every
section file.

When an open question is resolved, delete the line from here *and*
from the inline section. Both moves happen in the same commit. If a
new open question appears in a spec section, add a pointer here too.

This is separate from `planning/open-questions/` at the repo root —
that directory holds long-form design dossiers (a doc per question,
with arguments for and against). This file is a flat list pointing
into the spec sections themselves. Long form lives there; flat index
lives here.

---

## RAM pointers (`ram-pointers.md`, 2026-06-01)

- **Write-ack / ordering.** Is `ramWrite` fire-and-forget, or does it
  return a `Promise<void>` to `await` for read-after-write ordering?
- **What "RAM" physically is.** Flat host buffer for now; OS pages /
  Yantra storage tier / device file is a Yantra-side question.
- **Address space & out-of-bounds.** OOB read must return a
  meaningless-but-valid vector (no runtime errors by mechanism), not
  raise — confirm against `equality-and-defuzzification.md`.
- **Value width.** One `number` per cell (strings span cells) vs. a
  whole axon per cell.

---

> **Note on this file's nature.** Unlike the `planning/open-questions/`
> dossiers (a doc per question, which can rot after a decision is made),
> most entries here are genuinely-open spec decisions — the language's
> own deliberate list of choices it has not yet made. Do not assume an
> entry is "secretly decided elsewhere"; if you resolve one, delete it
> per the rule at the top.

## Types — `types.md`

- Whether `bool`'s defuzz counter has a ceiling.
- Whether other subtypes of vector (`probability`, `angle`,
  `unit_vector`) are needed.
- Whether matrices have first-class subtypes
  (`rotation_matrix`, `defuzz_matrix`, `is_X_matrix`).
- Semantics of `var[N] X : TYPE = expr;` (initialized array) —
  currently rejected at codegen.
- Static type checking: do we want one, at what stage, how strict?

## Operations — `operations.md`

- Which similarity operation is the Sutra default (dot, cosine,
  normalized dot, substrate-dependent).
- `bundle` semantics (straight sum, sum-then-normalize, weighted
  sum, substrate-specific superposition).
- Should `snap` and `argmax_cosine` unify under a single name that
  lowers per-substrate, or stay distinct?
- Semantic-role matrix fitting procedure when `learned_from(…)`
  lands (lstsq, ridge, Procrustes, low-rank). Substrate-dependent.
- Vector binary operators: are elementwise `+`/`-`/`*` on vectors
  spec operations, or are `bundle` / `displacement` / scale the
  only blessed paths? Today binary operators pass through to
  Python unchanged.
- Additional primitives worth first-class status (rotation,
  projection, scalar multiplication).

## Binding — `binding.md`

- Which fitting procedure for semantic role matrices (lstsq,
  ridge, Procrustes, low-rank).
- Whether learned matrices need to be orthogonal for clean
  unbinding.
- Which empirical-space directions qualify as "undersymbolic" for
  structural key placement.
- Whether there are roles that are genuinely non-linear (and so
  cannot be captured as a matrix).
- Whether there are other binding kinds worth populating beyond
  semantic and rotation (sparse-code, attention-style, hybrid).

## Equality and defuzzification — `equality-and-defuzzification.md`

- Construction of the "is-X" matrix (canonical function vs
  user-definable).
- Construction of the defuzz matrix.
- Ceiling behavior of the defuzz counter.
- Whether `is_true` is the only defuzzification primitive.
- Type of the truth-vector returned by matrix-mediated equality.

## Control flow — `control-flow.md`

- Multi-option `select` firing threshold and `select ... else`
  score formula (tracked in `todo.md` too).
- Exact rotation operator for `loop(cond)` eigenrotation (Haar-
  random today; substrate-specific / per-site alternatives?).
- Whether `loop(cond)` can terminate on non-similarity conditions.
- `try-catch` (parsed-but-unimplemented — see `todo.md`); and the
  dynamic-`foreach` case (named collections, runtime-computed
  iterables — the compile-time-known-array-literal form is already
  implemented). (`if/else` is design-rejected in `control-flow.md` —
  `select` is the only runtime branching primitive.)

## Program structure — `program-structure.md`

- Exact `atman.toml` schema (required vs optional fields, a
  validator).
- Substrate-incompatibility detection at compile time.
- Per-file compilation vs. import/module system.
- Project directory layout (nesting, multi-atman.toml walks).
- Multiple entry points (libraries, subcommand tools).
- Fate of parsed-but-ignored modifiers (`public` / `private` /
  `static`).
- Fate of parsed-but-rejected module-level items (methods,
  operator overloads, generic functions).

## Axons — `axons.md`

- How the per-entry type tag is represented and resolved (runtime
  cast vs. compile-time-erased static check, with what failure mode).
- How far the lazy analysis propagates (through nested axons, across
  dynamic dispatch, when the receiver's source isn't visible at
  compile time).
- What "hardware-linked" cashes out to inside the Sutra spec proper,
  vs. what is purely a downstream concern of the host system.
- Default axon width — single fixed width vs. carried as part of
  program configuration.
- How property-style access (`a.cat`) lowers when the key is *not*
  statically known. (Statically known: same as `item("cat")`.
  Dynamically computed: probably an error, but unspecified.)
- Behavior on missing key — compile error for statically-known-
  missing, runtime error, or noise-decoded value.
- Whether `Axon` is a new built-in class added to the surface vs. a
  special syntactic form.
- Whether role-as-operator transfer should have a first-class
  surface form or stay implicit in `add`.
- Error propagation across axon boundaries (sentinel-filler in a
  status key vs. error-shaped axon).
- Whether axons carry an explicit provenance role by default
  (Yantra-side question, not Sutra-side).
- One global codebook with namespaced roles vs. per-program
  codebooks (Yantra-side question, not Sutra-side).

## Concurrency — `concurrency.md`

- Explicit-mode surface syntax for the two shapes that need
  explicit handling (concurrent looping, MLP attractor search) —
  still open within the "explicit only when needed" framing.
- Convergence test: cosine threshold, snap identity, bit-
  identical value, or `||f(x) - x|| < ε` for attractor iterations.
- Result of the concurrent region: **partially committed** to
  "rotation-bound array of slots" (2026-04-22) but other shapes
  (single-vector merge, first-arrival) deferred rather than
  rejected.
- Whether a path is a first-class value (passable / storable).
- Whether a concurrent computation has a distinct type.
- How timing difference between paths is expressed.
- Semantics when one path diverges or never terminates.

## Promises and async/await — `promises.md`

First cut landed 2026-05-09. Spec defines surface syntax (`async`,
`await`, `Promise<T>`) and the lowering to existing tail-recursive
loop forms with axons at the boundary. Implementation tracked in
`queue.md`.

- Reject-channel encoding — two-scalar (`fulfilled`, `rejected`) vs
  one signed scalar.
- Multi-await fusion — when to fuse sequential awaits into a single
  multi-channel loop.
- Promise composition with axon types — does `Promise<axon X>`
  flatten? does `Promise<Promise<T>>`?
- Cancellation primitive — Sutra loops genuinely can be cancelled
  mid-flight (set rejected from outside); offer as explicit primitive
  or leave implicit?
- Backpressure / streaming — async generators (`async function*`) as
  separate construct vs. unified with `async function` via
  multi-write-event axons.
- Exception-object surface for `catch` — Sutra has no raise/throw;
  decide whether `catch` exposes the awaited promise's `.reason()`
  as an implicit binding.
- Top-level await — allow `async main()`, or compile-error pending
  modules?
