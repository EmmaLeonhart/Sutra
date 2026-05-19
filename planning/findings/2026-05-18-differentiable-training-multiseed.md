# 2026-05-18 — §3.6 differentiable-training: 5-seed replication

**Status:** positive / corroborating. Pre-arXiv rigor pass
(reviewer ask: "report mean ± s.d., n=5; plot accuracy over
epochs"). Numbers below are measurements, not targets.

## What was run

`experiments/differentiable_training_multiseed.py` (new, additive)
imports `differentiable_training.py` and reuses its exact data
pipeline, fuzzy-rule forward pass (`classify_batch`/`evaluate`),
Adam lr=0.005, 300 epochs, temperature 10. The **only** varied
quantity is `torch.manual_seed` (the sole seed-dependent part of
the original — prototype init, line 424), over seeds 0–4.
`differentiable_training.py` itself is **untouched**, so the
paper's existing single-seed-42 reproduction line stays valid.

## Measured 5-seed aggregate

| metric | mean ± s.d. (n=5) |
|---|---|
| accuracy before (random init) | 5.8 ± 2.4 % (chance 5%) |
| accuracy @ epoch 50 | 95.2 ± 0.1 % |
| accuracy @ epoch 299 | 95.3 ± 0.0 % |
| accuracy after (eval) | 95.3 ± 0.0 % |
| loss @ epoch 299 | 1.154 ± 0.000 |
| knee epoch (≤1 pp from final mean) | 22 |
| post-knee across-seed accuracy s.d. | 0.03 pp |
| gradient-norm range (all seeds, all 20 protos) | [0.94, 4.29], all nonzero |

All 5 seeds converge to **exactly 0.9530**. The single-run
seed-42 numbers the paper previously reported (95%, loss 1.154,
grad range 0.94–4.20) were representative, not cherry-picked; the
result is effectively seed-invariant. This is a *stronger* claim
than a single run and is what the paper now states.

## Word-count provenance — RESOLVED (paper was right)

The results-JSON `task` string says "1000 words"; the paper prose
says "992 words (50 each, deduplicated)". Checked directly:
20 categories × 50 = **1000 (word, label) pairs**; **992 distinct
word strings** (8 recur across categories: bronze, copper, gold,
heart, lavender, ring, silver, triangle). The paper's 992 is the
accurate distinct-string count; the script's JSON task-string
(`len(data)`=1000) is the loose one. No paper change needed; the
script is paper-cited/durable so its JSON string was left as-is.

## Paper changes (live `paper.md`; frozen `neurips/` untouched)

- Abstract + §3.6 Results: single-run numbers → n=5 mean ± s.d.,
  added knee/post-knee-s.d. and the seed-invariance statement;
  grad range corrected 0.94–4.20 → measured 0.94–4.29.
- Results table: now mean ± s.d. (n=5).
- Added a plain-TikZ accuracy-vs-epoch figure (mean + ±1 s.d.
  band) — coordinates generated from the real run, only the
  already-loaded `tikz` package (no pgfplots/graphicx), matching
  the existing soft-halt-cell figure's build path.
- Reproduction note now lists both scripts.

Artifacts: `experiments/differentiable_training_multiseed.py`,
`experiments/differentiable_training_multiseed_results.json`.
