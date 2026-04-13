# Target-k sweep on 140-D real-wiring Jaccard: 30/30

## What was measured

Counting-test pass rate at target `k ∈ {1, 2, 3, 5, 8, 12}` across 5
seeds each, on the 140-D real-wiring Q + real hemibrain MB Jaccard
loop. **Result: 30/30.** Every target k passes on every seed; every
loop terminates at exactly `n_iters == target_k`.

## Setup

- Script: `fly-brain/real_rotation_140D_jaccard_ksweep.py`
- Same Q and substrate as
  `planning/findings/2026-04-13-jaccard-140D-real-hemibrain.md`:
  140-D `Q = block_diag(Q_EPG_51, Q_hDelta-89)` from real FlyWire
  wiring; `FlyBrainVSA(use_hemibrain=True, snap_duration_ms=200)`;
  threshold=0.5 unchanged.
- `max_iters = max(8, target_k + 4)` so k=12 has room.
- 5 seeds (0–4).
- Wall clock: 80 s across all 30 trials.

## Raw numbers

```
k=1  | 5/5 PASS | n_iters: 1 1 1 1 1
k=2  | 5/5 PASS | n_iters: 2 2 2 2 2
k=3  | 5/5 PASS | n_iters: 3 3 3 3 3
k=5  | 5/5 PASS | n_iters: 5 5 5 5 5
k=8  | 5/5 PASS | n_iters: 8 8 8 8 8
k=12 | 5/5 PASS | n_iters: 12 12 12 12 12
```

## Interpretation

The Jaccard readout is not target-specific. Every k in the tested
range produces a target KC pattern that is distinguishable from every
off-target iterate at the chosen threshold. No re-tuning, no max_iters
pathology, no partial-period aliasing visible in the range tested.

This was the last residual worry: that k=3 just happened to sit at a
lucky point in the 140-D Q's spectrum. It doesn't. k=12 — four times
the tested horizon — still passes cleanly. Given that each extra
rotation step accumulates additional Poisson noise in the KC pattern,
and the KC pattern still matches the prototype exactly at iter 12
(peak Jaccard at target k = 1.000 means the top-K KCs match exactly),
the readout is robust as far out as we've pushed it.

## Implications

- **Loops problem is now fully closed** on the 140-D real-wiring
  substrate: end-to-end real wiring (rotation + readout), spec-aligned
  three-tier architecture, bimodal Jaccard gap with a measurement-
  justified threshold, stable across target k from 1 to 12.
- The paper's §Honest Limits §(iv) claim ("essentially solved") is
  supported by three independent findings (51-D synthetic MB, 713-D
  synthetic MB D-independence, 140-D real hemibrain MB) plus this
  target-k sweep.
- No queue items remain.

## Status

- Queue item 3 of 3 complete.
- Queue section in STATUS.md will be removed by this commit.
- Loops problem as scoped in `fly-brain-paper` is closed.
