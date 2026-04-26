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

**Today's priority: trim repo bloat ahead of public presentation
(2026-04-25).** The repo has accumulated weight that doesn't pay
for itself, and a public release is imminent so non-load-bearing
or dev-only material should come out.

**Active task: finish `chats/` triage.** Three substantive chats
deferred for a focused later pass — the rest of the original 33
have been triaged (each removed only after its content was
verified to be captured in spec / findings / open-questions / a
new doc, with the verdict in the commit message).

Deferred for focused review:

  - `chats/kolmogorov-arnold-networks-for-tensor-operations.md`
    (941 lines) — KART, beta-reduction-as-Sutra's-compilation-model,
    Chebyshev / lookup-table compilation of math functions, TOML
    backend/dtype settings, ISA analogy, currency stdlib idea,
    OWL-style ontological typing, hashmap-via-rotation origin.
    Some content already captured (rotation hashmap, ontological
    typing); compile-time math approximation + TOML backend
    settings are concrete future-features not yet captured.
  - `chats/vsa-operations-explained.md` (2204 lines, 80+ sections)
    — comprehensive early design conversation covering most of
    Sutra's foundations. Needs careful section-by-section
    comparison against current spec.
  - `chats/vsa-programming-languages.md` (933 lines, 22 turns) —
    early "what does a VSA programming language look like" deep
    dive. Same shape as the operations chat.

Done in this sweep:

  - `chats/` HTMLs and `_files/` browser-asset directories removed
    (~40 MB, commit 438dace).
  - `scripts/` removed in full (8 files: chat extractor + paper-
    submission/competition-review fetchers whose CI counterparts
    were already deleted).
  - 28 of 33 chat markdowns triaged and removed across many
    commits; each captured what was load-bearing first. Notable
    captures along the way:
      - `wait` keyword fully implemented (lexer / parser / AST /
        codegen / validator / corpus tests / docs / IDE
        highlighting). See no-null open question Candidate D and
        `examples/wait_keyword_demo.su`.
      - `planning/open-questions/nested-loops-as-orthogonal-subspaces.md`
      - `planning/prior-art-vsa-turing-completeness.md` (Flanagan,
        Plate, Smolensky, Lambek & Scott, arXiv refs).
      - `planning/exploratory/claw4s-paper-compile-time-vsa.md`
        (paper draft for 2026-04-30, four computational novelties).
      - `STATUS.md` egglog entry: Diospyros / JuliaSymbolics
        hash-consing / VCR prior-art notes.
      - `todo.md`: agent-friendly site item, class-system-as-
        autocomplete-recommendation.
      - CLAUDE.md Sutra Core Design: "runtime is committed to the
        math" + "opinionated, not authoritarian" principles, plus
        the agent-friendly website note.
  - Two chats scrubbed from git history (filter-repo): the resume
    chat and the akasha-vision-graph chat — both contained
    personal info / hiring-positioning content. History rewrite
    was a one-time blanket policy correction; not the default.

Next bloat sources to investigate:

  - `sdk/intellij-sutra/build/` — IntelliJ build output, indexes,
    sandboxes. Should be in `.gitignore` if it isn't, and the working
    copy should be cleared (`./gradlew clean` in that dir).
  - `fly-brain/flywire_data/` — already gitignored per CLAUDE.md, but
    worth confirming nothing has slipped in.
  - `fly-brain/` Python sprawl — the 2026-04-13 cleanup got it from
    33 to 15 files; check it hasn't crept back.
  - `experiments/` and `planning/findings/` — large but mostly
    paying their way; audit only if something stands out.
  - Cached embeddings, viz HTML siblings (`*_viz.html` from
    `--run-viz`), pyc/__pycache__ leakage.

The principle: anything that is regenerable (build output, caches,
extracted artifacts where the source is preserved elsewhere) should
not be tracked. Anything that takes substantial space and isn't
load-bearing for the language should be revisited.

**Compilation updates moved to `todo.md`.** Egglog post-pass +
matrix-chain fusion landed 2026-04-25; the remaining linearity
analysis codegen, CSE pass, and slot codegen integration are now
tracked under `todo.md` § "[Pre-YC] Compilation updates". The
imperative-reversible demo and the spec-text refresh both landed
2026-04-25.

Recently closed:
- **Pre-Anthropic-grant-app sprint — all three items** (2026-04-24).
  Grant app submitted ahead of the 2026-04-26 deadline.
  1. Rotation-binding capacity experiments — 5/5 PASS
     (`planning/findings/2026-04-24-synthetic-subspace-validation.md`,
     `experiments/synthetic_subspace_validation.py`). Zero cross-talk
     at N/2, capacity curve characterized past overlap, truth-axis
     orthogonality under semantic ops, 100-op reversibility at FP
     roundoff, fuzzy composition clean.
  2. Cross-substrate embedding sweep — 5/5 correct on all three
     substrates
     (`planning/findings/2026-04-24-capital-country-across-substrates.md`,
     `examples/_analogy_substrate_sweep.py`). nomic, mxbai, and
     minilm all resolve the capital→country retrieval with
     comfortable margins (mean > 0.14, min > 0.10).
  3. 2D-Givens-per-slot rotation binding as a runtime primitive
     (`planning/findings/2026-04-24-slot-rotation-runtime.md`,
     `experiments/slot_rotation_reversibility.py`). `slot_store` /
     `slot_load` / `rotate_slot` added to `_VSA` in codegen.py;
     48 independent slots, exact reassignment, 9e-16 rotation
     roundtrip, zero semantic-block drift. All 206 tests still pass.
