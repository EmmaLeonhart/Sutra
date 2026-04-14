---
name: SCC search on real Shiu W — only small loops are retinal R1-6 photoreceptor circuits
description: Strongly-connected-component analysis of real FlyWire v783 W (138,639²) finds one giant SCC (135,403 neurons containing the CX, MB, AL, CX) and 5 small isolated SCCs of size 10-500, all dominated by R1-6 photoreceptors in the optic lobe. The CX ring attractor is not a small SCC — it is wired into the giant component.
type: project
---

# SCC search on real Shiu W: only small loops are optic-lobe

**Date:** 2026-04-13
**Script:** `fly-brain/shiu_scc_search.py`
**Output CSV:** `planning/findings/2026-04-13-shiu-scc-candidates.csv`
**Substrate:** Real FlyWire v783 W (138,639² sparse, 15,091,983 nnz),
binarized for adjacency. `scipy.sparse.csgraph.connected_components(connection="strong")`.

## Question

Where in the real connectome are the isolated loop substrates that
could host Sutra's `loop (condition)` eigenrotation on the substrate,
independent of the central-complex ring attractor (which failed on
direct drive, `planning/findings/2026-04-13-shiu-cx-no-recurrence.md`)?

## Result

- **Total SCCs in Shiu W: 2624.**
- **Largest SCC: 135,403 neurons** (97.7% of the connectome). This
  giant component contains the central complex, mushroom body,
  antennal lobe, optic lobe central pathways, and all the recurrent
  inter-region wiring. The CX ring attractor is *inside* this giant
  SCC, not a small isolated loop.
- **SCCs with size ≥ 2: 199** (the rest are singletons).
- **SCCs with size in [10, 500]: 5.** All five are dominated by
  R1-6 photoreceptors and their lamina interneurons (L1, L2, L3,
  Lai, Lawf2). They are optic-lobe retinotopic modules — small,
  highly uniform-weight, low external in-degree, exactly the
  signature we were looking for:

| scc_id | size | ext_in_ratio | int_edges | weight_cv | composition |
|--------|------|--------------|-----------|-----------|-------------|
| 1288 | 17 | 0.000 | 43 | 1.000 | R1-6:13, L1:1 |
| 1393 | 13 | 0.000 | 37 | 1.007 | R1-6:7, L2:2, L1:2 |
| 1265 | 13 | 0.229 | 37 | 0.967 | R1-6:9, Lawf2:1, L1:1 |
| 1121 | 32 | 0.072 | 116 | 1.064 | R1-6:17, L3:4, L2:4 |
| 1484 | 10 | 0.137 | 25 | 1.039 | R1-6:6, Lai:1, L1:1 |

- **Zero SCCs in [10, 500] contain EPG, Delta7, PEN, or ER cell types.**
  The CX ring-attractor components are all in the giant SCC.

## Interpretation

Two things:

**(a) The CX is too wired-in to be a small loop.** The ring-attractor
components (EPG + Δ7 + PEN + ER) are part of the whole-brain giant
SCC, which means any "drive the ring and watch the bump" protocol
competes with feedback from the entire rest of the connectome. This
is consistent with the earlier negative findings: direct EPG drive
at 500 Hz / 500 ms produced noise-floor recurrence because the EPG
output signal is dispersed into the giant SCC rather than recycled
around a closed EPG→Δ7→EPG ring.

**(b) The five small SCCs are photoreceptor circuits, not control-flow
candidates.** R1-6 photoreceptor loops are well-characterized biologically
(motion-vision preprocessing; Borst & Helmstaedter 2015) — they are
retinotopic and feed into T4/T5 direction-selective neurons. They do
not implement arbitrary-state iteration; they implement spatial filtering
with temporal recurrence. Using them as `loop (condition)` substrates
would require repurposing them against their native function, and the
weight-CV ≈ 1 across all five suggests the recurrence is signal-dependent
rather than substrate-uniform.

## Implications

1. **Isolated loop substrates for Sutra `loop (condition)` are not
   structurally present in real FlyWire v783 W** at the SCC level
   outside the giant component. The loop substrate for iteration on
   this connectome must be realized *inside* the giant SCC, not as
   a small isolated module.
2. **The route forward for iteration on real W is to find closed
   cycles *within* the giant SCC** that are effectively dynamically
   isolated — i.e., circuits whose internal recurrence dominates
   external input on the relevant time scale. This is a different
   graph property (effective eigenvalue separation at the timestep
   granularity, or community-detection on the giant SCC) than binary
   strong-connectivity.
3. **This result supersedes the Claude.ai suggestion** (via the user's
   20:53 chat) that NO↔FB↔PB recurrence or MB↔MBON↔DAN might be
   "strong candidates." Those pathways exist in the connectivity
   but are inside the giant SCC on real FlyWire v783 + Shiu parameters;
   they are not graph-isolable by the SCC metric.

## Next steps (not yet done)

- **Community detection on the giant SCC.** Louvain, Leiden, or spectral
  clustering on the 135,403-neuron subgraph to find densely-connected
  modules that may be dynamically isolable even if they are graph-
  connected to the rest.
- **Effective time-constant analysis.** Rank candidate cycles by the
  ratio of internal edge weight to external incoming weight,
  weighted by the LIF membrane time constant — a dynamics-aware
  isolation metric.
- **Probe the 5 R1-6 SCCs for closed-loop persistence.** Even though
  they are not Sutra's target use case, measuring whether they sustain
  activity after drive release is a cheap sanity check that the
  SCC analysis reflects real substrate dynamics.

## Wall clock

SCC computation: 0.2 s (scipy on CPU for 15M-edge graph).
Full script including ranking and cell-type join: &lt;5 s.
