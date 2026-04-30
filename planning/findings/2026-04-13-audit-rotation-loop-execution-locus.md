---
title: Audit — where each runtime operation of `real_rotation_epg_loop_spiking.py` actually executes
date: 2026-04-13
status: confirmed
reproduced: yes (re-run on 2026-04-13 in this session: 3/5 seeds, 24.6s wall clock)
---

## What was measured

Line-by-line audit of `fly-brain/real_rotation_epg_loop_spiking.py` plus its core helper `neural_vsa.neural_linear_map`, to answer the question: *does the rotation actually run on spiking neurons, or is it numpy with a Brian2 fig leaf?* Motivated by the new Substrate Rule in `planning/sutra-spec/02-operations.md` (commit 148bac5) — numpy is compile-time only at runtime; any tier-2 op returning numpy results from a host computation is a lie about what executed.

## Setup

Static read of the two source files, cross-checked against one live run of the script on FlyWire v783 EPG→EPG Q (51-D, orthogonality residual 1.68e-14). Seeds 0–4, target k=3, max_iters=6, SIM_MS=3000.

## Findings — per-line locus

| Operation | Site | Executes on | Honest per spec? |
|---|---|---|---|
| Q construction (polar decomposition of W) | `nearest_rotation(W)` → numpy SVD | host at compile time | ✓ yes — compile-time is host |
| v₀ construction | `rng.randn(dim); v0 /= norm(v0)` | host at compile time | ✓ yes — input encoding |
| Prototype construction `proto = Q^k · v₀` | `np.linalg.matrix_power(Q, target_k) @ v0` | host at compile time | ✓ yes — comment on line 50-53 flags it as compile-time |
| **Rotation application `Q · state`** | `neural_linear_map(Q, state, ...)` | **substrate (Brian2 LIF)** | ✓ **yes — not a lie** |
| Similarity `cos(state, proto)` | `s_norm @ proto` on host numpy (line 72) | host at runtime | ✗ no — tier-2 similarity should run on substrate per new spec |
| State renormalization | `state = s_norm` on host numpy (line 77) | host at runtime | ⚠ gray area — norm isn't a listed Sutra op; this is a decoding correction for spiking-variance accumulation |
| Termination `argmax over cos_by_k` | `np.argmax(cos_by_k)` on host (line 78) | host at runtime | ✗ no — spec 03-control-flow.md termination should be substrate prototype match in KC space |

## Key verification: rotation is actually on spikes

`neural_linear_map(M, v)` (neural_vsa.py:213) does the following:

1. Input layer: `PoissonGroup(d_in, rates=_rate_of(v) * Hz)` — `v` is encoded as Poisson input rates, not used as a numpy operand.
2. Output layer: `NeuronGroup(d_out, eqs, method='exact')` — LIF population, Brian2.
3. Synapses: `syn.w = (M[out_idx, in_idx] * W_MV) * mV` — **M is realized as synapse weights**, not consumed by `np.dot`.
4. Simulation: `net.run(SIM_MS * ms)` — actual Brian2 integration for 3 seconds per iteration.
5. Readout: `mean_v_mV = np.mean(np.asarray(mon.v / mV)[:, mask], axis=1)` — reads from `StateMonitor`, which comes from the simulated LIF dynamics.
6. Decode: `(mean_v_mV - baseline_mV) / (GAIN_HZ * W_MV * TAU_MS * 1e-3)` — baseline correction and gain inversion on the spiking output to recover `(M @ v)` in vector form. The baseline uses M's row sums but **does not compute M @ v**; it corrects for the constant PN-current contribution.

There is no `np.dot(M, v)`, no `M @ v`, no `np.linalg.matrix_power(M, i) @ v` anywhere in the runtime path. The steady-state voltage of a linear LIF circuit driven by Poisson inputs through synapses weighted by M equals (up to affine scaling) `M @ v` — which is the whole point of the construction — but the executor is the spiking circuit, not numpy.

**Conclusion: the rotation is honest.** The paper's abstract claim "All algebraic operations (bundle, bind, rotation) run as spiking circuits" is correct for rotation as of this audit.

## What is NOT on the substrate

Three things in the loop body still run on host numpy at runtime:

1. **Similarity readout** (`s_norm @ proto`). This is a tier-2 `similarity` op by the spec, so it should run on the substrate. Currently it runs as a numpy dot product. For loops whose termination depends on similarity, this means the termination decision is host-side even though the rotation that produces the state is substrate-side.
2. **State renormalization** (`state = s_norm` between iterations). The comment at line 74-77 explains this as a correction for O(1/√T) spiking-decoding variance. It is not a listed Sutra operation, so it is not directly forbidden by the spec — but it is a runtime host operation on a state vector, which is the exact pattern the Substrate Rule is designed to flag.
3. **Loop-termination argmax** (`np.argmax(cos_by_k)`). Per spec `03-control-flow.md`, termination for `loop(condition)` is supposed to be a Jaccard match on KC patterns produced by the substrate. Here it is a host argmax over host-computed cosines. This means the termination decision — "was this iteration the right one?" — is made by the host, not the substrate.

## Re-run numbers (2026-04-13)

```
Spiking counting test: target k=3, max_iters=6, 5 seeds.

  seed=0  argmax_k=3  peak_cos=+0.753  PASS  [8.7s]
  seed=1  argmax_k=1  peak_cos=+0.687  FAIL  [3.8s]    k1=0.69, k3=0.68 — noise-flip
  seed=2  argmax_k=3  peak_cos=+0.752  PASS  [4.2s]
  seed=3  argmax_k=3  peak_cos=+0.693  PASS  [4.0s]
  seed=4  argmax_k=1  peak_cos=+0.766  FAIL  [3.8s]    k1=0.77, k3=0.64 — structural

Spiking counting at k=3: 3/5 seeds, wall clock 24.6s.
```

Seed 1's failure is a Poisson-noise flip (cos difference is 0.01). Seed 4's failure is structural — cos at k=1 is 0.13 above cos at k=3 — which is consistent with the Q² spectrum argument in queue.md (`cos(Q v, Q³ v) = cos(v, Q² v)` can be large if Q² has eigenvalues near 1).

## Implications

- **Paper's rotation claim is honest and does not need retraction.** It does need more explicit language about *which* ops run where — the current "all algebraic ops run as spiking circuits" is true for the ones listed (bundle, bind, rotation) but can be read as covering similarity, which it should not.
- **Paper should add a "where each op executes" table** that shows, for the headline pipeline, which runtime operations are on substrate and which are on host. The three host-resident ops above need to be acknowledged, not buried.
- **Headline 3/5 number is real and produced by a substrate rotation.** The numpy-rotation interpretation I offered in the session before this audit was wrong; Q @ v genuinely runs as spikes. What's weaker than the paper suggests is the substrate-completeness of the end-to-end loop, not the rotation.
- **Next items in the audit queue:** `neural_vsa.py`'s bundle/bind, `vsa_operations.py`, codegen-emitted Python. Apply the same per-line locus analysis. Any runtime numpy on a state vector is a finding.

## Open question

Is host-side similarity acceptable as a *readout* boundary (like MBON → motor command in the fly brain), or is it a substrate violation that must be fixed before headline results are trusted? The answer shapes whether item 1 of queue.md is "fix three ops" or "fix one op plus document two as readout-boundary host ops by design." See `planning/open-questions/` for where this might live when the answer is considered.
