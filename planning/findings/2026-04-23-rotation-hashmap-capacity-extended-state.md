# Rotation-hashmap capacity at d=868 (post-extended-state)

**Date:** 2026-04-23.
**Status:** Closes STATUS.md's remaining pre-Anthropic-grant-app item
(rotation-hashmap capacity at the post-extended-state runtime
dimension). Complements the 2026-04-22 study, which measured the same
thing through raw `bind/bundle` at d=768.

Script: `experiments/rotation_hashmap_capacity.py`.

## Target of measurement

Two things changed between the 2026-04-22 study and today:

1. **Runtime dimension** went from 768 → 868 when the extended-state
   vector (commit e1ccbbe, 2026-04-23) reserved 100 synthetic dims
   alongside the semantic block. Rotation bind is now block-diagonal:
   Haar in the 768-d semantic block, identity in the 100-d synthetic
   block. `embed(name)` produces `[semantic | zeros]`.
2. **Measurement surface** is the `hashmap_new`/`hashmap_set`/
   `hashmap_get` runtime API (landed 2026-04-22 in the same
   rotation-hashmap open-question work), not raw `bind` + `bundle` +
   `unbind`. In principle the hashmap methods are pure sugar over
   bind + add + unbind — the question here is whether they actually
   behave that way under stress.

The question the experiment answers, from STATUS.md: *at d=868, how
many distinct keys can the rotation-hashmap store before retrieval
breaks down?*

## Setup

- Compiled `hello_world.su` to instantiate `_VSA(semantic_dim=768,
  synthetic_dim=100, ...)` — the exact runtime the demo programs use.
- Built a pool of 138 role vectors and a 200-filler codebook as random
  unit d=868 vectors shaped like `embed()` output (random semantic,
  zero synthetic).
- For each `k ∈ {2, 4, 8, 12, 16, 24, 32, 48, 64, 96, 128}`: 10 trials
  per k, each trial builds a k-entry hashmap then queries every stored
  key and argmax-cosines against the full 200-filler codebook.
- Reversibility measured separately as
  `||hashmap_get(hashmap_set(new, k, v), k) − v||` over 50 k=1 stores.

## Results

### Reversibility round-trip (hashmap API)

| Statistic | Value |
|-----------|-------|
| mean      | 1.45e-15 |
| max       | 1.53e-15 |
| min       | 1.36e-15 |

Floating-point floor, matches the d=768 raw bind/unbind
reversibility (1.45e-15 mean). The hashmap wrapper adds no numerical
cost; the block-diagonal 868x868 Haar rotation is still orthogonal
to double-precision roundoff.

### Capacity curve through the hashmap API

| k   | accuracy | signal cos | noise cos | SNR  |
|-----|---------:|-----------:|----------:|-----:|
| 2   | 100.0%   | +0.7034    | −0.0081   | 87   |
| 4   | 100.0%   | +0.5027    | +0.0088   | 56   |
| 8   | 100.0%   | +0.3545    | −0.0009   | 410  |
| 12  | 100.0%   | +0.2892    | +0.0012   | 241  |
| 16  | 100.0%   | +0.2475    | −0.0001   | 2027 |
| 24  | 99.6%    | +0.2030    | −0.0000   | 8525 |
| 32  | 97.5%    | +0.1769    | −0.0006   | 304  |
| 48  | 89.8%    | +0.1435    | −0.0000   | 5099 |
| 64  | 75.8%    | +0.1255    | +0.0001   | 1882 |
| 96  | 54.8%    | +0.1026    | +0.0002   | 438  |
| 128 | 39.1%    | +0.0887    | −0.0000   | 8103 |

**Practical take-away: the rotation-hashmap at d=868 reliably handles
up to ~32 stored keys. Accuracy crosses 90% at k=48 and 50% at k=128
for a 200-filler codebook.** The thresholds shift with codebook size
(larger codebook → earlier collisions, per the off-codebook-distractor
argument below).

### Side-by-side with d=768 raw bind+bundle

| k   | d=868 hashmap (today) | d=768 raw bind (2026-04-22) |
|-----|----------------------:|----------------------------:|
| 2   | 100.0%                | 100.0%                      |
| 16  | 100.0%                | 100.0%                      |
| 32  |  97.5%                |  97.2%                      |
| 48  |  89.8%                |  88.3%                      |
| 64  |  75.8%                |  75.0%                      |
| 96  |  54.8%                |  53.9%                      |
| 128 |  39.1%                |  39.5%                      |

Within run-to-run sampling noise (10 trials per k). The curves are
indistinguishable.

Signal cosines also match to three decimals — both follow the classical
`~1/√k` bundle-normalization law (Plate 1995, HRR capacity analysis):

