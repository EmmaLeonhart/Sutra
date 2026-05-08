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

## Types — `types.md`

- Whether `bool`'s defuzz counter has a ceiling.
- Whether scalars can appear as function results (or only as
  inputs).
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

- ~~**Surface syntax for binding-kind choice**~~ — **resolved
  2026-04-21**. `role` for semantic bindings, `var` for rotation-
  bound storage.
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
- When `loop[N]` can't be unrolled (non-literal N), current
  codegen emits a host-Python `for _ in range(N)`. Is that
  acceptable, or should it error?
- Exact rotation operator for `loop(cond)` eigenrotation (Haar-
  random today; substrate-specific / per-site alternatives?).
- Whether `loop(cond)` can terminate on non-similarity conditions.
- Fate of parsed-but-rejected control forms: `if/else` (design-
  rejected, use `select`), `try-catch` (unimplemented — see
  todo.md). `do-while` was in this list until 2026-04-22 when it
  was implemented by desugaring to body + while. `foreach` over
  a compile-time-known array literal was also implemented on
  2026-04-22; the dynamic-foreach case (named collections,
  runtime-computed iterables) remains future work in todo.md.

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

Resolved 2026-05-07 (second cut):

- ~~Surface syntax for axon types (record-shaped, inline annotations,
  inferred)~~ — **none of those. There is no axon type with a
  declared key set; `Axon` is a single non-generic class. The
  compiler does dataflow analysis (for lazy evaluation) but does
  not type-check key sets.**
- ~~How `R_x` / `F_x` shorthand maps onto surface syntax~~ —
  **string-literal keys (`a.add("cat", c)`, `a.item("cat")`)
  syntactically, with property-style access (`a.cat`) preferred when
  ergonomic. Both forms compile to the same operation. The `R_x`
  notation is substrate-implementation shorthand only.**

Still open:

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
