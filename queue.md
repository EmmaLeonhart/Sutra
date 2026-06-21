# Sutra — Work Queue

**This file is a queue, not a state snapshot.** It lists what is being worked on now and
what is next, in execution order — barrel it top to bottom. **Finished work is REMOVED in the
same commit it ships** (history lives in `git log`, `DEVLOG.md`, `planning/findings/`).
`todo.md` is the longer-horizon backlog; items migrate `todo.md` → here → deleted on completion.

**Owned + autonomous (Emma 2026-06-20):** the agent organises this queue itself — pulls items from
`todo.md`/findings/specs, orders by value, decomposes into concrete steps, prunes done work, and
executes top-to-bottom WITHOUT asking. Report via commits + DEVLOG, not questions.

---

## Context (read first, do not work on)

- **`paper/paper.md` is UNFROZEN** (Emma 2026-06-07); `paper/neurips/` freeze RETIRED 2026-06-18.
  Measured numbers only; no overclaiming. Editing `paper/formal-verification/paper.md` or
  `paper/paper.md` triggers a clawRxiv resubmit CI — intended for real updates, not churn.
- **NEVER use `Math.mod`** (measured vector-collapse/NaN). Use complex rotation for wrap/periodic.
- **GUI is on Emma's SEPARATE branch** — OUT of this queue. Do NOT re-add GUI items.
- **Substrate purity is non-negotiable**: every op runs on the substrate, NO host readout
  (`.item()`/`float(tensor)`) inside operations.
- **Multi-clone**: editable `sutra_compiler` install points at the sibling `Github\Sutra`; verify
  changes here via `PYTHONPATH=sdk/sutra-compiler`. CI uses this repo's compiler.

## Recently shipped — pointer, NOT work (see DEVLOG.md 2026-06-20)

The session's big directed legs are done + validated:
- **Perf / fusion leg (§1A complete):** `_role_hash` fixes (~45× binding) + `M_key` write/read fusion +
  `axon_build` batched build + the consecutive-`.add` peephole + FIFO cache cap. ~3× sequential tick.
- **Genuine multi-process runtime (§1C core):** `ProcessPoolRuntime` — separate OS processes, bit-identical
  cross-process, **up to 3.21× throughput** (the lever in-process `tick_all` couldn't pull), dead-worker
  hardening. Design: `planning/sutra-spec/multi-process-runtime.md`.
- **FV surface fully discharged:** Kleene grid-exactness, branch-range (incl. composed-by-induction),
  termination, graph-equivalence, contract key-soundness (incl. the fused-`axon_build` vacuity fix), the
  NAND end-to-end worked example, and the dimension-audit sweep.

---

## ACTIVE — barrel top to bottom

### A. Measurement gates — state-locus + signal-separation (`todo.md` §"Promote the three measurement checks")

Dimension gate SHIPPED (`experiments/dimension_audit_sweep.py`). The other two need a per-`.su` CLAIM
annotation surface first (a way for a program to declare "I am an RNN" / "I am a classifier"), because —
unlike codebook-use — the property isn't intrinsic to the source. Steps: (1) design a lightweight claim
annotation (a recognised comment pragma or a manifest entry); (2) state-locus check — for RNN-claiming
files, assert a walk-N-steps-no-host-extraction test exists/passes (`count.su`'s test is the template);
(3) signal-separation check — for classifier-claiming files, assert a measured `gap = min(pos)−max(neg)`
table is present (`test_font_bound.py` is the template). Lower priority than A/B: harder to automate
cleanly, moderate value.

---

## PARKED — gated or owned elsewhere (do NOT start on this clone)

- **Full async/await Stage-1 desugar — DESIGN-BLOCKED (the await MODEL is unsettled).** First-class
  functions (now shipped) unblock the *mechanism* (a continuation can be a hoisted function), and the gap
  is concrete (`await` as a mid-function expr raises `CodegenNotSupported` in `codegen_base.py`; only
  tail-position `async function … return await e` works). BUT the await *model* itself is undecided: Emma
  2026-05-17 directed "model the awaited value as an implicit axon INPUT + an arrival-flag axis, NOT a poll
  loop," which conflicts with `planning/sutra-spec/promises.md`'s gated-while-loop lowering. That's a
  language-semantics decision (load-bearing, conforms to Promises/A+), not an implementation detail — so it
  is NOT a self-direct call. Parked until the model is settled; building either lowering now risks building
  the wrong one. (Do not queue this as a question — wait for Emma to settle the model in her own time.)
- **§1C steps 3 & 4 — per-process CUDA isolation + CUDA-IPC codebook sharing.** Need a Linux/CUDA box;
  unverifiable on this Windows clone (no CUDA IPC). The portable core is done + validated. Resume when a
  CUDA environment is available; until then writing the code would ship unverified substrate work.
- **§1C ProcessPoolRuntime CUDA path** (`force_cpu=False`, per-process CUDA contexts) — part of the above.
- **§2 WASM source frontend.** Sibling-owned (its own work-loop / `:33` cron) and largely
  clang/uv/wat2wasm-blocked here. Coordinate via CI; do not collide with the subtree agent. Decompose
  from `todo.md` §"Phase 3 — WASM" only if it lands on this clone with a toolchain.

---

## Pointers

- Substrate-leak catalogue: `Audit.md`. Longer-horizon backlog: `todo.md`. Findings: `planning/findings/`.
  Open design questions: `planning/open-questions/`. Devlog: `DEVLOG.md`.
- Transpiler edge cases (low-value, leave-on-WASM-fallback): `planning/wasm-fallback-edge-cases.md`.
- Corpus: `github.com/EmmaLeonhart/sutra-w2c-corpus` (submodule `corpus/`) + HF mirror.
- Yantra (downstream OS): vendored in-tree at `external/Yantra/`.

## Session bracket

- The autonomous loop is the self-timed `ScheduleWakeup` form (not the old three-cron playbook).
- Own the queue, barrel through, report via commits + DEVLOG — no questions.
