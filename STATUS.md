# Sutra — Work Queue

**This file is a queue, not a state snapshot.** When an item is done, delete it. Finished work lives in `git log` and `planning/findings/`.

The work here is **making Sutra the language actually work** — the compiler, the spec, the substrate-backed runtime, the demo programs. No papers, no submission deadlines. The question each queue item answers is: *what does it take to make this language a real thing someone can use?*

## Queued work

1. **Doc-reversal pass for the sign-flip phase-out.** The 2026-04-21 design session settled on a new binding model: state is an extended vector `[semantic_dims | synthetic_dims]`, rotation binding in the synthetic subspace replaces sign-flip, truth is a designated canonical axis, sign-flip is retired. See `planning/findings/2026-04-21-extended-state-and-rotation-binding.md`. Earlier commits that morning (`a2a5bd0`, `cf08ad3`, `621d2ed`) committed the now-stale framing that sign-flip is first-class. Reverse across: `STATUS.md` (this file, pinned items), `planning/sutra-spec/binding.md`, `planning/sutra-spec/vision.md`, `planning/sutra-spec/equality-and-defuzzification.md` (canonical truth axis), `planning/open-questions/binding-kind-surface-syntax.md` (mark for re-evaluation), and the memory file `feedback_no_sign_flip.md`.

2. **Capacity experiment for rotation binding in the synthetic subspace.** Before the rotation-binding design moves from findings into spec, validate it empirically. Concrete experiment: allocate N/2 variable slots with 2D-Givens-plane-per-slot allocation in a synthetic subspace of N dims (N ∈ {16, 32, 64, 128}); bundle random fuzzy values across all slots; read back each slot; measure recovery accuracy vs. capacity. Verify zero-cross-talk property holds in practice (not just in theory), verify truth-axis orthogonality under bind/bundle, verify reversibility round-trip for a sequence of assignments. See `planning/findings/2026-04-21-extended-state-and-rotation-binding.md` §"What remains to validate empirically."

3. **Surface-syntax re-evaluation with the new two-kinds model.** `planning/open-questions/binding-kind-surface-syntax.md` was drafted when the two kinds were sign-flip vs. learned-matrix. The kinds are now semantic (learned-matrix) vs. rotation, and "structural" now means rotation binding rather than sign-flip. Candidates A–E may re-sort; D (`role<semantic>` / `role<rotation>`) or C (inferred-from-RHS) likely dominate. Revisit, pick a winner, add the chosen syntax to `planning/sutra-spec/binding.md`, close the open question.

4. **Implement rotation binding + learned-matrix bind in the compiler.** Once items 1–3 settle the design and syntax: add the extended-state-vector runtime (semantic + synthetic subspace layout), implement rotation bind as 2D-Givens-plane-per-slot in the synthetic subspace, implement learned-matrix bind with a compile-time matrix-fitting step, migrate the three demo programs off sign-flip onto rotation binding. Remove sign-flip support after migration.

5. **Rebuild `planning/sutra-spec/` from scratch in the user's framing.** The deprecated spec (`planning/sutra-spec-deprecated/`) was largely Claude inventing structure. Process: each spec section starts as a question posed to the user; Claude writes down the user's framing; gaps go to `planning/open-questions/`. Current scaffolding in `planning/sutra-spec/README.md` lists what's already sketched. Partially in progress via the doc-reversal pass (item 1). The spec is load-bearing per CLAUDE.md — the implementation has to match it — so the rewrite is not optional.

6. **Concurrency as a new spec section.** Concrete sketch plus an example `.su` program. Real language work — concurrency is a genuinely open question (see `planning/sutra-spec/concurrency.md`).

7. **Hook the numpy backend to a real frozen LLM.** Today `codegen_numpy.py` draws fresh random vectors. Per the architecture, the embedding substrate (nomic-embed-text, mean-centered, 768-d) should be what demos actually run against. Requires: Ollama-backed vector lookup at runtime, cached codebook, mean-centering discipline.

