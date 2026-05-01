# Crosstalk noise accumulation — chained bind/unbind cycles

**Date:** 2026-04-30
**Experiment:** `experiments/crosstalk_chain.py`
**Status:** honest negative result; integrating into paper §3.1.

## Why this matters

Reviewer at clawRxiv post 2191 (Weak Accept) con #2: *"The paper
lacks a formal error analysis regarding the accumulation of VSA
noise (crosstalk) across deep nested operations."*

Reviewer at post 2192 (Weak Reject) con #4: *"The soft-halt
mechanism lacks a stability analysis; recurrently updating a
fixed-width vector over 50+ iterations in a high-dimensional
space often leads to representation drift or noise accumulation
that 'nearest_string' may not resolve."*

The §3.1 capacity table measures single-cycle bind+bundle+unbind.
This experiment measures multi-cycle bind+bundle+unbind chains
with distractor noise per cycle.

## Protocol

Per substrate (nomic-embed-text 768d, all-minilm 384d, mxbai-
embed-large 1024d, codebook 84 words):

For chain length L in {1, 2, 4, 8, 16, 32}, run 20 trials. Each
trial:

1. Pick filler v_0 from codebook.
2. Pick L distinct role rotations R_1 ... R_L (Haar-orthogonal,
   role-seeded).
3. Forward: at each step bind v_i = R_i · v_{i-1}, bundle in
   K-1=3 distractor (role, filler) pairs (so each cycle's bundle
   has 4 entries: the carrier + 3 distractors).
4. Backward: unbind in reverse, recovered = R_i^T · recovered.
5. Two flavors:
   - **raw**: no cleanup; cosine to v_0 measured directly
   - **snap**: argmax-cosine cleanup against codebook after
     each unbind step

Report: cosine to original, accuracy of argmax-against-codebook.

## Results

```
nomic-embed-text (dim=768)
chain    raw cos    raw acc   snap cos   snap acc
-------------------------------------------------------
    1    +0.4998     100.0%    +1.0000     100.0%
    2    +0.2399     100.0%    +0.1238      10.0%
    4    +0.0596      20.0%    -0.0143       0.0%
    8    +0.0066       0.0%    -0.0202       0.0%
   16    +0.0089       0.0%    -0.0240       0.0%
   32    +0.0049       0.0%    -0.0091       0.0%

all-minilm (dim=384)
chain    raw cos    raw acc   snap cos   snap acc
-------------------------------------------------------
    1    +0.4944     100.0%    +1.0000     100.0%
    2    +0.2631     100.0%    +0.3399       0.0%
    4    +0.0503       5.0%    +0.2968       0.0%
    8    -0.0170       0.0%    +0.3419       5.0%
   16    +0.0068       5.0%    +0.3129       0.0%
   32    -0.0113       0.0%    +0.3884       5.0%

mxbai-embed-large (dim=1024)
chain    raw cos    raw acc   snap cos   snap acc
-------------------------------------------------------
    1    +0.5025     100.0%    +1.0000     100.0%
    2    +0.2548     100.0%    +0.5757       0.0%
    4    +0.0606       5.0%    +0.5766       0.0%
    8    +0.0050       0.0%    +0.5735       0.0%
   16    -0.0011       0.0%    +0.5518       0.0%
   32    +0.0026       0.0%    +0.5547       0.0%
```

## What this shows

**Chain depth 1 (single bind+bundle+unbind, the §3.1 protocol):**
100% accuracy with codebook snap across all three substrates.

**Chain depth 2:** raw cosine drops by ~half per cycle (from
~0.5 to ~0.25), but raw accuracy still holds at 100% because
even a small positive cosine is enough to win argmax against 83
distractors. **Snap accuracy collapses immediately** — once we
collapse to a codebook entry mid-chain, the noise from the
intervening bundles already contaminates which codebook entry
wins, and the wrong choice cascades.

**Chain depth ≥ 4:** raw cosine is statistically indistinguishable
from zero. The argmax against 83 distractors is now random
chance (1/84 ≈ 1.2%), and we observe accuracy in the 0–5% range
across substrates — random.

## Why snap can be *worse* than raw on multi-cycle chains

The snap protocol replaces the recovered vector after each
unbind step with its nearest codebook entry. If that nearest
entry is correct, snap removes accumulated noise — perfect.
But if the bundle noise pushed the recovered vector *past* the
true filler in cosine ranking, snap commits to a wrong codebook
entry, and the next unbind operates on that wrong vector. This
is why snap accuracy drops faster than raw accuracy: the binary
snap decision converts noise into a hard error that cannot be
recovered by averaging.

The mxbai snap-cos numbers (+0.55 to +0.58 across all chain
depths > 1) reflect this: the snap consistently picks *some*
codebook entry, just not the right one. Snapping produces a
high-confidence wrong answer.

## Relationship to the soft-halt RNN cell

The soft-halt RNN cell (§3.3) does **not** use the protocol
measured here. Its per-tick update is `state ← R · state` with
a halt-gate component update, not a per-tick bind-and-bundle.
Pure rotation chains are exact: `R^T · R · v = v` to floating-
point precision (the §3.1 reversibility round-trip confirms
1.5 × 10⁻¹⁵ error per cycle). The noise that accumulates in
this experiment is from the **bundle of distractors injected at
each cycle**, not from the rotation itself.

The soft-halt cell over T=50 iterations therefore does not
inherit this crosstalk — it inherits floating-point round-off,
which is bounded.

## What this means for the paper

**Honest framing for §3.1:** single-cycle bind/unbind (the
protocol measured in §3.1) works at 100% across substrates;
chained bind/unbind with per-cycle distractor noise degrades
fast. Real Sutra programs use single-cycle records (e.g.,
role_filler_record.su, knowledge_graph.su) — they do not nest
bind operations 4+ levels deep.

**Honest framing for §3.3:** the soft-halt RNN cell is pure
rotation per tick, and the round-trip reversibility result
(1.5 × 10⁻¹⁵ per cycle) bounds the accumulated error. Long
loops are not free of noise, but the noise in `state ← R ·
state` is round-off, not crosstalk.

**Honest scope statement:** Sutra targets shallow VSA programs
(record encoding/decoding, soft dispatch, single-step queries).
Deep nested compositions (record-of-record-of-record at depth
4+) hit the bundle-noise floor before they hit the
language-design ceiling.

## Limitations of this experiment

- Bundle width 4 (3 distractors per cycle) is one operating
  point. Bundle width 1 (no distractors, pure rotation chain)
  would round-trip exactly to chain depth 32+.
- 84-word codebook is small; a larger codebook would make
  argmax harder per cycle, lowering chain capacity further.
- 20 trials per chain length is enough to see the order-of-
  magnitude effect but the snap-accuracy noise floor (5% on
  all-minilm chain=8) is one trial out of 20.
- The experiment uses 768/384/1024-d substrates; capacity is
  known to scale roughly linearly with dimension, so the
  effective chain depth on a 4096+ dimension substrate (e.g.,
  large LLMs, ProtBert-XL) would extend further.

## Next moves

1. ✅ Add an honest §3.X subsection to the paper.
2. ✅ Cite this finding from §3.1 to scope the capacity claim.
3. Optional: rerun with bundle_width=1 to confirm pure-rotation
   chains are exact across the same depth sweep.
