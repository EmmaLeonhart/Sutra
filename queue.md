# Sutra — Work Queue

**This file is a queue, not a state snapshot.** It lists what is being worked on now
and what is next, in execution order — barrel it top to bottom. **Finished work is
REMOVED from this file in the same commit it ships** (history lives in `git log`,
`DEVLOG.md`, and `planning/findings/`). `todo.md` is longer-horizon; items migrate
`todo.md` → `queue.md` → deleted on completion.

**Big-leg order (Emma 2026-06-19): FV spectral-gap → Yantra OS → WASM.** FV spectral-gap
is SHIPPED (2026-06-19); the two remaining sections below are in execution order. Do them
top to bottom; do not start a lower one until the one above is shipped (or explicitly parked).

---

## Context (read first, do not work on)

- **`paper/paper.md` is UNFROZEN** (Emma 2026-06-07); `paper/neurips/` freeze RETIRED 2026-06-18.
  Measured numbers only; no overclaiming.
- **NEVER use `Math.mod`** (measured vector-collapse/NaN). Use complex rotation for wrap/periodic.
- **GUI is on Emma's SEPARATE branch** — OUT of this queue. Do NOT re-add GUI items.
- **Substrate purity is non-negotiable**: every op runs on the substrate, NO host readout
  (`.item()`/`float(tensor)`) inside operations.

---

## 1. Yantra OS integration — ACTIVE (FV spectral-gap shipped 2026-06-19)

Downstream consumer work: wire more of the Sutra substrate into the vendored `external/Yantra/` OS.
(GUI agenda is OUT per the Context section; the transformer-vm/WASM path is §2.) First concrete step
is the **cross-repo health check** (CLAUDE.md § "Cross-repo workflow": when a session edits Sutra
source, verify against Yantra) — this session changed `axon_add` (now sets `AXIS_AXON_POPULATED` +
the reserved-flag-axis permutation fix), added the type-test predicates, and reworked the RAM device,
all of which Yantra's substrate consumers (`external/Yantra/apps/`, `kernel/services/*.su`, the calc
axon programs) depend on. Steps:

1. **DONE 2026-06-20.** Ran Yantra's substrate-facing tests against the current SutraDev compiler.
   Found + fixed: (a) the `vsa.real()` host-accessor drift — Yantra consumed the accessor Sutra
   removed in the 2026-06-07 purity overhaul; migrated 6 files to `vsa._re()`. (b) Surfaced that this
   session's `axon_add` populated-flag was net-negative (corrupted nested-axon + string-in-axon
   reads) — REVERTED it (commit `fb58373d`); the `is_axon` type-test is a documented negative result.
   Yantra substrate suite (echo/axon_serialise/linux_000/symbol_fidelity/calc/kernel) green; main CI
   green.
2. **DONE 2026-06-20.** Ran the FULL Yantra suite (tests/ + orchestrator/tests/) against the current
   SutraDev compiler (PYTHONPATH override; confirmed `sutra_compiler.__file__` resolves into SutraDev):
   **208 passed, 1 xfailed** — no drift from this session's codegen change (the `axon_build` peephole).
   Precompile-cache regeneration confirmed: `cached_compile._cache_key` hashes the codegen SOURCE
   (`_CODEGEN_SOURCE_FILES = codegen_pytorch.py + codegen_base.py`), so any SutraDev codegen edit
   auto-invalidates every consumer's on-disk cache and regenerates on next compile — the suite exercised
   exactly this (cache-miss → regenerate → pass), and wrote no stale artifacts into the vendored tree.
