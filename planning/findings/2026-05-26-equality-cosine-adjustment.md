---
date: 2026-05-26
status: MEASURED 2026-05-27 (run `bu7o9mqxu` completed exit 0, 9891.2 s)
---

# 2026-05-26 — Equality cosine-similarity adjustment: training a global temperature on `similarity` isolates the cosine-decompression lever

**Context.** First piecemeal target of the "Agentic RAG for constrained-training design" agenda (`todo.md`). The Stage-B finding (`planning/findings/2026-05-18-differentiable-training-is-a-proxy-not-compiled.md` § "Cron fire 9") showed a per-rule scalar gain `w` trained through the compiled graph baked back into `.su` as a literal (round-trip max logit Δ ≈ 2×10⁻⁷). But Stage-B's K=5 classification saturated at 100% accuracy, so the trained `w*≈1.43`'s direct effect on the cosine output was not visible — accuracy was already at the ceiling before the gain was needed.

This experiment **isolates the cosine-temperature lever**:
- prototypes FROZEN at `embed(category-name)` (no joint prototype-and-gain learning);
- ONLY a scalar `T` is trained;
- the reported metric is the **logit margin** (logit_correct − max logit_wrong), measured before training (T=1) and after (T=T*) — the *equality-discrimination headroom*, not classification accuracy.

## Verified facts (read, not assumed)

- Experiment file: `experiments/equality_cosine_adjustment.py` (this commit).
- `.su` shape: identical to Stage-B's `rule(x, own, others..., number T)` = `(T*sim(x,own)) && !(T*sim(x,o_j))…`. Compiled via the real PyTorch codegen (`translate_pytorch`), runtime_dim=768, runtime_seed=42.
- Prototypes are detached `embed("animal" | "vehicle" | "food" | "color" | "clothing")` tensors — never in the optimizer's parameter list.
- Equivalence guard: `torch.vmap(single)` vs per-sample `single(x)` at T=1, asserted to agree to 1e-4 before training begins; the run aborts on failure.
- Bake-back: trained `T*` substituted as a numeric literal (6-digit rounded) into a fresh `.su` with the `T` param removed; recompiled via the same codegen; max logit Δ checked against the param-`T` model.
- Smoke test (K=3, per-class=5, 20 epochs, seed=0, 2026-05-26): equivalence guard 2.98e-07, baseline margin +0.1103, trained margin +0.1303, T*=1.2481, round-trip max|Δ| 2.38e-07, ratio +1.18× — sanity check that the harness wires correctly.

## Measured numbers (real run `bu7o9mqxu`, K=5, per-class=5, epochs=40, seeds=0,1,2)

- **Equivalence guard max|Δ| (T=1, K=5):** 2.98e-07 (< 1e-4 threshold, passed).
- **Per-seed** (all three identical — see "Honest finding" below):
  - seed 0: baseline margin = +0.0748 → trained margin = +0.0807, T*=1.1118, round-trip max|Δ|=3.58e-07, round_trip_ok=True
  - seed 1: identical to seed 0
  - seed 2: identical to seed 0
- **Aggregate** (n=3, but see degeneracy below):
  - baseline margin (T=1): **+0.0748 ± 0.0000**
  - trained margin (T=T*): **+0.0807 ± 0.0000**
  - trained T*: **1.1118 ± 0.0000**
  - ratio = trained/baseline = **+1.08×**
