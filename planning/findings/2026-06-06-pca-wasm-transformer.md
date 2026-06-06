# PCA / SVD of the analytic WASM transformer — what's actually reducible

**Date:** 2026-06-06 (todo.md TOP PRIORITY; PCA pivot)
**What:** built the analytic `transformer-vm` (MILP schedule, 5.7 s) and ran
SVD/PCA on every weight matrix to find the genuine low-dimensional structure for
the reduced-attention DNC work. Analysis on the constructed weights
(numpy/torch off the runtime hot path) — allowed. Script:
`experiments/wasm_transformer_pca/pca.py`. Schedule cached to `plan.yaml`.

## The model (already tiny)

`VanillaTransformer`: **d_model = 38, 7 layers, vocab = 915, 144,286 params.**
7 attention layers (`in_proj` 114×38 = QKV for 19 heads of dim 2; `out_proj`
38×38), 7 ReGLU FFN (`ff_in` 86×38, `ff_out` 38×43), token + head embeddings
(915×38). This is **not** an over-parameterized model with a big embedding dim to
shrink — d_model is already 38.

## Headline: magnitude-PCA is the wrong lens here (importance ≠ norm)

The analytic construction uses **extreme-dynamic-range** weights — singular values
span up to ~1e30 (some matrices to 1e89–1e119) for the hardmax temperature
(`HARD_K = 1e10`) and the address/position arithmetic (2^k scales), down to ~1 for
the actual byte logic. So **energy-fraction "effective rank" is dominated by a few
giant singular values and reports a misleadingly-low rank** — the small-magnitude
dimensions carry the real computation but contribute almost nothing to the Frobenius
norm. You cannot PCA-truncate this transformer by magnitude: dropping the small
singular directions would delete the logic, not redundancy. (`s**2` even overflows
float32; the analysis runs in float64.)

## What IS concretely reducible (measured)

1. **Two attention layers are entirely zero.** `attn.5` and `attn.6` have
   `in_proj` and `out_proj` summing to exactly **0** — the schedule places all
   attention in the first 5 layers; layers 5–6 do FFN-only work. **2 of 7
   attention blocks are directly prunable.**
2. **The vocabulary embedding is genuinely low-rank.** `tok.weight` (915×38) and
   `head.weight` (915×38) carry **99% of their energy in 3 of 38 dimensions**
   (90% in 1–2). The 915-token vocab effectively lives in a ~3-dimensional
   subspace — a real, magnitude-honest reduction (no giant switches there).

## What is NOT reducible by PCA

The **addressing / hardmax matrices** (`attn.*.in_proj`, several `ff_in`) have
1e30+ dynamic range. Their low energy-rank is a giant-switch artifact, not
redundancy — the moderate- and small-magnitude singular directions are the
opcode/byte logic. Magnitude-based dimension reduction would break exact addressing.

## Implication for the reduced-attention DNC work

Naive "PCA the weights → drop small directions" does **not** yield a reduced
attention for this machine — importance is decoupled from magnitude by
construction. The reducible surface is (a) the 2 zero attention layers and (b) the
~3-d vocabulary embedding; the attention *core* must be reduced from the
**computation graph / schedule** (fewer scheduled dims/heads in the DSL), not from
SVD of the constructed weights. This is a negative result for the PCA-truncation
approach, with two concrete positives and a redirect.

## Numbers (per-matrix, full SVD)

- token/head embeddings: energy-rank @99% = **3 / 38**.
- `attn.5`, `attn.6`: **all-zero** (rank 0).
- attention `out_proj` layers 1–4: relative-rank (sv > max·1e-6) **8, 18, 12** of
  38 — the logic attention genuinely uses most of the 38-d space.
- `in_proj` (addressing): dynamic range 1e10–1e86; energy-rank 1 (artifact).
- `ff_out`: relative-rank 6–19 / 38; `ff_in`: dynamic range up to 1e119.