3. **Multi-process Sutra runtime — ACTIVE (Emma 2026-06-20 chose this entry point).** Let the
   orchestrator run all admitted programs SIMULTANEOUSLY on one GPU. `MultiProcessRuntime`
   (`sdk/sutra-compiler/sutra_compiler/multi_process.py`) already hosts N programs over a shared
   `_VSA`, but `tick(name, input)` dispatches SEQUENTIALLY (one program per call; relies on incidental
   CUDA scheduling). Concrete first step — true concurrent dispatch (the concurrency-spec "multiple
   paths through vector space, computed for each, splitting"):
   a. **DONE (`eb9fcece`).** `tick_all(inputs: dict[name, axon]) -> dict[name, axon]`: per-program
      `torch.cuda.Stream` launch + one `torch.cuda.synchronize()`; GPU overlaps the kernels, Python
      launch sequential under the GIL so the shared-`_VSA` caches don't race; CPU-sequential fallback.
   b. **DONE (`eb9fcece`).** Tests: `tick_all` == per-program `tick` (bit-identical), name-validation-
      before-launch, empty round; 13/13 `test_multi_process_runtime.py`, compiler CI green.
   c. **DONE 2026-06-20.** Added `Init.tick_concurrent()` (external/Yantra/kernel/init.py): an OPT-IN
      tick that dispatches shared-`MultiProcessRuntime` GPU-resident services CONCURRENTLY via
      `runtime.tick_all` (per-program CUDA streams), in waves over their drained inboxes; per-service-
      `_VSA` and non-Sutra services stay sequential. SEMANTICS are deliberately the production
      "simultaneous" model (NOT a drop-in for `tick()`): every process reads the START-of-tick inbox
      state, so a prod→cons pipeline takes one extra tick to flow — pinned by
      `test_tick_concurrent_simultaneous_semantics`. `tick()` (sequential intra-tick flow) is
      unchanged. Tests: independent-services concurrent dispatch + the simultaneous-semantics flow; full
      Yantra kernel suite 73 pass.

   **Multi-process runtime leg: core DONE** (tick_all primitive + Yantra concurrent integration).
   d. **DONE 2026-06-20 — measured the throughput (finding `2026-06-20-tick-all-no-speedup-python-
      bound.md`).** NEGATIVE result: `tick_all` is 0.95x vs sequential at N=8 — NO speedup, because a
      program's per-tick cost is 98% GIL-bound Python orchestration and only 2% GPU kernel time, and
      streams overlap only the kernels. Corrected the docstrings; committed `experiments/bench_tick_all.py`.
      Consequence: real multi-process throughput is GATED on shrinking per-tick Python (the compile-time
      FUSION PASS that collapses a program's per-tick graph to one fused op), not on more dispatch
      plumbing. That fusion work is the real lever — a bigger leg, not yet decomposed.
   e. **DONE 2026-06-20 — profiled the per-tick Python, found + fixed a 66x hot-spot.** `_role_hash`
      computed its cache-key via `bytes(tensor.view(uint8))`, which iterates the d-vector element-wise
      (`__iter__`→`unbind`, ~6.4ms/call). Fix: `.tolist()` (C++ bulk, not numpy), byte-identical →
      `_role_hash` 66x faster, the whole binding tick ~18x faster (347→18.8ms/8-prog round). Benefits
      EVERY binding Sutra program. CI green. See the finding.
   f. **DONE 2026-06-20 — memoized `_role_hash` by role key (the `.cpu()` hot-spot).** Threaded the
      role KEY STRING through axon_add/axon_item → bind/unbind/_axon_permutation_for/_rotation_for →
      _role_hash, memoizing the hash by key (deterministic `embed`, string-keyed so no collision risk;
      `role_key=None` keeps the vector path). 18.8ms → 8.4ms (~2.2x more; **~41x total** from original).
      `tick_all` now 1.33x. 85 + 37 tests pass. See the finding.
   The multi-process leg core is shipped + measured (~45x perf). Its deeper levers are §1A–§1C below.

---

## 1A. Compile-time FUSION PASS — ACTIVE (Emma 2026-06-20: do §1A → §1B → §1C in sequence)

The deeper perf lever for the remaining ~61% per-op orchestration. After the two `_role_hash` hot-spot
fixes (~45x), a single binding tick is ~0.95ms and the residual cost is GENUINE substrate ops launched
per-op in Python: `bind` (the rotation matmul `Q @ filler`, ~3/tick) and `_axon_permute_synthetic`
(the synthetic-block gather + clone, ~3/tick). The fusion pass collapses a program's per-tick per-op
kernel launches into one (or few) fused tensor-op graph(s), so the GPU does the work in fewer dispatches
and the Python orchestration shrinks. Existing infra to build on: `simplify_egglog.py` already does
COMPILE-TIME matrix-chain fusion (R_CHAIN: collapse `R1·R2·…·Rn`).

**Attempt 1 (2026-06-20) — the "cat" fusion — REVERTED. Critical lesson recorded.** Fused
`permute(bind(key,value))` to `cat(Q_sem @ value[:sem], value[sem:][perm])` — bit-identical, 3x faster
in isolation, HELPED sequential `tick` (8.4→6.3ms) but **REGRESSED `tick_all` to 0.4–0.68x** (slower
than sequential — defeats the primitive), because it trades 2–3 ops for 5 SMALLER ops and CUDA streams
want FEWER/BIGGER kernels. **Lesson: fusion for the concurrent goal must reduce op COUNT, not op size.**

**Attempt 2 — the `M_key` fusion — SHIPPED 2026-06-20.** `axon_add` now does ONE matmul
`axon + M_key @ value` (`M_key = blockdiag(Q_sem, P_perm)`, cached per key in `_axon_op_for`). Bit-
identical (max diff 0.0; 100 tests pass). Sequential tick ~2x (6.8→3.3ms); `tick_all` NOT regressed
(5.9–6.6ms) — op-count reduction confirmed (vs the reverted attempt-1 cat-fusion). See the finding
§"attempt 2".

**Read-path fusion — SHIPPED 2026-06-20.** `axon_item == M_key^T @ axon` (one matmul, reuses the cached
M_key; the inverse is the transpose since Q is orthogonal + P_perm a permutation). Bit-identical, ~10x/
op (0.343→0.033ms); 83 compiler + 99 Yantra axon tests pass. Both axon write+read are now single-matmul.

**Fusion extension (Emma 2026-06-20: "extend the fusion pass") — SHIPPED 2026-06-20.**
`axon_build(axon, keys, values)` batches N axon_adds: stack the N cached `M_key` operators into one
`(N,d,d)` bmm + sum instead of N separate matmuls. Bit-identical (max diff 0.0). **Primitive AND codegen
wiring both shipped** — the wiring is a statement-list peephole (`_translate_stmts_fused` in
`codegen_base.py`) that collapses a maximal run of consecutive same-axon `.add(K,V)` (no intervening use
of the var) into one `axon_build`, batching only the NON-elided keys. Records/tuples lower to direct
`.add` sequences, so this catches frontend record construction AND explicit `Axon a; a.add()×N`. Verified
bit-identical across the full OCaml suite (152) + Scala/Haskell/Elixir/Erlang record/tuple fixtures (62) +
compiler axon/codegen/elision (182). The cross-function elision safety tests were made fusion-aware
(`assertMaterialized`: a key is kept whether it lands in `axon_add` or batched `axon_build`).

**§1A is COMPLETE.** Write-path (`M_key`), read-path (`M_key^T`), batched build (`axon_build`), the
codegen peephole wiring, AND the bounded-cache robustness follow-on are all shipped. The d×d role-keyed
caches (`_rot_cache` + `_axon_op_cache`) are FIFO-capped (`_role_cache_cap`, default 1024) so a
pathological key vocabulary can't grow them without limit; eviction is bit-identical (every value is a
deterministic function of its key, so recompute == evicted). FIFO (not move-to-end LRU) keeps zero extra
Python on the hit hot path the perf work optimized. §1B is RESOLVED (above); §1C (GPU arenas) deferred
per Emma. **Next big leg: §2 (WASM source frontend).**

## 1B. Per-process state SERIALISATION — RESOLVED / NOT NEEDED (verified 2026-06-20)

§1B's premise is stale. Yantra's own audit `external/Yantra/planning/26-orchestrator-serialisation.md`
§(b) (2026-05-25) concluded the Sutra-side `serialise-process-state` primitive is **not needed**:
current Sutra is purely functional (concurrency.md: "No shared mutable state, no cross-path"), compiled
programs carry no trainable weights, and the `_VSA` caches (`_rot_cache`/`_perm_cache`/`_codebook`, and
now `_axon_op_cache`) are **deterministic from key strings** — they rebuild lazily on resume, they are
not state. So "per-program substrate state is empty"; the orchestrator's own state is the whole game,
and `kernel/checkpoint.py` already serialises it. **`Tier.RAM` cold-store SHIPPED 2026-05-25 without a
Sutra primitive.** Nothing to build here unless Sutra gains persistent per-process mutable state.

## 1C. GENUINE multi-process runtime — ACTIVE (Emma chose this 2026-06-20)

Emma's call (2026-06-20, over "in-process GPU memory pools" and other options): build the **genuine
multi-process runtime — separate OS processes**. The `tick_all` finding established that the current
"MultiProcessRuntime" is single-process + GIL-bound (no speedup); separate OS processes are the only real
throughput lever AND deliver §1C's original per-process GPU memory isolation. One mechanism, both wins.
Design doc (forks + verification plan): `planning/sutra-spec/multi-process-runtime.md`. Decomposed:

1. **`ProcessPoolRuntime` prototype (portable, Windows-safe) — DONE 2026-06-20.** New sibling to
   `MultiProcessRuntime` (`multi_process.py`; the single-process path untouched). W worker processes
   (`multiprocessing` spawn context, target is the module-level `_pool_worker_main` so it pickles without a
   `__main__` guard); each worker compiles its round-robin-assigned `ProgramSpec`s and rebuilds its `_VSA`
   caches lazily. Axons cross as CPU tensors (`_to_cpu`; CUDA tensors would need CUDA IPC, unsupported on
   Windows). `force_cpu=True` pins workers to CPU (sets `CUDA_VISIBLE_DEVICES=""` before the worker's torch
   import resolves `_DEVICE`) — portable GIL-escape without a CUDA context per process. Context-manager
   lifecycle (`close()` joins workers).
2. **Verification.** (b) **Bit-identical / determinism — DONE 2026-06-20.**
   `tests/test_process_pool_runtime.py`: two separate OS processes running the same program on the same
   input produce BIT-IDENTICAL output (rebuild-per-process is deterministic — validates the no-IPC-needed
   design), and the output decodes correctly across the boundary (x=5, y=8). 3 tests pass.
   (a) **Throughput — DONE 2026-06-20. The leg is VALIDATED.** `experiments/bench_process_pool.py` (CPU,
   1 thread/process to isolate process-parallelism; compute-heavy K=16-read program; steady-state):
   sequential ~113 ms/round vs pool **1.54× (W=2) / 2.47× (W=4) / 3.21× (W=8)** — a real, monotonic
   throughput win, the exact opposite of in-process `tick_all` (0.4–0.95×). Sub-linear from per-tick IPC +
   serial gather + physical-core cap (expected isolation costs, not a defect). Spawn+compile ~6.6 s one-time
   (break-even ~99 rounds). Separate OS processes ARE the GIL-escape lever the tick_all finding predicted.
   Finding: `planning/findings/2026-06-20-genuine-multiprocess-throughput.md`. Added `threads_per_worker`
   to `ProcessPoolRuntime` (pin intra-op threads so W workers don't oversubscribe).
3. **CUDA-context isolation (CI/Linux-gated follow-on).** Per-process CUDA context = the §1C memory
   isolation; verify one worker's allocations aren't visible to another via per-process
   `torch.cuda.memory_stats`. Needs a CUDA box; gate behind capability check.
4. **CUDA-IPC sharing (CI/Linux-gated, optional).** Share ONE codebook tensor read-only across workers via
   `cudaIpcGetMemHandle` to drop the per-process codebook duplication — only if codebook GPU memory becomes
   the constraint, and only on Linux (Windows has no CUDA IPC).

Start at step 1 (the portable core that tests Emma's premise on this machine before any platform-gated IPC).

---

## 2. WASM source frontend — after the §1A–§1C sequence

The `WASM/`-subtree source→Sutra path (Phase 3 in `todo.md`). NOTE: the `WASM/` subtree is actively
worked by its OWN work-loop / `:33` sibling-watch cron, and its remaining items are largely
clang/uv/wat2wasm-blocked on this clone. Coordinate / route through CI; do not collide with the
subtree agent. Decompose from `todo.md` §"Phase 3 — WASM" when the §1 sequence is done.

---

## Pointers

- Substrate-leak catalogue: `Audit.md`. Longer-horizon: `todo.md`. Findings: `planning/findings/`.
  Open design questions: `planning/open-questions/`. Devlog: `DEVLOG.md`.
- Transpiler edge cases (low-value, leave-on-WASM-fallback): `planning/wasm-fallback-edge-cases.md`.
- Corpus: `github.com/EmmaLeonhart/sutra-w2c-corpus` (submodule `corpus/`) + HF mirror.
- Yantra (downstream OS): vendored in-tree at `external/Yantra/`.

## Session bracket

- The autonomous loop is the self-timed `ScheduleWakeup` form (not the old three-cron playbook).
