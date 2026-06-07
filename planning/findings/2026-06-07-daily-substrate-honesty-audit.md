# Daily substrate-honesty audit — 2026-06-07

**Window:** commits after `ac10ef16` (the 2026-06-06 audit) through `f5d9fc1c`.
Dominated by the SUBSTRATE-PURITY → FUSED-NN overhaul. Checked against CLAUDE.md
§"Subtler substrate breaches — measurement-required" (dim / state-locus / signal-
separation).

## (a) Dimension audit — CLEAN

`experiments/iso5_substrate_dispatch/mini_wasm_machine.su` has **0 `basis_vector`
calls** (no LLM codebook used — it's an integer machine on synthetic axes), and
its regression test compiles at **`runtime_dim=2`** — the smallest dim the task
needs. No silent 96× cost; the dim already matches the work. The fused-NN demos
under `experiments/fused_nn/` are likewise codebook-free arithmetic graphs.

## (b) "Substrate-pure / verified / differentiable / RNN" claims — VERIFIED

The overhaul commits claim substrate-purity, differentiability, and fused-graph
export. Re-ran the guards (not the prior session's framing):

- `test_no_host_readout.py` — purity gate (baseline 21 `.item()`, +1 loop-halt),
  green.
- `test_fused_nn.py` — all 6 fusion building blocks (differentiable_substrate,
  trace_to_graph, recurrence_fusion, orchestrator_model, emit_weight_file,
  ram_tensor_step), green.
- 11 passed in 6.5s.

The `recur`/RNN framing in `f5d9fc1c` is a SPEC refinement (recurrence on the
substrate) recording Emma's design intent, not a measurement claim — no code
change to verify.

## (c) Signal-separation gap — was MISSING, now MEASURED

The `mini_wasm_machine` 21-opcode dispatch is a substrate classifier
(`is_X = truth_axis(defuzzy(op == X))`) shipped (commit `1be294be`, 30/30 test
pass) WITHOUT the required gap table. Measured it across all 21×21 (opcode,
target) pairs via the exact compile path:

  **gap = min(selected) − max(leaked) = (+1.0) − (−1.0) = +2.000000**

at both `runtime_dim=2` and `50` — maximal, dim-independent separation. Expected:
opcodes are exact integers, so `op == target` is exact. The 30/30 test pass was
real, not a host artifact. Table added to
`planning/findings/2026-06-06-iso5-mini-wasm-machine-runs-on-substrate.md`;
measurement script `experiments/iso5_substrate_dispatch/measure_dispatch_gap.py`;
fast CI guard `test_dispatch_gap` added to `test_mini_wasm_machine.py`.

## Verdict

CLEAN. One required artifact (the dispatch gap table) was missing and is now
produced + guarded. No faked results, no doctored numbers, no substrate breach in
the audited window.
