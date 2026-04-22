# Sutra — Work Queue

**This file is a queue, not a state snapshot.** When an item is done, delete it. Finished work lives in `git log` and `planning/findings/`.

The work here is **making Sutra the language actually work** — the compiler, the spec, the substrate-backed runtime, the demo programs. No papers, no submission deadlines. The question each queue item answers is: *what does it take to make this language a real thing someone can use?*

## Queued work

1. ~~Doc-reversal pass~~ **DONE 2026-04-21** (commits `a2a5bd0`, `cf08ad3`, `621d2ed`, `4e24814`). Spec, status, and memory all reflect the sign-flip phase-out.

2. **Capacity experiment for rotation binding.** Design doc at `planning/findings/2026-04-21-rotation-binding-capacity-experiment-design.md` with five concrete experiments. Not yet run. Partial real-world characterization exists in `planning/findings/2026-04-22-rotation-binding-prototype-results.md` — rotation binding passes 10 of 12 smoke tests on the frozen LLM substrate; two partial regressions (`fuzzy_dispatch` 1/4, `sequence` 10/11) look like capacity effects the full experiment would characterize.

3. ~~Surface-syntax re-evaluation~~ **DECIDED 2026-04-21: Candidate B (`role` for semantic, `var` for rotation-bound).** The syntax looks like `role capital_of = learned_from("cities.tsv");` and `var r_name : vector;` / `var[16] slots : vector;`. Parser/compiler support for the new declaration forms is part of queue item 4b.

4. **Compiler-level implementation.** Split into two phases based on priority:

   **4a. Rotation binding: DONE 2026-04-22** (this pass). `codegen_numpy.py` now emits role-seeded Haar-random orthogonal bind/unbind with per-role caching. Sign-flip retired from the demo backend. Four `.su` demos migrated to the role-first convention (see the results findings doc for the migration footprint). Two new `.su` programs demonstrate rotation binding (`rotation_record.su`, `rotation_book_catalog.su`). Rotation-hashmap library-pattern prototype runs as runtime methods (`hashmap_new`/`set`/`get`) and exercises 5/5 exact lookup on nomic-embed-text.

   **4b. Learned-matrix binding: DEFERRED until post-grant-app (~2026-04-29).** Per user priority on 2026-04-22. Work for this item: add a matrix-fitting step at compile time, wire the `role X = learned_from(data)` surface syntax into the parser, emit `R @ filler` runtime for semantic roles. New demo exercising learned-matrix bind (e.g. a location-of-country program using cartography-style displacement data).

   **4c. Extended state vector (synthetic subspace + canonical truth axis): DEFERRED.** The prototype runs rotation binding on the same 768-d semantic subspace rather than a dedicated synthetic subspace (see `planning/findings/2026-04-22-rotation-binding-prototype-design.md` §"The compromise"). Full spec target remains; move after 4b.

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
