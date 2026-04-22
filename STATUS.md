# Sutra — Work Queue

**This file is a queue, not a state snapshot.** It is the **persistent
task list across sessions**. Claude loads items from here into the
task tool (`TaskCreate`) at session start, works through them, and
**removes completed items from this file** as they finish. Finished
work lives in `git log` and `planning/findings/`; this file is only
the *pending* work.

See CLAUDE.md §"STATUS.md and the task tool" for the full workflow.

The work here is **making Sutra the language actually work** — the
compiler, the spec, the substrate-backed runtime, the demo programs.
No papers, no submission deadlines. The question each queue item
answers is: *what does it take to make this language a real thing
someone can use?*

Longer-horizon items (pre-Anthropic-grant-app, pre-YC-pitch, this-
year) live in `todo.md`. Items in this file are the ones Claude should
pick up next.

## Queued work

1. **`main(embedding_space: string)` runtime override.** Partial
   progress on STATUS's old #1: file-level (`// @embedding`) and
   project-level (`atman.toml` `[project.embedding]`) substrate
   declarations both land in the harness 2026-04-22. What remains
   is the third layer — a .su-language-level `main(embedding_space:
   string)` form that passes the substrate as a main() argument and
   overrides both file and project declarations at runtime. Requires
   parser changes (main signature validation, typed string params)
   and runtime rework (lazy _VSA initialization so main's argument
   can pick the substrate before any `embed()` happens at module
   scope). Deferred here as a substantial piece; lands alongside
   learned-matrix binding in the pre-grant-app queue per todo.md.

2. **Rebuild `planning/sutra-spec/` from scratch in the user's
   framing.** Process: each spec section starts as a question posed
   to the user; Claude writes down the user's framing; gaps go to
   `planning/open-questions/`. The `binding.md`, `vision.md`, and
   `equality-and-defuzzification.md` rewrites from 2026-04-21 are
   partial progress; `concurrency.md`, `control-flow.md`,
   `operations.md`, `program-structure.md`, `types.md` still need
   user-driven rewrites. Ongoing work across sessions, not a single
   task.

3. **Concurrency spec section.** A concrete sketch with an example
   `.su` program. Genuinely open design question — see
   `planning/sutra-spec/concurrency.md` and
   `planning/open-questions/concurrency-and-monads.md`.

4. **PyTorch/GPU backend.** `codegen_numpy.py` compiles to matmuls,
   sums, and cosines — every operation has a trivial GPU equivalent.
   Do this only after items 2-3 are settled so the spec being
   targeted is stable.

## Deferred (see `todo.md`)

These are real commitments but not "next active session" work. Kept
here as pointers so they don't fall off the radar:

- **Learned-matrix binding** (pre-Anthropic-grant-app): `role X =
  learned_from(data)` fits a matrix at compile time; `bind` for
  semantic roles becomes `R @ filler`. Deferred from 2026-04-22 per
  user priority. Full spec in `todo.md` and
  `planning/sutra-spec/binding.md` §"Semantic binding".
- **MLP-backed Monte-Carlo attractor search** (pre-Anthropic-grant-
  app, not today): train an MLP as an attractor function over the
  codebook, run Monte-Carlo trajectories from `v0 = king - man +
  woman` into the learned basins, compare attractor quality across
  substrates. Full details in `todo.md`. Placeholder script at
  `examples/_king_queen_attractor_search.py` is random-rotation-
  plus-nearest-neighbor — NOT the real attractor search; keep for
  the fragility-check use case only.
- **Extended state vector** (`[semantic | synthetic]` with canonical
  truth axis in the synthetic subspace) — structural target for the
  language. Currently deferred because the 2026-04-22 rotation-
  binding prototype runs in the 768-d semantic subspace instead.
  Move after learned-matrix binding lands.

## Pinned semantic corrections (I keep dropping these)

1. **`loop[N]` unrolls at compile time. Zero runtime iteration. No
   eigenrotation.** Only `loop(condition)` with data-dependent
   termination eigenrotates.
2. **No loop counters live on the host at runtime.** The "counter"
   for `loop(condition)` IS the angular position on the helix
   R^i·v₀ in the substrate.
3. **"Rotation on neurons" has two meanings. Don't conflate:**
   - Synthetic R (Givens) as Brian2 synapse weights → works.
   - Real FlyWire weight matrix AS the rotation → does not rotate
     (compressive projection).
4. **Semantic roles are learned matrices; semantic `bind` is
   `R @ filler`.** Not random vectors (HRR), not sign-flip. A
   *semantic* role is a matrix fit to the substrate — "object of a
   sentence" is the matrix fit on `(sentence_emb, object_emb)` pairs;
   `is_cat` is the matrix fit on `(thing_emb, is_cat_label)` pairs.
   See `planning/sutra-spec/binding.md` §"Semantic binding".
   **Implementation status: deferred** (see "Deferred" section above).
5. **Sutra has two binding kinds: semantic (learned-matrix) and
   rotation.** Spec-level design in
   `planning/findings/2026-04-21-extended-state-and-rotation-binding.md`.
   **Current implementation state** (as of 2026-04-22): rotation
   binding runs live on the 768-d frozen-LLM semantic subspace via
   role-seeded Haar matrices (not yet in a dedicated synthetic
   subspace). Semantic binding is deferred. So when coding, only
   rotation binding is actually executable today.
6. **Sign-flip binding is retired** (from the codegen as of
   2026-04-22). Rotation is the current `bind` implementation in
   `codegen_numpy.py`. The name `permute` was a deprecated alias
   and is also retired.
7. **Truth is designed as a canonical axis in the synthetic
   subspace.** Spec target in `planning/sutra-spec/equality-and-
   defuzzification.md`. **Implementation status: not yet runtime-
   supported.** `is_true` and defuzzification don't currently
   project onto a dedicated axis; adds with the extended-state-
   vector work.
8. **Numpy is the demo substrate. Fly-brain is segregated.** Two
   backends: `codegen_numpy.py` (demo path, self-contained, no
   fly-brain imports) and `codegen_flybrain.py` (fly-brain-specific
   work, not the demo). PyTorch/GPU is a future refactor target.
9. **Defuzzification polarizes, never binarizes.** `is_true` and
   `defuzzify` keep the result fuzzy and differentiable. No commit
   primitive exists; `select` does all branching. Don't reintroduce
   `gate`.
10. **`bool` is a subclass of `fuzzy`, not crisp.** Carries a defuzz
    counter as compile-time metadata. Drives method overloading.
    A bool value is (per design) a scalar on the canonical truth
    axis; runtime realization pending extended-state-vector work.

## Pointers

- Longer-horizon agenda: `todo.md`.
- Deprecated spec (read-only reference): `planning/sutra-spec-deprecated/`.
- New spec dir + meta-failure note: `planning/sutra-spec/README.md`.
- Findings (dated): `planning/findings/`.
- Open design questions: `planning/open-questions/`.
- Hardwired assumptions in the demo path: `examples/todo.md`.
