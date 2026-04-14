---
name: Louvain on the giant SCC yields 16 coarse regions, none in loop-substrate size range
description: NetworkX Louvain (resolution=1.0) on the 135,403-node giant SCC of real FlyWire v783 W (undirected |w| projection, 13.1M edges) produces 16 communities — largest 45,790, median 1,394 — with zero communities in the [50, 2000] target range for loop substrate candidates. Louvain at default resolution finds brain-region-scale modules, not circuit-scale loops. Higher resolution or a different algorithm (Leiden, spectral, or weighted-directed community detection) is the next step.
type: project
---

# Louvain on giant SCC: 16 coarse regions, no loop-scale modules

**Date:** 2026-04-13
**Script:** `fly-brain/shiu_community_detection.py`
**Substrate:** 135,403-node giant SCC of real FlyWire v783 W, undirected projection
`A[i,j] = |w_ij| + |w_ji|`, nnz = 26,151,044 (13,075,522 unique edges).
**Algorithm:** NetworkX Louvain, resolution = 1.0, seed = 42.

## Result

- 16 communities found (10.9 min wall clock on CPU).
- Size distribution: max = 45,790, median = 1,394.
- **Communities in target range [50, 2000]: 0.**

## Interpretation

Louvain at default resolution is optimizing global modularity, which on
a strongly-connected 135k-neuron graph returns brain-region-scale
modules (optic lobe, central complex, mushroom body, etc. — tens of
thousands of neurons each). These are too large to serve as `loop
(condition)` substrate candidates in Sutra's sense: a loop substrate
needs a circuit small enough that its internal recurrence dominates
external input on the LIF time scale, which empirically means a few
dozen to a few hundred neurons (consistent with the 5 R1-6 SCC modules
of size 10–32 that the SCC search found).

The "zero in [50, 2000]" result does not mean no such modules exist —
it means they are nested inside the Louvain super-communities and
would be found by either (a) recursive Louvain on each super-community,
or (b) a higher-resolution parameter (γ > 1) that penalizes large
communities more strongly, or (c) an algorithm better suited to
directed weighted graphs (e.g. Leiden with directed modularity, or
Infomap on the original directed signed W).

## Compared to the prior SCC result

The SCC search (`planning/findings/2026-04-13-shiu-scc-search.md`)
found 5 small SCCs in [10, 500], all R1-6 photoreceptor modules. The
Louvain result is consistent: at the global-modularity level, the rest
of the connectome clusters into large regions, not small loops.
Finding dynamics-isolable circuit-scale loops inside the giant SCC
requires a finer-grained method than default Louvain.

## Next steps (follow-up, not queued)

1. **Re-run Louvain with resolution γ = 5 or 10.** Higher resolution
   biases toward more, smaller communities. Cheap — same 10 min on
   this graph.
2. **Recursive Louvain on each of the 16 super-communities.** Extract
   subgraph, re-run Louvain, look for modules of size 50–500. More
   expensive but avoids parameter-tuning.
3. **Install `leidenalg` and `igraph`.** Leiden gives provably better
   modularity optima than Louvain and supports directed weighted
   modularity; currently not in `brain-fly` env.
4. **Effective time-constant analysis per candidate module.** Even
   once candidate modules are identified, rank by internal/external
   weight ratio weighted by LIF membrane time constant — the
   dynamics-aware isolation metric from the SCC-search finding's
   next-steps list.

## Wall clock

- SCC + subgraph extraction: 0.7 s
- NetworkX graph build: 62.1 s
- Louvain: 654.7 s (10.9 min)
- Total: 11 min, one-shot on CPU.

The `iso_ratio` / cell-type-join analysis at the end of the script
crashed with KeyError because the qualifying-communities list was
empty — cosmetic; no data was lost. The script needs a guard before
the sort if the filter returns nothing.
