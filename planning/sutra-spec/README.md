# Sutra spec

This directory is the **authoritative design surface** for Sutra — the canonical,
fullest-fidelity description of the language, read by AI agents and contributors.
When something is true about Sutra's design, it is true here first. Code
(`sdk/sutra-compiler/`, `examples/`) is ground truth for *behavior*; this spec is
ground truth for *intent*. When the two disagree, that is a bug to resolve
explicitly (fix the code or update the spec), not to paper over.

## Index

Core model:
- `vision.md` — how Sutra inverts VSA's random-role premise.
- `operations.md` — what each Sutra operation computes.
- `binding.md` — semantic vs non-semantic binding.
- `equality-and-defuzzification.md` — `is_true`, the undersymbolic realm.
- `types.md` — the type lattice (everything is a vector; subtypes are compile-time metadata).
- `axons.md` — structured embeddings, role-as-operator, the hardware-linked-monad framing.
- `strings.md` — synthetic-axis-encoded codepoint arrays; `String` and `Character`.

Program shape and control:
- `program-structure.md`, `control-flow.md` (conditionals via `select`; loops),
  `non-halting-loop.md`, `concurrency.md`, `promises.md`.
- `recursion-execution-model.md` — the settled five-tier recursion-lowering hierarchy
  (loops → pre-eval → memoization → WASM fallback).
- `ram-pointers.md`, `axon-io.md`, `arbitrary-precision.md`, `matrix-valued-bake-back.md`.

Frontends, verification, open work:
- `transpiler-frontends.md` — the `sutra-from-*` source-language lowering passes.
- `formal-verification.md` — the FV obligations and what is machine-checked.
- `open-questions.md` — the spec-wide index of unresolved design decisions.

## Conventions

- **Files are named by topic, not numbered.** `concurrency.md`, not `01-concurrency.md` —
  numbering imposes a false linear order and every reorder breaks cross-references.
- **Open questions are allowed inline in each section.** A section does not have to be
  closed before it lands; writing down what is settled, with the remaining gaps explicit,
  is a valid state. The spec-wide index of those gaps is `open-questions.md` — when a
  section acquires or resolves an open question, update that file in the same commit
  (and delete the resolved line rather than striking it through).

## The meta-failure this spec exists to avoid (worth keeping)

An earlier version of this directory drifted badly: asked to build a single-source-of-truth
spec on the model of a normal language, and finding the VSA/HDC literature thin (Sutra is
Emma's own design, not a derivative of it), the agent filled the gap by inventing
structure that *sounded* spec-shaped — tier hierarchies, primitive taxonomies, "snap is the
universal terminal commit," "bool is a crisp boolean" — rather than asking. It looked
authoritative (section numbers, definitions), so the drift compounded across sessions until
Emma had to tear it out. (The rejected tier-1/2/3 op-stratification was the same failure
mode.) The lesson, still binding: **do not write into the spec from scratch where Emma has
not expressed a position.** Record what she has said, in her framing; mark a genuine gap as
an open question and wait, rather than papering over it with a plausible default.

## Pointers

- Code is the source of truth for behavior: `sdk/sutra-compiler/`, `examples/`.
- Spec-wide open-question index: `open-questions.md` (this dir).
- Long-form design dossiers: `planning/open-questions/`.
- Things tried, with results (esp. negative): `planning/findings/`.
- Things parked but not closed: `planning/exploratory/`.
- Longer-horizon agenda: root `todo.md`. Active queue: `queue.md`. History: `DEVLOG.md`.
