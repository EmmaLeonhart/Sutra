"""§1C step 2a — throughput: does the GENUINE multi-process runtime (separate OS
processes) beat single-process sequential, the tick_all finding's prediction?

The tick_all finding showed in-process CUDA streams give NO speedup because a
program's per-tick cost is ~GIL-bound Python orchestration, and one process holds
one GIL. `ProcessPoolRuntime` runs programs across W worker OS PROCESSES (separate
GILs). This benchmarks the steady-state throughput of N independent program ticks:

  - sequential: `MultiProcessRuntime.tick` x N per round (one process, one GIL)
  - pool:       `ProcessPoolRuntime.tick_all({N inputs})` per round (W processes)

FAIR COMPARISON: run the whole thing on CPU (set CUDA_VISIBLE_DEVICES="" before
launching) so both paths use the same device — CPU is also where the GIL actually
serialises Sutra's Python orchestration, so it is the right testbed for the
hypothesis. Steady-state (the spawn + per-worker compile is one-time setup, timed
and reported SEPARATELY, with the break-even round count).

The workload is a `make_real`-only program (no Ollama) with K axon_item reads
(each a separate, non-fused, GIL-orchestrated matmul) so per-tick work is
substantial and parallelisable.

Usage:  CUDA_VISIBLE_DEVICES="" python experiments/bench_process_pool.py [N] [W] [K] [dim] [rounds]
"""
from __future__ import annotations

import os
import pathlib
import sys
import tempfile
import time

# Force CPU + isolate PROCESS parallelism BEFORE torch is imported anywhere:
#   - CUDA hidden so single-process and pool both run CPU (the fair GIL testbed);
#   - each process pinned to 1 torch thread so the only parallelism is across
#     processes (else multi-threaded matmuls + W workers oversubscribe the cores
#     and muddy the result). This measures exactly "do separate processes escape
#     the GIL that serialises one process's per-tick Python orchestration?"
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "-1")


def _heavy_program(k: int) -> str:
    adds = "\n".join(
        '    a.add("k%d", make_real(%d.0));' % (i, i) for i in range(k)
    )
    reads = ["    vector acc = a.item(\"k0\");"]
    for i in range(1, k):
        reads.append('    acc = bundle(acc, a.item("k%d"));' % i)
    body = "    Axon a;\n" + adds + "\n" + "\n".join(reads) + "\n    return acc;"
    return "function vector on_axon(vector input_axon) {\n" + body + "\n}\n"


def _timed(fn, reps: int) -> float:
    t0 = time.perf_counter()
    for _ in range(reps):
        fn()
    return (time.perf_counter() - t0) / reps


def main() -> None:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 8
    w = int(sys.argv[2]) if len(sys.argv) > 2 else 4
    k = int(sys.argv[3]) if len(sys.argv) > 3 else 16
    dim = int(sys.argv[4]) if len(sys.argv) > 4 else 768
    rounds = int(sys.argv[5]) if len(sys.argv) > 5 else 30

    from sutra_compiler.multi_process import (
        MultiProcessRuntime, ProcessPoolRuntime, ProgramSpec)
    import torch as _torch

    _torch.set_num_threads(1)  # parent: 1 thread, so the sequential baseline
    # is single-core too — the pool's win must come from PROCESSES, not threads.
    dev = "cuda" if _torch.cuda.is_available() else "cpu"
    print(f"N={n} programs  W={w} workers  K={k} reads/tick  dim={dim}  "
          f"rounds={rounds}  device={dev}  (1 thread/process)")
    if dev == "cuda":
        print("  WARNING: CUDA still visible despite CUDA_VISIBLE_DEVICES=-1 — "
              "result is NOT the intended CPU GIL test.")

    tmp = pathlib.Path(tempfile.mkdtemp())
    src = tmp / "heavy.su"
    src.write_text(_heavy_program(k), encoding="utf-8")
    specs = [ProgramSpec(name=f"p{i}", source_path=src) for i in range(n)]

    # --- single-process sequential ---
    seq = MultiProcessRuntime(specs, runtime_dim=dim)
    v = seq.vsa()
    inp = v.zero_vector()
    names = [s.name for s in specs]
    # warm one round (lazy caches)
    for nm in names:
        seq.tick(nm, inp)
    seq_ms = _timed(lambda: [seq.tick(nm, inp) for nm in names], rounds) * 1000

    # --- genuine multi-process pool ---
    inp_cpu = inp.detach().to("cpu")
    t0 = time.perf_counter()
    pool = ProcessPoolRuntime(specs, num_workers=w, runtime_dim=dim,
                              force_cpu=True, threads_per_worker=1)
    spawn_s = time.perf_counter() - t0
    pool_inputs = {nm: inp_cpu for nm in names}
    pool.tick_all(pool_inputs)  # warm
    pool_ms = _timed(lambda: pool.tick_all(pool_inputs), rounds) * 1000
    pool.close()

    speedup = seq_ms / pool_ms if pool_ms else float("nan")
    print(f"\nsequential (1 proc):  {seq_ms:7.1f} ms/round")
    print(f"pool ({w} procs):       {pool_ms:7.1f} ms/round")
    print(f"speedup:              {speedup:7.2f}x")
    print(f"pool spawn+compile:   {spawn_s*1000:7.0f} ms (one-time)")
    if speedup > 1.0:
        # rounds to amortise spawn: spawn / (per-round saving)
        saving = (seq_ms - pool_ms) / 1000
        be = spawn_s / saving if saving > 0 else float("inf")
        print(f"break-even:           ~{be:.0f} rounds "
              f"(spawn paid back by the per-round saving)")


if __name__ == "__main__":
    main()
