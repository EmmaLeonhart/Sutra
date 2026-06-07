# Pruned transformer step 3: the "low-rank" embedding is NOT SVD-compressible (negative)

**Date:** 2026-06-06
**Context:** Pruned-transformer build (task #1), step 3. Script:
`experiments/wasm_transformer_pca/vocab_compress_verify.py`.

## Expectation vs. result

The PCA reported the 915×38 token and head (readout) embeddings carry ~99% of
their energy in 3 of 38 dimensions, and an earlier paper draft called this "a
reduction the magnitude spectrum supports." **Measurement says otherwise.**

SVD-truncating `tok.weight` and `head.weight` to rank k and checking generation
equivalence to the full model on 8 random inputs: **no rank preserves output —
not even rank 38 (full).** The rank-38 SVD round-trip introduces a reconstruction
error of only **1.1e-12** (max entry 256), and that alone flips the model's
output.

## Why

The constructed model is a razor-sharp digital circuit: the head readout has
entries to 1e5, attention runs at `HARD_K = 1e10`, and selection is hardmax
(argmax). A 1e-12 perturbation of the embedding propagates through the high-gain
hardmax and changes a discrete decision. So energy concentration (99% in 3 dims)
does NOT imply compressibility — the discarded ~1% (and even float-level noise)
carries decision-flipping information.

## Significance

This is the §4 thesis — *magnitude ≠ importance; spectral pruning is unsafe for
this model* — confirmed at the one place that looked like an exception. Spectral
truncation fails even on the embedding. The reducibility that holds is the
**exactly-zero** structure (step 1: 2 zero attention sublayers; step 2: 91 fully
zero head-slots), not low-rank truncation. The paper bullet claiming the
embedding is a magnitude-supported reduction was an overclaim and has been
corrected to match this measurement.

## Caveat / scope

Equivalence checked on random inputs (a lower bar than the 6 reference programs).
But the result is negative and the mechanism (1e-12 → flipped hardmax) is
input-independent, so the negative conclusion is robust: a coordinated reduction
that also adjusts downstream weights might still be possible, but naive SVD
truncation of the embedding is not output-preserving at any rank.

## Substrate-purity note

Compile/monitor analysis on the constructed `transformer-vm` weights (torch, off
any Sutra runtime hot path) — allowed; not a Sutra operation.
