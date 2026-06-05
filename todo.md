# todo — long-horizon

Abstract destinations, not concrete steps. Pull an item here into `queue.md`,
decompose into executable steps, then execute. See `CLAUDE.md` workflow rules.

## Forward goal: integrate transformer-vm into the Yantra OS

Adopt `transformer-vm` as the way the user's OS **Yantra** runs WebAssembly.
Architecture decided in the 2026-06-05 interview — full design + trap-and-resume
ABI + phased roadmap in **`notes/yantra_integration.md`**. Decisions: real neural
executor · universal interpreter · per-process sandbox · full WASM MVP · syscalls
trap-and-resume to kernel · floats trap to host FPU · linear memory = real RAM.

Phases (decompose into `queue.md` one at a time; design only until then):

- **P0 — Trap substrate** (the linchpin): trap ABI + C++ engine pause/host-callback/
  resume + one round-tripping demo trap.
- **P1 — Memory as trapped real RAM** (LOAD/STORE → host RAM).
- **P2 — Syscalls / WASI** over the trap channel.
- **P3 — Floats via host-FPU trap.**
- **P4 — Integer ISA completion** (i64, native bitwise/shift, br_table, typed select).
- **P5 — Tables / indirect calls, memory.grow.**
- **P6 — Per-process lifecycle** (snapshot/restore residual+hull state; scheduling).

## Replication follow-ups (optional — core replication already done)

- **Python hull path:** with `python3-dev` installed, confirm `wasm-eval --hull`
  and `pytest -m "not slow"` pass fast; compare hull (O(log n)) vs `--nohull`
  brute-force timings to quantify the attention-scaling claim.
- **Throughput gap:** investigate the ~18K vs ~30K tok/s gap (WSL overhead,
  BLAS-free Linux matvec); try a native-Linux or BLAS-linked build.
