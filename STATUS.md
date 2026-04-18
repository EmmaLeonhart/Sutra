# Sutra — Work Queue

**This file is a queue, not a state snapshot.** When an item is done, delete it. Finished work lives in `git log` and `planning/findings/`. Strategic direction lives in `claw4s-scope.md`.

## Queued work (do in order)

Strategic frame: **one last Hail Mary for the papers, low-stress.** User is not heavily invested; the goal is to run the straightforward experiments that should already be in the papers, non-defensively describe the results (positive or null), and let CI resubmit. No iteration cycles on reviewer responses — that is what accumulated the scar tissue in the first place. Anthropic Fellowship (Apr 26) is the real goal; Claw4S (Apr 20) is side-benefit only.

### Hail-Mary experiment queue (autonomous, minimal user input)

1. **Fly-brain: remaining library operations on Shiu substrate.** Bundle (cos=0.97) and snap (15/16) already measured on Shiu. Need unbind, sign-flip-bind, and a direct rotation attempt reported per-op with honest numbers, under the same harness as `shiu_conditional.py`. Budget one script per op. Negative results go in `planning/findings/`.
2. **Many-to-many paper: replicate + extend.** User flagged the paper already got reviewer pushback. Re-run the 9/9 comparison on a cold sample (fresh Wikidata pull, fresh embeddings) to verify. Don't iterate on reviewer response — just re-run, report.
3. **Patch language paper with the GTE-large numbers.** Non-defensive: replace the "placeholder binding" limitation with the actual positive result (continent-of 87%, located-in-country 76% via ridge-0.1 on GTE-large). Frame nomic as a worked null counter-example, not a missing feature. Let papers-ci resubmit.

Substrate evals now complete (done — see findings): GTE-large works
(`2026-04-17-gte-large-learned-matrix-positive.md`), nomic is null
across three text variants (`2026-04-17-wikidata-learned-matrix-null.md`,
`2026-04-17-wikidata-learned-matrix-templates-null.md`,
`2026-04-18-nomic-description-text-still-null.md`).

### Strategic spec/language work (deferred — not the Hail Mary)

5. **Build a new `planning/sutra-spec/` from scratch, in the user's framing.** Deferred until after the Apr 20 window. The deprecated spec (`planning/sutra-spec-deprecated/`) was largely Claude inventing structure. Process: each section starts as a question to the user; Claude writes down the user's framing; gaps go to `planning/open-questions/`.
6. **Concurrency design as the first new spec section.** Concrete sketch plus example program. Real language work.

**Hard stop:** if by end of Apr 19 the papers aren't in submittable state, drop the Claw4S push entirely. Fellowship pitch (Apr 26) is the real goal.

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
