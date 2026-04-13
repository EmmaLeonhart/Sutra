# Rotation pipeline — which file does what

This repo accumulated ~10 `real_rotation_*.py` scripts as the
real-wiring rotation pipeline evolved motif-by-motif. They are
**not** redundant copies — each one tests a specific combination of
(Q construction, dimension, iteration substrate, readout). This
manifest says which is active for the paper, which is historical,
and which finding each produced. Read this before touching any of
them; don't add a new variant without updating the table.

## Pipeline stages

Rotation in Sutra decomposes into four axes:

1. **Q construction.** How the orthogonal operator is derived from
   FlyWire weights. Start: SVD survey. Then: polar decomposition of
   a single motif (EPG, 51-D). Then: block-diagonal composition
   across motifs (EPG + LH + FB vDelta + FB hDelta, 713-D). Then:
   140-D tile matched to hemibrain's PN count (EPG 51 + hDelta 89).
2. **Iteration substrate.** Numpy matmul `Q @ v` — a substrate-compliance
   gap per the current spec (`planning/sutra-spec/02-operations.md`
   requires every vector operation to run on the substrate at runtime;
   numpy is allowed only for compile-time Q construction and
   post-hoc monitoring) — vs Brian2 LIF via `neural_linear_map` (Q as
   synapse weights, Poisson-rate-coded input → steady-state voltage
   readout).
3. **Readout.** Direct cosine against target `Q^k v_0` vs mushroom-body
   Jaccard on KC patterns (sparse projection, 5% APL-enforced sparsity).
4. **Evaluation.** Counting-at-k, ordering (EARLY-first), target-k
   sweep, multi-seed.

## Active files (keep)

| File | Q | Iteration | Readout | Result | Finding doc |
|---|---|---|---|---|---|
| `survey_rotation_candidates.py` | — | — | — | Found EPG→EPG is 10× closer to orthogonal than anything else in FlyWire | — |
| `real_rotation_epg.py` | EPG polar decomp, 51-D | — | — | Q^T Q = I to 1e-14, det = +1 | — |
| `real_rotation_epg_loop.py` | EPG 51-D | numpy | cosine | **10/10 counting + 5/5 ordering** (numpy reference) | — |
| `real_rotation_composed.py` | EPG+LH+vDelta+hDelta, 713-D | numpy | cosine | 10/10 + 5/5 at every stage; orth residual 5.34e-14 | — |
| `real_rotation_epg_loop_spiking.py` | EPG 51-D | Brian2 LIF | cosine | 3/5 seeds at k=3 (numpy is 10/10; cos-readout Poisson noise) | `planning/findings/2026-04-13-spiking-Q-rotation-3-of-5.md` |
| `real_rotation_composed_spiking.py` | Composed 713-D | Brian2 LIF | cosine | 3/5 seeds (peak cos ~0.1 in high-D) | `planning/findings/2026-04-13-composed-Q-spiking-3-of-5.md` |
| `real_rotation_epg_loop_jaccard.py` | EPG 51-D | numpy | KC-Jaccard | 5/5 (readout test — rotation half is numpy, not substrate) | `planning/findings/2026-04-13-jaccard-on-KC-5-of-5.md` |
| `real_rotation_composed_jaccard.py` | Composed 713-D | numpy | KC-Jaccard | 5/5 (dimension independence) | `planning/findings/2026-04-13-jaccard-713D-dim-independence.md` |
| `real_rotation_140D_jaccard.py` | EPG 51 + hDelta 89 = 140-D real-wiring | numpy | KC-Jaccard on real hemibrain | **5/5** (currently headline result for paper §Result 2; rotation half runs on numpy — substrate-compliance gap) | `planning/findings/2026-04-13-jaccard-140D-real-hemibrain.md` |
| `real_rotation_140D_jaccard_ksweep.py` | 140-D real-wiring | numpy | KC-Jaccard | **30/30** across k ∈ {1,2,3,5,8,12} × 5 seeds (same numpy-rotation caveat) | `planning/findings/2026-04-13-jaccard-target-k-sweep-30-of-30.md` |
| `combined_pipeline.py` | 140-D real-wiring | Brian2 LIF | KC-Jaccard on real hemibrain | **0/5** — full substrate pipeline does NOT pass. MB is an anti-correlator; spiking-rotation decode noise produces a different KC mask than the prototype | `planning/findings/2026-04-13-combined-pipeline-0-of-5.md` |

## Headline paper pipeline and its caveat

`fly-brain-paper/paper.md` leads with **`real_rotation_140D_jaccard.py`**
(+ its k-sweep sibling). Rotation is numpy, readout is KC-Jaccard on
the real hemibrain MB. The rotation half is **not** substrate-compliant
per the current spec — that is explicitly flagged in the paper's
§Honest Limits section. The combined-pipeline attempt that would have
closed the gap (spiking rotation + KC-Jaccard together on the MB) was
measured at 0/5: the MB's anti-correlator role in the circuit (sparse
PN→KC with APL is specifically designed to decorrelate similar inputs)
means small vector-space perturbations become large KC-space
perturbations. Jaccard cannot rescue noise that changes *which* KC
mask the substrate lands on. The MB is not the right readout to
compose with a noisy spiking rotation.

Open question for the next iteration: either (a) find a substrate
whose readout is *correlation-preserving* at the target dimensionality
(candidates in the full FlyWire connectome — central complex
ring-attractor dynamics, not MB sparse coding), or (b) insert a
cleanup step between rotation and the anti-correlator so the state
is pulled back onto the prototype before sparsification. Neither is
a currently-working path; both are open engineering.

## Rules for new files

Before adding `real_rotation_<something>.py`:

- Does an existing file cover this stage combination? If yes, add a
  flag instead of copying.
- Is this an exploratory run? If yes, the code lives in
  `planning/findings/` per CLAUDE.md §"Avoiding `fly-brain/` Python sprawl".
- If you keep it, add a row to the table above in the same commit.
