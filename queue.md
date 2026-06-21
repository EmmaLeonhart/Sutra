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

## ACTIVE — barrel top to bottom (Emma's 2026-06-20 design decisions, now unblocked)

### A. `await` mid-function → poll-loop lowering (Emma: "polling loop is desired; the input+flag form is the β-reduction case")

`await` as a mid-function expr raises `CodegenNotSupported` today (only tail-position `async … return await
e` works). Emma's model: the RUNTIME lowering is the **gated polling loop** (`promises.md`'s while_loop) —
`vector v = await x; return g(v);` becomes a substrate loop that polls `x` until its arrival flag is set,
then continues with `g(v)` (first-class functions now make the continuation expressible). The value-as-
INPUT + arrival-flag form is the COMPILE-TIME β-REDUCTION case: when the awaited value can be statically
resolved, the poll loop reduces away to a direct input+flag read. Build the poll-loop lowering first; add
the β-reduction-to-input+flag as the optimisation. Conform to `promises.md` + Promises/A+.

### B. All numbers on the SUBSTRATE (Emma: "purist, the old goal") — BIG, foundational, substrate-purity-critical

Emma chose: `int`/`number`/`scalar` math should run on the substrate (the number axis), NOT host floats.
So host-int is a **gap to CLOSE**, not the intended design (correct the spec/finding accordingly — substrate
is the committed direction). Move numeric ops onto the substrate: `int` literal → number-vector, `a + b` →
substrate add on the number axis, comparisons, augmented assignment, the int-return boundary. **Big blast
radius + sub-questions to resolve while building** (decompose, may surface design sub-decisions): do loop
counters / array indices / array lengths also become substrate vectors, or stay host for control flow? (The
number-axis encoding already exists — `make_real` puts a value there; the work is routing ALL numeric
lowering through it instead of host floats.) Highest-priority on substrate-purity grounds but the largest;
do in verified increments (prefer a worktree). Pairs with the int/scalar finding
`planning/findings/2026-06-20-int-scalar-is-host-not-substrate.md` (reframe: substrate is the goal).

Order: A (bounded, quick win) → B (medium) → C (big/critical, decompose). All three are now design-unblocked.

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
