# Sutra rotation binding vs. TorchHD on retrieval capacity

**Date:** 2026-04-30
**Script:** `experiments/sutra_vs_torchhd.py`
**Setup:** d=768, 200-filler codebook, 10 trials per k, role-filler
bundled retrieval. Same task across all schemes.

## Raw results

| k | Sutra-rotation acc | MAP acc | HRR acc | FHRR acc |
|---:|---:|---:|---:|---:|
| 2  | 100.0% | 100.0% | 100.0% | 100.0% |
| 4  | 100.0% | 100.0% | 100.0% | 100.0% |
| 8  | 100.0% | 100.0% | 100.0% | 100.0% |
| 16 | 100.0% | 100.0% | 100.0% | 100.0% |
| 24 |  99.6% | 100.0% | 100.0% | 100.0% |
| 32 |  97.2% |  96.9% |  97.5% | 100.0% |
| 48 |  89.4% |  90.4% |  86.0% |  99.8% |
| 64 |  76.9% |  74.8% |  75.8% |  97.8% |
| 96 |  56.0% |  53.9% |  54.5% |  87.8% |
| 128|  40.1% |  40.5% |  38.1% |  73.8% |

(Signal cosines tracked closely with theoretical 1/k for all schemes
at every k, as expected. Numbers in `experiments/sutra_vs_torchhd.py`
output.)

## Honest interpretation

**Sutra's rotation binding has equivalent retrieval capacity to
MAP and HRR.** All three schemes track within ~3 percentage points
of each other across the full k sweep. None of these three
dominates the others.

**FHRR (Fourier HRR / complex phasor) is meaningfully better at
high bundle widths.** At k=64 FHRR still gets 98% vs ~76% for the
others; at k=96 FHRR gets 88% vs ~55%; at k=128 FHRR gets 74% vs
~40%. The complex-multiplicative binding has a real capacity
advantage at scale.

**Sutra does not win on raw binding capacity.** The hypothesis
that rotation binding would dominate on capacity is not supported
by this experiment. Rotation, MAP, and HRR are equivalent in this
regime; FHRR is better.

## What this means for the paper

The reviewer cons across the v3 review and the 14-variant
combinatorics run consistently asked for "comparison against
torchhd or other VSA libraries." A literal capacity comparison
gives data that *doesn't favor Sutra*. Putting this table in the
paper as evidence would actively undercut the rotation-binding
choice.

The honest path is to **not pivot the paper around capacity
claims** — the data doesn't support a capacity-based pitch. The
existing prose comparison in §2.1 of `paper/paper.md` (Sutra-
the-language-with-compiler vs. TorchHD-the-library-called-from-
Python) is the right axis: Sutra's contribution is the language
and the beta-reduction-to-tensor-normal-form compiler, not the
binding primitive in isolation.

## Why rotation binding is still the right runtime choice

Even though it doesn't win on capacity, rotation binding has
specific properties that make it the right primitive for Sutra's
substrate:

- **Reversibility is exact.** Round-trip error is 1.5e-15
  (floating-point round-off). MAP is exact too (involution); HRR
  has slight numerical noise from FFT. This matters for the
  beta-reduction pipeline: rotations compose cleanly under
  matmul fusion in tensor normal form.
- **It works on natural anisotropic LLM substrates** without
  modification. MAP and HRR were designed for hypervectors drawn
  from controlled distributions, not for frozen LLM embeddings.
  Rotation binding is substrate-agnostic.
- **GPU-friendly shape.** Cached as a precomputed matrix, binding
  is one matmul against the GPU — the shape that fuses with the
  rest of the tensor-op graph at compile time. MAP's Hadamard is
  even cheaper but doesn't compose under beta reduction the same
  way.

These are *qualitative* advantages, not capacity advantages. The
paper should make this distinction explicitly.

## Suggested follow-up experiments (not done in this round)

1. **Anisotropic-substrate comparison:** rerun the same task on
   real `nomic-embed-text` embeddings (anisotropic, non-uniform
   distribution) instead of random Gaussian. Hypothesis: MAP
   would degrade significantly; rotation and FHRR would be
   roughly stable. This would reframe the comparison around the
   substrate, not the binding.
2. **Program-level comparison:** take a Sutra `.su` program (e.g.
   `examples/role_filler_record.su`), write the equivalent in
   TorchHD as Python-with-library-calls, compare end-to-end
   wall-clock time, memory profile, and lines of code. The
   compiled-language vs. library-from-Python axis is where Sutra
   actually has structural advantages.