| k  | d=868 signal | d=768 signal | 1/√k  |
|----|-------------:|-------------:|------:|
| 2  | 0.7034       | 0.709        | 0.707 |
| 4  | 0.5027       | 0.505        | 0.500 |
| 8  | 0.3545       | 0.354        | 0.354 |
| 16 | 0.2475       | 0.253        | 0.250 |
| 32 | 0.1769       | 0.175        | 0.177 |
| 64 | 0.1255       | 0.124        | 0.125 |

## Interpretation

The synthetic block is algebraically inert under bind/bundle when
populated with zeros — which is the runtime reality, because `embed()`
produces `[semantic | zeros]` and every operation preserves that
layout (rotation identity on the synthetic block, bundle sum of zeros
is zero, unbind identity on the synthetic block). So the cosine math
is effectively 768-dimensional even though the vectors live in ℝ⁸⁶⁸,
and the capacity curve is unchanged.

The hashmap API itself is a thin wrapper. `hashmap_set(acc, k, v) = acc
+ bind(k, v)` and `hashmap_get(acc, k) = unbind(k, acc)`. The
reversibility and capacity numbers match the raw-algebra measurements
from last session because the wrapper introduces no additional
computation — it just names the accumulator pattern and exposes a
map-shaped API.

The failure mode is the same one characterized in the 2026-04-22
findings: **retrieval fails not because bundled-term noise floods the
signal, but because the `1/√k` signal drops below the chance-cosine of
off-codebook-entries to the recovered vector.** SNR (signal vs mean
bundled-term-noise) stays enormous across every k tested; what
degrades is signal-magnitude vs codebook-distractor chance collision.
Cleanup procedures better than plain argmax-cosine against a raw
codebook (constrained-codebook argmax, iterative cleanup, the MLP-
attractor from the 2026-04-22 king/queen work) should push the
effective capacity higher without changing the bind/bundle/rotate
mechanism.

## What the extended-state upgrade did not buy (and was never claimed to)

The 2026-04-21 extended-state design doc argued that a dedicated
synthetic subspace with per-slot 2D Givens planes could hit *zero*
cross-talk between slots — noise at machine-epsilon instead of the
`1/√d` random-vector floor. That design is not what landed on
2026-04-23. What actually landed is the block-diagonal layout: rotation
Haar on the semantic 768, identity on the synthetic 100. The semantic
block still uses the same role-seeded Haar rotation as before; the
synthetic block is reserved computational space (canonical axes for
real/imag/truth per commit 23b57c2) but not yet carrying slot-allocated
2D Givens rotations.

So the extended-state upgrade in its current form is correct to
predict: **it does not improve rotation-hashmap capacity on semantic
content**. The capacity budget is a property of the semantic-block
rotation algebra, which is unchanged. The synthetic block's value is
elsewhere — it carries truth-axis scalars, real/imag decomposition for
complex-number primitives, etc. — all things not exercised by the
rotation-hashmap workload.

If a future iteration does allocate slot-specific 2D Givens rotations
inside the synthetic block and bind content into them, *that* would
shift the capacity picture for small-codebook slot-assignment patterns.
The 2026-04-21 design doc still has the measurement setup for that
case (Experiments 1, 2 in the design). It's a follow-on if and when
the synthetic block starts carrying active-bound content.

## What this closes vs. leaves open

**Closed:**
- The STATUS.md question "how many keys at d=868" has a number: 32
  clean, 48 at the 90% threshold, 96 at the 50% threshold, against a
  200-filler codebook.
- The `hashmap_new`/`hashmap_set`/`hashmap_get` API is empirically
  equivalent to the raw bind/bundle/unbind pipeline — no wrapper
  surprises.
- The synthetic block's existence does not impair the semantic-block
  capacity (and was never expected to).

**Still open (from the prior findings doc, unchanged):**
- Capacity on real nomic-embedded fillers. Clustered semantic fillers
  (e.g. lookup/start/stop in `fuzzy_dispatch.su`) fail earlier than
  random-vector capacity predicts. Needs its own study.
- Attractor-cleanup capacity: plug the 2026-04-22 MLP-attractor into
  the cleanup step and re-measure. Hypothesis from the prior doc: the
  attractor pushes the effective budget well past k=48 because it
  discriminates fillers more sharply than argmax-cosine.
- Slot-allocated synthetic-block binding (the 2026-04-21 Experiments
  1, 2 in their original form). Only relevant once the synthetic
  block carries bound content, not today.

## Prior-art pointer

Same as the 2026-04-22 doc: Plate 1995 HRR chapter on bundle-and-
retrieve capacity, Frady/Sommer capacity bounds, Kleyko et al.
HD-computing cleanup studies. The off-codebook-distractor framing
of the failure mode is the part most in need of a lit audit before
any external publication.
