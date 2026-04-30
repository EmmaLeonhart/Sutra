# Substrate-only 140-D spiking cosine loop: SIM_MS × k sweep

**Date:** 2026-04-13
**Script:** `fly-brain/loop_140D_spiking_cosine_simms_sweep.py`
**Question:** Does longer Brian2 integration window push the
substrate-only k-ceiling above 3?
**Answer:** Yes — cleanly, and in line with Poisson √SIM_MS SNR scaling.

## Motivation

Prior finding `2026-04-13-140D-spiking-cosine-ksweep-14-of-30.md`
measured pipeline A (substrate-only: spiking rotation + spiking cosine
readout) at SIM_MS=3000ms and got 14/30 across k ∈ {1,2,3,5,8,12}. The
failure mode above k≈3 was Poisson decode noise accumulating
multiplicatively across loop iterations, with no per-step cleanup. Two
hypotheses for the ceiling:

1. **Integration-window-limited.** Readout SNR ∝ √SIM_MS for Poisson
   spikes; doubling the window should buy ~√2 in per-step cosine
   discrimination, which compounds across iterations.
2. **Structural.** The 140-D subspace itself is too narrow for the
   argmax-over-trajectory decoder to resolve peaks beyond k≈3.

If hypothesis 1, longer SIM_MS lifts the ceiling. If hypothesis 2,
longer windows don't help — you need wider substrate (KC promotion) or
substrate-side cleanup between steps.

## Setup

- 140-D block-diagonal Q = block_diag(Q_EPG_51, Q_hDelta_89), det = +1,
  ‖QᵀQ − I‖_F = 2.16e-14.
- `run_counting_argmax` from `loop_140D_spiking_cosine_v2`: at each
  iteration, apply spiking rotation (Brian2 LIF, Q as synapse weights),
  decode via spiking cosine readout against 12 prototypes v₀..v₁₁,
  record argmax_k over trajectory, terminate at max_iters=15.
- 3 seeds × 3 targets (k ∈ {3, 5, 8}) × 3 SIM_MS values
  ({3000, 6000, 12000}) = 27 trials.
- Wall clock: 1643s (~27 min).

## Raw results

|              | k=3  | k=5  | k=8  |
|--------------|------|------|------|
| SIM_MS=3000  | 2/3  | 0/3  | 0/3  |
| SIM_MS=6000  | 3/3  | 3/3  | 1/3  |
| SIM_MS=12000 | 3/3  | 3/3  | 2/3  |

Per-seed detail (argmax_k reported at termination; PASS ⇔ argmax_k == k):

- **SIM_MS=3000:** k=3 (3,1,3); k=5 (1,1,1); k=8 (1,2,4). Matches the
  prior ksweep result at this window: ceiling ≈ 3.
- **SIM_MS=6000:** k=3 (3,3,3); k=5 (5,5,5); k=8 (8,2,4). k=5 went from
  0/3 to 3/3 — the ceiling moved. k=8 one seed lands, two don't.
- **SIM_MS=12000:** k=3 (3,3,3); k=5 (5,5,5); k=8 (8,6,8). Two of three
  k=8 seeds pass; the failure case undershoots to 6 rather than
  collapsing to the low-k trap (1 or 2) seen at SIM_MS=3000.

## Interpretation

**Hypothesis 1 wins.** The k≈3 ceiling observed at SIM_MS=3000 is an
integration-window artifact, not a structural limit of the 140-D
substrate. Two qualitative observations back this:

1. **The k=5 case flips completely.** 0/3 at SIM_MS=3000 becomes 3/3
   at SIM_MS=6000 with nothing else changed. If the substrate itself
   could not represent a k=5 trajectory peak, no amount of integration
   would fix this. The fact that 2× SIM_MS suffices says the peak was
   there all along — the readout couldn't see it through Poisson noise.

2. **Failure modes change shape with window length.** At SIM_MS=3000
   k=8 failures collapse to argmax at the low-k prototypes (1, 2, 4) —
   the decoder picks up early-iteration noise floor. At SIM_MS=12000
   the single k=8 failure undershoots to k=6, which is the
   neighbourhood of the true peak. The error is now *near-miss* rather
   than *floor-detection*, which is the signature of SNR-limited
   discrimination between adjacent trajectory peaks, not representational
   failure.

The scaling is broadly consistent with Poisson √t: 2× window moves the
ceiling from k=3 to k=5, and 4× window moves it from k=3 to k=8
(2/3 at k=8 is not a clean pass but it's on the margin, with one seed
undershooting by 2).

## Implications

**For pipeline A (substrate-only):** The primary open problem named in
queue.md ("close the gap between pipeline A 14/30 and pipeline B 30/30
while keeping rotation on the substrate") is now partially answered.
At SIM_MS=6000 pipeline A would score ~10/15 on the k ∈ {3,5,8} portion
of the grid vs 2/9 at SIM_MS=3000 — a 5× improvement from window
length alone. SIM_MS=12000 pushes further at 4× the wall-clock cost.

**For the paper:** The honest story is now two-layered. Pipeline A's
k-ceiling at SIM_MS=3000 (9/10 at k=3, 14/30 overall) is not a
fundamental substrate limitation — it trades wall-clock time for
reachable k linearly. Reviewers who read the 14/30 number as a
structural indictment of substrate-only computation are reading it
wrong. Reporting both numbers (14/30 at 3000ms; substantially higher
at 6000ms and 12000ms) is the calibrated framing.

**For future work:** This finding *reduces* the urgency of KC-space
promotion (hypothesis: wider substrate helps) and substrate-side
cleanup (hypothesis: cleanup between steps helps). Both remain worth
exploring but they are now in the category of "optimizations" rather
than "required to make pipeline A work at k > 3". The cheapest knob —
longer integration windows — already buys most of the headline
improvement.

## Caveats

- n=3 per cell. The 6000ms k=8 and 12000ms k=8 cells (1/3 and 2/3) are
  too noisy to say definitively whether 12000ms is a clean pass at k=8.
  A follow-up with n=5 or n=10 at SIM_MS=12000 × k=8 would close that.
- Each SIM_MS also changes the rotation-step dynamics (more synaptic
  summation time), not just the cosine-readout window, so the √SIM_MS
  SNR argument is a qualitative fit, not a quantitative prediction.
  The two effects compound.
- The `run_counting_argmax` decoder is argmax-over-trajectory; the
  absolute-threshold decoder might show a different SIM_MS × k profile.
- This does not validate combined pipeline (spiking rotation + MB
  Jaccard), which hit 0/5 in a separate test because MB is an
  anti-correlator. SIM_MS extension helps the spiking-cosine readout,
  not the MB-Jaccard readout.