8. **Demonstrate `loop(cond)` end-to-end.** The compiler implements data-dependent iteration but no demo exercises it. Writing a `.su` program that uses `loop(cond)` with a genuine data-dependent termination condition (not a `loop[N]` unroll) would prove out the part of the language that `loop[N]` doesn't.

9. **PyTorch/GPU backend.** `codegen_numpy.py` compiles to matmuls, sums, and cosines — every operation has a trivial GPU equivalent. The port is a mechanical refactor of the code-emission layer, not a rewrite. Do this only after items 4 and 5 are settled so the spec being targeted is stable.

## Pinned semantic corrections (I keep dropping these)

1. **`loop[N]` unrolls at compile time. Zero runtime iteration. No eigenrotation.** Only `loop(condition)` with data-dependent termination eigenrotates.
2. **No loop counters live on the host at runtime.** The "counter" for `loop(condition)` IS the angular position on the helix R^i·v₀ in the substrate.
3. **"Rotation on neurons" has two meanings. Don't conflate:**
   - Synthetic R (Givens) as Brian2 synapse weights → works.
   - Real FlyWire weight matrix AS the rotation → does not rotate (compressive projection).
4. **Semantic roles are learned matrices; semantic `bind` is `R @ filler`.** Not random vectors (HRR), not sign-flip. A *semantic* role in Sutra is a matrix fit to the substrate — "object of a sentence" is the matrix fit on (sentence_emb, object_emb) pairs; `is_cat` is the matrix fit on (thing_emb, is_cat_label) pairs. Unifies with `is_cat` and defuzz matrices. See `planning/sutra-spec/operations.md` §"Roles are matrices." (Structural roles — variable storage, array positions — use rotation binding; see item 5.)
5. **Sutra has two binding kinds: semantic (learned-matrix) and rotation.** Semantic binding acts in the semantic subspace (real frozen-LLM embedding dims) and carries meaning. Rotation binding acts in the synthetic subspace (a small number of dedicated computational dimensions) and handles opaque variable storage, array positions, and reversible imperative-style assignment. The two subspaces are structurally orthogonal, so operations in one cannot contaminate the other. See `planning/findings/2026-04-21-extended-state-and-rotation-binding.md` for the full design.
6. **Sign-flip binding is retired.** Earlier versions treated sign-flip as a first-class structural kind; rotation binding in the synthetic subspace strictly dominates it (zero cross-talk by construction, ordered structure, reversibility, natural fit for imperative-style state). Sign-flip is still in the codegen as the current implementation of `bind` in `codegen_numpy.py`, pending migration to rotation binding (queue item 4). The name `permute` was a deprecated alias and is also retired.
7. **Truth is a canonical axis in the synthetic subspace.** One designated antipodal dimension; `true = +1`, `false = -1`, fuzzy values are continuous between. Because the synthetic subspace is structurally orthogonal to the semantic subspace, semantic vectors have zero projection onto the truth axis by construction — truth is decorrelated from meaning. Other canonical synthetic axes may be designated later (integer, enum, position, time) to support other data types through VSA.
8. **Numpy is the demo substrate. Fly-brain is segregated.** Two backends: `codegen_numpy.py` (demo path, self-contained, no fly-brain imports) and `codegen_flybrain.py` (fly-brain-specific work, not the demo). PyTorch/GPU is a future refactor target.
9. **Defuzzification polarizes, never binarizes.** `is_true` and `defuzzify` keep the result fuzzy and differentiable. No commit primitive exists; `select` does all branching. Don't reintroduce `gate`.
10. **`bool` is a subclass of `fuzzy`, not crisp.** Carries a defuzz counter as compile-time metadata. Drives method overloading. A bool value is a scalar on the canonical truth axis.

## Pointers

- Deprecated spec (read-only reference): `planning/sutra-spec-deprecated/`.
- New spec dir + meta-failure note: `planning/sutra-spec/README.md`.
- Findings (dated): `planning/findings/`.
- Open design questions: `planning/open-questions/`.
- Hardwired assumptions in the demo path: `examples/todo.md`.
