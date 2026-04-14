---
name: Single-EPG drive produces zero recurrent EPG response on real W
description: NEGATIVE. 47 single-EPG drives on the Shiu LIF model produce spikes only on the directly-driven neuron, zero on every other EPG. Ring-attractor recurrence does not engage under direct EPG drive at this protocol.
type: project
---

# Single-EPG drive → zero recurrent EPG response on real Shiu W

**Date:** 2026-04-13
**Script:** `fly-brain/shiu_cx_bump_position.py`
**Substrate:** Shiu LIF 138,639 neurons / 15,091,983 synapses, real
FlyWire v783 W. 47 EPG neurons identified via FlyWire
consolidated_cell_types.csv.gz (`primary_type == "EPG"`) and mapped to
Shiu tensor indices.
**Question:** Does driving a single EPG neuron for 100 ms at 200 Hz
produce any activity in the other 46 EPGs — i.e., does real W's
EPG-to-EPG recurrence transmit a positional signal?
**Answer: NO.** All 47 trials: ~8–13 spikes on the driven neuron, zero
spikes on every other EPG, for every drive.

This is a structural negative result about how the ring attractor is
wired in FlyWire v783 + the Shiu LIF parameters. It explains why the
paper's polar-decomp Q is not just math-shortcut but a fundamental
misfit: the EPG-only subgraph of real W does not carry the ring
dynamics the polar decomposition pretends to capture.

## Setup

- 47 EPG neurons identified by root_id match between FlyWire
  consolidated_cell_types.csv.gz and Shiu completeness CSV.
- For each EPG k (47 total): drive ONLY neuron k at 200 Hz Poisson,
  0 Hz everywhere else, 100 ms simulation. Record 47-D EPG-only
  spike-count vector. Zero out the driven-neuron entry to isolate
  recurrent response.
- PyTorch CUDA on 4070 Laptop, 49.6 s wall for 47 drives.

## Raw result

| drive EPG | directly-driven spikes | max recurrent spikes (any other EPG) |
|-----------|-----------------------:|-------------------------------------:|
| 0         | 8                      | 0                                    |
| 10        | 13                     | 0                                    |
| 20        | 10                     | 0                                    |
| 30        | 9                      | 0                                    |
| 40        | 12                     | 0                                    |
| 46        | 11                     | 0                                    |

Aggregate:
- drives with zero recurrent EPG response: **47 / 47**
- mean recurrent spikes per drive across all 46 non-driven EPGs: **0.0**
- 47 × 47 recurrent-only cosine matrix is identically zero off-diagonal
  (all rows are the zero vector after masking the driven neuron)

## Why this happens (biologically)

EPG neurons in the fly central complex do NOT primarily inhibit or
excite each other directly. The ring attractor dynamics are supported
by a surrounding network:

- **Δ7 neurons** provide long-range inhibition across the ring.
- **PEN1 / PEN2** convey heading velocity input.
- **ER / R-ring neurons** feed sensory drive (mostly visual).

Direct EPG-to-EPG synapses are sparse in FlyWire v783 (most pairs have
0 or 1 synapse). The polar-decomposition Q the paper constructs from
the 51x51 EPG-to-EPG submatrix is therefore extracted from a very
small slice of a connectome whose actual ring dynamics live in the
~few-thousand-neuron Δ7+PEN+EPG+R subnetwork. The polar decomposition
rounds that sparse slice to the nearest orthogonal matrix —
mathematically well-defined, biologically a different object.

This finding confirms what the polar-decomp-Q framing was obscuring:
the rotation operator the paper reports is not "real FlyWire EPG
rotation" — it is an orthogonalized approximation of a very sparse
slice of real FlyWire that, on its own, does not rotate.

## Implications for the paper

Three operations have been tested on the real Shiu substrate today:

- `bundle` — LINEAR, at stability ceiling (cos = 0.97). Runs natively.
- `snap` — 15/16 on random inputs, failure is predictable random
  overlap, not dynamics. Runs natively.
- `rotate` — fails twofold: (a) generic iteration collapses to fixed
  point; (b) CX-restricted drive does not engage recurrence at all.
  Does NOT run natively at this protocol.

The fly-brain paper's current headline relies on rotation. That claim
does not survive contact with the real-W substrate at any protocol
tried today. The honest strategic options for the paper are:

1. **Narrow to operations that work.** Rewrite §Result 2 around bundle
   + snap on real W, drop the rotation/counting claim. This is the
   clean, honest version of the paper; it moves the headline from
   "Sutra compiles to rotation on the fly brain" to "Sutra compiles
   to bundle and snap on the fly brain; rotation requires
   sub-circuit-specific implementation not yet demonstrated."
2. **Retry rotation with Δ7 + PEN included.** Drive EPGs via PEN inputs
   and let the Δ7-mediated inhibition shape the dynamics. This is
   biologically the correct way to engage the ring attractor but is
   an open research question, not a 1-week deliverable.
3. **Keep polar-decomp Q but report it transparently.** Report Q as
   "mathematical approximation of the EPG submatrix" not "real-W
   rotation," with this finding cited as the reason the approximation
   is needed. This is worse than option 1 because the AI reviewer
   has already flagged the Q-vs-W gap.

Recommend option 1.

## Caveats

- Drive rate: 200 Hz. Higher drive (say 500+) might cross threshold
  on postsynaptic EPGs via the few direct connections that exist. Not
  tested; would be easy follow-up.
- Window: 100 ms. Longer windows don't change the finding if the
  instantaneous postsynaptic current is sub-threshold, which it
  appears to be.
- Shiu LIF parameters (wScale=0.275, vThreshold=-45 mV) are the
  calibrated values from Shiu et al. 2024; altering them to force EPG
  recurrence would be the kind of "tune until it looks biological"
  move CLAUDE.md forbids.
- Does NOT test whether indirect pathways (EPG → Δ7 → EPG, EPG → PEN →
  EPG) transmit the signal over longer windows. Those pathways exist
  in the connectivity table, the Shiu model includes those neurons,
  and this protocol just doesn't engage them.

## Not tested (honest scope)

- Multi-EPG drive (localized cluster of 3–5 adjacent EPGs) at higher
  rate (500+ Hz) for longer windows (300–1000 ms).
- Δ7-mediated inhibition: drive EPG cluster + monitor Δ7s + re-drive
  through Δ7 feedback.
- PEN-driven heading shift: drive ER/PEN with a sensory pattern and
  observe EPG bump displacement.

Any of these could produce positive rotation results. None are
1-week deliverables for the Claw4S deadline.
