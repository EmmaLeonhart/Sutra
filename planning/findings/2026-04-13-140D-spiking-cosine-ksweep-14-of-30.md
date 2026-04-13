# 140-D substrate-only k-sweep — 14/30

**Date:** 2026-04-13
**Script:** `fly-brain/loop_140D_spiking_cosine_ksweep.py`
**Compare to:** `real_rotation_140D_jaccard_ksweep.py` → **30/30** (numpy
rotation + MB-Jaccard readout, paper's headline k-sweep)

## What was measured

Substrate-only 140-D loop (spiking rotation via `neural_linear_map` +
cosine readout on decoded voltage, Kabsch-corrected det=+1 Q) across
six target-k values × 5 seeds. Mirror of the paper's k-sweep harness
but with rotation executing on Brian2 synapse weights instead of numpy.

SIM_MS = 3000 ms per step, max_iters = 15, argmax-over-trajectory
termination. Wall clock 435 s.

## Raw numbers

```
k=1:  5/5  PASS
k=2:  5/5  PASS
k=3:  4/5  PASS  (seed 1 locks at k=1 — tied peak, same failure as v2)
k=5:  0/5  FAIL  (all seeds argmax at k=1)
k=8:  0/5  FAIL  (argmax drifts across k=1..6)
k=12: 0/5  FAIL  (argmax drifts across k=4..10)

TOTAL: 14/30
```

## Interpretation

The substrate rotates correctly for small k (1, 2, 3) and loses the
target past k=3. Two compounding mechanisms:

1. **Poisson decode noise accumulates multiplicatively across
   iterations.** Each `neural_linear_map` step injects rate-coded
   Poisson noise into the decoded voltage. After k iterations the
   state has drifted by O(√k) in angular error relative to the ideal
   `Q^k · v0`. At 140-D, by k≈4 this drift is comparable to the
   target-prototype separation, so argmax stops reliably landing on k.

2. **k=5, 8, 12 collapse to argmax at early k.** The decoded state at
   k=1 happens to be closer to the k=5 prototype than the (heavily
   noised) state at k=5 is. This is the Poisson ceiling kicking in
   hard at large k: the noise floor at step k is larger than the
   cosine distance from the target prototype to a clean Q-applied
   state near the origin of the trajectory.

## Compare against the numpy-rotation harness

`real_rotation_140D_jaccard_ksweep.py` gets 30/30 on the same k-grid
because:

- Rotation iterates in numpy: `state = Q @ state`, no Poisson noise.
- Readout is KC-Jaccard, which tolerates within-pattern noise at the
  readout stage, but there is no within-rotation noise to tolerate.

The 30/30 number is measuring "can numpy compute Q^k v0 correctly and
then can the MB Jaccard match it?" The answer is yes. The
substrate-only 14/30 measures "can spiking neurons iterate Q k times
without the Poisson ceiling eating the target?" The answer is yes for
k≤3 and no for k≥5.

## What this means for the paper

The paper ships two different measurements of "loop on the connectome":

1. **Headline (30/30)**: numpy rotation + real MB Jaccard readout.
   Compiles cleanly, 30/30 on the k-sweep. The rotation iteration
   is on the host, not the substrate. Readout IS on the substrate.
2. **Substrate-only (14/30)**: spiking rotation + cosine on decoded
   voltage. Rotation IS on the substrate. Readout substrate is the
   CX (voltage comparison), not the MB. 5/5 at k=1,2; 4/5 at k=3;
   0/5 beyond.

Both are legitimate numbers to report. They measure different things
and they should be labeled as such. Neither is "wrong" — they tell
the reader different things about what the substrate can do.

The combined pipeline (spiking rotation + MB Jaccard), which would
have given us both on-substrate at once, gets 0/5 because the MB
destroys the Poisson-noised rotation output at readout. See
`2026-04-13-combined-pipeline-0-of-5.md`. That is not fixable by
tuning — the MB is designed to decorrelate similar inputs.

## Implications

- **The substrate has a practical k-ceiling around 3 under current
  SIM_MS.** Paper can honestly report this bound. It is not a
  result that gets brushed under "Poisson noise"; it is the main
  quantitative constraint on how long a substrate-only Sutra loop
  can iterate before the readout loses the target.
- **Longer SIM_MS should push the ceiling higher** at a proportional
  wall-clock cost. Not measured here — the current experiment
  already ran 7 minutes. Would be a good follow-up but is not
  blocking the paper.
- **Paper's §Result 2 and §Honest Limits need rewriting** to
  present both pipelines side by side: the numpy-rotation + Jaccard
  "full paper demo" at 30/30 with its host-rotation caveat, and the
  substrate-only at 14/30 with its k≤3 ceiling. This is the task
  that follows this finding.