- **Stdlib function-expansion pipeline v0.3 — all six steps**
  (9001f90 / 3106ec8 / a72ec29 / 9b9d85f / 31a4300 / 2a0c065 /
  1250912, 2026-04-24). Full pipeline from `.su` stdlib definitions
  through inlining, operator lowering, dead-runtime-method deletion,
  the `intrinsic function ... ;` language surface, and the first
  slice of the fusion pass (full literal-on-literal arithmetic
  folding). Callers that were `_VSA.logical_and(a, b)` / `_VSA.eq`
  pathways now compile to inline polynomial arithmetic; callers
  with literal arguments collapse to a single compile-time
  constant. `logical_and(0.7, 0.3)` → `_VSA.make_truth(0.33705)`
  with zero runtime arithmetic. 206 tests pass.

  What the fusion pass does NOT yet do (real compiler work,
  separate future passes): matrix-chain composition (`M2 @ M1 @ v`
  → `(M2 @ M1) @ v` at module init), CSE for repeated
  subexpressions, linearity analysis to recognize "this function
  body is matrix M, precompute M once," purity tracking for
  runtime-constant methods. The groundwork — stdlib directory,
  inliner, intrinsic surface, constant folding — is all in place;
  the remaining fusion work builds on top.
- **Release v0.2.0** (7595dd2, 2026-04-24). First tagged release.
  __version__ bumped from dev placeholder 0.1.0. CHANGELOG.md added.
  GitHub release at https://github.com/EmmaLeonhart/Sutra/releases/tag/v0.2.0.
- **stdlib scaffolding for Sutra-source system functions** (cd48bf0 /
  fea4523 / 7b44a51, 2026-04-23). Created seven `.su` files under
  `sdk/sutra-compiler/sutra_compiler/stdlib/` — one per category.
  Implementable-as-Sutra functions (defuzzy, logical_not/and/or, neq,
  lt, ge, le) carry real bodies the parser accepts today; the rest
  carry commented pseudo-Sutra bodies showing the target expansion
  and noting which runtime primitive they're blocked on.
  README.md has the full inventory plus the six-step pipeline above.
  Not wired into codegen yet — canonical reference files for the
  inliner to consume.
- **Dropped numpy as a user-facing backend** (b21974f / e77563b,
  2026-04-23). `codegen_numpy.py` → `codegen.py`; class
  `NumpyCodegen` → `Codegen`. `--emit-numpy` removed; `--emit` and
  `--run` now target PyTorch directly. PyTorch is the compiler's
  runtime library — Sutra compiles to torch tensor ops the way clang
  compiles to LLVM IR. Internal IR still uses `_np.` strings in
  `codegen.py` that PyTorch post-processes; full purge is a follow-up.
- **Rotation-hashmap capacity at d=868** (2026-04-23). Measured
  through the `hashmap_new/set/get` API on the extended-state runtime.
  Findings:
  `planning/findings/2026-04-23-rotation-hashmap-capacity-extended-state.md`.
  Capacity curve matches the d=768 raw-bind/bundle study within
  sampling noise (100% up to k=24, 90% threshold at k=48, 50% at
  k=128, 200-filler codebook). The synthetic block is algebraically
  inert under bind/bundle when held at zero (the runtime reality), so
  the extended state does not shift the capacity story — which is the
  honest expected result given the block-diagonal rotation design.
- **PyTorch/GPU backend** (47ff23b, 2026-04-23). New
  `codegen_pytorch.py` emits self-contained torch modules picking
  CUDA at module init. Demos run end-to-end on GPU with identical
  algebra and extended-state layout. Generalized ANF + dep analysis
  for fusion across non-bundle/bind patterns is NOT done — only the
  `bundle(bind,bind,...)` pattern is fused; mixed sequences like
  `bundle(bind(r,f), c, bind(r2,f2))` still emit sequentially.
  That widening folds into step 6 of the stdlib pipeline above —
  the fusion pass will subsume it.
- **Extended state vector** (e1ccbbe, 2026-04-23).

## Deferred (see `todo.md`)

These are real commitments but not "next active session" work. Kept
here as pointers so they don't fall off the radar:

- **`main(embedding_space: string)` compile-time override.** Partial
  progress: file-level (`// @embedding`) and project-level
  (`atman.toml` `[project.embedding]`) substrate declarations both
  land in the harness 2026-04-22. The third layer — declaring the
  substrate from inside `.su` source itself — is a compile-time
  concern (not runtime as earlier framed) and sequenced post-
  Anthropic-grant-app per user direction 2026-04-23. Full scope
  in `todo.md`.
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
8. **PyTorch is the compiler's runtime target. Fly-brain is
   segregated.** Two backends: `codegen_pytorch.py` (the main path —
   emits torch modules picking CUDA at module init) and
   `codegen_flybrain.py` (fly-brain-specific work, not the main demo).
   `codegen.py` is an internal IR step that `PyTorchCodegen` inherits
   from and post-processes; no longer user-reachable as a "numpy
   backend" — `--emit` and `--run` go to PyTorch. `--emit-numpy` is
   gone.
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
