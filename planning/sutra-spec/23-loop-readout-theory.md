# 23. Loop Readout: Why KC-Jaccard, Not Cosine

## Summary

`loop (condition)` in Sutra compiles to eigenrotation (`03-control-flow.md`):
the host iterates `state_k = R^k · v_0` and the substrate checks
whether `state_k` matches a prototype. The spec prescribes the match
test as **Jaccard overlap of mushroom-body KC patterns**, not cosine
similarity of PN-space vectors. This document explains why that
choice is load-bearing, not stylistic. It is written because
empirical results from the fly-brain substrate (`planning/findings/
2026-04-13-*`) show the two readouts differ by an order of magnitude
in pass rate under Poisson spike noise — cosine readout tops out at
3/5 seeds, KC-Jaccard readout achieves 5/5 — and without a principled
reason that gap looks like tuning. It isn't; it's an SNR argument.

## The question

Given a spiking substrate with per-dimension Poisson decode noise and
a prototype vector `p = R^k_target · v_0`, how should the substrate
decide whether the current state matches `p`?

Two options are on the table:

1. **Cosine test.** Decode the spiking state back to a vector `v_hat`
   in PN space, compute `cos(v_hat, p)`, compare against a threshold.
2. **KC-Jaccard test.** Project the state through the mushroom body
   (PN → KC with APL sparsification), compare the resulting binary KC
   pattern against a pre-compiled prototype KC pattern via Jaccard
   overlap, threshold that.

Both are valid readouts. The claim is that option 2 is strictly
better on a spiking substrate with Poisson noise, and that the gap
*grows* with dimension.

## Noise model

The substrate is a Brian2 LIF population with Poisson rate-coded
inputs. Each decoded dimension of a D-dimensional state vector carries
independent Poisson spike-count variance. For a simulation window of
`T` ms and a per-dimension firing rate in the 0.5 × `gain` range
characteristic of `neural_vsa.py`, the per-dimension decode variance
is `σ² ∝ 1/T`.

The decoded vector is `v_hat = v_true + ε` where `ε ~ N(0, σ² I_D)`
(approximately, for T large enough that Poisson counts are
Gaussian-like).

## Cosine readout: SNR scales as 1/√D

`cos(v_hat, p) = (v_true · p + ε · p) / (‖v_hat‖ · ‖p‖)`.

The signal term `v_true · p` is an O(1) scalar (states and prototypes
are unit-norm). The noise term `ε · p` is a scalar with mean 0 and
variance `σ² ‖p‖² = σ²`. The denominator is O(1) with small
multiplicative fluctuation.

So `SNR = signal / stdev(noise) ∝ 1/σ ∝ √T`. This is not the
scaling problem yet. The problem appears when the signal `v_true · p`
is *itself* small because the operator spectrum puts off-target
iterates close to the target — e.g. for a ring-attractor `Q` with
eigenphases clustered near 1, `cos(state_1, state_3) = cos(v_0, Q^2
v_0)` can be numerically close to 1, so the cosine gap between
true-target `state_3` and adjacent `state_1` or `state_5` is narrow.
Poisson noise of amplitude σ then straddles that gap on a constant
fraction of seeds.

Worse: Poisson noise energy scales with `D` (D i.i.d. contributions
to the variance of `‖ε‖²`), while signal energy is concentrated.
Peak `cos(v_hat, p)` observed empirically drops from ~0.7 at D=51 to
~0.1 at D=713 on the composed FlyWire `Q`, a factor of ~7 —
consistent with the 1/√(713/51) = 1/3.7 per-component drop compounded
by tighter eigenvalue clustering in the mixed spectrum. See
`planning/findings/2026-04-13-composed-Q-spiking-3-of-5.md`.

## KC-Jaccard readout: bimodal with O(1) gap

The mushroom body is a sparse random projection (`PN → KC` with
~20-row-weight expander `W` in binary approximation) followed by APL
winner-take-all sparsification. Output is a binary vector
`kc(v) ∈ {0,1}^{N_KC}` with sparsity `s ≈ 0.05–0.10` — i.e. the top
`~s·N_KC` KCs by summed PN input fire; the rest are silenced.

For two *unrelated* states `v, v'`, `kc(v)` and `kc(v')` are
approximately independent binary masks with sparsity `s`. Expected
Jaccard overlap:

    E[ |kc(v) ∩ kc(v')| / |kc(v) ∪ kc(v')| ] ≈ s² / (2s − s²) ≈ s/2

For `s ≈ 0.05–0.10`, chance Jaccard is in `[0.025, 0.05]`.

For two *matching* states — same PN-space vector up to noise — the
KC pattern is determined by the top-K PN → KC currents, and modest
Poisson perturbations don't flip the top-K ranking (the margin
between rank-K and rank-(K+1) KC is a constant fraction of the total
input, not a 1/√D fraction). So matching Jaccard is near 1.

