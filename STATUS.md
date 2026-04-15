# Sutra — Work Queue

**This file is a queue, not a state snapshot.** When an item is done, delete it. Finished work lives in `git log` and `planning/findings/`. Strategic direction lives in `claw4s-scope.md`.

## Queued work (do in order)

Strategic frame: **Sutra ecosystem > Claw4S.** Anthropic Fellowship (Apr 26) is the goal. Claw4S (Apr 20) is a side-benefit if the language paper happens to be in shape. Every queue item below serves the ecosystem.

### Language paper (`language-paper/paper.md`) — recurring v1–v5 reject reasons, all cheap

1. **Reword self-citations.** Drop the "Leonhart (2026)" form that the AI reviewer keeps flagging as hallucinated future-dated. Use descriptive titles only ("Leonhart, *Latent space cartography…*"); never name a venue or year.
2. **Drop `gate` from §2/§3, present `select` / `select else` / single-option threshold per the new spec §26.** Reviewers v1, v2, v4 still list both as primitives. The §26 change just landed; the paper has to match.
3. **Add a `loop(cond)` example to the demo set.** The paper defines `loop(cond)` but never exercises it; `examples/` should have something looping. The compiler already supports it — should be straightforward.
4. **Demonstrate Turing-completeness instead of asserting it.** One Rule-110-shaped snippet, or a counter-in-`loop(cond)`, in the paper text plus `examples/`.

### Sutra paper (`sutra-paper/paper.md`)

5. **Same self-citation reword.** 10-minute fix; same recurring complaint.
6. **Expand evaluation using Wikidata.** Mirror the approach the old VSA paper (in a separate repo, do not edit here) used: pull a structured Wikidata corpus and evaluate the sign-flip binding / VSA ops at meaningful scale. Replaces the "10/10 chained steps is statistically insignificant" complaint that recurs across v1–v14.

### Fly-brain paper (`fly-brain-paper/paper.md`)

7. **Re-implement the §6.6 if-statement on the real Shiu fly brain** (the canonical substrate per CLAUDE.md, `C:/Users/Immanuelle/shiu-fly-brain`). The MB-only "if-statement" the paper claimed in §6.6 doesn't actually run on the connectome the way the paper implies — re-do it on Shiu so the headline result is honest. Once it works on Shiu, retitle/scope the paper around that single result and drop the rest.

### Concurrency (harder, but do not skip)

8. **Concurrency design.** Real work on a language, not a one-line note. Open-question doc is updated with "two or more paths through the vector space" framing; the next step is a concrete sketch in `planning/sutra-spec/` and an example program. Not in scope for Apr 26 unless the earlier items finish quickly.

**Hard stop:** if by end of Apr 17 the language paper isn't in submittable state, drop the Claw4S push. The Fellowship pitch (Apr 26) is the actual goal.

## Pinned semantic corrections (I keep dropping these)

1. **`loop[N]` unrolls at compile time. Zero runtime iteration. No eigenrotation.** Only `loop(condition)` with data-dependent termination eigenrotates. Spec: `planning/sutra-spec/03-control-flow.md`.
2. **No loop counters live on the host at runtime.** The "counter" for `loop(condition)` IS the angular position on the helix R^i·v₀ in the substrate.
3. **"Rotation on neurons" has two meanings. Don't conflate:**
   - Synthetic R (Givens) as Brian2 synapse weights → works.
   - Real FlyWire weight matrix AS the rotation → does not rotate (compressive projection). Paper must say which every time.
4. **Permute → sign_flip rename.** The op does `a * sign(role)`, not dimension permutation. Spec's `permute` means shuffle. Aliases preserved.
5. **Numpy is the demo substrate. Fly-brain is segregated.** The compiler has two backends: `codegen_numpy.py` (demo path, self-contained, no fly-brain imports) and `codegen_flybrain.py` (fly-brain-specific work, not the demo). PyTorch/GPU is a future refactor target.

## Pointers

- Strategic scope & Apr 20 build list: `claw4s-scope.md`.
- Formal Sutra grammar (EBNF): `planning/sutra-spec/24-grammar.ebnf` (prose wrapper: `24-grammar.md`).
- Spec: `planning/sutra-spec/{02-operations,03-control-flow,04-defuzzification,11-vsa-math,19-substrate-candidates}.md`.
- Findings (dated): `planning/findings/`.
- Open design questions: `planning/open-questions/`.
