# `tick_all` is correct but delivers NO speedup today — the runtime is GIL-bound, not GPU-bound

**Date:** 2026-06-20
**Measured negative result. `MultiProcessRuntime.tick_all` (per-program CUDA streams) is correct
but does not parallelize Sutra programs on the current Python-orchestrated runtime.**

## Measured (dev GPU; `experiments/bench_tick_all.py`)

8 programs, each `on_axon` = 3 `axon_add`s (two embedded keys + the input), `runtime_dim=768`
(`dim=868`), caches warm:

| dispatch | ms / round | speedup |
|---|---|---|
| sequential `tick` ×8 | 347.6 | 1.00x |
| `tick_all` (concurrent, 8 streams + 1 synchronize) | 365.4 | **0.95x** |

Splitting the round into the Python-launch portion vs the GPU-wait portion:

| portion | ms / round | fraction |
|---|---|---|
| Python-launch-only (no `cuda.synchronize`) | 357.2 | **98%** |
| GPU kernels (launch + synchronize − launch) | ~9 | **2%** |

So `tick_all` is **0.95x** — marginally *slower* than sequential (the per-stream setup is pure
overhead), and the round is **98% GIL-bound Python orchestration**, only **2% GPU kernel time**.

## Why

`tick_all` launches each program's `on_axon` on its own `torch.cuda.Stream` so the GPU can overlap
their **kernels**. But the kernels are 2% of the cost. The other 98% is the Python that *builds and
launches* each program's tensor-op graph per tick — `axon_add` alone is dozens of Python-level torch
calls (embed-cache lookups, `_rotation_for`, `bind`, `_axon_permutation_for`, the permuted add), all
under the GIL. CUDA streams overlap GPU execution; they do nothing for serialized Python. With the
GPU work this small, there is nothing to overlap, and the stream bookkeeping makes it slightly worse.

## What this means (no overclaim)

- **`tick_all` is the right ABI shape and is CORRECT** (results are bit-identical to sequential
  `tick`; `test_multi_process_runtime.py`). It is the concurrency dispatch point Yantra's
  `Init.tick_concurrent()` consumes. Keep it.
- **It does NOT deliver parallelism on today's runtime.** The "CUDA-stream-level parallelism on
  independent compute" framing in the `multi_process.py` docstring is true only in the limit where
  GPU kernels dominate, which is the opposite of the measured regime. Docstring corrected to cite
  this number.
- **True multi-process speedup needs the per-tick Python to shrink**, so the GPU kernels become the
  dominant cost: (a) the compile-time **fusion pass** collapsing each program's per-tick graph into
  one (or few) fused tensor ops — far fewer Python-level launches per tick; and/or (b) genuine
  parallel execution of the orchestration (separate processes, or releasing the GIL), which one
  Python process + CUDA streams cannot provide. Until then, `tick_all`'s value is correctness + the
  forward-looking dispatch shape, not throughput.

## Reproduce

`python experiments/bench_tick_all.py [N] [runtime_dim]`