The resulting distribution of Jaccard(state_k, proto) across k is
**bimodal**: one mode at chance (~0.05), one mode at match (~1.0),
with an O(1) gap between them that does not depend on D. Empirically
on the 51-D EPG `Q` (`planning/findings/
2026-04-13-jaccard-on-KC-5-of-5.md`):

    k=1  jaccard=0.237
    k=2  jaccard=0.015
    k=3  jaccard=1.000   ← target
    k=4  jaccard=0.007
    k=5  jaccard=0.230
    k=6  jaccard=0.045

Off-target iterates sit in [0.007, 0.237]; target is at 1.000. A
threshold anywhere in (0.25, 0.95) discriminates perfectly. The k=1
and k=5 values at ~0.23 reflect the eigenspectrum's partial period
(Q has ring-attractor-clustered eigenphases, so states at `k` and
`k+4` partially re-align) — this is a real signal about the operator,
not readout noise, and it sits well below 0.5.

## Why the gap doesn't close with dimension

As D grows, both the prototype and the state are projected into the
same `N_KC`-dimensional sparse code. APL sparsification acts as a
normalizer: it selects top-K firing KCs regardless of how many PN
dimensions feed in. So the chance Jaccard (≈ s/2) and the match
Jaccard (≈ 1) are both invariant to D. The gap between chance and
match is D-independent.

Contrast with cosine: because cosine noise scales with the L2 norm
of a D-dimensional Gaussian, the gap in cosine space *shrinks* as
`√D`. This is why composed-Q spiking collapsed at D=713 while the
KC-Jaccard readout would not.

## Why this is the spec's prescription, not a workaround

The Sutra spec (`03-control-flow.md`) prescribes KC-Jaccard because
the mushroom body is anatomically and computationally an
**anti-correlator / classifier** — its job is to discriminate sparse
patterns with minimal cross-talk (see Modi et al. 2020 for the
biology; Kanerva 2009 for the VSA-theoretic framing of sparse
distributed memory). Using it as a loop-termination readout is
aligned with the substrate's native function.

Cosine on raw PN space is using the substrate as a linear
interpolator, which it is not. The empirical gap between the two
readouts (3/5 vs 5/5) is the cost of using the wrong substrate
operation.

This is also the reason *both* tiers (tier-2 algebra and tier-3
substrate) are needed. Tier-2 (`R^k · v_0`) is clean linear algebra
and can run on any orthogonal matrix, including a real FlyWire `Q`.
Tier-3 (MB Jaccard) is categorical — match / no-match — and
inherently substrate-level. Trying to merge them (e.g. "run the
rotation on neurons and read out the rotation result via cosine") is
the configuration that empirically fails.

## Consequences for the spec

The following are prescribed, not optional, for `loop (condition)`:

1. The state trajectory `R^k v_0` may be computed on the host (tier-2
   algebraic per `02-operations.md`). Running it on the substrate is
   not incorrect but not required; the pass rate does not depend on
   where the rotation runs, only on where the readout runs.
2. The termination check **must** route through a sparse KC
   projection (tier-3). Direct cosine comparison of decoded state to
   prototype is non-spec-compliant and degrades with dimension.
3. The match threshold should be picked from the observed bimodal
   distribution of the particular `R`, not copied from a default. For
   operators with ring-attractor-clustered spectra (like EPG), the
   off-target mode extends higher (up to ~0.24 for the 51-D EPG Q)
   and the threshold should sit above that. A default of 0.5 is
   conservative across all operators we've measured.

## Open implementation questions

- **Hemibrain matching-dimension requirement.** The MB readout in
  `vsa_operations.py` uses the hemibrain PN count (140) as its input
  dimension. For a real-wiring `Q` of arbitrary dimension `D ≠ 140`,
  either `Q` must be embedded non-trivially in 140-D (an identity
  padding fails — the unchanged dims dominate the KC projection and
  every loop terminates at iter 1) or the MB loader must be rebuilt
  at dimension `D`. See the caveat in
  `planning/findings/2026-04-13-jaccard-on-KC-5-of-5.md`. Current
  workaround: use a random PN→KC projection at matched dimension
  (`use_hemibrain=False`). Real hemibrain readout at arbitrary D is
  an open implementation question, not a theoretical one — the theory
  above is dimension-invariant.

## References in this repo

- Empirical result: `planning/findings/2026-04-13-jaccard-on-KC-5-of-5.md`
- Cosine-readout baseline: `planning/findings/2026-04-13-spiking-Q-rotation-3-of-5.md`
- Cosine collapse with D: `planning/findings/2026-04-13-composed-Q-spiking-3-of-5.md`
- Spec for `loop (condition)`: `planning/sutra-spec/03-control-flow.md`
- Tier model: `planning/sutra-spec/02-operations.md`
- Substrate architecture: `planning/sutra-spec/19-substrate-candidates.md`
- Implementation: `fly-brain/real_rotation_epg_loop_jaccard.py`,
  `fly-brain/vsa_operations.py` (`FlyBrainVSA.loop`,
  `compile_prototypes`).
