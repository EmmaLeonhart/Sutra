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

2. **PyTorch/GPU backend.** `codegen_numpy.py` compiles to matmuls,
   sums, and cosines — every operation has a trivial GPU equivalent.
   The compile-side prerequisites for the port landed 2026-04-22:
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

   **What still blocks the port:** actually writing the pytorch
   backend (mechanical — swap `_np` for `_torch`, keep the fused
   shapes). Generalized ANF + dep analysis is NOT done — only the
   `bundle(bind,bind,...)` pattern is currently fused; other
   potentially-independent sequences (e.g. `bundle(bind(r,f), c,
   bind(r2,f2))`) still emit sequentially. For the three demo
   programs (hello_world, fuzzy_branching, role_filler_record) the
   fused shapes cover the hot path; larger programs may hit the
   sequential fallback and want broader dep analysis.

3. **CUDA-prerequisite simplifications** (2026-04-23 review). These
   are cleanup items identified during the cuda-simplification
   review — every one is a mechanical, reviewable change that makes
   the PyTorch/GPU port in queue item 2 substantially smaller. They
   are numbered so they can be worked sequentially.

   3a. **Extract `_NumpyVSA` runtime into a real `runtime_numpy.py`
       file.** Today the entire VSA runtime (~500 lines) lives inside
       `codegen_numpy.py` as a stream of `self._emit("...")` calls
       (codegen_numpy.py:120-633). The file cannot be linted, typed,
       or tested as Python — only as a string-building pass. The GPU
       port would duplicate the whole emit stream. Fix: move the
       runtime into `sdk/sutra-compiler/sutra_compiler/runtime_numpy.py`,
       have the codegen inline its text verbatim into the prelude.
       Highest-leverage item — every cleanup below becomes trivial
       once this lands, and the PyTorch port reduces to a new
       `runtime_torch.py` file plus a ~30-line dispatch swap.

   3b. **Deduplicate runtime helpers.** `_argmax_cosine` and
       `_vector_map_lookup` have byte-for-byte identical cosine-stack
       logic (codegen_numpy.py:572-633). `embed` and `embed_batch`
       duplicate mean-center/normalize/pad/truncate (lines 242-320).
       Fold each pair onto a shared helper once 3a makes the runtime
       a real file.

   3c. **Vectorize `_NumpyVSA.loop` prototype match.** Currently
       (codegen_numpy.py:528-556) iterates host-side in Python with
       an inner for-loop over prototypes calling `self.similarity`
       per prototype per iteration. Stack prototypes into `(P, d)`
       once at loop entry; per iteration do one `(P, d) @ (d,)`
       matmul. Same shape the GPU version will reuse.

   3d. **Simplify `make_random_rotation`.** Original claim in this
       queue item was that the fractional-matrix-power branch was
       dead code (no demo uses a non-π angle). **That audit was
       wrong** — the loop-using demos (`concept_search.su`,
       `counter_loop.su`, `loop_rotation.su`) go through the
       eigenrotation-loop emit path that hardcodes `angle=1.0`,
       which IS a non-π angle, so the eigendecomposition branch
       runs on every loop construct. The original "drop it" plan
       would have broken live code. Noted as a self-caught shortcut
       per CLAUDE.md.
       Real simplification actually applied: `Q` is real orthogonal
       (hence normal), so its eigenvector matrix `V` from
       `_np.linalg.eig(Q)` is unitary, and `_np.linalg.inv(V) ==
       V.conj().T` to machine precision. Swap the O(d³) explicit
       inversion for the O(d²) conjugate transpose. Same numerical
       result, much cheaper — especially at the 768-dim substrate.
       Also: `make_random_rotation` runs once per loop construct at
       R-construction time (compile-time for R, not hot-path), so
       eigendecomp cost itself is not a CUDA concern; the inv→conj.T
       swap is pure quality-of-implementation.

   3e. **Flatten `NumpyCodegen → FlyBrainCodegen` inheritance.** The
       numpy backend inherits from the fly-brain backend purely to
       reuse AST-walking code; the two emit completely different
       runtimes. The inheritance bleeds fly-brain assumptions into
       numpy init (`runtime_n_kc=0`, `use_hemibrain=False` passed to
       `super().__init__`) and forces future `TorchCodegen` to pick
       a parent. Extract a `CodegenBase` with just the AST walker;
       make each backend a sibling.

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
