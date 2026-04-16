# Sutra — Work Queue

**This file is a queue, not a state snapshot.** When an item is done, delete it. Finished work lives in `git log` and `planning/findings/`. Strategic direction lives in `claw4s-scope.md`.

## Queued work (do in order)

Strategic frame: **Sutra ecosystem > Claw4S.** Anthropic Fellowship (Apr 26) is the goal. Claw4S (Apr 20) is a side-benefit if the language paper happens to be in shape. Every queue item below serves the ecosystem.

### Paper revisions first (cheap, paper-CI auto-submits each push)

### Then rebuild the spec from scratch

1. **Build a new `planning/sutra-spec/` from scratch, in the user's framing.** The deprecated spec (`planning/sutra-spec-deprecated/`) was largely Claude inventing structure without checking — see `planning/sutra-spec/README.md` "meta-failure" section. Process: Claude does NOT write into the new spec from scratch. Instead, each section starts as a question to the user; Claude writes down the user's answer in the user's framing; gaps go to `planning/open-questions/` rather than being filled with plausible defaults. Concurrency (item 2) is the natural first section to draft because it's already an open question with user-articulated framing ("two or more paths through the vector space").
2. **Concurrency design as the first new spec section.** Concrete sketch in `planning/sutra-spec/` plus an example program that demonstrates the design. Real work on a language, not a one-line note.

**Hard stop:** if by end of Apr 17 the language paper isn't in submittable state, drop the Claw4S push. The Fellowship pitch (Apr 26) is the actual goal.

## Pinned semantic corrections (I keep dropping these)

1. **`loop[N]` unrolls at compile time. Zero runtime iteration. No eigenrotation.** Only `loop(condition)` with data-dependent termination eigenrotates.
2. **No loop counters live on the host at runtime.** The "counter" for `loop(condition)` IS the angular position on the helix R^i·v₀ in the substrate.
3. **"Rotation on neurons" has two meanings. Don't conflate:**
   - Synthetic R (Givens) as Brian2 synapse weights → works.
   - Real FlyWire weight matrix AS the rotation → does not rotate (compressive projection). Paper must say which every time.
4. **Roles are learned matrices; `bind` is `R @ filler`.** Not random vectors (HRR), not sign-flip (`a * sign(role)`). A role in Sutra is a matrix fit to the substrate — "object of a sentence" is the matrix fit on (sentence_emb, object_emb) pairs; `is_cat` is the matrix fit on (thing_emb, is_cat_label) pairs. Unifies with `is_cat` and defuzz matrices. Empirical grounding: cartography's 86-predicate displacement finding (r=0.861) is the rank-0 special case. Full-matrix generalization for sentence-level roles is not yet verified in nomic — open experiment. See `planning/sutra-spec/operations.md` §"Roles are matrices."
5. **Sign-flip binding is rejected.** The current `bind` in both codegens compiles to `a * sign(role)` as a historical artifact, not a design choice. Treat as pending removal. `sutra-paper/` is still titled *"Sign-Flip Binding…"* — retitling + refounding is queued in `todo.md`.
6. **Permute → sign_flip rename.** The deprecated op name `permute` aliased to sign-flip; now that sign-flip itself is rejected, both names are tombstones.
7. **Numpy is the demo substrate. Fly-brain is segregated.** Two backends: `codegen_numpy.py` (demo path, self-contained, no fly-brain imports) and `codegen_flybrain.py` (fly-brain-specific work, not the demo). PyTorch/GPU is a future refactor target.
8. **Defuzzification polarizes, never binarizes.** `is_true` and `defuzzify` keep the result fuzzy and differentiable. No commit primitive exists; `select` does all branching. Don't reintroduce `gate`.
9. **`bool` is a subclass of `fuzzy`, not crisp.** Carries a defuzz counter as compile-time metadata. Drives method overloading.
10. **Naming heads-up:** `sutra-paper/` is the embedding paper. `language-paper/` is the Sutra-language paper. Legacy from akasha → sutra rename.

## Pointers

- Strategic scope: `claw4s-scope.md`.
- Deprecated spec (read-only reference): `planning/sutra-spec-deprecated/`.
- New spec dir + meta-failure note: `planning/sutra-spec/README.md`.
- Findings (dated): `planning/findings/`.
- Open design questions: `planning/open-questions/`.
- Hardwired assumptions in the demo path: `examples/todo.md`.
