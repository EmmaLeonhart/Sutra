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

**Today's priority: trim repo bloat (2026-04-25).** The repo has
accumulated weight that doesn't pay for itself. First sweep already
landed: `chats/` lost ~40 MB by extracting the five remaining HTML
exports to markdown and deleting the `.html` + `_files/` browser-
asset directories (commit 438dace). chats/README.md and CLAUDE.md
updated to reflect the new policy (markdown is canonical; HTMLs go
after extraction).

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

**Website HTTPS cert — manual user action required.** sutralang.dev
serves 200 OK over both HTTP and HTTPS (verified 2026-04-24), but
the TLS cert being presented on port 443 is GitHub's default wildcard
`*.github.io` instead of a Let's Encrypt cert for `sutralang.dev`.
That's why browsers reject the connection with `ERR_TLS_CERT_
ALTNAME_INVALID`. GitHub Actions deploys are succeeding (last three
runs all `success`); `docs/CNAME` and `_site/CNAME` both pin
`sutralang.dev` correctly.

**The fix has to happen in the GitHub UI, not in this repo.** Visit:
`https://github.com/EmmaLeonhart/Sutra/settings/pages`. Check that:

  1. Custom domain shows `sutralang.dev` with a green "DNS check
     successful" indicator. If it's missing or red, re-save the
     domain field and wait for DNS validation.
  2. The "Enforce HTTPS" checkbox is checked. If greyed out, Let's
     Encrypt hasn't provisioned the cert yet — wait ~15 min, refresh,
     try again. Provisioning can stall after a DNS change; the usual
     fix is to remove the custom domain, save, re-add it, save, wait
     for DNS check, tick Enforce HTTPS.

If Enforce HTTPS is ticked and the cert is still wrong after 24 hours,
open a support ticket with GitHub — cert provisioning is their side.

**Egglog integration — algebraic-simplification backend.** The
current hand-written `simplify.py` (900 lines, 16 rules) covers the
basics but doesn't do matrix-chain composition, linearity analysis,
or CSE — the three passes that would let the global-efficiency story
(every tensor-op program fuses into one kernel) actually realize.
Research pass 2026-04-24 landed on `egglog` (actively maintained
Python e-graph library, v13, supports matrix-valued expressions,
direct precedent in `sdiehl/mlir-egglog` for numpy→compiler-IR
exactly). Plan: replace the hand-rolled rewrites in `simplify.py`
with an egglog-driven pass that subsumes them + adds the three
missing passes.

  - [x] ~~Install `egglog` (`pip install egglog`) and smoke-test
    Python 3.13 import.~~ DONE 2026-04-24. v13.1.0 installs cleanly,
    5/5 rewrite rules fire correctly in
    `experiments/egglog_smoke_test.py`.
  - [x] ~~Proof-of-concept: matrix-chain fusion with a cost model.~~
    DONE 2026-04-24. `experiments/egglog_matrix_chain_fusion.py`
    takes nested `Mn.apply(...M2.apply(M1.apply(v)))` chains of
    lengths 2-5 and extracts the fully-fused `(Mn @ ... @ M1).apply(v)`
    form via a cost model that charges 100/apply (hot path) and 1/matmul
    (module init). All chain lengths fuse to exactly one apply. This is
    the pass `simplify.py` does not have today.
  - [ ] Lift the 16 existing rewrites from `simplify.py` into egglog
    rule form. Validate equivalence against the existing 206-test
    suite. Next step.
  - [ ] Wire egglog-based simplification into the compiler pipeline
    as a post-pass on the existing `simplify.py` output (safer
    than replacing it in one shot — incremental migration).
  - [ ] Add linearity analysis: function bodies that are pure
    linear tensor-op compositions get a single cached matrix M and
    compile-down to `M @ arg`. Builds on the matrix-chain fusion.
  - [ ] CSE pass — comes almost free from equality saturation; just
    needs the extraction cost to charge per-use.

Follow-ups surfaced during the 2026-04-24 pre-Anthropic-grant-app
sprint that aren't urgent-next but should land pre-YC:

1. **Sutra-language surface syntax for slot primitives.** The
   runtime (`slot_store` / `slot_load` / `rotate_slot` on `_VSA`)
   landed 2026-04-24 and passes all four reversibility tests — but
   there is no `.su` syntax that compiles to them. Pick a surface
   (`var x : int = 0;` with the compiler allocating a slot? an
   explicit `slot[N] x;` declaration? `@slot` annotation?) and wire
   it through parser + validator + codegen. Unlocks the
   imperative-reversible demo programs.

2. **Spec-text refresh for the synthetic-subspace design.** The
   design doc
   (`planning/findings/2026-04-21-extended-state-and-rotation-binding.md`)
   has been empirically validated (`planning/findings/2026-04-24-
   synthetic-subspace-validation.md`) and the runtime primitive is
   in. `planning/sutra-spec/binding.md` still describes rotation
   binding in the synthetic subspace as a design target rather than
   a committed primitive — needs refresh, and the "pending
   experimental validation" language on the 2D-Givens-per-slot design
   should come out.

3. **Imperative-reversible demo `.su` program.** Once (1) lands, a
   demo that writes `x = a; x = b; x = a;` at the source level and
   compiles to `slot_store` calls, provably producing the same
   runtime state as a single `x = a;`. Pedagogical payoff for the
   "variable assignment is a pure transform of state" commitment.

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
