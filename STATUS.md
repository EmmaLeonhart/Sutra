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

1. **Extended state vector — reserve 100 synthetic dimensions.**
   User direction 2026-04-23: *"just have it so that there are 100
   dimensions... we have n semantic dimensions, and then we have
   100 programming dimensions. The 100 programming dimensions are
   not ones that we're all going to be using, but we're essentially
   reserving them in all of our working stuff for the stuff that
   we actually need. That's just simple."*

   Minimum scope for this pass: runtime dim becomes
   `semantic_dim + 100` everywhere. `embed()` produces
   `[semantic | zeros]`. Rotation bind acts block-diagonally —
   Q_semantic in the top-left, identity in the synthetic block —
   so the synthetic 100 stays reserved (zero-preserved) until
   something explicitly uses it. All three demo programs
   (hello_world, fuzzy_branching, role_filler_record) must still
   pass. Full test suite must stay green.

   Out of scope for this pass (follow-ons in todo.md):
   - Moving rotation binding into the synthetic subspace (per-slot
     2D Givens planes).
   - Designating the canonical truth axis in the synthetic subspace
     + wiring `is_true` / defuzzification to project onto it.
   - Per-variable synthetic-axis allocation at compile time.

   The "reserve the space first" step is a prerequisite for the
   PyTorch/GPU backend and for the follow-ons above — everything
   downstream assumes the state is already extended.

2. **PyTorch/GPU backend.** Sequenced after item 1 — the torch port
   must run on the extended state, not the pre-extension 768-d.
   `codegen_numpy.py` compiles to matmuls, sums, and cosines — every
   operation has a trivial GPU equivalent. The compile-side
   prerequisites landed 2026-04-22:
   - Algebraic simplifier rewrites (bundle/compose flattening,
     similarity-of-self, unbind/bind and bind/unbind inverses,
     displacement-of-self → zero, zero-absorption in + / − / bundle).
   - Vectorized `argmax_cosine` and vector-map-lookup — one stacked
     matmul instead of N sequential `_VSA.similarity` calls. Same
     shape torch/CUDA wants.
   - Fused `bundle_of_binds` — when every arg to `bundle(...)` is a
     `bind(...)` call (the role-filler-record pattern), the codegen
     emits a single runtime call that does the N binds as one batched
     einsum over (N, d, d) Q-stack × (N, d) filler-stack. O(N) kernel
     launches collapse to O(1).
   - Runtime embedding disk cache (`~/.cache/sutra/embeddings/
     <model>-d<dim>.npz`). Second run is offline.

   **What still blocks the port:** item 1 first, then the mechanical
   torch rewrite (swap `_np` for `_torch`, keep the fused shapes).
   Generalized ANF + dep analysis is NOT done — only the
   `bundle(bind,bind,...)` pattern is currently fused; other
   potentially-independent sequences (e.g. `bundle(bind(r,f), c,
   bind(r2,f2))`) still emit sequentially. For the three demo
   programs (hello_world, fuzzy_branching, role_filler_record) the
   fused shapes cover the hot path; larger programs may hit the
   sequential fallback and want broader dep analysis.

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
