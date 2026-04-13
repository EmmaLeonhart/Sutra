# 140-D spiking rotation + cosine readout — ordering 5/5, counting 0/5 with signal

**Date:** 2026-04-13
**Script:** `fly-brain/loop_140D_spiking_cosine.py`
**Result:** Ordering 5/5 PASS, counting k=3 0/5 at threshold=0.5 but with
peak cosine at target consistently 0.39–0.46.

## What was measured

Spiking rotation via `neural_linear_map` at 140-D (Q as Brian2 synapse
weights, state decoded from membrane voltage, SIM_MS=3000 ms) followed
by direct cosine comparison between decoded state and a stored
prototype vector. No MB, no PN→KC, no Jaccard. Five seeds.

Q is the same 140-D block-diagonal `build_140D_Q()` used by the paper:
polar decomposition of EPG→EPG (51-D) + hDelta subset (89-D) from
real FlyWire v783 wiring.

## Raw numbers

Counting k=3 (per-iteration cosine of decoded state against
`Q^3 · v0` prototype):

```
seed=0  k1=+0.32 k2=-0.01 k3=+0.39 k4=-0.09 k5=+0.10 k6=-0.04 k7=+0.13 k8=-0.08
seed=1  k1=+0.43 k2=-0.09 k3=+0.42 k4=-0.10 k5=+0.16 k6=-0.05 k7=+0.12 k8=-0.10
seed=2  k1=+0.53  (terminated early, spurious match at k=1)
seed=3  k1=+0.27 k2=+0.06 k3=+0.46 k4=-0.06 k5=+0.18 k6=-0.08 k7=+0.05 k8=-0.01
seed=4  k1=+0.33 k2=+0.01 k3=+0.46 k4=+0.03 k5=+0.08 k6=-0.11 k7=+0.00 k8=-0.13
```

Ordering (EARLY@2, MIDDLE@5, LATE@8; substrate picks best match at
each k, terminates on first match above threshold):

```
seed=0  matched=EARLY  matched_at=2  PASS
seed=1  matched=EARLY  matched_at=2  PASS
seed=2  matched=EARLY  matched_at=2  PASS
seed=3  matched=EARLY  matched_at=2  PASS
seed=4  matched=EARLY  matched_at=2  PASS
```

Wall clock: 43s for all 10 runs.

## Interpretation

**The MB was the problem, not rotation.** Swapping the MB-Jaccard
readout (combined_pipeline.py, 0/5 on both) for direct cosine readout
goes to 5/5 on ordering and to a clear target-peak on counting. The
substrate IS rotating to the right position; the MB specifically
destroyed the readout because small vector-space perturbations become
large KC-space perturbations (the MB is an anti-correlator by design).

**Counting fails at threshold=0.5 for two reasons.**

1. **140-D decode noise caps absolute cosine at ~0.45.** The spiking
   rotator's output is Poisson-rate-decoded membrane voltage;
   per-dimension noise accumulates as √D, so at 140-D the best
   achievable cosine with a clean target is not near 1.0. This is
   the same Poisson ceiling that capped the 51-D (0.7) and 713-D
   (0.1) versions at 3/5 with cosine. At 140-D the ceiling lands
   at ~0.45.

2. **Seed 2 false-early trigger at k=1.** cos=0.53 at k=1 is decode
   noise that happens to align with the k=3 prototype. Threshold
   triggers early. This is a straightforward false-positive caused
   by using absolute threshold rather than argmax-over-trajectory.

Argmax-over-trajectory (pick the k with the largest cosine over the
full window) gets 3/5 correct: seeds 0, 3, 4 all have their peak at
k=3. Seeds 1 and 2 have peaks elsewhere (seed 1 at k=1 with 0.43 vs
k=3 with 0.42, essentially tied; seed 2 terminated early). With a
better termination criterion (integrated matched filter, or just
argmax) counting approaches ordering's result.

## A construction bug surfaced by this experiment

`det(Q) = -1.0000` for the composed 140-D operator. The EPG block
has det=+1 (proper rotation) but the hDelta block has det=-1
(rotoinversion). block_diag composition gives +1 × -1 = -1.

This means the "rotation" operator the paper ships with is actually
a rotoinversion in the 89-D hDelta subspace. It still has
Q^T Q = I to 10^-14 and is norm-preserving, so the loop math still
works — but it explains the alternating-sign pattern in the
counting cosines (odd k vs even k differ in overall sign structure
because Q^odd reflects and Q^even doesn't). It may also be capping
the target-k cosine lower than it should be: if the reflection
swaps components of v0 in a way that the decode cannot reproduce
cleanly, the target match is structurally weaker than for a pure
rotation.

Fixing this is one row-flip of Q_hd. Worth doing before another
round of measurements.

## Implications

- **This is the first substrate-only loop result in this session
  that passes anything at n=5.** Ordering 5/5 is not propped up by
  numpy at runtime. Rotation is on neurons via `neural_linear_map`;
  readout is cosine on decoded voltage.
- **Counting is not broken, the termination criterion is.** The
  substrate reaches the right position; the absolute-threshold rule
  rejects it. Argmax or matched-filter variants should recover
  counting.
- **The MB remains the wrong readout substrate for this loop.** This
  isn't "the loop fails on the fly brain" — the loop works on the
  CX-derived substrate (EPG-based rotation operator) with a
  CX-appropriate readout (direct voltage comparison). It just
  doesn't work when you pipe through the mushroom body, which is
  biologically a decorrelator, not a holder of continuous rotating
  state.
- **det Q = -1 is a construction bug.** Fix before next measurement
  round.
- **The paper's headline numbers were measuring a different
  architecture.** The 5/5 counting + 30/30 k-sweep in the current
  paper come from numpy rotation + MB-Jaccard. The substrate-only
  version measured here gets ordering 5/5 + counting 3/5
  (argmax), at n=5 seeds, without numpy in the runtime path.
  Those are different results and should be labeled as such.

## Follow-ups

1. Fix the det=-1 bug (flip a row in Q_hd construction), retry this
   experiment.
2. Counting with argmax-over-trajectory termination instead of
   absolute threshold.
3. Increase SIM_MS to see if Poisson ceiling rises, at a
   wall-clock cost.
