# Sutra spec — under construction

This directory is intentionally empty. The previous spec (29 files,
plus an EBNF grammar) lives at `planning/sutra-spec-deprecated/`.
**Do not cite it as authoritative.** It accumulated across many
sessions, much of it written aggressively into the spec without first
checking against the user's vision, and as of 2026-04-15 the user has
flagged that the deprecated docs do not match what Sutra is supposed
to be.

## The meta-failure (worth recording)

The user originally asked Claude to build out this spec dir as a
single source of truth, on the model of how a normal language has a
spec. That request had a hidden trap: VSA / HDC scientific literature
is thin and inconsistent, and Sutra's design is not a derivative of
that literature — it's the user's own thing. So when Claude ran out
of literature to lean on (which happened immediately), Claude filled
the gap by inventing structure that *sounded* spec-shaped (tier
hierarchies, primitive taxonomies, "snap is the universal terminal
commit," "bool is a crisp boolean") rather than asking the user. The
user did not catch this fast enough because the doc *looked* like a
spec — it had section numbers and definitions and looked authoritative
— so the drift compounded across many sessions.

This is the same failure mode as the tier-1/2/3 framing the user
explicitly rejected: Claude found a structuring schema that felt
satisfying, ran with it, and the user later had to explicitly tear
it out. The deprecated spec is mostly that, at scale.

The lesson for the new spec: **do not write into it from scratch when
the user hasn't expressed a position.** Write down what the user has
said, in the user's framing. When there's a gap, mark it as an open
question in `planning/open-questions/` and wait for the user to
resolve it. Do not paper over a gap with a plausible-sounding default
just because spec docs are supposed to be self-contained.

## Why deprecate

Concrete problems with the deprecated spec:

- **`snap` was promoted to a universal terminal commit** in §02 and
  in language-paper §1/§2.2. The user's actual position is that snap
  is one possible commit a program *may* choose; many programs
  output raw vectors, logits, or fuzzy results.
- **`bool` was specified as a crisp boolean** until 2026-04-15. The
  user's actual position is that `bool` is a subclass of `fuzzy`,
  carries a defuzzification counter as compile-time metadata, and
  exists to drive method overloading — there is no crisp boolean in
  Sutra.
- **`gate` was specified as a second branching primitive** until
  2026-04-15. The user dropped it; `select` is the one branching
  primitive (single-option / multi-option / `else`-clause forms).
- **The numpy backend was documented as if it embedded with a frozen
  LLM** when in fact it draws fresh random unit vectors per name. The
  user's actual position is that the numpy backend should be backed
  by a frozen LLM (the same one the embedding paper uses).
- **Many smaller drifts** across the 29 files. Each individual edit
  looked reasonable at the time; the cumulative drift produced a doc
  the user does not endorse.

## What this directory will become

A fresh, smaller spec, written incrementally, only after the user
has expressed a position on each part. Sessions writing here should
**not** translate the deprecated spec forward — that just relaunders
the drift. Treat the deprecated dir as "what we used to think,"
useful as historical context and as a list of questions the new spec
will need to answer, but not as source material to copy.

## What papers should do in the meantime

- The language paper (`language-paper/paper.md`) and the embedding
  paper (`sutra-paper/paper.md`) and the fly-brain paper
  (`fly-brain-paper/paper.md`) should describe what the
  implementation actually does, not what the deprecated spec says.
  When in doubt, look at `examples/`, the compiler, and the actual
  results — those are ground truth right now, not the deprecated
  spec.
- Any cross-reference in a paper to `planning/sutra-spec/*.md` should
  be removed or rewritten to cite the implementation directly.

## Conventions for the new spec

- **Files are named by topic, not numbered.** `concurrency.md`, not
  `01-concurrency.md`. Numbering creates a false linear ordering and
  every section-reorder invalidates cross-references.
- **Open questions are allowed inline in each section.** Spec sections
  do not have to be closed before they land — writing down what the
  user has said, with the remaining gaps explicit, is a valid state.
- **The spec-wide index of open questions lives at `open-questions.md`**
  in this directory. When a section acquires or resolves an open
  question, update that file in the same commit.

## Pointers while the new spec is being built

- Code is the source of truth: `sdk/sutra-compiler/`, `examples/`.
- Spec-wide open-question index: `planning/sutra-spec/open-questions.md`.
- Long-form design dossiers: `planning/open-questions/`.
- Things tried, with results: `planning/findings/`.
- Things parked but not closed: `planning/exploratory/`.
- Hardwired assumptions in the demo path: `examples/todo.md`.
- Deprecated spec (read-only reference): `planning/sutra-spec-deprecated/`.
