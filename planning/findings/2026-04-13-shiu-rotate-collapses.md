---
name: real-W iterative rotate collapses to fixed point (Shiu LIF)
description: NEGATIVE RESULT. Iterating "drive top-K active neurons" on the real Shiu substrate lands every trajectory step at cos>0.95 to every other — fixed-point attractor, no structured orbit.
type: project
---

# Real-W iterative rotate collapses to a fixed-point attractor

**Date:** 2026-04-13
**Script:** `fly-brain/shiu_rotate_test.py`
**Substrate:** Shiu LIF 138,639 neurons / 15,091,983 synapses, real
FlyWire v783 W.
**Question:** Does iterating the Shiu LIF dynamical map
`state_{n+1} = f(state_n)` — where f = "drive top-K active neurons of
state_n at 200 Hz for 100 ms, read spike-count vector" — produce a
structured trajectory of distinguishable states (the substrate-native
analog of the paper's `state ← R · state` rotation)?
**Answer: NO.** Every trajectory state is cos ≈ 0.97 to every other
trajectory state. The iteration lands in a fixed-point attractor by
step 1. No counting-by-orbit on real W under this protocol.

This is a critical negative result per CLAUDE.md rules 4 and 6. It is
not a noise or implementation failure — it is the substrate telling us
that generic top-K feedback does not rotate.

## Setup

- Start: random 50-neuron drive pattern v_0 (seed 42).
- Step: drive current set at 200 Hz for 100 ms, read per-neuron
  spike-count vector (138,639-D), pick top-K=50 active neurons by
  spike count as the next drive set.
- 10 iterations. Trajectory = [out_0, out_1, ..., out_9].
- Measure cos(out_i, out_j) for all pairs.

## Raw result

Per-step active-neuron counts stayed in a narrow band (59–77 active,
top-50 sum ~490–515 spikes), consistent with the iteration finding a
stable operating point fast.

**Cosine matrix (trajectory self-similarity):**

```
        i=0    i=1    i=2    i=3    i=4    i=5    i=6    i=7    i=8    i=9
 i=0: 1.000  0.972  0.966  0.971  0.969  0.970  0.971  0.967  0.978  0.971
 i=1: 0.972  1.000  0.967  0.980  0.965  0.964  0.970  0.952  0.975  0.967
 i=2: 0.966  0.967  1.000  0.974  0.962  0.974  0.969  0.969  0.968  0.970
 i=3: 0.971  0.980  0.974  1.000  0.974  0.971  0.973  0.970  0.978  0.984
 i=4: 0.969  0.965  0.962  0.974  1.000  0.971  0.979  0.966  0.978  0.974
 i=5: 0.970  0.964  0.974  0.971  0.971  1.000  0.975  0.969  0.975  0.974
 i=6: 0.971  0.970  0.969  0.973  0.979  0.975  1.000  0.973  0.976  0.976
 i=7: 0.967  0.952  0.969  0.970  0.966  0.969  0.973  1.000  0.962  0.973
 i=8: 0.978  0.975  0.968  0.978  0.978  0.975  0.976  0.962  1.000  0.979
 i=9: 0.971  0.967  0.970  0.984  0.974  0.974  0.976  0.973  0.979  1.000
```

Summary:
- mean cos(step_i, step_{i+1}) = 0.9717 (consecutive)
- mean cos(step_i, step_{i+2}) = 0.9720 (skip-1)
- cos(step_0, step_9)           = 0.9705 (endpoints)
- off-diagonal pairs with cos < 0.5: **0 / 90**
- off-diagonal pairs with cos < 0.95: small handful, all barely under

This is not a "trajectory with small step size." A small-step orbit
would show cos(0, 9) much lower than cos(0, 1). Here cos(0, 1) = 0.972
and cos(0, 9) = 0.9705 are indistinguishable. Step direction is not
preserved; the dynamics have converged.

## Why this is not surprising in hindsight

1. **Top-K feedback is non-linear and convergent.** Picking the
   highest-firing neurons as the next drive set creates a sharp
   positive-feedback loop: whatever downstream hub gets excited
   stays excited because its neurons are the top-K. The real W has
   dense hubs (KCs, MBONs, CX ring neurons) that act as attractor
   basins under this protocol.
2. **The paper's polar-decomp Q bypassed this.** Q is *constructed*
   to be orthogonal — its eigenvalues lie on the unit circle, so
   iterating Q·v produces a structured trajectory mathematically, by
   design. That's exactly the attractor CLAUDE.md names as forbidden:
   the math was doing the rotation because we chose a math object
   that rotates, not because the substrate does.
3. **The fly does rotate — but in a specific sub-circuit.** The CX
   EPG ring attractor (Kim 2017, Turner-Evans 2020, Kakaria & de
   Bivort 2017) implements rotation *biologically* via an explicitly
   ring-shaped recurrent network of ~46 EPG neurons with lateral
   inhibition. That is the circuit the paper should be running on —
   not generic 50-neuron random subsets.

## What this means for the paper

- The fly-brain paper's rotation claim, as currently framed around
  polar-decomp Q, does not survive contact with real W iterated
  dynamics under the generic protocol tested here. The reviewer's
  critique on this point is correct.
- The honest paper claim is narrower: **rotation runs on the specific
  CX sub-circuit that is biologically known to rotate; it does not
  run on arbitrary subsets of real W.**
- Next experiment: restrict the drive + readout to the EPG neuron
  population only (or EPG + hDelta joint 140-D subset already used
  for the paper's Q construction) and iterate within that sub-circuit.
  If structure appears there but not on whole-brain, that is the
  honest circuit-level claim the paper can stand behind.

## Caveats

- Only tested one protocol: top-K feedback. Alternatives that might
  behave differently:
  - Continuous drive proportional to spike count (not top-K threshold)
  - Smaller K (e.g. top-10) to be more selective
  - Longer windows so alpha-synapse dynamics can complete
  - Refractory-period-respecting state update
  - Spike-timing-based readout rather than spike-count
- Single starting seed. A multi-seed sweep might reveal whether the
  attractor basin depends on the starting pattern.
- Random input. Biologically-structured inputs (ORN or PN subsets)
  might engage different downstream circuits.

## Immediate follow-up

`shiu_rotate_cx_test.py` — restrict drive and readout to FlyWire EPG
cell-type population (or the 140-D EPG+hDelta subset used for the
paper's Q construction). If this produces a structured trajectory,
the paper claim becomes "the CX sub-circuit rotates on real W; our
polar-decomp Q was an approximation to what that sub-circuit does."
If not, the paper must drop the rotation claim and reframe around the
operations that do run on real W (bundle linear, snap 15/16).

## Implications for the queue

This result is more important than it is pretty. It matches the
pattern CLAUDE.md describes: a shortcut (polar-decomp Q) was masking
the fact that the underlying claim (real-W rotation) doesn't hold in
the generic form. The paper either narrows to a sub-circuit that
genuinely rotates, or drops the rotation claim and leans on the ops
that do run on real W.