- **Round-trip recompile**: passed all seeds; max|Δ| over all seeds = 3.58e-07 (< 1e-4 threshold).
- **Wall-clock**: 9891.2 s ≈ 2.75 h (per-sample driver path — vmap-batched would be ~96× faster per Stage-A's finding; deferred as a future optimization).

## Verdict

The cosine-temperature lever is **real but modest** at K=5 with frozen embed-anchor prototypes. A trained T*≈1.11 — a small decompression of the cosine output across the anisotropic LLM cone — produces a +1.08× margin improvement on the equality-discrimination metric. The bake-back round-trip is clean (max|Δ| 3.58e-07), so the trained model IS legible recompilable source per the Stage-B precedent: the entire trained classifier is `(1.1118 * similarity(x, own)) && !(1.1118 * similarity(x, other)) && ...` literally written in `.su`.

Comparison with the K=3 smoke test (per-class=5, 20 epochs, single seed): trained T*=1.2481, ratio +1.18×. So as K rises (3 → 5), the trained T* *decreases* (1.25 → 1.11) and the margin improvement *decreases* (+1.18× → +1.08×). Interpretation: more competing classes mean each class's single embed-anchor prototype is less salient, so a global decompression helps less per-class — a per-class T* (rank-1 with per-class gain, not a global one) might capture more, and rank-k explicitly addresses the sub-cluster case. Both are queued (rank-k is_X is queue.md #2; per-class-T is a follow-up).

## Honest finding (integrity surface): the n=3 is degenerate

**All three seeds returned BIT-IDENTICAL numbers** (std=0.0000 on every measured aggregate). With prototypes FROZEN at `embed(category-name)` (deterministic given the cached embeddings), a fixed data ordering, T initialized at 1.0, and Adam state initialized deterministically given the rest, **the only seeded RNG (`torch.manual_seed(s)`) had no live source of variation to inject**. The "n=3" is effectively n=1 repeated three times.

What this means:
- The +0.0748 → +0.0807, T*=1.1118 numbers are real measurements of the *one* deterministic trajectory the experiment defines. They're not random variates; the ±0.0000 is real, not a precision artifact.
- The experiment as run does NOT establish that the improvement is consistent across different prototype-init / data-ordering choices, only that it is what it is on this specific deterministic trajectory.
- The "n=3" claim in the harness output (`n={len(seeds)}`) is technically truthful but interpretively misleading; future ticks should patch the harness to either (a) reduce to n=1 explicitly, or (b) introduce a real per-seed variation source (random word sub-sampling within categories, or perturbing the frozen prototypes by ε*N(0,1) per seed, etc.). This is queued.

This integrity finding does NOT invalidate the headline +1.08× margin and 1.11 T* — those are real measured numbers on a real compiled-graph training run. It just bounds how strongly those numbers generalize beyond the one trajectory.

## What is NOT claimed

- Not "training cosine similarity makes Sutra correct" — `T` is a single scalar; it scales cosine output but does not change what the underlying anisotropic LLM embedding represents.
- Not "the right place for `T` is per-call-site / per-program / language-level" — this experiment is the *probe*. The placement decision was resolved separately in `planning/open-questions/equality-cosine-T-placement.md` (Emma 2026-05-26: lean = per-rule literal, status quo from Stage-B).
- Not "this generalizes the Stage-B `w` to all `similarity` calls in the language" — the experiment uses a single rule with one `T`. Cross-rule sharing, per-call-site gain, and compile-time calibration are distinct designs that the constrain-train agenda lists as separate experiments.
- Not a margin-loss objective — the experiment trains the same cross-entropy loss as Stage-B; the margin is *measured*, not optimized directly.
- **Not statistically robust to prototype-init or data-ordering choice** — see "Honest finding" above. The n=3 is degenerate; one deterministic trajectory.

## Follow-ups (not done in this finding)

- **Patch the harness** to either reduce the n=3 → n=1 explicitly OR introduce a real per-seed variation source (data sub-sampling, prototype ε-perturbation). Pick (b) for a more informative experiment.
- **Per-class T** (each class gets its own gain) — quick follow-up; uses the same harness shape, more parameters; tests whether per-class gain captures more margin than global T*.
- **vmap-batched** version of the harness — the per-sample path took 2.75 h here, ~96× too slow per Stage-A's finding; the vmap-batched form is bit-identical and unblocks larger-scale experiments.
- **Rank-k `is_X` constrain-train experiment** (queue.md #2, scaffold shipped 2026-05-26 `b6f21a24`): the more architectural next target — k prototypes + k gains per class. Now the GPU is free; training is the next work-loop tick.
- **Larger K** (K=10+) to see whether T* and the margin-improvement ratio continue to decrease as cone saturation worsens.

## What is NOT claimed

- Not "training cosine similarity makes Sutra correct" — `T` is a single scalar; it scales cosine output but does not change what the underlying anisotropic LLM embedding represents.
- Not "the right place for `T` is per-call-site / per-program / language-level" — this experiment is the *probe*. The placement decision is queued as an explicit follow-up (`planning/open-questions/` if not obvious from the result).
- Not "this generalizes the Stage-B `w` to all `similarity` calls in the language" — the experiment uses a single rule with one `T`. Cross-rule sharing, per-call-site gain, and compile-time calibration are distinct designs that the constrain-train agenda lists as separate experiments.
- Not a margin-loss objective — the experiment trains the same cross-entropy loss as Stage-B; the margin is *measured*, not optimized directly. (A margin-loss variant is a separate follow-up if the cross-entropy ratio looks marginal.)

## Follow-ups (not done in this finding)

- Decide language placement for `T` (per-call, per-program, language constant). Queue.md item #6 of the Equality cosine-similarity adjustment plan.
- Margin-loss variant: replace cross-entropy with an explicit margin-maximization loss; check whether `T*` converges to the same value.
- Larger K (K=10+) to see whether `T*` migrates as the anisotropic-cone discrimination problem worsens.
- The "low-hanging fruit" next scalar targets (`select` sharpness, soft-halt threshold, similarity temperature global vs per-rule) — see the constrain-train priority sequence in `todo.md`.
