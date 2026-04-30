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

### RNN-style loop execution — DONE 2026-04-30

`loop(cond)` rewired as a branchless RNN unroll. T fixed cell steps
(default 50), no host-side `for iters in range`, no host-side `if
best_score >= threshold`. Soft halt via sigmoid + monotone cumulative
freezes state once convergence; output gating multiplies value axes
by `halt_cum` so a non-converging loop emits a near-zero output. New
canonical synthetic axis `AXIS_LOOP_DONE = 4` carries the cumulative
halt as the substrate-side completion flag (loop-specific instance of
the broader exception-channel pattern — divide-by-zero, NaN
propagation TBD).

Architecture: non-looping Sutra programs = MLP (forward pass);
looping Sutra programs = RNN (recurrent forward pass). Both
branchless on the substrate. cos / sin are still the eigenrotation
primitive (chat's design that worked); the new piece is the soft-
halt cell + output gating.

Tests: `sdk/sutra-compiler/tests/test_branchless_loop.py` (7 PASS) +
80 broader codegen tests still green. Spec updated
`planning/sutra-spec/control-flow.md`.

### Transcendentals — DONE 2026-04-29

All seven math intrinsics (`exp`, `log`, `sin`, `cos`, `tan`,
`sqrt`, `pow`) wired with substrate-pure runtime methods on both
backends. 34/34 dedicated tests PASS plus the full 266-test suite.

Architecture (substantively different from the chat sketch):
- **cos / sin** via the eigenrotation primitive (R(theta) applied
  to (1, 0)) — exactly as the chat described. FP precision.
- **realExp** via degree-25 Taylor + 5-pass squaring range reduction.
- **realLog** via `math.frexp` range reduction + degree-30 artanh
  series (FP precision across float64 range).
- **complex exp / log** compose; **sqrt / pow / tan** derive from
  exp / log / sin / cos.

The chat's bound-table-via-binding architecture for exp / ln did
not pencil out — the 2-scalar bundle has fundamental capacity
limits for non-periodic functions. Empirical finding written up
in `planning/findings/2026-04-29-bound-table-capacity-limit.md`
with `experiments/bound_table_transcendentals.py` as reproducer.
cos / sin are the part of the chat's design that DID work
exactly (because rotation IS the trig primitive there).

Chat retained in `chats/` as working reference; no formal triage
needed since the implementation work landed.

### Repo bloat sweep — flagged item

The retired `fly-brain/` directory (47 files), `codegen_flybrain.py`
backend, and `--emit-flybrain` CLI flag are also gone (2026-04-26);
findings docs under `planning/findings/2026-04-1*-*` are preserved
as historical record.

**Flagged for user decision:** local `fly-brain/` working copy is
**101 MB** as of 2026-04-29. The directory is gitignored
(`.gitignore` line 39 with the explanation that the user keeps it
locally for "possible future revival" with the canonical copy at
`C:\Users\Immanuelle\flybrain\`). Not deleting without an explicit
ask — but worth confirming whether the local mirror is actively
needed or whether it can be reclaimed (the canonical copy lives
outside the repo).

Recently cleared:
  - `sdk/intellij-sutra/build/` — 1.1 GB local working copy deleted
    2026-04-28. Already in `.gitignore` (line 12), no files tracked.
  - 9 `examples/*_trace.json` (~52 KB) + 3 `__pycache__` dirs in
    `examples/`, `sdk/sutra-compiler/sutra_compiler/`, and
    `sdk/sutra-compiler/tests/` (~1.16 MB) — deleted 2026-04-29.
    All gitignored and regenerable.

Not cleared (regen cost > storage cost):
  - `~/.cache/sutra/` — 1.9 MB embedding cache. Refetching from
    Ollama is slow and the cache is small enough to leave.

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
