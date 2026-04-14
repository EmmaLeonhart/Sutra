---
name: Shiu substrate probe — real W, first run
description: First Sutra-adjacent operation on the real Shiu LIF whole-brain model (138k neurons, 15M synapses, FlyWire v783 W). Stability + distinctness checks pass.
type: project
---

# First real-W Sutra probe on the Shiu whole-brain model

**Date:** 2026-04-13
**Script:** `fly-brain/shiu_substrate_probe.py`
**Substrate:** `eonsystemspbc/fly-brain` at `C:/Users/Immanuelle/shiu-fly-brain/`
(Shiu et al. 2024 Nature LIF, PyTorch backend, CUDA on RTX 4070 Laptop).
**Question:** Does the full 138,639-neuron LIF model with real FlyWire v783
W — no polar decomposition, no 140-D slice, the whole brain —
produce (a) repeatable spike patterns for the same input and
(b) distinguishable spike patterns for different inputs? Both are
prerequisites for any Sutra op (bundle, bind, snap, similarity) to run
on real W.
**Answer:** Yes, cleanly. Stability ~0.96, distinctness ~0.00 at 100 ms.

## Setup

- Model: Shiu et al. 2024 whole-brain LIF, loaded via
  `run_pytorch.get_weights(conn_path, comp_path, wt_dir, csr=True)`.
  W is a 138,639 × 138,639 sparse CSR tensor with 15,091,983 nonzeros,
  built from `data/2025_Connectivity_783.parquet` using the
  `Excitatory x Connectivity` column. No rewiring, no decomposition.
- Dynamics: `TorchModel(batch=1, size=138639, dt=0.1ms, ...)` →
  Poisson input → sparse matmul `spikes @ W.T` → AlphaLIF.
- Output state = per-neuron spike count over 100 ms (NUM_STEPS=1000).
- Input pattern: 50 neurons chosen uniformly at random from the 138,639,
  driven at 200 Hz Poisson; all other neurons at 0 Hz. Two disjoint
  patterns A and B drawn with `np.random.default_rng(42)`.
- Two runs per pattern with distinct `torch.Generator` seeds (1000, 1001
  for A; 1002, 1003 for B) to drive Poisson randomness while keeping W
  fixed.

## Raw results

GPU: NVIDIA GeForce RTX 4070 Laptop
Weight load: 0.8 s (CSR cache hit after first run)
4 sims × 100 ms biological time: 4.2 s wall clock total.

Per-run active-neuron counts (neurons with ≥1 spike in 100 ms):

| run | active neurons |
|-----|---------------:|
| A1  |            80  |
| A2  |            75  |
| B1  |            60  |
| B2  |            61  |

Cosine similarity on the full 138,639-D spike-count vector:

| pair             | cos     | interpretation |
|------------------|--------:|----------------|
| A1 vs A2         | 0.9618  | stability (same input, different Poisson seed) |
| B1 vs B2         | 0.9674  | stability (same input, different Poisson seed) |
| A1 vs B1         | 0.0000  | distinctness (different inputs) |
| A1 vs B2         | 0.0000  | distinctness (different inputs) |
| A2 vs B1         | 0.0000  | distinctness (different inputs) |
| A2 vs B2         | 0.0000  | distinctness (different inputs) |

## Interpretation

Three things were being checked and all three hold:

1. **Real W is stable under Poisson noise.** Same 50-neuron input, two
   independent Poisson streams, cos ≈ 0.96. The Shiu LIF dynamics plus
   real W produce reproducible per-neuron spike profiles; the
   substrate's response is not dominated by input-side noise at this
   rate/duration.
2. **Real W preserves input distinction.** Two disjoint 50-neuron
   inputs drive zero-overlap downstream spike sets at 100 ms. The
   population code has not collapsed to a common attractor in this
   window.
3. **The pipeline actually runs.** 138k-neuron sparse LIF on the 4070
   Laptop's 8 GB VRAM fits with headroom and executes 100 ms of
   biological time in ~1 s wall. The earlier concern that VRAM might
   be tight is retired.

Together these three are the necessary conditions for building Sutra
operations directly on the Shiu model: if same-input → same-output is
not reliable, or different-input → different-output is not reliable,
no vector-algebraic operation built on top can work. They are.

## What this is NOT

- **Not a paper result.** n=1 per pattern-pair, no task, no readout
  beyond raw cosine. This is a substrate probe, not an evaluation of
  any Sutra op.
- **Not a test of bundle/bind/snap/similarity on real W.** Each of
  those is the follow-up experiment this probe unblocks. The
  fly-brain paper's rotation/conditional claims remain on the 140-D
  polar-decomposition-Q harness for deadline reasons; moving them to
  real W on the Shiu substrate is post-deadline work.
- **Not biologically grounded input.** 50 random neurons at 200 Hz is a
  generic drive — not ORNs, not PNs, not a specific olfactory code.
  Paper-ready versions must target a defined input population (ORNs /
  PN classes / SEZ channels).
- **Not a long window.** 100 ms biological time. Many circuits (CX
  ring attractor, MB learning) operate over 1–10 s; results at longer
  windows may differ.

## Caveats

- Windows OMP duplicate-lib warning required `KMP_DUPLICATE_LIB_OK=TRUE`
  to run. Not expected to change numerics but flagged for the record.
- Cosine = exactly 0.0000 across all A/B pairs is partly a consequence
  of choosing *disjoint* input sets at a *short* window — the 100 ms
  budget is not enough for downstream mixing to create any shared
  active-neuron set between the two patterns. At longer windows the
  distinctness number will drop from 0 but should stay well below the
  0.96 stability number; if it doesn't, the substrate is entering
  a common attractor and cos-based readouts won't discriminate.
- The PyTorch backend was used because Brian2 standalone has a
  Windows `subprocess.call(["main"])` path bug on this machine; fixing
  Brian2 CPU as ground truth is a separate post-deadline task.

## Next steps (post-deadline)

- Run the same probe at 200 ms, 500 ms, 1 s to map how cos(A, B)
  drifts upward vs how cos(A1, A2) drifts downward. The window where
  the two stay well-separated is the operating envelope for real-W
  Sutra ops.
- Replace random-neuron inputs with ORN subsets from the FlyWire
  cell-type table (external repo `C:/Users/Immanuelle/flybrain/`)
  and measure PN / KC / MBON downstream response.
- Implement `bundle` on real W: drive pattern A alone, pattern B
  alone, pattern A ∪ B, and compare cos(out_{A∪B}, normalize(out_A +
  out_B)). If high, the substrate superposes linearly at 100 ms.
  If low, propose the honest non-linear bundle operator the paper
  will actually compile to.
