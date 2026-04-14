---
name: Bind/unbind on Shiu — self-inverse works, role discrimination fails due to sparse substrate response
description: bind(a,r)=a*sign(r) on 138,639-D Shiu spike-count vectors is perfectly self-inverse (cos=1.000) but substrate-derived role masks don't discriminate — driving a 40-neuron role population produces sparse spike responses, so median-split yields ~43 +1 dims vs ~138,596 -1 dims, making all roles ≈ -1 and cross-unbind cos = 0.999 (should be ~0). The math works; the encoding doesn't.
type: project
---

# Bind / unbind on real Shiu W: self-inverse OK, role discrimination fails

**Date:** 2026-04-13
**Script:** `fly-brain/shiu_bind_test.py`
**Substrate:** Real FlyWire v783 W via Shiu 2024 whole-brain LIF (138,639 neurons, 15,091,983 nnz).

## Setup

- 4 value populations + 3 role populations, disjoint 40-neuron random pools.
- Each driven at 200 Hz for 100 ms → 138,639-D spike-count vector.
- Role sign mask: drive role pop, take spike-count response, median-split → ±1 mask.
- `bind(v, r) = v * sign(r)` elementwise; `unbind(x, r) = x * sign(r)`.

## Results

| metric | value | expected | pass? |
|--------|-------|----------|-------|
| self-inverse cos(unbind(bind(v,r),r), v) | 1.000000 | 1.0 | ✓ |
| sign-match on bind | 1.0000 | 1.0 | ✓ |
| cross-unbind cos (wrong role) | 0.9989 | ~0 | ✗ |
| bind separation (v_i vs v_j same r) | mean 0.143, max 0.836 | low | partial |

## Why cross-unbind fails

Substrate-derived role masks are heavily imbalanced:

| role | +1 dims | -1 dims |
|------|---------|---------|
| r0 | 43 | 138596 |
| r1 | 84 | 138555 |
| r2 | 43 | 138596 |

The 138,639-D spike-count response to a 40-neuron / 100 ms drive is
sparse: only a few hundred neurons fire meaningfully, the rest sit at
zero. Median of a mostly-zero vector is zero; the "above-median" tie-
break lands a tiny minority at +1 and everything else at -1. Every
role mask ends up ≈ `-1` everywhere with a thin minority of +1s in
different places.

Consequence: `bind(v, r_j) * r_k ≈ -v * -v = v` for any r_k, because
both masks are dominated by -1. Self-inverse holds trivially
(`sign² = 1` pointwise regardless of balance), but roles don't carry
discriminative information.

## Interpretation

The bind/unbind *math* is correct on Shiu spike-count vectors — the
elementwise arithmetic is exact and the algebraic property holds. But
the *encoding* of role as "median-split of a substrate response vector"
fails on this substrate because the substrate's response to point
drive is too sparse to yield a balanced ±1 mask.

This is the inverse of the bundle/snap result (which works on Shiu
because bundling superposes *spike counts*, which is what the
substrate emits natively). Bind as currently specified needs a
*balanced* ±1 pattern; Shiu's natural output is a sparse spike
count. The spec and the substrate disagree on what "role vector"
means.

## Options to close the gap

1. **Balance the mask differently.** Instead of median-split, take
   the top-k most-responding dimensions as +1 and a matched random
   sample of non-responding dimensions as -1 (or rank-based split
   with k/2 on each side). Gives a balanced mask but throws away the
   substrate-derived identity of most dimensions.
2. **Compile roles via a denser drive.** Drive role populations harder
   or longer so the response covers more of the 138,639 dimensions.
   Costs wall clock and may still be sparse on this substrate.
3. **Use a different bind operation.** The HRR / circular-convolution
   bind doesn't need balanced masks but needs FFT arithmetic that
   does not run natively on spiking substrate.
4. **Redefine role on this substrate.** Declare that on Shiu, a role
   is the *projected pattern* itself (used as a multiplicative key
   via signed count, not a hard ±1), and report that bind is still
   self-inverse modulo rescaling. This changes the spec rather than
   the substrate.

Option (1) is the cheapest next step. Option (4) is the most honest
alignment between spec and substrate and may be the right answer.

## What this means for the paper

- Bind/unbind cannot be claimed as "working on Shiu" in the same
  sense bundle/snap/conditional can. The self-inverse property holds
  but role discrimination does not.
- This is a substrate-encoding mismatch, not a substrate-dynamics
  failure — analogous to, but distinct from, the CX ring-attractor
  negative result.
- Paper should either (a) omit bind/unbind from the Shiu result
  table and confine them to the hemibrain MB substrate where they
  already work, or (b) report this mixed result honestly.

Choosing (b) per CLAUDE.md rule: every operation gets its turn on
Shiu, and mixed results are reported as mixed.

## Wall clock

7 substrate runs (4 values + 3 roles) at ~1 s each on CUDA = 7.6 s
substrate + negligible numpy bind/unbind. Full test: ~12 s including
model load.
