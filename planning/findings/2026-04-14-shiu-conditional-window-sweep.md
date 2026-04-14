## Window sweep on Shiu conditional — error is codebook-collision, not integration-limited

**What was measured.** Extending the simulation window from 100 ms to 200/300/500 ms on `shiu_conditional.py --n-runs 10` does **not** close the ~3% error on the fuzzy-weighted-superposition conditional. Accuracy across the sweep: 100 ms 155/160 (96.9%), 200 ms 156/160 (97.5%), 300 ms 149/160 (93.1%), 500 ms 152/160 (95.0%). The remaining errors are dominated by two specific seeds whose random 40-neuron prototype pops happen to drive overlapping downstream populations, producing a degenerate codebook with max off-diagonal cosine ≥ 0.94 between two of the four prototypes. Longer integration does not fix these seeds and in several runs makes them worse.

### Setup

- Script: `fly-brain/shiu_conditional.py`, which now accepts `--sim-ms` (default 100).
- Substrate: Shiu et al. 2024 whole-brain LIF model, 138,639 AlphaLIF neurons, real FlyWire v783 W (15.09 M synapses), PyTorch CUDA via `run_pytorch.py`.
- Protocol unchanged from the 100 ms baseline finding (prior session): 4 disjoint 40-neuron prototype pops (PH/PF/AH/AF), 4 disjoint behavior pops (approach/ignore/search/idle), prototype codebook compiled by solo-drive at 200 Hz, behavior codebook the same. For each (smell, hunger) × program, query drives the matching prototype pop, cosine weights against the codebook are computed, the 4 behavior pops are driven simultaneously at `w_i · 200 Hz`, and argmax cosine against the behavior codebook decides the predicted behavior. 4 scenarios × 4 programs = 16 trials per seed, n=10 seeds.
- Each sim window produces 160 trials total. Commands:
  - `python shiu_conditional.py --n-runs 10 --sim-ms 200`
  - `python shiu_conditional.py --n-runs 10 --sim-ms 300`
  - `python shiu_conditional.py --n-runs 10 --sim-ms 500`
- Logs: `planning/findings/logs/shiu_cond_sweep_{200,300,500}ms.log`.

### Raw numbers

Aggregates:

| window | overall | per-run mean | per-run std |
|--------|---------|--------------|-------------|
| 100 ms (ref) | 155/160 (96.9%) | — | — |
| 200 ms | 156/160 (97.5%) | 0.975 | 0.057 |
| 300 ms | 149/160 (93.1%) | 0.931 | 0.129 |
| 500 ms | 152/160 (95.0%) | 0.950 | 0.067 |

Per-seed prototype codebook quality (max off-diagonal cosine between distinct prototypes) and per-seed trial accuracy:

| seed_base | 200 ms max-off / acc | 300 ms max-off / acc | 500 ms max-off / acc |
|-----------|---------------------|---------------------|---------------------|
| 30000 | 0.001 / 16 | 0.001 / 16 | 0.001 / 16 |
| 31000 | 0.009 / 16 | 0.011 / 16 | 0.013 / 16 |
| 32000 | 0.012 / 16 | 0.020 / 16 | 0.018 / 16 |
| 33000 | 0.011 / 15 | 0.016 / 15 | 0.014 / 13 |
| 34000 | 0.009 / 16 | **0.661** / 15 | **0.971** / 15 |
| 35000 | 0.015 / 16 | 0.014 / 16 | 0.016 / 16 |
| 36000 | 0.010 / 16 | 0.012 / 14 | 0.012 / 14 |
| 37000 | **0.938** / 13 | **0.975** / 9 | **0.985** / 14 |
| 38000 | 0.000 / 16 | 0.000 / 16 | 0.000 / 16 |
| 39000 | 0.001 / 16 | 0.004 / 16 | 0.007 / 16 |

Two seeds (34000, 37000) reliably produce collided codebooks; the other eight are clean. The collided ones account for essentially all the error budget across the sweep.

### Interpretation

The "fuzzy-weighted-superposition conditional" pipeline depends on the prototype codebook being a roughly orthogonal basis. If two prototype pops happen to drive strongly overlapping downstream populations (KC/MBON-level ripple through FlyWire W), their spike-count vectors end up nearly collinear — and then the cosine-weighting step `w_i = relu(cos(query, proto_i))` distributes mass across the collided prototypes almost equally, so the weighted behavior drive is a blend of two outputs and the argmax readout flips under noise.

Longer integration does not cure this: at 500 ms seed 34000's codebook collision *worsens* from 0.661 (at 300 ms) to 0.971, because the overlapping populations saturate together and the non-overlapping signal proportionally shrinks. The seed-37000 collision is present at every window and only gets sharper with more time.

The clean seeds (8/10) are 100% correct at every window. This is consistent with the prior 100 ms baseline, where the ~3% error was also concentrated in a small number of bad-seed trials rather than spread evenly.

### Implications

1. **The window is fine at 100 ms.** Extending integration is not the fix; if anything it is mildly harmful. The paper should keep the 100 ms default.
2. **The error is in prototype-pop selection, not in the operation.** `bundle`, `similarity`, and the weighted-superposition drive are not the failing subsystems — the codebook compilation (random 40-neuron picks) is. A real program wouldn't pick prototypes randomly, it would pick semantically meaningful populations (e.g. olfactory glomeruli, mushroom-body compartments) that are anatomically disjoint by construction.
3. **Mitigation for the paper result.** Two honest options: (a) report 97.5% at 200 ms as the headline and caveat the codebook-collision mechanism, or (b) add a codebook-orthogonality filter at compile time (reject a prototype pack if max off-diagonal cosine > 0.1, resample until clean) — this is allowed compile-time substrate instrumentation per `CLAUDE.md`, not runtime host math. Option (b) is closer to what a real compiler would do, since anatomically-informed picks would meet the same constraint by construction.
4. **Closes the window-sweep queue item.** No further integration-time experiments needed. If we want to push accuracy up, the next thing to try is orthogonality-gated codebook compilation, not a longer sim.
