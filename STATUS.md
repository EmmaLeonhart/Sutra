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

### Chat triage in progress — one chunk at a time

Three big chats were restored 2026-04-27 and split into 24
topic-scoped chunks in `chats/` (commit `17d350c`), to be triaged
individually. The session-by-session protocol the user is following:

1. **Per chunk, write a triage note**: brief content summary, case
   FOR removing, case AGAINST removing, and concrete harvest
   candidates (where the content would land if kept).
2. **The user decides per chunk**: harvest-and-clear (write the
   harvest target, then delete the chat file), keep-for-later
   (leave the file and revisit), or drop-without-harvest
   (delete with a verdict in the commit message).
3. **Each batch of decisions commits and pushes** so the queue is
   visible and the user can pick up the next session cold.

This is the explicit replacement for the misread triage policy that
preceded it (see memory note
`feedback_chats_triage_is_check_not_migrate.md`). The original
mistake was extracting "ideas" from chats into permanent planning
docs as a substitute for the chat logs themselves; the corrected
flow keeps the chat log alive until a per-chunk triage decision is
made with the user, then either harvests in a directed way or
deletes without harvest.

**Active paper draft.** The 2026-04-28 KART triage produced a new
paper-draft file at `planning/exploratory/sutra-paper-draft.md`. It
is **not** a revival of the deleted Claw4S draft — it uses the
**embedding-space-as-instruction-set-architecture** framing as the
rhetorical anchor instead of the compile-time-beta-reduction-vs-
runtime-VSA-LC contrast the deleted draft was built on. The four
computational novelties (beta-reduction-to-tensor-normal-form,
differentiable Lagrange-polynomial fuzzy logic, eigenrotation loops,
synthetic-dimension-rotation hashmaps) compose around the
embedding-as-ISA pillar and the paper's empirical claim is that the
four together make that ISA story coherent. No target venue or
deadline yet; treat as a parking lot for framing and contributions
list until it gets promoted to real work.

