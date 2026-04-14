---
name: Strong drive (500 Hz, 500 ms) produces only trace recurrent EPG activity on real W
description: NEGATIVE (marginal). 5× drive rate and 5× window beyond baseline yields 0.4 mean recurrent spikes/drive (Variant A, single EPG) and only 1/5 clusters produced non-trivial recurrent activity (Variant B). Not a ring attractor — noise-floor leakage through sparse direct EPG-EPG synapses.
type: project
---

# Strong-drive CX probe: marginal, not a ring attractor

**Date:** 2026-04-13
**Script:** `fly-brain/shiu_cx_strong_drive.py`
**Substrate:** Shiu LIF on real FlyWire v783 W, 47 EPG neurons.

## Setup

Two last-ditch variants pushing drive far beyond biological range:
- **Variant A:** single-EPG drive, 500 Hz Poisson, 500 ms window (5× rate, 5× window vs. baseline). 10 samples spaced across the 47 EPGs.
- **Variant B:** 5 adjacent EPGs driven simultaneously at 500 Hz for 500 ms. 5 cluster positions.

## Result

Variant A (10 drives, total 78.4 s GPU time):
- Direct-neuron spike counts 74–83 (expected for 500 Hz × 500 ms).
- Recurrent EPG spikes: 0 on 7/10 drives; 1 on 2 drives; 2 on 1 drive.
- **Mean recurrent 0.4, max 2** across 46 non-driven EPGs per drive.

Variant B (5 cluster drives):
- Four of 5 clusters: 0–1 recurrent spikes total across 42 non-driven EPGs.
- One cluster (positions 10–14): 15 recurrent spikes on 2 other EPGs (max 10 on a single neuron).
- No coherent bump, no structure by distance from drive.

Script's boolean verdict reported "RECURRENT FIRING DETECTED" because `any(r > 0)` — but that threshold is wrong for a ring-attractor claim. A handful of spikes scattered across 500 ms at 5× drive is sparse direct-synapse leakage, not recurrent dynamics.

## Interpretation

Consistent with the earlier `shiu_cx_bump_position.py` finding (47/47 drives, zero recurrence at baseline). The EPG-only subgraph of real FlyWire v783 does not carry ring dynamics even under drive regimes well outside biology. The ring attractor in real flies lives in the Δ7 + PEN + EPG + R subnetwork, not the EPG-EPG slice.

## Implication for paper

Option 4 from the strategic menu fails. Narrowing the fly-brain paper to **bundle + snap on real W** and dropping the rotation claim is now the decision. Option 3 (Δ7 + PEN broader sub-circuit rotation) moves to research-scope, not deadline-scope.
