---
date: 2026-05-26
status: DRAFT (measurements landing — run `bu7o9mqxu` in progress)
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

## Measured numbers (real run: K=5, per-class=5, epochs=40, seeds=0,1,2)

**TO BE FILLED FROM `bu7o9mqxu` ON COMPLETION.** Numbers are measurements; report whatever they are.

- Equivalence guard max|Δ| (T=1, K=5): `<MEASURED>`
- Per-seed: `(seed, baseline_margin, trained_margin, T*, round-trip max|Δ|, round_trip_ok)`
- Aggregate: `baseline margin = <MEAN> ± <SD> (n=3)`; `trained margin = <MEAN> ± <SD> (n=3)`; `trained T* = <MEAN> ± <SD>`; `ratio = trained/baseline = <RATIO>x`.
- Wall-clock for the K=5 n=3 run.

## Verdict

`<PENDING measurements — fill in once `bu7o9mqxu` completes.>`

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
