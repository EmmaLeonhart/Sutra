# Sutra — Work Queue

**This file is a queue, not a state snapshot.** When an item is done, delete it. Finished work lives in `git log` and `planning/findings/`. Strategic direction lives in `claw4s-scope.md`.

## Queued work (do in order)

Strategic frame: **one last Hail Mary for the papers, low-stress.** User is not heavily invested; the goal is to run the straightforward experiments that should already be in the papers, non-defensively describe the results (positive or null), and let CI resubmit. No iteration cycles on reviewer responses — that is what accumulated the scar tissue in the first place. Anthropic Fellowship (Apr 26) is the real goal; Claw4S (Apr 20) is side-benefit only.

### Hail-Mary experiment queue (autonomous, minimal user input)

1. **Patch language paper with the GTE-large numbers.** Non-defensive: replace the "placeholder binding" limitation with the actual positive result (continent-of 87%, located-in-country 76% via ridge-0.1 on GTE-large). Frame nomic as a worked null counter-example, not a missing feature. Let papers-ci resubmit.
2. **Patch many-to-many paper with precise metric language.** The paper's "9/9 MRR improvements" claim over-promises on a saturated metric (all methods tie at 1.0). Replace with MAP framing (8/9 full-over-naive, 9/9 full-over-ctrl) or P@k framing (4/9 perfect vs 0/9 baselines). See `2026-04-18-many-to-many-cold-replication.md`.

Done — see findings:
- GTE-large works (`2026-04-17-gte-large-learned-matrix-positive.md`).
- Nomic null across three text variants
  (`2026-04-17-wikidata-learned-matrix-null.md`,
  `2026-04-17-wikidata-learned-matrix-templates-null.md`,
  `2026-04-18-nomic-description-text-still-null.md`).
- Shiu library-op queue resolved: bundle (`2026-04-13-shiu-bundle-linear.md`),
  snap (`2026-04-13-shiu-snap-15-of-16.md`), bind/unbind median-split
  (`2026-04-13-shiu-bind-unbind.md`), bind/unbind top-k balanced
  (`2026-04-18-shiu-bind-topk-mask-also-fails.md`), rotation generic
  (`2026-04-13-shiu-rotate-collapses.md`), rotation CX-restricted
  (`2026-04-13-shiu-cx-no-recurrence.md`). Summary: bundle + snap
  + fuzzy conditional work on real W; bind/unbind and rotation do not
  under any tried encoding. Paper scope already restricted accordingly.
- Many-to-many cold replication
  (`2026-04-18-many-to-many-cold-replication.md`): re-ran the 3×3
  experiment grid. Under MRR all methods tie at 1.0 (saturated).
  Under MAP full structured beats naive 8/9 (one 0.4pt regression
  on all-minilm/Animals), beats ctrl-only 9/9. Paper's "9/9" claim
  survives with metric-precision rewording (queued above).

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
