# Yantra × transformer-vm — integration design

Living design record for adopting Percepta's `transformer-vm` as the way the
user's operating system **Yantra** runs WebAssembly. Design only — no
implementation code until a phase is pulled into `queue.md`.

## Architecture decisions (2026-06-05 architecture interview)

From two `AskUserQuestion` rounds:

| Axis | Decision |
|------|----------|
| Runtime role | **Real neural executor** — the transformer IS how Yantra runs WASM; neural execution is the point (research/experimental OS), slowness accepted |
| Execution mode | **Universal interpreter** — one shared model runs any program (program lives in the input tokens), no per-program rebuild |
| OS placement | **Per-process sandbox** — each WASM workload in its own sandboxed userspace VM |
| ISA scope | **Full WASM MVP** (target), built up from today's integer core |
| Syscalls / host calls | **Trap-and-resume to kernel** — trap out, kernel services natively, resume |
| Floating point | **Trap to host FPU** — float ops handled like a coprocessor |
| Linear memory | **Real RAM + neural compute** — LOAD/STORE hit host RAM via trap |

## Key insight

The three "trap" choices collapse the hard part of "full MVP as a real neural
executor." The neural core must *natively* (in analytic weights) do only:
**integer compute + WASM control flow + trap signaling.** Everything expensive or
impure — floats, large memory, syscalls — is offloaded to conventional host code
through ONE uniform trap-and-resume primitive. Full MVP becomes a bounded
roadmap, not a moonshot.

## The shape: neural CPU core + conventional coprocessor

- **Neural core (shared, read-only):** the universal analytic transformer
  (~1.2 MB weights; in the replication: `d_model=38, 7 layers, 19 heads,
  vocab=915`) executes WASM bytecode autoregressively, one byte of machine state
  per token. It is the integer ALU + control unit.
- **Per-process state:** residual stream + hull KV-caches + the process's real
  linear-memory RAM region + its capability set. Weights are shared and read-only
  → the sandbox boundary is structural (a process can only do what its bytecode
  says, because the weights *are* the WASM semantics).
- **Host coprocessor (kernel / privileged userspace):** services traps — host FPU
  for floats, MMU/RAM for LOAD/STORE, kernel for WASI/syscalls.

## The linchpin: trap-and-resume primitive (proposed ABI)

Grounded in two mechanisms that **already exist** in `transformer-vm` (verified in
source, not speculation):

- **Byte emission (OUTPUT):** the engine has a byte-emit state machine
  (`emit_out` / `emit_byte` / `is_producing_bytes` in `wasm/interpreter.py`) — the
  core can emit arbitrary byte sequences.
- **Runtime input (`input_base`):** input is NOT baked into weights; it is
  provided at runtime and loaded from a memory region pointed to by `input_base`
  (opcode `0xFE`) via LOAD (`compilation/compile_wasm.py:_compute_input_base`,
  `format_input_section`).

Proposed trap = generalized OUTPUT request + host-written response read back via
LOAD:

1. The neural core reaches a trap opcode (host import / float op / LOAD-STORE to
   real RAM).
2. It emits a structured **request** through the byte-emit path:
   `[trap-id, operand bytes …]`.
3. The C++ engine's generation loop detects the trap marker, **pauses**, and calls
   a host callback. The kernel performs the real effect (FPU / RAM / syscall) and
   writes the **response bytes** into the process's host-accessible location (its
   real RAM / a result register slot).
4. Execution **resumes**: the core LOADs the response into the target WASM
   stack/local slot and continues.

Because memory is host-backed RAM (the chosen model), the **same channel** carries
float results and syscall results — the host writes the result into RAM/register
and the transformer LOADs it. One primitive, three uses. The bulk of the
engineering is in the C++ generation loop (pause → host callback → resume) plus a
small, uniform set of trap opcodes in the analytic construction; floats / large
memory / syscalls do NOT need to be encoded in the graph.

## Phased roadmap (design only)

- **P0 — Trap substrate.** Define the trap ABI; extend the C++ engine generation
  loop with pause / host-callback / resume; one demo trap (host `putchar` /
  `getchar`) round-tripping correctly with consistent state across the trap.
- **P1 — Memory as trapped RAM.** LOAD/STORE trap to a real per-process RAM region
  so memory scales to MBs (the chosen memory model).
- **P2 — Syscalls / WASI.** A minimal WASI surface over the trap channel
  (`fd_write`, `fd_read`, `args_get`, `clock_time_get`, `proc_exit`) so processes
  do real I/O (the chosen syscall model).
- **P3 — Floats via FPU trap.** f32/f64 ops trap to the host FPU (the chosen float
  model) — a large chunk of "full MVP" with little neural work.
- **P4 — Integer ISA completion.** i64 ops, native bitwise/shift (currently
  compile-time lowered), `br_table`, typed `select`, full comparison set — built
  into the analytic construction.
- **P5 — Tables / indirect calls.** `call_indirect`, function tables,
  `memory.grow` — the remainder of MVP.
- **P6 — Per-process lifecycle.** Snapshot/restore the residual-stream + hull-cache
  state for context-switch / suspend / resume; schedule multiple neural processes.

## Open questions for the next session

- **Trap marker encoding:** reserved opcode vs sentinel in the OUTPUT stream —
  must be unambiguous mid-generation.
- **Resume determinism:** guarantee the host-written result lands in exactly the
  right residual slot at the resume step (weight-construction detail).
- **Memory tiering:** "Real RAM + neural compute" was chosen over the tiered
  option — confirm token-history memory is fully replaced by RAM, not kept as an
  L1 tier.
- **Throughput budget:** at ~18K tok/s (one byte of state per token), what
  workloads is Yantra actually targeting? Decides whether the Futamura/hybrid
  specialization path is needed later for hot paths.
