# `tick_all` is correct but delivers NO speedup today — the runtime is GIL-bound, not GPU-bound

**Date:** 2026-06-20
**Measured negative result, THEN a hot-spot fix. `MultiProcessRuntime.tick_all` (per-program CUDA
streams) is correct but does not parallelize on the Python-orchestrated runtime — and profiling the
"98% Python" revealed most of it was a PERF BUG in `_role_hash`, not irreducible orchestration.**

> **LEVER PULLED → RESOLVED (2026-06-20).** This finding's conclusion — that real multi-process throughput
> needs genuine parallelism (separate OS processes / GIL release), not in-process CUDA streams — was acted
> on: `ProcessPoolRuntime` (separate OS processes) delivers **up to 3.21×** where `tick_all` gave
> 0.4–0.95×. See `2026-06-20-genuine-multiprocess-throughput.md`. `tick_all` keeps its value as the correct
> in-process dispatch SHAPE; the throughput win lives in the process-pool runtime.

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

**Next hot-spot — FIXED (option a, the key-memo).** `_role_hash`'s `.cpu()` GPU→CPU transfer was the
remaining ~68% of the (now tiny) tick, recomputed every tick because `embed` returns a `.clone()`
(fresh object). Fixed by threading the role KEY STRING through `axon_add`/`axon_item` →
`bind`/`unbind`/`_axon_permutation_for` → `_role_hash`, which memoizes the hash by the key string
(`embed(key)` is deterministic, so the hash is a pure function of the key; the memo is keyed by string
only, so it cannot collide a different vector onto a cached hash). `role_key=None` (the bare
`bind`/`bundle` builtins) computes from the vector as before. Measured: 18.8ms → **8.4ms/8-prog round**
(another ~2.2x; **~41x total** from the original 347.6ms). `tick_all` is now **1.33x** vs sequential —
Python is down to 61% of the round, so the GPU overlap finally pays. 85 axon/bind/rotation +
37 Yantra-kernel tests pass (byte-identical hashes).

## Perf chain CONCLUDED — the remaining cost is genuine substrate work (fusion-pass territory)

