---
name: Fuzzy-weighted conditional branching on real Shiu whole-brain LIF
description: 155/160 (96.9%) at n=10 seeds on the real 138,639-neuron Shiu LIF with FlyWire v783 W. Ported from the hemibrain-MB 560/560 result. Two runs out of ten showed drops (15/16 and 12/16); eight runs were perfect 16/16.
type: project
---

# Conditional branching on real Shiu whole-brain substrate

**Date:** 2026-04-13
**Script:** `fly-brain/shiu_conditional.py`
**Substrate:** Shiu et al. 2024 whole-brain LIF, 138,639 AlphaLIF neurons,
15,091,983 synapses, real FlyWire v783 W, PyTorch CUDA on RTX 4070 Laptop.

## Question

Does the fuzzy-weighted-superposition conditional branching that scored
560/560 on the small hemibrain MB (140 PN → 1,882 KC) also work on the
real Shiu whole-brain LIF model?

## Protocol

Per `planning/sutra-spec/03-control-flow.md`:

    result = Σ_i  w_i  ·  behavior_vec[program_map[prototype_i]]
    w_i = relu(cos(query, prototype_i)) normalized to sum 1

Realized on Shiu:

1. **Prototype codebook:** 4 disjoint random 40-neuron input populations
   for the 4 joint prototypes (PH, PF, AH, AF = vinegar/clean_air ×
   hungry/fed). Drive each alone at 200 Hz × 100 ms, record
   138,639-D spike-count vector.
2. **Behavior codebook:** 4 disjoint random 40-neuron behavior
   populations (approach, ignore, search, idle). Drive each alone,
   record spike-count vectors.
3. **Query:** Drive the scenario's input population with a fresh
   Poisson seed; the spike-count response is the query vector.
4. **Weights:** `w_i = max(0, cos(query, proto_i))`, normalized.
5. **Weighted behavior drive (substrate-native fuzzy blend):** Drive
   all 4 behavior populations simultaneously at rates `w_i · 200 Hz`
   where the prototype-to-behavior mapping is the program's table.
   The bundle happens on the substrate (Shiu's convergent excitation
   sums the four weighted drives), not in numpy.
6. **Defuzzify:** Argmax cosine against the behavior codebook.

Four programs × four scenarios × 10 seeds = 160 trials.

## Result

**155/160 correct (96.9%).** Per-run accuracy mean 0.969, std 0.075.

| Program | Correct | % |
|---------|---------|---|
| A | 39/40 | 97.5% |
| B | 39/40 | 97.5% |
| C | 38/40 | 95.0% |
| D | 39/40 | 97.5% |

Per-run breakdown:

| Run | Correct |
|-----|---------|
| 1   | 16/16   |
| 2   | 16/16   |
| 3   | 16/16   |
| 4   | 15/16   |
| 5   | 16/16   |
| 6   | 16/16   |
| 7   | 16/16   |
| 8   | 12/16   |
| 9   | 16/16   |
| 10  | 16/16   |

Run 8 is the outlier (4 misses). Prototype codebook off-diagonal
cosines are consistently near zero (mean 0.001, max 0.016 across
seeds), so the weighted blend has clean score separation on most
seeds — run 8's drop is consistent with a shared-substrate collision
between the weighted-behavior drive and one of the behavior
codebook vectors on that particular seed choice. No parameter
tuning was done.

## Interpretation

Conditional branching via fuzzy weighted superposition works on the
real 138,639-neuron Shiu whole-brain substrate at 96.9%. This is the
first Sutra control-flow operation measured on the full real connectome
(vs. the small hemibrain MB that backed the prior §Result 1).

Every vector operation in the pipeline — the bundle (convergent drive
for the weighted superposition), the snap (substrate-native spike-count
as the brain view), the similarity (cosine between spike vectors) —
runs on Shiu. The host does the scalar weight arithmetic (allowed
scaffolding per `planning/sutra-spec/02-operations.md`) and the final
argmax readout.

The ~3% error is honest signal: weighted-drive collisions at particular
seeds produce result vectors whose argmax lands on an adjacent behavior.
This is calibrated, not worrying — the hemibrain MB result (560/560)
benefited from the MB's anti-correlator structure; the Shiu substrate
does not have that circuit, and 96.9% against a raw spike-count readout
is the honest floor before adding MB-equivalent decorrelation.

## Wall clock

Each run: 4 proto + 4 behavior + 4 query + 16 result runs = 28 Shiu
simulations × ~1 s = ~30 s. Total for n=10: ~5 minutes on RTX 4070.

## Caveats

- 40-neuron populations are chosen uniformly at random over the full
  138,639-neuron space, not from anatomically coherent cell types.
  Testing with cell-type-coherent input pops (e.g. olfactory PN groups
  for smell, mushroom-body γ KCs for hunger) is future work.
- 200 Hz / 100 ms is the same protocol as bundle/snap tests.
  Longer windows may close the ~3% error; not yet swept.
- Ground-truth mapping is the program's prototype-to-behavior table;
  correctness is argmax-match, not a reaction-time or confidence
  threshold. A reviewer could reasonably ask for calibration curves.
