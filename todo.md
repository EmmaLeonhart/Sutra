# todo — long-horizon

Abstract destinations, not concrete steps. Pull an item here into `queue.md`,
decompose into executable steps, then execute. See `CLAUDE.md` workflow rules.

## Forward goal: integrate transformer-vm into the Yantra OS

The point of replicating Percepta's `transformer-vm` is to adopt it as the way
the user's own operating system, **Yantra**, runs WebAssembly. Open architectural
questions (to be drawn out in the 4:30 PM architecture-interview cron, then
decomposed here):

- Execution mode in Yantra: universal interpreter vs Futamura-specialized weights
  per program vs a hybrid/JIT that specializes hot programs.
- Where WASM execution lives: kernel syscall/driver, privileged userspace runtime,
  or per-process sandbox.
- Is the analytic-weight transformer the *actual* runtime, or a reference/oracle
  while Yantra runs a conventional WASM interpreter that must match its traces?
- ISA scope: the 35-opcode subset (with compile-time lowering) vs fuller WASM MVP.
- Backend & hardware target: the C++ hull-cache engine vs PyTorch vs a new backend.
- Memory model: how residual-stream-as-machine-memory maps to Yantra's process &
  I/O model.

## Replication follow-ups (optional — core replication already done)

- **Python hull path:** with `python3-dev` installed, confirm `wasm-eval --hull`
  and `pytest -m "not slow"` pass fast; compare hull (O(log n)) vs `--nohull`
  brute-force timings to quantify the attention-scaling claim.
- **Throughput gap:** investigate the ~18K vs ~30K tok/s gap (WSL overhead,
  BLAS-free Linux matvec); try a native-Linux or BLAS-linked build.
