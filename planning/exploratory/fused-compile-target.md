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

**#7 DONE — `_step` is module-level and exports end-to-end.** `_step` is now
emitted at module level as `_step_loop_<name>(_t, [this,] [arr,] state..., _init...)`
(the `_init_*` capture params are passed explicitly since a module-level fn can't
close over the driver's locals — the loop-capture desugar re-pins captured vars via
`name = _init_name` in the body). An UNBOUNDED `while_loop` exports end-to-end:
`experiments/fused_nn/emit_loop_weight_file.py` traces the step → `step.pt`
(host-readout-free) + a tiny torch-only orchestrator that drives the recurrence and
reproduces the result (n=5), cross-checked vs the eager driver; CI-guarded
(test_fused_nn). The straight-line case shipped earlier (`emit_weight_file`,
`7181c2a4`).

**Known follow-up (cuda trace device quirk).** `torch.jit.trace` records a
comparison literal as a CPU constant on a CUDA box (eager runs fine on cuda), so the
loop-export demo pins CPU. Exporting a comparison-using step on GPU needs a
device-placement fix in the trace path — separate, bounded.

**Remaining toward the full WASM machine as ONE fused recurrent net:** (1) the
machine keeps all state in a host RAM *list* with host-driven steps — move it to a
single `(N, dim)` tensor threaded through the step (the `ram_gather`/`ram_scatter`
primitives exist); (2) lift the v1 one-slot-`recur` limit so pc+sp+stack+RAM recur
together on the substrate (multi-state recurrence).

### The WASM machine RAM — do NOT fuse it (corrected 2026-06-07)
A previous version of this section proposed making the machine's RAM a single
`(N, dim)` VRAM tensor threaded through the step (`step(ram_tensor) -> ram_tensor'`)
so the whole machine fuses into one graph. **That is wrong — it treats VRAM as RAM**
and contradicts the NTM design (`planning/sutra-spec/ram-pointers.md`): RAM is
**EXTERNAL host memory**, the program holds only a pointer + VRAM mailbox, and an
**orchestrator** does the actual RAM I/O. `ramRead`/`ramWrite` are the I/O boundary,
not substrate ops; the `int(round(ptr.real.item()))` address decode is the
**sanctioned orchestrator wire**, not a leak. The NTM is one of three DISTINCT
architectures (RNN / NTM / reservoir) and must stay external-memory. The fused
compile target here applies to the **RNN path** (straight-line + loop recurrence,
#6/#7) — NOT to RAM. The real NTM lives in `experiments/ntm_ram/` (orchestrator +
ram_device + mailbox); a trainable NTM trains the **controller**, not the RAM access.
The `ram_gather`/`ram_scatter` / `fused_ram_machine` / `ram_tensor_step` code that
implemented the fuse-RAM idea was reverted.

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
