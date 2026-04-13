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
2. **Iteration substrate.** Numpy matmul `Q @ v` (tier-2 spec-compliant,
   pure math) vs Brian2 LIF via `neural_linear_map` (Q as synapse
   weights, Poisson-rate-coded input → steady-state voltage readout).
3. **Readout.** Direct cosine against target `Q^k v_0` vs mushroom-body
   Jaccard on KC patterns (sparse projection, 5% APL-enforced sparsity).
4. **Evaluation.** Counting-at-k, ordering (EARLY-first), target-k
   sweep, multi-seed.

## Active files (keep)

| File | Q | Iteration | Readout | Result | Finding doc |
|---|---|---|---|---|---|
| `survey_rotation_candidates.py` | — | — | — | Found EPG→EPG is 10× closer to orthogonal than anything else in FlyWire | — |
| `real_rotation_epg.py` | EPG polar decomp, 51-D | — | — | Q^T Q = I to 1e-14, det = +1 | — |
| `real_rotation_epg_loop.py` | EPG 51-D | numpy | cosine | **10/10 counting + 5/5 ordering** (tier-2 reference) | — |
| `real_rotation_composed.py` | EPG+LH+vDelta+hDelta, 713-D | numpy | cosine | 10/10 + 5/5 at every stage; orth residual 5.34e-14 | — |
| `real_rotation_epg_loop_spiking.py` | EPG 51-D | Brian2 LIF | cosine | 3/5 seeds at k=3 (numpy is 10/10; cos-readout Poisson noise) | `planning/findings/2026-04-13-spiking-Q-rotation-3-of-5.md` |
| `real_rotation_composed_spiking.py` | Composed 713-D | Brian2 LIF | cosine | 3/5 seeds (peak cos ~0.1 in high-D) | `planning/findings/2026-04-13-composed-Q-spiking-3-of-5.md` |
| `real_rotation_epg_loop_jaccard.py` | EPG 51-D | numpy | KC-Jaccard | 5/5 (proof that Jaccard readout beats cosine) | `planning/findings/2026-04-13-jaccard-on-KC-5-of-5.md` |
| `real_rotation_composed_jaccard.py` | Composed 713-D | numpy | KC-Jaccard | 5/5 (dimension independence) | `planning/findings/2026-04-13-jaccard-713D-dim-independence.md` |
| `real_rotation_140D_jaccard.py` | EPG 51 + hDelta 89 = 140-D real-wiring | numpy | KC-Jaccard on real hemibrain | **5/5** (headline result for paper §Result 2) | `planning/findings/2026-04-13-jaccard-140D-real-hemibrain.md` |
| `real_rotation_140D_jaccard_ksweep.py` | 140-D real-wiring | numpy | KC-Jaccard | **30/30** across k ∈ {1,2,3,5,8,12} × 5 seeds | `planning/findings/2026-04-13-jaccard-target-k-sweep-30-of-30.md` |

## Headline paper pipeline

`fly-brain-paper/paper.md` leads with **`real_rotation_140D_jaccard.py`**
(+ its k-sweep sibling). Rotation is numpy tier-2 (spec-compliant, see
`planning/sutra-spec/03-control-flow.md`), readout is KC-Jaccard on the
real hemibrain MB (tier-3, genuinely on the connectome). This is
pipeline **(B)** in STATUS.md queue item #12.

## Open gap

Pipeline **(C)** — spiking rotation *and* spiking KC-Jaccard at 140-D
end-to-end — does not have a file yet. The closest is the pair
`real_rotation_epg_loop_spiking.py` (spiking rotation, cosine readout)
+ `real_rotation_140D_jaccard.py` (numpy rotation, KC-Jaccard readout).
Combining them retires the tier-2-on-host compliance caveat and is
STATUS.md queue item #12.

## Rules for new files

Before adding `real_rotation_<something>.py`:

- Does an existing file cover this stage combination? If yes, add a
  flag instead of copying.
- Is this an exploratory run? If yes, the code lives in
  `planning/findings/` per CLAUDE.md §"Avoiding `fly-brain/` Python sprawl".
- If you keep it, add a row to the table above in the same commit.
