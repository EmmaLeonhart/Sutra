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

## Concurrency — `planning/sutra-spec/concurrency.md`

- Surface syntax for splitting into parallel paths.
- Operational meaning of "convergence on a common thing" (cosine
  threshold? snap identity? bit-identical value?).
- What the concurrent region returns when convergence fires.
- Whether a path is a first-class value.
- Whether a concurrent computation has a distinct type from a
  single-path one.
- How timing difference between paths is expressed.
- Semantics when one path diverges or never terminates.

---

Sections with no open questions yet: *(none — concurrency is the
only rebuilt section so far).*
