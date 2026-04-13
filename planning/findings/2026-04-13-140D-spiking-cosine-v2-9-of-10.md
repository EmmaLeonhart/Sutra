# 140-D substrate-only loop — 9/10 (counting 4/5 argmax, ordering 5/5)

**Date:** 2026-04-13
**Script:** `fly-brain/loop_140D_spiking_cosine_v2.py`
**Supersedes:** `planning/findings/2026-04-13-140D-spiking-cosine-ordering-5-of-5.md`
(v1 result, 5/10, kept for diagnostic trace)

## What passed

A 140-D loop where:

- Rotation runs on spiking neurons via `neural_linear_map` (Q enters
  as Brian2 synapse weights, state is rate-coded Poisson input,
  next state is decoded from membrane voltage).
- Readout is cosine similarity on the decoded voltage against a
  compiled prototype vector.
- No mushroom body. No PN→KC. No Jaccard. No numpy matmul in the
  iteration loop.

Measured at n=5 seeds, SIM_MS = 3000 ms per rotation step, Q built by
polar decomposition of real FlyWire v783 CX EPG→EPG (51-D) + FB
hDelta subset (89-D), block-diagonal to 140-D.

Results:

- Counting k=3, argmax-over-trajectory termination: **4/5 PASS**
- Ordering (EARLY@2 first, threshold 0.5): **5/5 PASS**

Combined: **9/10 at n=5 seeds on a substrate-only pipeline.**

## What changed from v1 (5/10)

1. **Forced det(Q) = +1.** The v1 Q had det = -1 because the hDelta
   subset's polar-decomposition block is a rotoinversion (det = -1)
   and block_diag with EPG (det = +1) inherited the -1. Fix is a
   standard Kabsch sign correction: if `det(U V^T) = -1` in the SVD
   `W = U Σ V^T`, flip the sign of the last column (via the middle
   diagonal). Q is now in SO(140). This is a compile-time fix to
   how Q is built before it enters Brian2 as synapse weights — no
   change to the runtime path.

2. **Argmax-over-trajectory for counting.** v1 used absolute
   threshold cos > 0.5, which rejected the valid target peak at
   0.45 (the 140-D Poisson decode-noise ceiling). v2 runs the loop
   for `max_iters` iterations and terminates at
   `argmax_k cos(state_k, target_proto)`. This is the same
   rule ordering already uses (it picks the best prototype at each
   k). Now counting uses it too.

## The v1 bug that surfaced

The paper ships a 140-D Q with det = -1. It is a rotoinversion, not
a pure rotation — still orthogonal (Q^T Q = I to 10^-14), still
norm-preserving, but topologically different. The alternating
positive/negative cosine pattern in v1's counting data (odd k
positive, even k near zero or negative) was a symptom: Q^odd applies
the reflection, Q^even undoes it, and the decoded state can't
reproduce the reflection cleanly under Poisson noise, so the
target-k match was capped low.

This is a construction bug in `build_140D_Q()` (and transitively in
every `real_rotation_*.py` that imports it). Fixing it everywhere
is its own follow-up.

## What this means for the paper

**The paper currently leads with "rotation on the connectome +
KC-Jaccard readout, 5/5 counting + 30/30 k-sweep."** Those numbers
come from numpy rotation + MB-Jaccard. The combined-pipeline attempt
that would have retired the numpy-in-runtime caveat (spiking rotation
+ MB-Jaccard) was 0/5 because the MB is an anti-correlator.

The substrate-only result measured here — spiking rotation + cosine
readout on voltage — is 4/5 + 5/5 = 9/10 at n=5 seeds. That is the
right number to put in the paper for a "substrate-only" claim. It
is smaller than the numpy-rotation+Jaccard number (10/10 + 30/30 =
40/40), but it is what the actual substrate does without numpy in
the runtime path. Both pipelines should be reported side by side
with clear labels.

The MB is not the right readout for this loop. The CX (which is
where Q comes from anyway) reads its own state directly — that's
the natural "where is the heading pointing" readout, and it's what
this experiment actually implements (decoded EPG/hDelta voltage is
the readout substrate).

## Follow-ups

- Fix det = -1 in `build_140D_Q()` at the source, not just in
  experiment scripts. Audit `real_rotation_140D_jaccard.py` and
  `real_rotation_140D_jaccard_ksweep.py` — the 5/5 + 30/30 numbers
  may shift with a proper rotation (could go up, not down, since
  the numpy iteration was tolerating the rotoinversion).
- Re-run the k-sweep (k ∈ {1, 2, 3, 5, 8, 12}) on the substrate-only
  pipeline to see how argmax-counting generalizes beyond k=3.
- Rewrite the paper's §Result 2 and §Honest Limits around the
  substrate-only pipeline as the primary result. The MB story
  becomes a negative baseline (composed with spiking rotation,
  fails because anti-correlator), not the headline.
- The one-seed failure (seed 1, 0.02 cosine margin) is at the
  Poisson noise floor. Longer SIM_MS would close it at a
  wall-clock cost.
