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
   a. `tick_all(inputs: dict[name, axon]) -> dict[name, axon]`: launch each program's `on_axon` on its
      OWN `torch.cuda.Stream` (no inter-stream sync), then `torch.cuda.synchronize()` and collect, so
      the GPU overlaps them. Python launch stays sequential under the GIL (so the shared-`_VSA` lazy
      caches don't race); only the device kernels overlap. CPU fallback: plain sequential (streams are
      a CPU no-op), correctness preserved.
   b. Test (`test_multi_process_runtime.py`): `tick_all` results are IDENTICAL to per-program `tick`
      (correctness first); N independent programs dispatch concurrently and all outputs are correct.
   c. Wire Yantra's kernel router to `tick_all` for a round of admitted services (follow-on, after the
      primitive lands + is tested).

---

## 2. WASM source frontend — NEXT (do after §1)

The `WASM/`-subtree source→Sutra path (Phase 3 in `todo.md`). Several sub-parts are CI/clang-blocked
on this clone (need `uv`/`clang`/`wat2wasm`); route those through CI. Decompose from `todo.md`
§"Phase 3 — WASM" + the `WASM/` agenda when §1 is done.

---

## Pointers

- Substrate-leak catalogue: `Audit.md`. Longer-horizon: `todo.md`. Findings: `planning/findings/`.
  Open design questions: `planning/open-questions/`. Devlog: `DEVLOG.md`.
- Transpiler edge cases (low-value, leave-on-WASM-fallback): `planning/wasm-fallback-edge-cases.md`.
- Corpus: `github.com/EmmaLeonhart/sutra-w2c-corpus` (submodule `corpus/`) + HF mirror.
- Yantra (downstream OS): vendored in-tree at `external/Yantra/`.

## Session bracket

- The autonomous loop is the self-timed `ScheduleWakeup` form (not the old three-cron playbook).