Re-profiling after both fixes: a single-program tick is now ~0.95ms (from ~43ms, **~45x**). `_role_hash`
is negligible (0.002s, from 8s). The new top costs are `bind` (the rotation matmul `Q @ filler`,
~0.1ms × 3/tick) and `_axon_permute_synthetic` (the synthetic-block gather + a `clone`, ~0.09ms ×
3/tick) — these are GENUINE substrate operations (the actual binding + axon storage), not fixable bugs
like the `bytes(tensor)` / `.cpu()` hot-spots were. Squeezing them further needs the compile-time
FUSION PASS (collapse a program's per-tick per-op kernel launches into one fused tensor-op graph), a
bigger compiler leg, not a micro-optimization. The two bounded hot-spot fixes here (`.tolist()` +
key-memo) recovered the easy ~45x; the fusion pass is the deeper, separate lever.

## Fusion-pass attempt 1 — the "cat" fusion REGRESSED tick_all (reverted). KEY LESSON.

First fusion attempt (2026-06-20): `axon_add` does `bind` (full d×d matmul `Q@value`, Q identity on the
synthetic block) then `_axon_permute_synthetic` (gather + a full-vector clone). Since Q is identity on
the synthetic block and the permute only touches it, `permute(bind(key,value))` ==
`cat(Q_sem @ value[:sem], value[sem:][perm])` — verified BIT-IDENTICAL (max diff 0.0). In isolation the
fused expression is ~3x faster (0.276 → 0.091 ms/call: a d_sem matmul + gather vs a full d×d matmul +
clone).

But measured end-to-end it HELPED sequential `tick` (8.4 → ~6.3 ms/round) and **REGRESSED `tick_all`**
(6.3 → 8.9–15.7 ms/round; 1.33x → 0.4–0.68x — i.e. concurrent became SLOWER than sequential, defeating
the whole primitive). Reverted (working tree clean).

**The lesson (load-bearing for the fusion pass):** the cat-fusion trades 2–3 ops for 5 SMALLER ops
(slice, matmul, slice, gather, cat). Fewer/bigger ops win on the CONCURRENT path (CUDA streams overlap
big kernels; more small kernel launches add per-launch + sync overhead with no overlap to amortize it).
So **for the multi-process goal, fusion must reduce op COUNT, not op SIZE.** The right fusion is the
one that makes each `axon_add` ONE op: precompute `M_key = blockdiag(Q_sem, P_perm)` per key (a single
d×d matrix; `P_perm` the permutation matrix so `P_perm @ syn == syn[perm]`), so
`axon_add(key,value) == axon + M_key @ value` — ONE matmul, no clone, no gather, no cat. Same matmul
size as today's `bind` but it ALSO absorbs the permute+clone, so it's fewer ops for BOTH paths. Cost:
`M_key` is d×d per key (~3 MB at dim 868), so cache it per key (bounded by the axon key vocabulary) and
cap/evict for pathological key sets. This is the next §1A step (fresh context).

## Fusion-pass attempt 2 — the `M_key` operator SUCCEEDED (shipped). Op-count lesson confirmed.

Implemented `M_key = blockdiag(Q_sem, P_perm)` (the synthetic-block permutation as a matrix:
`P_perm = eye(d_syn)[perm]`, so `P_perm @ syn == syn[perm]`), cached per role-hash in `_axon_op_for`,
and rewrote `axon_add` to `axon + M_key @ value` — ONE matmul instead of bind (matmul) + permute
(clone + gather). Verified BIT-IDENTICAL (`M_key @ value` max diff 0.0 vs the old path; round-trips and
string-in-axon exact; 100 axon/bind/multi-process/rotation/string/type-test tests pass).

Measured (8-program round, dim 868): in isolation `M_key @ value` is ~10x the old per-add cost
(0.267 → 0.025 ms). End-to-end: **sequential `tick` ~6.8 → 3.3 ms/round (~2x)**, and crucially
`tick_all` is **5.9–6.6 ms (NOT regressed**; pre-fusion 6.3 ms) — the exact opposite of the cat-fusion,
which had pushed it to 8.9–15.7 ms. This confirms the lesson: collapsing 3 ops → 1 op (op COUNT) does
not hurt the concurrent path, where the cat-fusion's 3 → 5 smaller ops (op SIZE) did. The
`tick_all`/sequential RATIO drops to ~0.5x only because the per-program work is now so small that the
stream overhead outweighs the overlap — a "too fast to bother parallelising at this size" regime, not
a regression (both paths are absolutely faster).

**Read path also fused (same commit-series).** `axon_item(axon, key) = unbind(key, unpermute(axon))`
== `cat(Q_sem^T @ axon[:sem], P_perm^T @ axon[sem:])` == **`M_key^T @ axon`** — the inverse is the
transpose because `Q` is orthogonal and `P_perm` is a permutation. So `axon_item` is ONE matmul reusing
the SAME cached `M_key` (no new operator). Bit-identical (max diff 0.0); the `.T` is a strided matmul,
no copy. Measured ~10x/op (0.343 → 0.033 ms). 83 compiler + 99 Yantra axon tests pass. Both axon write
(`M_key @ value`) and read (`M_key^T @ axon`) are now single-matmul, 3 ops → 1 each.

Memory note: `M_key` is d×d per key (~3 MB at dim 868), cached in `_axon_op_cache`, bounded by the axon
key vocabulary in practice; a program with a pathologically large key set would want an LRU cap
(follow-on, not needed by current fixtures). §1A is then complete except that cap.

## Fusion-pass extension — `axon_build` BATCHES N adds into one bmm (primitive shipped).

After M_key, the next op-count win: an `on_axon` body / record construction does N `axon_add`s = N
separate `M_key @ value` matmuls. `axon_build(axon, keys, values)` stacks the N cached `M_key` operators
into one `(N,d,d)` batch and does a single `bmm` + sum — folds the N adds, BIT-IDENTICAL (verified, max
diff 0.0; `test_axon_build.py`, 4 tests), collapsing N launches to 1. Measured (3 adds): 0.155 →
0.050 ms (~3x with the M-stack reused) / 0.108 ms (~1.4x stacking per call). Fewer ops, so it helps the
concurrent path (the cat-fusion lesson applied — and validated here, unlike attempt 1).

**Shipped:** the `axon_build` runtime primitive (additive, tested).

**Codegen wiring — SHIPPED 2026-06-20.** The class/record factory was a dead end: language frontends do
NOT lower records/tuples to Sutra `class`/`new`; they emit direct `Axon _r; _r.add("x",a); _r.add("y",b);`
sequences (verified on the OCaml `record` fixture). So `_emit_class_factory` would help almost nothing.
The real target — and what shipped — is a statement-list **peephole** (`_translate_stmts_fused`,
`codegen_base.py`, routed from the function-body loop): it collects a maximal run of consecutive
`<var>.add(K,V)` on the same axon var (breaking the run if a later value expr uses `<var>`, or the next
stmt is not a same-var `.add`), drops the keys the existing cross-function elision already elides, and
emits one `<var> = _VSA.axon_build(<var>, [K…], [V…])` for the kept run (≥2 kept), a lone `axon_add` for
1 kept, nothing for 0. Bit-identical (the primitive is pinned bit-identical; the peephole only changes op
COUNT). Verified green: OCaml suite (152), Scala/Haskell/Elixir/Erlang record/tuple/struct/map/nested
fixtures (62), compiler axon/codegen/bind/string/type-test (182). The cross-function elision safety tests
were made fusion-aware (`assertMaterialized`: a key counts as kept whether emitted as `axon_add` or inside
a batched `axon_build`) so they assert the no-over-prune property without pinning the per-add shape.

**Cache memory bound — SHIPPED 2026-06-20 (closes §1A).** The fused operators live in d×d caches
(`_axon_op_cache` for `M_key`, `_rot_cache` for the Haar Q each `M_key` is built from — both ~6MB at
d=868 float64), previously unbounded. A pathologically large axon-key / role vocabulary could grow them
without limit; and capping only `_axon_op_cache` would not bound memory, because the Q persists in
`_rot_cache` (the two co-grow). Both are now FIFO-capped at `self._role_cache_cap` (default 1024).
**FIFO, not move-to-end LRU**, is the deliberate choice: LRU's per-hit reorder reintroduces Python onto
the cache-hit hot path this finding spent its effort removing, whereas FIFO adds ZERO on hits (eviction
fires only on the overflowing insert). Eviction is correctness-safe — every value is a deterministic
function of its key (seeded Haar rotation / fixed permutation), so a recomputed entry is bit-identical to
the evicted one (pinned by a small-cap overflow test). The cap is generous: real programs use a handful
to a few dozen distinct keys, far under it, so they never evict — only pathological key sets trade
recompute for bounded memory.

## Fusion-pass effect MEASURED end-to-end (2026-06-20) — sequential ~3x; tick_all sharpened to ~0.4–0.6x

After wiring the `axon_build` peephole, re-ran `bench_tick_all.py 8 768` (dev GPU, dim=868, caches warm).
The bench program (`Axon a; a.add("x",…); a.add("y",…); a.add("z", input); return a`) now compiles to a
single batched `a = _VSA.axon_build(a, ['x','y','z'], …)` (verified emitted), so each program's per-tick
graph is ~1 fused op instead of 3 `axon_add`s.

| dispatch | ms / 8-prog round (4 runs) | speedup |
|---|---|---|
| sequential `tick` ×8 | 2.5 / 2.6 / 2.8 / 2.9 (~2.7) | 1.00x |
| `tick_all` (8 streams + 1 synchronize) | 6.5 / 7.0 / 6.8 / 4.6 | **0.38–0.60x** |

Two findings, both honest:

1. **The fusion WON on the sequential path (the measurable goal).** The 8-program round went from
   347.6 ms (original, pre-`_role_hash` fix) → 8.4 ms (after the `_role_hash` 66x + key-memo) → **~2.7 ms**
   (after M_key write/read fusion + the `axon_build` peephole). That last stage is **~3x** on top of
   key-memo, **~129x** across the whole chain. Fewer/bigger ops per tick = less GIL-bound Python = faster
   sequential ticks. This is what the fusion pass was for, and it delivered.

2. **`tick_all` got MORE net-negative, not less: 0.95x → ~0.4–0.6x.** Counter-intuitive but coherent.
   `tick_all`'s per-round cost is ~fixed CUDA-stream machinery (8 stream creates + context switches + 1
   synchronize), which the original finding already measured as pure overhead at 0.95x. Shrinking the
   *work* (fusion) did nothing to that fixed overhead — so now the overhead (~4–7 ms) DWARFS the ~2.7 ms
   of actual work, and the ratio drops further. **Sharpened conclusion: CUDA streams are the wrong
   concurrency mechanism for this workload at any per-program work size, and making the work smaller only
   widens the gap.** Real multi-process throughput still needs genuine parallelism (separate processes or
   GIL release), exactly as the original finding concluded — the fusion pass was the right lever for the
   *sequential* cost, and it is now essentially exhausted (per-tick work is ~1 op). `tick_all` keeps its
   value as the correct *dispatch shape* (bit-identical, the API Yantra's `tick_concurrent` consumes), not
   as a throughput win on today's single-process GIL-bound runtime.

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
