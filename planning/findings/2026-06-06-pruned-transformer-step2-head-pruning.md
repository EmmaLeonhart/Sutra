# Pruned transformer step 2: the 91 idle attention heads are fully zero (lossless to drop)

**Date:** 2026-06-06
**Context:** Pruned-transformer build (task #1), step 2. Script:
`experiments/wasm_transformer_pca/head_prune_verify.py`.

## The question

A head "attends" iff its Q AND K in_proj rows are non-zero (42/133, per-layer
7,5,11,11,8,0,0). But an *idle* head (Q,K zero) is not automatically free: zero
Q,K make the scores zero, softmax becomes uniform, and the head outputs
`mean(V)` over positions, which `out_proj` adds to the residual. So an idle head
is only removable if that contribution is actually zero. Step 1 only covered the
2 fully-zero attention sublayers (layers 5,6); step 2 asks about all 91 idle
head-slots.

## Result (measured)

Per head, measured `|Q rows|`, `|K rows|`, `|V rows|`, `|out_proj cols|`:

- **42/133** heads attend.
- **91/133** are idle AND **fully zero**: their V rows *and* out_proj columns are
  exactly zero, not just Q/K. (`idle but NONZERO V or out_proj cols: 0`.)

So the `mean(V)` worry does not arise: the idle heads contribute exactly zero
because V and out_proj are zero too. Dropping them is lossless. Consistency
check: zeroing the out_proj columns of all 91 non-attending heads leaves
generation token-for-token identical on 5/5 random-input trials.

Attention weight that is exactly zero: 91/133 head-slots = **68% of the
attention parameters** (each head-slot is 3·hd·D in_proj + D·hd out_proj = 304
params; 91·304 = 27,664 of 40,432 attention params). This subsumes step 1 (the
38 head-slots of layers 5,6 are a subset of the 91).

## Takeaway

The model genuinely uses **42 of 133** attention head-slots; a 42-head model is
output-identical to the full one. The 42-count does NOT understate the
output-load-bearing heads (the other 91 are zero, not merely attention-idle).
The reduction lever remains the schedule, and the schedule under-provisions
attention by ~68%.

## Not yet done

A dimensionally-reduced model (literally `n_heads` smaller per layer, weights
re-packed) is the mechanical next move; the equivalence above shows it will be
output-identical. Canonical byte-for-byte sign-off on the 6 WASM programs is the
committed-fixtures route (Emma 2026-06-06; needs a one-time clang-equipped run).

## Substrate-purity note

Compile/monitor analysis on the constructed `transformer-vm` weights (torch, off
any Sutra runtime hot path) — allowed; not a Sutra operation.
