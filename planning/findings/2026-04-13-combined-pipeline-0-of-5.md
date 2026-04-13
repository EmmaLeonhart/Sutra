# Combined pipeline (spiking rotation + KC-Jaccard, 140-D) — 0/5

**Date:** 2026-04-13
**Script:** `fly-brain/combined_pipeline.py`
**Result:** 0/5 counting at k=3, 0/5 ordering. Pipeline does **not** pass.

## What was measured

End-to-end substrate pipeline at 140-D:

- Rotation: `state ← Q · state` via `neural_vsa.neural_linear_map` (Q as
  Brian2 synapse weights, state rate-coded as Poisson, output decoded
  from membrane voltage). No numpy matmul on the state at runtime.
- Readout: MB PN→KC on real hemibrain wiring with APL sparsification,
  Jaccard against a compiled prototype KC pattern. Threshold 0.5.
- SIM_MS = 3000 ms per rotation step.

Both halves run on the substrate. Numpy is used only to build Q (polar
decomposition of FlyWire weights, compile-time), draw `v₀`, and
compute the numerical prototype `Q^k v₀` that is then itself pushed
through the substrate once to get its KC pattern. Iteration and
matching happen on neurons.

## Raw numbers

Counting k=3 (5 seeds, Jaccard by iteration):

```
seed=0  k1=0.24 k2=0.19 k3=0.33 k4=0.18 k5=0.24 k6=0.14 k7=0.22 k8=0.18
seed=1  k1=0.31 k2=0.15 k3=0.27 k4=0.15 k5=0.22 k6=0.21 k7=0.20 k8=0.21
seed=2  k1=0.37 k2=0.19 k3=0.30 k4=0.11 k5=0.22 k6=0.11 k7=0.17 k8=0.16
seed=3  k1=0.29 k2=0.21 k3=0.36 k4=0.12 k5=0.26 k6=0.16 k7=0.24 k8=0.16
seed=4  k1=0.29 k2=0.24 k3=0.38 k4=0.16 k5=0.17 k6=0.15 k7=0.21 k8=0.18
```

Ordering: all 5 seeds terminated with matched=None (nothing ever
crossed 0.5 across 15 iterations).

Wall clock: 337s across 10 runs.

## Interpretation

The numpy-iterated 140-D pipeline (`real_rotation_140D_jaccard.py`)
produces Jaccard = 1.000 at target and ≤0.373 off-target — a clean
bimodal distribution with an order-of-magnitude gap, which is the
entire reason the Jaccard-threshold-0.5 design works.

Spiking rotation collapses that distribution. At target k=3 the
Jaccard is 0.27–0.38 — indistinguishable from the off-target band
(0.11–0.26). There is no peak at target. The iteration is not
drifting *around* the correct prototype pattern; it is visiting
*different* KC patterns than the prototype.

The physical reason is that the mushroom body is an anti-correlator:
APL-sparsified PN→KC is specifically designed so that similar inputs
produce maximally-different sparse codes. A "mostly right" rotated
state (close to `Q^k v₀` in vector-space cosine but perturbed by
Poisson decode noise) does not project to a "mostly right" KC mask —
it projects to a *freshly sparse* KC mask that happens to share only
a small chance-level overlap with the prototype's mask.

Jaccard tolerates noise *within* a pattern (same mask with a few
flipped bits). It cannot tolerate noise that changes *which* mask
the substrate lands on. The cosine-side Poisson noise on the spiking
rotation is large enough to cross the anti-correlator's discrimination
threshold, and once you cross it the KC-space distance is effectively
randomized.

## Why this contradicts the earlier hypothesis

The combined_pipeline.py docstring predicted that Jaccard would
tolerate the decode noise because it is "categorical match/no-match
on a sparse binary pattern." That was wrong. The prediction was
based on Jaccard's tolerance of *per-dimension* noise in the rotated
state, but the PN→KC projection is not per-dimension preserving —
it is a sparse projection designed to decorrelate. Small vector-space
perturbations become large KC-space perturbations by design.

Corollary: chaining spiking-rotation and MB-Jaccard as written is
not the right pipeline architecture. The two halves each work in
isolation (rotation spiking at 51-D passes 3/5 with cosine;
KC-Jaccard at 140-D passes 5/5 when rotation is iterated on numpy)
but composing them multiplies their failure modes rather than
covering them.

## Implications

- **Do not delete** the numpy-iterated rotation files
  (`real_rotation_140D_jaccard.py` etc.). They remain the only
  pipeline that achieves the paper's loop-test numbers, and the
  spec-compliance gap (numpy `Q @ v` at runtime) is still open.
- **Do not rewrite the paper** claiming a substrate-only loop. The
  §Honest Limits section's retraction about the numpy `Q@v` gap
  remains current and correct.
- **The real open question** is how to run rotation on neurons
  without the Poisson decode noise destroying the readout. Candidates:
  (a) much longer integration windows (SIM_MS ≫ 3000 ms — but this
  scales linearly with iteration count and is already dominant at
  3000 ms); (b) denoising the rotated state before PN→KC via a
  substrate-side cleanup step (attractor dynamics in a recurrent
  layer that pulls the state toward the nearest codebook vector
  before it gets sparsified); (c) a different rotation substrate
  whose output is a sparse code directly, bypassing the
  vector-space → KC-space re-encoding step.
- **The tier framing removal is still correct** regardless of this
  result. The rule "every op runs on the substrate" is a design
  commitment, not a claim about what currently does. This finding
  is a measurement of how far current implementations are from that
  commitment.

## Status

Negative result. Documented here, reported to STATUS.md queue item 3
as "pipeline built and measured, does not pass." No paper claims
change; the paper's existing retraction about the numpy `Q@v` gap
remains accurate.
