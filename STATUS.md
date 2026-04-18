# Sutra — Work Queue

**This file is a queue, not a state snapshot.** When an item is done, delete it. Finished work lives in `git log` and `planning/findings/`.

The work here is **making Sutra the language actually work** — the compiler, the spec, the substrate-backed runtime, the demo programs. No papers, no submission deadlines. The question each queue item answers is: *what does it take to make this language a real thing someone can use?*

## Queued work

1. **Replace sign-flip `bind` with learned-matrix `bind` in the numpy backend.** The current `bind(role, filler)` in `codegen_numpy.py` compiles to `filler * sign(role)` — a historical placeholder. The spec calls for `R · filler` where R is a matrix learned from (input, output) pairs in the embedding substrate. This means: (a) pick a substrate for the demo (GTE-large has known-working numbers; nomic collapses), (b) add a matrix-fitting step to the compiler so a `role "located-in-country"` declaration fits an R matrix at compile time, (c) make `bind` at runtime be `R @ filler`, (d) make `unbind` be `R⁻¹ @ bound` (or `R^T` when orthogonal). The three demo programs keep passing either way because their roles are arbitrary tags, but the semantic-binding path needs to exist for anything beyond toys.

2. **Rebuild `planning/sutra-spec/` from scratch in the user's framing.** The deprecated spec (`planning/sutra-spec-deprecated/`) was largely Claude inventing structure. Process: each spec section starts as a question posed to the user; Claude writes down the user's framing; gaps go to `planning/open-questions/`. Current scaffolding in `planning/sutra-spec/README.md` lists what's already sketched. The spec is load-bearing per CLAUDE.md — the implementation has to match it — so the rewrite is not optional.

3. **Concurrency as the first new spec section.** Concrete sketch plus an example `.su` program. Real language work — concurrency is a genuinely open question (see `planning/sutra-spec/concurrency.md` if it exists, else an open-question doc).

4. **Hook the numpy backend to a real frozen LLM.** Today `codegen_numpy.py` draws fresh random vectors. Per the architecture, the embedding substrate (nomic-embed-text, mean-centered, 768-d) should be what demos actually run against. Requires: Ollama-backed vector lookup at runtime, cached codebook, mean-centering discipline.

5. **Demonstrate `loop(cond)` end-to-end.** The compiler implements data-dependent iteration but no demo exercises it. Writing a `.su` program that uses `loop(cond)` with a genuine data-dependent termination condition (not a `loop[N]` unroll) would prove out the part of the language that `loop[N]` doesn't.

6. **PyTorch/GPU backend.** `codegen_numpy.py` compiles to matmuls, sums, and cosines — every operation has a trivial GPU equivalent. The port is a mechanical refactor of the code-emission layer, not a rewrite. Do this only after items 1 and 2 are settled so the spec being targeted is stable.

## Pinned semantic corrections (I keep dropping these)

1. **`loop[N]` unrolls at compile time. Zero runtime iteration. No eigenrotation.** Only `loop(condition)` with data-dependent termination eigenrotates.
2. **No loop counters live on the host at runtime.** The "counter" for `loop(condition)` IS the angular position on the helix R^i·v₀ in the substrate.
3. **"Rotation on neurons" has two meanings. Don't conflate:**
   - Synthetic R (Givens) as Brian2 synapse weights → works.
   - Real FlyWire weight matrix AS the rotation → does not rotate (compressive projection).
4. **Roles are learned matrices; `bind` is `R @ filler`.** Not random vectors (HRR), not sign-flip (`a * sign(role)`). A role in Sutra is a matrix fit to the substrate — "object of a sentence" is the matrix fit on (sentence_emb, object_emb) pairs; `is_cat` is the matrix fit on (thing_emb, is_cat_label) pairs. Unifies with `is_cat` and defuzz matrices. See `planning/sutra-spec/operations.md` §"Roles are matrices."
5. **Sign-flip binding is rejected as the headline.** The current `bind` in both codegens compiles to `a * sign(role)` as a historical artifact, not a design choice. Treat as pending removal (queue item 1). Sign-flip remains a legitimate non-semantic binding mode; it is just not what semantic `bind` means.
6. **Permute → sign_flip rename.** The deprecated op name `permute` aliased to sign-flip; now that sign-flip is no longer the headline binding, both names are tombstones except where explicitly used as non-semantic.
7. **Numpy is the demo substrate. Fly-brain is segregated.** Two backends: `codegen_numpy.py` (demo path, self-contained, no fly-brain imports) and `codegen_flybrain.py` (fly-brain-specific work, not the demo). PyTorch/GPU is a future refactor target.
8. **Defuzzification polarizes, never binarizes.** `is_true` and `defuzzify` keep the result fuzzy and differentiable. No commit primitive exists; `select` does all branching. Don't reintroduce `gate`.
9. **`bool` is a subclass of `fuzzy`, not crisp.** Carries a defuzz counter as compile-time metadata. Drives method overloading.

## Pointers

- Deprecated spec (read-only reference): `planning/sutra-spec-deprecated/`.
- New spec dir + meta-failure note: `planning/sutra-spec/README.md`.
- Findings (dated): `planning/findings/`.
- Open design questions: `planning/open-questions/`.
- Hardwired assumptions in the demo path: `examples/todo.md`.
