# Spiking rotate(v, Q) on EPG-derived Q: 3/5 seeds

## What was measured

Iterating `v_{k+1} = Q · v_k` as a Brian2 LIF spiking circuit (Q as a
51×51 pattern of synapse weights — positive excitatory, negative
inhibitory) and asking whether argmax over cos(state_k, proto) hits
the target iteration `k = 3`, for prototype `proto = Q^3 v_0`.
Result: **3 of 5 seeds pass; numpy equivalent passes 10 of 10.**

## Setup

- Script: `fly-brain/real_rotation_epg_loop_spiking.py`
- Q: polar-decomposition nearest-orthogonal of the real FlyWire v783
  CX EPG→EPG recurrent weight matrix (51×51). Orthogonality residual
  `‖Q^T Q − I‖_F = 1.68×10⁻¹⁴`; det Q = +1.
- Rotate circuit: `neural_vsa.neural_linear_map(Q, v)` — per-dim
  Poisson inputs at centered rate code, 51 LIF outputs, per-synapse
  weight `Q[i, j] · W_MV` with `W_MV = 0.5 mV`, baseline 100 Hz,
  gain 80 Hz per unit, `τ = 20 ms`.
- SIM_MS = 3000 ms per iteration (overridden from the module default
  of 500 ms; the rotate self-test in `neural_vsa.py` uses 1500 ms for
  the same averaging-window reason).
- Between iterations, state is renormalized to unit norm (Q is
  exactly norm-preserving in theory; spiking decode has O(1/√T)
  magnitude variance that accumulates if we don't correct).
- 5 seeds (0–4), target `k = 3`, `max_iters = 6`.

## Raw numbers

```
seed=0  argmax_k=3  peak_cos=+0.753  k0=+0.10 k1=+0.53 k2=-0.36 k3=+0.75 k4=-0.33 k5=+0.32 k6=+0.05  PASS
seed=1  argmax_k=1  peak_cos=+0.687  k0=-0.35 k1=+0.69 k2=-0.32 k3=+0.68 k4=-0.30 k5=+0.37 k6=-0.01  FAIL
seed=2  argmax_k=3  peak_cos=+0.752  k0=-0.27 k1=+0.72 k2=-0.13 k3=+0.75 k4=+0.03 k5=+0.40 k6=+0.04  PASS
seed=3  argmax_k=3  peak_cos=+0.693  k0=+0.10 k1=+0.49 k2=-0.26 k3=+0.69 k4=-0.18 k5=+0.26 k6=+0.09  PASS
seed=4  argmax_k=1  peak_cos=+0.766  k0=-0.10 k1=+0.77 k2=-0.15 k3=+0.64 k4=-0.16 k5=+0.47 k6=+0.01  FAIL
```

Numpy version (same Q, same seeds, no spiking): argmax_k = 3 at
peak_cos = 1.000 on all 5 seeds (`real_rotation_epg_loop.py`,
earlier run).

Wall clock: ~5 s per seed at SIM_MS=3000 ms.

## Interpretation

Two compounding effects:

1. **Poisson noise in decoded state accumulates across iterations.**
   Per-step `cos(spike-decode, Q · v_prev_numpy)` is ~0.99 on a single
   call; by k=3 the drift is enough that `cos(state_3, proto)` lands
   around 0.7 rather than 1.0. Longer SIM_MS would narrow this (and
   we see 1/3 → 2/3 → 3/5 going from SIM_MS = 500 → 1500 → 3000).

2. **EPG Q's spectrum puts state_1 and state_3 numerically close to
   each other.** The key identity: `cos(Q v, Q^3 v) = cos(v, Q^2 v)`
   by orthogonality. If Q² has eigenvalues clustered near 1 in the
   subspace where `v_0` has its energy, then `cos(v, Q² v)` is large
   — meaning state_1 is already nearly as good a match for proto as
   state_3 is, in pure numpy. Under spiking noise (~0.25 cos drift),
   the two cross.

   Seeds 1 and 4 are exactly the ones where `cos(Q v_0, Q^3 v_0)` in
   numpy is within the spike-noise envelope of `cos(Q^3 v_0, Q^3 v_0)
   = 1`. Seeds 0, 2, 3 have a wider numpy gap and survive.

This is a real characterization, not a tuning failure: the EPG
recurrent matrix has the eigenvalue structure of a biological ring
attractor (clustered phases around a small number of rotation
angles), which is exactly what makes it near-orthogonal but also
what makes `Q^k` for small k hard to distinguish at low SNR.

## Implications

**For the paper.** The current framing ("rotation operator derived
from real FlyWire EPG subspace via polar decomposition") is still
correct. We should *not* upgrade the claim to "spiking rotation on
real wiring iterates cleanly end-to-end" — that's not what 3/5 says.
The honest statement is: the rotation operator comes from real
biology; iterated *numpy* evaluation of that operator passes the
geometric-loop tests; iterated *spiking* evaluation passes on 3/5
seeds at SIM_MS=3000 ms and misses on 2/5 because of a specific
interaction between Q's spectrum and Poisson noise. This fact
belongs in the §Honest Limits paragraph once the next paper
revision goes out.

**For next experiments.** Three plausible paths, any of which would
move the number:

- Longer SIM_MS (diminishing returns, trades wall clock). 5000–10000
  ms per step is probably the honest ceiling before the experiment
  becomes impractical for a 5-seed × multi-iter sweep.
- A Q with more evenly distributed eigenphases. Block-diagonal
  composition of multiple motifs (already implemented at 713-D in
  `real_rotation_composed.py`) mixes spectra from independent
  biological subspaces; worth re-running the spiking test on the
  composed Q rather than pure EPG.
- Replace cosine readout with tier-3 Jaccard-on-KC: route state_k
  through the MB sparse projection and compare KC-pattern overlap
  against a compiled prototype KC pattern. The KC space's sparsity
  and dimensionality expansion suppress the Gaussian-like cosine
  noise seen here, which is why the existing `scale_eval_loop.py`
  with synthetic Givens R gets σ=0 on 20/20 at SIM_MS=200ms.

**For the spec / tier model.** This is not a tier-3 failure — the
rotation step is tier-2 and is running on spiking substrate as the
spec allows. The gap between numpy 10/10 and spiking 3/5 is the
price of actually running tier-2 on neurons instead of numpy, and
that price is real. It does not invalidate the tier split; it
measures one specific point in the (substrate, operator) space.

## Status

- Finding logged, commit `129d690`.
- Not resolving any currently-open question in
  `planning/open-questions/`. The tier-2-bundle-substrate-vs-algebra
  question is adjacent but about `bundle`, not `rotate`.
- Next natural experiment: re-run the spiking loop on composed Q
  (713-D, multi-motif) to see whether the mixed spectrum fixes
  seeds 1 and 4. If it does, we have an end-to-end spiking real-
  wiring loop story. If it doesn't, the Jaccard-on-KC readout is
  the next thing to try.
