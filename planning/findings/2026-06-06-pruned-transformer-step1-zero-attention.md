# Pruned transformer step 1: dropping the two zero attention sublayers is lossless

**Date:** 2026-06-06
**Context:** Pruned-transformer build (Emma greenlit "Full pruned core + verify").
First staged reduction the PCA diagnosed. Script:
`experiments/wasm_transformer_pca/prune_zero_attention.py`.

## Result (measured)

- `attn[5]` and `attn[6]` of Percepta's `transformer-vm` have **in_proj and
  out_proj weights that are exactly zero** (`max|w| = 0.000e+00` for all four
  tensors). Confirms the PCA's rank-0 / dyn-range-0 reading.
- A zero attention block computes `x = x + out_proj(attn(...)) = x + 0`, i.e. an
  identity pass-through. Removing the attention sublayers of layers 5 and 6
  therefore cannot change any output.
- Verified numerically: the stock model vs. a model that skips attention in
  layers 5/6 produce **token-for-token identical** generations on **5/5 random
  input trials**.
- Parameter reduction: **11,552 / 146,680 = 7.9%** removed.

## Important correction to the framing

Layers 5 and 6 keep **non-zero FFNs** (`ff_in.5`/`ff_out.5`/`ff_in.6`/`ff_out.6`
are full-rank). So this drops only the **attention sublayers** of those layers,
not whole transformer layers. "2/7 attention layers are zero" is about the
attention sublayers; the layers' feed-forward compute remains.

## What is NOT yet verified, and why

The byte-for-byte check on the 6 reference WASM programs (the project's stated
oracle) is **blocked locally on clang/uv**: generating each program's input
token stream requires compiling C -> wasm (`compile_wasm.ensure_data` calls
clang), and the reference traces need `uv run wasm-reference`. Neither clang,
wat2wasm, nor a C++ toolchain (also needed for the Hull O(log n) cache) is
available outside WSL. The random-input equivalence above already proves
output-preservation for THIS reduction (the dropped sublayers are exactly zero,
so equivalence is exact, not approximate); the 6-program oracle is the broader
end-to-end confirmation and remains future work pending the WSL build.

## Next reduction steps (task #1)

2. Prune idle heads: keep only the 42/133 attending head-slots (per-layer
   7,5,11,11,8,0,0). Not lossless a priori — must verify equivalence.
3. Compress the token/head embedding to its ~3-d effective subspace.
Each verified independently, then stacked. Full byte-for-byte sign-off needs WSL.

## Substrate-purity note

This is compile/monitor analysis on the constructed `transformer-vm` weights
(torch, off any Sutra runtime hot path) — allowed. It is not a Sutra operation.
