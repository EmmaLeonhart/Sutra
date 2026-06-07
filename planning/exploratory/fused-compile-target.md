# Fused compile target — network (weight file) + tiny orchestrator

**Status:** design (not yet implemented). Grounds the next big Phase-2 codegen
build. Architecture per Emma 2026-06-07 (`project_orchestrator_model` memory);
foundations proven + CI-guarded in `experiments/fused_nn/` (`test_fused_nn`).

## Goal

`sutra compile foo.su` should produce **two artifacts**, not one Python module of
host-orchestrated calls:

1. **The network** — the program's computation as a single fused, differentiable
   tensor graph, exported as a real **weight file** (e.g. `foo.network.pt` via
   `torch.jit.save` / `torch.export`). Zero host readout inside it.
2. **The orchestrator** — a *tiny* Python driver (`foo.run.py`) whose ONLY job is
   to: load the network, feed input, drive any recurrence (host loop calling the
   step graph), read the **halt signal** to stop, and read the **output** to
   print. The halt-read and output-read live here — the legitimate terminal
   boundary, not in-graph introspection.

## What is already proven (experiments/fused_nn/, CI-guarded)

- `differentiable_substrate` — substrate-pure functions are end-to-end
  differentiable; `.real()` is a gradient wall.
- `trace_to_graph` — a function compiles to one fused TorchScript graph, saved to
  a file, reloaded, run with identical output + intact gradients.
- `recurrence_fusion` — a bounded recurrence `loop(N)` fuses into one
  differentiable graph, gradients through every step.
- `orchestrator_model` — a compiled step graph is host-readout-free
  (no `aten::item`/`Float`); a ~10-line Python orchestrator drives the recurrence
  and reads halt+output at the boundary.

## The codegen build (the remaining work)

### Straight-line programs
The network = the whole function (already traceable, `trace_to_graph`). The
orchestrator runs it once and reads the output.

### Recurrent programs (`loop`/`recur`/`do_while`/`while_loop`)
Today the codegen emits the iteration + halt **inside** one function
(`_loop_X`: `while True: …; if float(_halted) >= 0.99: break`). Restructure to:

- **Network step** — `_step_X(state) -> (new_state, halt)`: ONE iteration of the
  loop body, pure tensor ops, no `while`, no `break`, no `float()`. `halt` is a
  substrate truth (the soft-halt signal) on the state's truth axis.
- **Orchestrator** — drives it:
  ```python
  state, halted = init, 0.0
  while halted < 0.99:            # host loop in the tiny driver
      state, h = step(state)      # run the network step
      halted = min(halted + h, 1) # (or read the step's halt axis)
  output = read(state)            # terminal boundary
  ```
  The `float(...)`/`while`/`break` live HERE (the orchestrator), which is allowed.

This moves the one host-readout (`float(_halted)`) out of the network and into the
orchestrator — meeting the `test_no_host_readout` loop-emission goal (0 inside the
step) by RELOCATION, and making the step graph exportable.

### State as a tensor (for the WASM machine)
The mini_wasm_machine keeps state in the RAM device (host-mutable list). For its
step to be a pure exportable graph, RAM must be a single tensor threaded as
`step(ram_tensor) -> ram_tensor'` (gather/scatter for cell reads/writes instead of
device mutation). Additionally the machine's multi-state recurrence needs the v1
one-slot-`recur` limit lifted (separate spec decision, `non-halting-loop.md`).

## Open decisions
- Artifact format: `torch.jit.save` (TorchScript) vs `torch.export` (the newer
  path; `torch.jit` emits a deprecation warning). Pick one for the weight file.
- The orchestrator's halt source: recompute `halted` host-side from the step's
  returned `halt`, or read a dedicated halt axis the step writes. Latter is
  cleaner (step owns the halt math; orchestrator only reads + thresholds).
- RAM-as-tensor addressing: gather/scatter indices come from the pointer's real
  axis — keep that decode at the device/orchestrator boundary (the I/O wire).

## HARD RAIL
Every step verified substrate-to-substrate (decoded output == reference); the
network graph must contain zero `aten::item`/host readout; "it traced" ≠ "it's the
right computation" — compare to the eager run.
