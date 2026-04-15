# Sutra — Work Queue

**This file is a queue, not a state snapshot.** When an item is done, delete it. Finished work lives in `git log` and `planning/findings/`. Strategic direction lives in `claw4s-scope.md`.

## Queued work (do in order)

Strategic frame: **Sutra ecosystem > Claw4S.** Anthropic Fellowship (Apr 26) is the goal. Claw4S (Apr 20) is a side-benefit if the language paper happens to be in shape. Every queue item below serves the ecosystem.

### Paper revisions first (cheap, paper-CI auto-submits each push)

1. **Fly-brain paper — re-implement the §6.6 if-statement on the real Shiu fly brain** (the canonical substrate per CLAUDE.md, `C:/Users/Immanuelle/shiu-fly-brain`). The MB-only "if-statement" the paper claimed in §6.6 doesn't actually run on the connectome the way the paper implies — re-do it on Shiu so the headline result is honest. Once it works on Shiu, retitle/scope the paper around that single result and drop the rest.

### Then rebuild the spec from scratch

2. **Build a new `planning/sutra-spec/` from scratch, in the user's framing.** The deprecated spec (`planning/sutra-spec-deprecated/`) was largely Claude inventing structure without checking — see `planning/sutra-spec/README.md` "meta-failure" section. Process: Claude does NOT write into the new spec from scratch. Instead, each section starts as a question to the user; Claude writes down the user's answer in the user's framing; gaps go to `planning/open-questions/` rather than being filled with plausible defaults. Concurrency (item 3) is the natural first section to draft because it's already an open question with user-articulated framing ("two or more paths through the vector space").
3. **Concurrency design as the first new spec section.** Concrete sketch in `planning/sutra-spec/` plus an example program that demonstrates the design. Real work on a language, not a one-line note.

**Hard stop:** if by end of Apr 17 the language paper isn't in submittable state, drop the Claw4S push. The Fellowship pitch (Apr 26) is the actual goal.

## Pinned semantic corrections (I keep dropping these)

1. **`loop[N]` unrolls at compile time. Zero runtime iteration. No eigenrotation.** Only `loop(condition)` with data-dependent termination eigenrotates.
2. **No loop counters live on the host at runtime.** The "counter" for `loop(condition)` IS the angular position on the helix R^i·v₀ in the substrate.
3. **"Rotation on neurons" has two meanings. Don't conflate:**
   - Synthetic R (Givens) as Brian2 synapse weights → works.
   - Real FlyWire weight matrix AS the rotation → does not rotate (compressive projection). Paper must say which every time.
4. **Permute → sign_flip rename.** The op does `a * sign(role)`, not dimension permutation. Aliases preserved.
5. **Numpy is the demo substrate. Fly-brain is segregated.** Two backends: `codegen_numpy.py` (demo path, self-contained, no fly-brain imports) and `codegen_flybrain.py` (fly-brain-specific work, not the demo). PyTorch/GPU is a future refactor target.
6. **Defuzzification polarizes, never binarizes.** `is_true` and `defuzzify` keep the result fuzzy and differentiable. No commit primitive exists; `select` does all branching. Don't reintroduce `gate`.
7. **`bool` is a subclass of `fuzzy`, not crisp.** Carries a defuzz counter as compile-time metadata. Drives method overloading.
8. **Naming heads-up:** `sutra-paper/` is the embedding paper. `language-paper/` is the Sutra-language paper. Legacy from akasha → sutra rename.

## Pointers

- Strategic scope: `claw4s-scope.md`.
- Deprecated spec (read-only reference): `planning/sutra-spec-deprecated/`.
- New spec dir + meta-failure note: `planning/sutra-spec/README.md`.
- Findings (dated): `planning/findings/`.
- Open design questions: `planning/open-questions/`.
- Hardwired assumptions in the demo path: `examples/todo.md`.
