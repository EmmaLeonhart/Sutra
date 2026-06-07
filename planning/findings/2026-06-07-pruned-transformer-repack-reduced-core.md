# Pruned transformer: the re-packed reduced core is output-identical (68.4% less attention)

**Date:** 2026-06-07
**Context:** Pruned-transformer build (task #1), the dimensional re-pack — the
concrete deliverable of Emma's "Full pruned core + verify". Script:
`experiments/wasm_transformer_pca/repack_reduced.py`.

## Result (measured)

Built the literally-smaller model: per layer, the attention `in_proj` keeps only
the used heads' Q/K/V rows and `out_proj` keeps only their columns; layers with
no used heads have no attention. FFNs and embeddings unchanged.

- Used heads per layer: **[7, 5, 11, 11, 8, 0, 0] = 42/133**.
- Attention parameters: **40,432 → 12,768 (68.4% removed)**.
- The re-packed 42-head model is **output-identical to the full model
  token-for-token on 8/8 random inputs.** Identity is exact because every removed
  row/column was exactly zero (steps 1-2).

## Status of task #1

The pruned core is **built and verified locally**:
- step 1: drop 2 zero attention sublayers (lossless),
- step 2: 91 idle head-slots are fully zero (lossless),
- step 3: the embedding is NOT spectrally compressible (negative),
- re-pack: concrete 42-head model, output-identical, 68.4% less attention.

The one remaining verification is the canonical **6-WASM-program byte-for-byte
oracle**, which needs a one-time clang-equipped run (Emma's committed-fixtures
route, 2026-06-06). Random-input equivalence is exact here because the dropped
weights are exactly zero, so the reduced core is correct independent of that
oracle; the oracle is the broader end-to-end confirmation.

## Note on the reviewer's "reduction is trivial" framing

clawRxiv reviews call this "trivial — just zeros from the MILP scheduler." That
is accurate as a description and is the point: the reduction lever is the
schedule (which leaves 68% of attention unprovisioned), not the weight spectrum.
The contribution is the measurement, not a novel compression algorithm; spectral
methods fail here (see the step-3 negative finding).

## Substrate-purity note

Compile/monitor analysis on the constructed `transformer-vm` weights (torch, off
any Sutra runtime hot path) — allowed; not a Sutra operation.
