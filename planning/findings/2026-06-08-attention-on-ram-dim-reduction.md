# Attention-on-RAM parser reduces to the synthetic-axis floor (runtime_dim = 3)

**Date:** 2026-06-08
**Context:** NTM-archetype track step (d) — the reduction study (design doc §5:
"smallest dim/head count still passing the oracle, measured"). Sweep:
`experiments/attention_on_ram/dim_sweep.py`; guard
`test_reference.py::test_parser_reduces_to_synthetic_axis_floor`.

## Result (measured)

Compiling each OCaml→substrate fixture at decreasing `runtime_dim` and running it on
the substrate, comparing the decoded result to the oracle:

| fixture | oracle | smallest passing `runtime_dim` |
|---|---|---|
| `attn_sum_tape` | 10.0 | **3** |
| `attn_dot_tape` | -2.0 | **3** |
| `attn_select_field` | 22.0 | **3** |

All three pass at the **floor** `runtime_dim = 3` (and at every dim 3–16). Dim 3 is
the minimum that holds the three synthetic axes (real=0, imag=1, truth=2) with
`semantic_dim = 0` — i.e. **zero semantic/LLM-codebook capacity**.

## Why this is the right floor (dim audit, CLAUDE.md)

The parser fixtures contain **0 `basis_vector` calls** — they encode only numbers and
RAM addresses, never LLM-embedding atoms — so the semantic subspace is unused and
correctly collapses to nothing. The computation lives entirely on the real axis
(arithmetic, the weighted RAM aggregate) plus the truth axis (the branch/compare). The
measured floor of 3 matches that account exactly: there is nothing to put in a
semantic dimension, so none is needed.

## Reduction achieved

- vs the CLI default `runtime_dim` (≈50): **~16× smaller**.
- vs the `transformer-vm`'s residual stream (d=38): **~13× smaller**.

The attention-on-RAM parser is a genuinely tiny object — the synthetic-axis floor —
which is the design-doc §5 goal (shrink while holding behavioral equivalence) reached
for the parser's dimensionality. The remaining reduction axis is head/operator count
(O4: a fresh-isomorphic minimal one-head construction vs a sliced real `transformer-vm`
head); the one head used here is already the minimum for a single-read parse.

## Scope / not claimed

This reduces the *parser's* runtime dimension, not the `transformer-vm`'s constructed
weights (whose reduction is the schedule-driven head pruning, finding
`2026-06-07-pruned-transformer-repack-reduced-core.md`). The sweep RUNS each `.su` on
the substrate; the only host read is the terminal result decode (the external
orchestrator boundary), as in the CLI `--run`. No new readout, no faking — 42
compile+run measurements (3 fixtures × dims 3–16), all decoded against the oracle.
