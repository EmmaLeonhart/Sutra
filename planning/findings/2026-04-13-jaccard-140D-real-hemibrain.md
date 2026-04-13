# 140-D real-wiring Q + real hemibrain MB Jaccard: 5/5 + 5/5

## What was measured

Running the Jaccard-on-KC loop test with:
- **rotation:** 140-D `Q` built as `block_diag(Q_EPG_51, Q_hDsubset_89)`,
  both blocks from real FlyWire v783 polar-decomposition nearest-
  orthogonal.
- **readout:** real hemibrain v1.2.1 PN→KC wiring (140 PNs → 1882
  KCs), APL sparsification, 200 ms snap window. No synthetic MB.

**Result: 5/5 counting to k=3 + 5/5 ordering (EARLY first).** Wall
clock 16 s total across 10 trials. This closes the synthetic-MB
caveat from the 51-D Jaccard run: both the rotation and the readout
are now real connectome wiring.

## Setup

- Script: `fly-brain/real_rotation_140D_jaccard.py`.
- 89-D hDelta subset: types hDeltaJ (30) + hDeltaK (31) + hDeltaA
  (12) + hDeltaD (8) + hDeltaE (8) = 89 neurons. Chosen by subset-sum
  over FlyWire hDelta type sizes to hit exactly 140 − 51 = 89.
- 140-D Q: orthogonality residual at machine precision (block_diag
  of two machine-precision orthogonal blocks is still machine
  precision).
- Substrate: `FlyBrainVSA(use_hemibrain=True, snap_duration_ms=200)`.
  dim auto-detected as 140 from the hemibrain cache, exactly matching
  our composed Q.
- Threshold = 0.5 (unchanged from the 51-D and 713-D runs).
- 5 seeds (0–4).

## Raw numbers

Jaccard gap probe (seed=0, target k=3, real hemibrain MB):
```
k=1  jaccard=0.373
k=2  jaccard=0.182
k=3  jaccard=1.000   ← target
k=4  jaccard=0.211
k=5  jaccard=0.245
k=6  jaccard=0.203
```

Counting k=3:
```
seed=0  PASS n_iters=3
seed=1  PASS n_iters=3
seed=2  PASS n_iters=3
seed=3  PASS n_iters=3
seed=4  PASS n_iters=3
```

Ordering (EARLY@2 / MIDDLE@5 / LATE@8):
```
seed=0  PASS matched=EARLY n_iters=2
seed=1  PASS matched=EARLY n_iters=2
seed=2  PASS matched=EARLY n_iters=2
seed=3  PASS matched=EARLY n_iters=2
seed=4  PASS matched=EARLY n_iters=2
```

## Interpretation

### End-to-end real wiring works

The composition is:
- Rotation operator: polar decomposition of real FlyWire EPG→EPG (51)
  and real FlyWire hDelta-subset→hDelta-subset (89).
- Rotation execution: host numpy matmul (tier-2, spec-compliant per
  `02-operations.md`).
- Readout: real hemibrain 140-PN → 1882-KC projection run as a Brian2
  spiking circuit with APL inhibition for sparsification; termination
  decided by Jaccard overlap in KC space (tier-3).

All 10 trials pass. The "next active experiment" from the 51-D
finding is resolved.

### Hemibrain MB is noisier than random-at-matched-dim but still clean

Off-target max Jaccard sitting at 0.373 (seed 0, k=1) is higher than
both the 51-D synthetic case (0.237) and the 713-D synthetic case
(0.049). This makes sense structurally: real PN→KC wiring is not a
uniform random expander — it has biological biases (clustered KC
claws, non-uniform PN reach), so two rotated states are more likely
to drive overlapping KC subsets than under a uniform random
projection. The bimodal separation still holds — off-target is
clamped below 0.4, target is at 1.0 — and threshold=0.5 discriminates
cleanly.

If we pushed to very high target `k` or composed a Q whose spectrum
is pathologically ring-attractor-like across most of its volume, the
hemibrain off-target mode could approach 0.5 and this threshold might
fail. That would be a new experiment (queue item 3: target-k sweep),
not a current limitation.

### The dimension and the wiring are both real

At this point the paper's claim "loops on a connectome-derived
circuit" reduces to: the rotation operator is polar-decomposition of
real FlyWire synapse counts; the readout is real hemibrain synapse
counts; the match test is the biologically-prescribed KC-Jaccard.
The only non-substrate step is the host-side `state ← R^i · v₀`
matmul, which the spec explicitly keeps on the host as a tier-2
algebraic op. There is no longer any "random synthetic matrix" in
the path.

## Implications

### Paper update warranted

`fly-brain-paper` §Honest Limits §(iv) currently describes the
"remaining caveat" as "the MB readout uses random PN→KC wiring at
matched 51-D rather than real hemibrain." That caveat is now closed.
The paper can be updated to state: at D=140, with real FlyWire
rotation and real hemibrain readout, counting and ordering both pass
5/5. This is the strongest end-to-end claim the substrate allows
without moving to physical in-vivo execution (which is explicitly
out of scope).

### What remains

- **Target-k sweep (queue item 3).** Only k=3 counting is tested;
  confirm Jaccard-readout robustness at k=5, 8, 12.
- **Physical deployment.** Not a software question.

## Status

- Finding logged with this commit.
- Queue item 2 of 3 complete.
- Next: queue item 3 (target-k sweep).