**Triaged so far** (24 chunks total):

  - **Triaged 2026-04-28:**
      - `kart-engineering-vs-research-rotation-novelty.md` →
        harvested into `planning/exploratory/sutra-paper-draft.md`
        (embedding-as-ISA framing, four novelties, parallax origin
        story); chat removed.
      - `kart-embedding-training-and-knowledge-graphs.md` → harvested
        into `planning/exploratory/sutra-native-embedding-space.md`
        (traversal-compositionality loss, knowledge-graph prior art,
        Wikidata pollution caveat, fine-tuning paths); chat removed.
      - `kart-owl-ontology-and-casting.md` → harvested into
        `docs/ontology.md` (proof-theoretic vs ontological framing)
        and `planning/sutra-spec/types.md` (cast taxonomy: no-op /
        projection / embedding); chat removed.
      - `kart-as-tensor-op-decomposition.md` → harvested into
        `planning/exploratory/sutra-paper-draft.md` (extended
        novelty 1 with "program is a value" framing + related-work
        contrast against supercompilation, polyhedral, AD; tightened
        KART entry as completeness certificate for novelty 1);
        chat removed.
      - `kart-beta-reduction-and-fsharp-competition.md` → harvested
        into `planning/exploratory/sutra-paper-draft.md` (added
        Cat=="cat" worked example for novelty 1; extended KART
        entry with explicit tier hierarchy and TOML precision
        setting) and new file
        `planning/exploratory/sutra-as-math-language.md` (Julia/F#
        precision contrast, finance positioning, units-of-measure-
        as-ordinary-types); chat removed.
      - `kart-currency-stdlib-and-precision.md` → harvested into
        `planning/exploratory/sutra-paper-draft.md` (refined
        worked example with "input is the only runtime variable"
        framing; split TOML mention into `[math]` and `[backend]`
        with the dtype axis exposed),
        `planning/sutra-spec/types.md` (new section on operator
        inheritance defaults — Number branch on, Entity branch
        off — with full hierarchy diagram), and
        `planning/exploratory/sutra-as-math-language.md`
        (extended Currency stdlib design with `ExchangeMatrix`
        and "no implicit cross-currency arithmetic"). Spawned
        new exploratory doc
        `planning/exploratory/eigenrotation-for-sine-and-modulus.md`
        from a math insight raised mid-triage (sin/cos/tan +
        modulus as Exact-tier via the existing rotation
        primitive); validated empirically same day in
        `planning/findings/2026-04-28-eigenrotation-as-trig-validation.md`
        (cost-saving claim refuted; architectural-uniformity
        argument survives). Chat removed. **All 4 KART chunks
        now triaged.**
      - `vsa-all-algebraic-branching-and-floating-point.md` →
        dropped without harvest. Three threads (system summary,
        probabilistic-TC + floating-point analogy, "laptop
        isn't TC because power can fail" reductio); mostly
        Claude synthesizing rather than novel content, FP-analogy
        rebuttal is re-derivable, and the system summary is
        partly stale. User verdict: remove.
      - `vsa-as-assembly-positioning.md` → dropped without
        harvest. Origin-conversation chunk: decision-to-build
        moment, "abstracts mostly away" framing, "no
        datatypes everything add/multiply" homogeneous-value
        insight, "VSA assembly" framing → "lower than C#"
        refinement. Technical content fully superseded by
        current paper draft (embedding-as-ISA supersedes VSA
        assembly), CLAUDE.md (homogeneous values, garbage-in-
        garbage-out), and types.md (dimensionality + VSA model
        per program already implemented). Historical trail
        preserved in git. User verdict: remove.
      - `vsa-as-programming-language-compiler.md` → dropped
        without harvest. Origin-conversation chunk: "compiler
        for vector space" framing, C#/Rust syntax direction,
        "matrix is the function" duality, "turn cat into dog
        is matrix multiply", "data and functions are the same
        thing" / "practically minded not lambda calculus".
        All five threads have matured into sharper current
        formulations: embedding-as-ISA (paper draft), novelty 1
        (matrix-is-function natively), canonical truth axis
        (equality-and-defuzzification.md), learned-matrix
        binding (binding.md, deferred), homogeneous value
        model (types.md). User verdict: remove.
  - **Pending** (15 chunks): 6 remaining
    `vsa-programming-languages` chunks, 9 remaining
    `vsa-operations-explained` chunks.

### Repo bloat sweep — remaining items

The retired `fly-brain/` directory (47 files), `codegen_flybrain.py`
backend, and `--emit-flybrain` CLI flag are also gone (2026-04-26);
findings docs under `planning/findings/2026-04-1*-*` are preserved
as historical record.

Next bloat sources to investigate:

  - `experiments/` and `planning/findings/` — large but mostly
    paying their way; audit only if something stands out.
  - Cached embeddings, viz HTML siblings (`*_viz.html` from
    `--run-viz`), pyc/__pycache__ leakage.

Recently cleared:
  - `sdk/intellij-sutra/build/` — 1.1 GB local working copy deleted
    2026-04-28. Already in `.gitignore` (line 12) and no files were
    tracked, so no commit needed; this was purely local cleanup.

The principle: anything that is regenerable (build output, caches,
extracted artifacts where the source is preserved elsewhere) should
not be tracked. Anything that takes substantial space and isn't
load-bearing for the language should be revisited.

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
3. **Rotation runs in the synthetic subspace, not on connectome
   weights.** The retired fly-brain investigation established that
   real FlyWire weight matrices do not function as rotation operators
   (they're compressive projections). Synthetic Givens rotations on
   the dedicated subspace are what the language compiles to today.
   Findings: `planning/findings/2026-04-13-shiu-rotate-collapses.md`
   and the cluster of 2026-04-13 / 2026-04-18 docs.
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
   `codegen.py` and `codegen_pytorch.py`. The name `permute` was a
   deprecated alias and is also retired.
7. **Truth is designed as a canonical axis in the synthetic
   subspace.** Spec target in `planning/sutra-spec/equality-and-
   defuzzification.md`. **Implementation status: not yet runtime-
   supported.** `is_true` and defuzzification don't currently
   project onto a dedicated axis; adds with the extended-state-
   vector work.
8. **PyTorch is the compiler's runtime target.** `codegen_pytorch.py`
   emits torch modules picking CUDA at module init. `codegen.py` is
   an internal IR step that `PyTorchCodegen` inherits from and
   post-processes; no longer user-reachable as a separate "numpy
   backend." `--emit` and `--run` go to PyTorch. The fly-brain
   experimental backend was retired 2026-04-26.
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
