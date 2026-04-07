# Inquisitive Transformer — Status Notes (2026-04-03)

## Current Assessment: Paused — methodology too inexact

The E1-E5 experiments produced a structured negative result: alpha modulates attention behavior (category-level shifts are real and consistent) but does not improve overall anomaly detection on GPT-2 without training. The perplexity experiment (E5) showed interesting asymmetries between forward and backward processing, but the overall approach feels too inexact and the methodology isn't tight enough to draw strong conclusions.

We are trying to do too much at once — modifying attention, designing surprise functions, building a benchmark, AND writing a paper, all without a clear signal that the core mechanism actually works at the most basic level.

## Before continuing: the "Jewish cat" test

**Benchmark sentence:** "The Jewish cat caught the mouse"

The word "Jewish" should be unambiguously flagged as the unexpected/surprising token in this sentence. This is the minimum viable test for whether the surprise function is doing anything useful:

- If the causal running mean distance (or any of our 4 surprise functions) correctly identifies "Jewish" as the outlier token → we have a working primitive and can proceed to attention modulation
- If it doesn't → the surprise functions themselves are broken and no amount of alpha tuning will help

This is a much cleaner litmus test than the 24-item CVD benchmark. Get this right first, then scale up.

## What's here and worth keeping

- The `InquisitiveAttention` module is a clean, working drop-in replacement for GPT2Attention
- The 4 surprise functions are implemented and computationally cheap
- The CVD benchmark is well-designed (if premature)
- E1-E5 experiment results are real data even if the conclusion is negative
- The paper honestly reports a negative result, which has value

## What needs rethinking

- The evaluation methodology — multiple-choice log-prob scoring may be the wrong metric entirely
- Whether inference-time injection (no training) can ever work, or if learned alpha is required
- Whether GPT-2 (124M) is too small for this to matter — larger models have more specialized heads
- The surprise function design — maybe surprisingness should be query-dependent, not key-intrinsic
