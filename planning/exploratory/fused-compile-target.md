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

**#6 DONE (`28623769`):** the codegen no longer fuses iteration + halt inside one
function. `_translate_loop_function_decl` now emits a PURE per-tick step + a thin
driver:

- **Network step** — a nested `def _step(_t, [this,] state...) -> (state..., _halted)`:
  ONE iteration (condition + body + soft-halt blend), pure tensor ops, no `while`,
  no `break`, no `float()`. `_halted` is the substrate soft-halt signal.
- **Driver (in-module orchestrator)** — `while True: state, _halted = _step(...);
  if float(_halted) >= 0.99: break`. The single `float(_halted)` host-readout lives
  HERE (the legitimate boundary), never in `_step`.

Verified: loop+await 59 green; reframed `test_no_host_readout` asserts `_step` is
readout-free + the read stays in the driver. The host-readout-relocation goal is met.

**#7 remaining — make `_step` exportable.** `_step` is currently NESTED inside the
loop function, so `torch.jit.trace`/`torch.export` can't grab it standalone. Hoist
it to a module-level `_step_<name>(_t, [arr,] [this,] state...)` (do_while/while_loop
close over only `_VSA`; foreach also takes the array param; class loops also `this`),
then trace it → `foo.network.pt` + a tiny driver = the loop weight-file target. The
straight-line case already ships this end-to-end (`emit_weight_file`, `7181c2a4`).

### State as a single tensor (for the WASM machine)
NOTE: the RAM cells are ALREADY in VRAM — each `self.ram[addr]` is a `cuda`
number-vector. The data is not off-GPU. What is host-side is (a) the **container**
(`self.ram` is a Python *list* of tensors, not one tensor) and (b) the
**addressing** (`addr = int(round(ptr[AXIS_REAL]))` → Python list index
`self.ram[addr]`), neither of which is a traceable tensor op. For the step to be a
pure exportable graph, change the container to a single `(N, dim)` VRAM tensor and
the access to tensor **gather/scatter** (a tensor index, not a host int), threaded
as `step(ram_tensor) -> ram_tensor'`. The data stays in VRAM; only list→tensor +
int-index→gather/scatter change. Additionally the machine's multi-state recurrence
needs the v1 one-slot-`recur` limit lifted (separate spec decision,
`non-halting-loop.md`).

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
