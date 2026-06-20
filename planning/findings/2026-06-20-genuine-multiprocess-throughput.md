# Genuine multi-process Sutra DELIVERS throughput (up to 3.21×) — the lever tick_all couldn't pull (2026-06-20)

## Question

The `tick_all` finding (`2026-06-20-tick-all-no-speedup-python-bound.md`) showed in-process CUDA streams
give **no** speedup (0.4–0.95×) because a program's per-tick cost is GIL-bound Python orchestration, and
one process holds one GIL. Its conclusion: real multi-process throughput needs **genuine parallelism —
separate OS processes (each its own GIL)**. Emma greenlit that leg (2026-06-20). `ProcessPoolRuntime`
(`multi_process.py`) is the implementation. Does it actually deliver?

## Setup (the fair, isolated test)

`experiments/bench_process_pool.py`, dev machine:
- **Both paths on CPU** (`CUDA_VISIBLE_DEVICES=-1` before any torch import) — CPU is where the GIL actually
  serialises Sutra's per-tick Python, so it is the right testbed; and it makes single-process vs pool a
  same-device comparison.
- **1 torch thread per process** (parent + every worker) — so the only parallelism is across PROCESSES, not
  nested intra-op threads (otherwise multi-threaded matmuls + W workers oversubscribe the cores and muddy
  the result). This measures exactly "do separate processes escape the one-GIL serialisation?"
- **Workload:** a `make_real`-only program (no Ollama), K=16 `axon_item` reads per tick (each a separate,
  non-fused, GIL-orchestrated 868×868 matmul) so per-tick work is substantial. N=8 independent programs.
- **Steady-state:** the spawn + per-worker compile is one-time setup, timed and reported separately.

## Result

| dispatch | ms / round (N=8) | speedup |
|---|---|---|
| sequential `tick`×8 (1 process, 1 GIL) | ~113 | 1.00× |
| `ProcessPoolRuntime`, W=2 | 73.9 | **1.54×** |
| `ProcessPoolRuntime`, W=4 | 45.4 | **2.47×** |
| `ProcessPoolRuntime`, W=8 | 35.5 | **3.21×** |

Sequential baseline stable at ~112–114 ms across runs. One-time spawn+compile ≈ 6.6 s (break-even ≈ 99
rounds — paid back quickly for a long-running orchestrator; it is startup, not per-round).

**The contrast is the whole point:** in-process `tick_all` = 0.4–0.95× (slower); genuine separate
processes = up to 3.21× (faster). Separate OS processes ARE the throughput lever the finding predicted.

## Why sub-linear (honest)

Ideal would be W×. We get 1.54× / 2.47× / 3.21× at W=2/4/8 — monotonic but with diminishing returns:
- **Per-tick IPC.** Each tick pickles the input axon to the worker and the output back over a
  `multiprocessing` queue (CPU tensor ≈ 7 KB each way) — fixed overhead per tick the sequential path
  doesn't pay.
- **Serial gather.** `tick_all` collects the W workers' results in a single loop on the parent.
- **Physical cores.** Beyond the box's physical core count, more workers contend rather than parallelise;
  the W=8 → 3.21× (vs W=4 → 2.47×) shows it still helps but is flattening, consistent with a ~4–8-core box
  plus the parent.

These are the expected costs of process isolation, not a defect. A larger per-tick workload (more reads,
larger dim) would push the ratio toward W× by amortising the fixed IPC.

## Why this is SAFE (not just fast)

The correctness gate (`test_process_pool_runtime.py`) pins that two separate OS processes running the same
program on the same input produce **bit-identical** output — each worker rebuilds its `_VSA` caches
independently and gets the same Haar rotations / codebook, because the caches are key-deterministic, not
state (the §1B finding). So no cross-process cache sharing is needed for correctness; the speedup does not
cost determinism.

## Scope / next

- This isolates **process parallelism** (CPU, 1 thread/process). Real deployments tune threads × processes
  to the hardware; the result here is the clean lower-bound demonstration that the GIL was the wall and
  processes clear it.
- **CUDA path (queue §1C step 3, CI/Linux-gated):** `force_cpu=False` gives each worker its own CUDA
  context = per-process GPU memory isolation (§1C's original goal). On CUDA the per-tick GPU compute is
  tiny (the tick_all finding's 2%), so the CPU result here is the stronger demonstration of the GIL-escape;
  the CUDA path's value is isolation + overlapping the (still GIL-bound) Python launch across processes.
- **CUDA-IPC codebook sharing (step 4, optional):** only if per-process codebook GPU memory becomes the
  constraint, and only on Linux (Windows has no CUDA IPC).

## Reproduce

`CUDA_VISIBLE_DEVICES=-1 python experiments/bench_process_pool.py [N] [W] [K] [dim] [rounds]`
(defaults 8 4 16 768 30). The env var is also set inside the script.
