# Spiking rotate(v, Q) on composed 713-D real-wiring Q: 3/5 seeds

## What was measured

Running the same spiking counting test as
`2026-04-13-spiking-Q-rotation-3-of-5.md` but with `Q` block-diagonally
composed from four FlyWire motifs (EPG 51-D + LH 116-D + vDelta 357-D
+ hDelta 189-D = 713-D). **Result: 3/5 seeds pass — same rate as the
51-D EPG case, and peak cos dropped from ~0.7 to ~0.1.**

## Setup

- Script: `fly-brain/real_rotation_composed_spiking.py`
- Q: `block_diag` of four per-motif polar-decomposition nearest-
  orthogonal matrices. Residual `‖QᵀQ − I‖_F = 5.34×10⁻¹⁴`; det Q = +1.
- Same spiking config as the EPG run: `neural_vsa.neural_linear_map`,
  SIM_MS = 3000 ms, per-iteration renormalization, 5 seeds, target k=3,
  max_iters=6.
- Wall clock: 37 s total (7–8 s per seed). Much faster than feared
  given 713² synapses — Brian2 scales well here.

## Raw numbers

Numpy baseline (all 5 seeds, clean):
```
seed=0  k0=+0.00 k1=+0.12 k2=+0.01 k3=+1.00 k4=+0.01 k5=+0.12 k6=+0.00  argmax=3
seed=1  k0=-0.04 k1=+0.15 k2=-0.06 k3=+1.00 k4=-0.06 k5=+0.15 k6=-0.04  argmax=3
seed=2  k0=+0.01 k1=+0.12 k2=-0.00 k3=+1.00 k4=-0.00 k5=+0.12 k6=+0.01  argmax=3
seed=3  k0=-0.02 k1=+0.05 k2=+0.03 k3=+1.00 k4=+0.03 k5=+0.05 k6=-0.02  argmax=3
seed=4  k0=+0.02 k1=+0.21 k2=+0.02 k3=+1.00 k4=+0.02 k5=+0.21 k6=+0.02  argmax=3
```

Spiking (713-D composed Q):
```
seed=0  argmax=3  peak=+0.166  k0=+0.00 k1=-0.02 k2=+0.00 k3=+0.17 k4=-0.07 k5=-0.02 k6=+0.01  PASS
seed=1  argmax=1  peak=+0.148  k0=-0.04 k1=+0.15 k2=-0.01 k3=+0.07 k4=-0.04 k5=+0.02 k6=-0.04  FAIL
seed=2  argmax=6  peak=+0.078  k0=+0.01 k1=+0.04 k2=-0.00 k3=+0.06 k4=+0.04 k5=-0.05 k6=+0.08  FAIL
seed=3  argmax=3  peak=+0.057  k0=-0.02 k1=+0.02 k2=+0.03 k3=+0.06 k4=-0.00 k5=-0.05 k6=+0.03  PASS
seed=4  argmax=3  peak=+0.118  k0=+0.02 k1=+0.09 k2=-0.00 k3=+0.12 k4=+0.05 k5=-0.03 k6=+0.06  PASS
```

## Interpretation

The mixed-spectrum hypothesis predicted 4/5 or 5/5 — the idea was that
averaging `cos(v, Q²v)` across four independent subspaces would push it
away from 1 and widen the numpy gap between k=1 and k=3. The numpy
baseline confirms *that* part of the hypothesis: the gap is now enormous
(k=3 hits 1.00 at machine precision, k=1 sits at 0.05–0.21).

But the win in numpy SNR did not transfer to spiking. **Peak cos
collapsed from ~0.7 in the 51-D EPG case to ~0.1 in the 713-D composed
case.** The cause is the other half of the SNR equation: Poisson
rate-coded spike decoding has a per-dimension variance floor set by the
SIM_MS integration window. Going from 51 to 713 dimensions multiplies
the variance by ~14×; √14 ≈ 3.7×; the clean-vs-noisy cosine drops
roughly by that factor. The 1.00 gap at k=3 survives (barely), but the
cos values themselves are now in the regime where *any* correlated
noise spike at k=1 or k=6 can flip argmax.

Seed 2's argmax=6 is symptomatic: peak cos of 0.078 at k=6 vs 0.06 at
k=3. At this SNR, there is no robust signal — we are reading off
noise. Seed 0 passes with peak cos 0.17, barely above the background.

## Implications

**Negative result on the mixed-spectrum hypothesis, but informative.**
The bottleneck is not Q's spectrum — it is Poisson decode noise scaling
with dimension. Adding more independent motifs helps numpy but *hurts*
spiking decode because each extra dimension adds variance without
reinforcing the signal (the proto only has energy in the direction
`Q³v₀`, not uniformly across the 713-D space).

**For the paper.** The honest addition to §Honest Limits is that scaling
to the 713-D composed `Q` preserves numpy correctness but does not
improve the spiking pass rate — and in fact the peak cos degrades by
~7×, putting the 3/5 composed result much closer to a noise floor than
the 3/5 EPG result was. The 51-D EPG circuit's 3/5 is the strong number
here; the 713-D composed 3/5 is the same count but weaker evidence.

**For the three paths forward listed in the prior finding:**

- **Longer SIM_MS:** variance scales as 1/T, so 10× SIM_MS gets back ~3×
  peak cos. That would bring 713-D back up to the 51-D regime but cost
  30s → 5min per seed. Probably worth characterizing.
- **Tier-3 Jaccard-on-KC termination:** now the most promising path.
  Routing spiking state through the MB sparse projection converts the
  Gaussian-like cosine noise into a sparse pattern-overlap readout,
  which is what `scale_eval_loop.py` already demonstrates works at
  SIM_MS=200ms with synthetic Givens R. The composed-Q result reinforces
  that cosine readout is the wrong discriminator at high D.
- **Mixed-spectrum Q:** closed. Composition alone is not the fix.

## Status

- Finding logged alongside this commit.
- Does not close any open question. Clarifies that the rotation-loop
  SNR problem is readout-bound, not spectrum-bound.
- Next experiment: tier-3 Jaccard-on-KC termination on the 51-D EPG
  Q. If that brings 51-D pass rate to 5/5 it generalizes the existing
  synthetic-Givens result to real biology and is the strongest end-to-
  end story we can get without changing the substrate.
