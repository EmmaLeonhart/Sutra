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
2. **NEXT:** run the FULL Yantra test suite (not just substrate-facing) to catch any remaining drift;
   confirm the precompile caches regenerate against the current compiler.
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
COMPILE-TIME matrix-chain fusion (R_CHAIN: collapse `R1·R2·…·Rn`). First step: read the codegen emit
model + the egglog pass, find the concrete fusable pattern in the per-tick path (e.g. batch the
multiple `axon_add` binds into one batched matmul, or precompute a fused per-key operator), prototype +
measure it against the bench (`experiments/bench_tick_all.py`), decompose into concrete steps here.
Finding to extend: `2026-06-20-tick-all-no-speedup-python-bound.md` (§"Perf chain CONCLUDED").

## 1B. Per-process state SERIALISATION — NEXT (after §1A)

The Sutra primitive Yantra names as the blocker for Disc↔RAM↔GPU storage-tier moves: snapshot a
process's substrate state to a portable blob and restore it (so eviction preserves running state, not
just residency). Yantra's `kernel/checkpoint.py` + `SutraService.unload()` document the gap ("running
state is NOT preserved across unload — needs the Sutra serialise-process-state primitive"). Decompose
when §1A ships.

## 1C. Per-process GPU ARENAS — LAST of the three (after §1B)

The `MultiProcessRuntime` "What this is NOT": per-process GPU memory isolation (CUDA stream/IPC), so
admitted programs don't all share one pool. Device-level work. Decompose when §1B ships.

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
