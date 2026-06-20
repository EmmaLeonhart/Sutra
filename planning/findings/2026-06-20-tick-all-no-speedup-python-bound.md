# `tick_all` is correct but delivers NO speedup today — the runtime is GIL-bound, not GPU-bound

**Date:** 2026-06-20
**Measured negative result, THEN a hot-spot fix. `MultiProcessRuntime.tick_all` (per-program CUDA
streams) is correct but does not parallelize on the Python-orchestrated runtime — and profiling the
"98% Python" revealed most of it was a PERF BUG in `_role_hash`, not irreducible orchestration.**

## UPDATE 2026-06-20 — `_role_hash` was doing `bytes(tensor)` element-wise iteration (66x slow)

Profiling a warm `on_axon` (cProfile, 200 ticks) showed `_role_hash` at ~98% of the per-tick time,
dominated by `unbind` (3.3s/1200 calls) + `.cpu()` (1.4s) + tensor `__iter__` (0.95s). Root cause:
`_role_hash` computed its hash via `bytes(role_vec.detach().cpu().contiguous().view(uint8))`, and
`bytes(tensor)` invokes the tensor's `__iter__`, which `unbind`s the d-vector into d 0-d tensors —
~6.4ms/call at dim 868. `_role_hash` runs 6x per axon-add tick (the rotation + permutation cache
keys), so this single line was the bottleneck. (It was introduced when `.numpy().tobytes()` was
removed for the no-numpy-on-hot-path rule — the replacement avoided numpy but was pathologically slow.)

**Fix:** `bytes(... .view(uint8).tolist())` — `.tolist()` is a torch C++ bulk conversion (NOT numpy,
NOT per-element Python), producing BYTE-IDENTICAL output (verified, so the cache keys and all behavior
are unchanged). Measured: `_role_hash` 6.37ms → 0.096ms (**66x**); the whole 8-program round
347.6ms → **18.8ms (~18x)**. This sped up EVERY Sutra program that binds (every `bind`/`axon_add`),
not just multi-process. 72 axon/bind/rotation/multi-process tests pass (byte-identical hashes).

After the fix `tick_all` is 1.08x vs sequential (the concurrency finally shows a small benefit) and the
round is 84% Python at the new, ~18x-lower absolute time (~3.1ms/tick).

**Next hot-spot (re-profiled, NOT yet fixed — queued).** `_role_hash` is still ~68% of the (now tiny)
tick, dominated by its `.cpu()` GPU→CPU transfer (~0.26ms × 6 calls/tick ≈ 1.5ms/tick). The hash is
recomputed every tick because `embed`/`basis_vector` return a `.clone()` of the codebook entry (fresh
object each call), so nothing is stable to memoize on. Eliminating it (another ~2x) needs one of: (a)
thread the role KEY STRING through `bind`/`_rotation_for`/`_axon_permutation_for`/`_role_hash` so the
hash memoizes by key (clean, but a multi-method signature change); or (b) make `embed` return the
cached codebook object (no clone) so `_role_hash` can memoize by `id` — faster but risks codebook
corruption if any caller mutates an embed result in place (today they appear read-only, but that
contract isn't enforced). Both are careful changes, not done here. The compile-time fusion pass remains
the deeper lever for the genuine per-op orchestration once this hash cost is gone.

---

## Original measurement (before the `_role_hash` fix)

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
