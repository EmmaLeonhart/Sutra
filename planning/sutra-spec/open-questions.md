# Sutra spec — open questions

One-stop index of every open question sitting in the spec right now.
Each section in the new spec can (and should) carry its own open
questions inline; this file is the rolled-up view so a reader can see
the whole set of decisions the language has not yet made without
walking every section file.

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

- How "matrix-shaped" vs "non-matrix-shaped" functions are
  distinguished at compile time.
- Exact construction of the defuzz matrix.
- Whether the defuzz counter on `bool` has a ceiling.
- Whether scalars can appear as function results.
- Whether other subtypes of vector (probability, angle,
  unit_vector, …) are needed.
- Whether matrices have first-class subtypes.

## Operations — `operations.md`

- Which similarity operation is the Sutra default (dot, cosine,
  normalized dot, substrate-dependent).
- Exact semantics of `bind`, `bundle`, `unbind`, `snap`
  (intertwined with the sign-flip revisit item in `todo.md`).
- Whether other primitives deserve first-class status (rotation,
  projection, scalar multiplication).

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
- Whether the C-style iteration loop needs its own surface syntax.
- Whether the compiler silently falls back to `loop(condition)`
  when a loop can't be unrolled, or errors.
- Exact rotation operator for `loop(condition)` eigenrotation.
- Whether `loop(condition)` can exit on non-similarity conditions.

## Program structure — `program-structure.md`

- `meru.toml` schema (required / optional fields, defaults).
- How substrate incompatibility is detected and reported.
- Per-file import system vs whole-project compilation.
- Project directory layout.
- Multiple-entry-point programs.

## Concurrency — `concurrency.md`

- Surface syntax for splitting into parallel paths.
- Operational meaning of "convergence on a common thing" (cosine
  threshold? snap identity? bit-identical value?).
- What the concurrent region returns when convergence fires.
- Whether a path is a first-class value.
- Whether a concurrent computation has a distinct type.
- How timing difference between paths is expressed.
- Semantics when one path diverges or never terminates.
