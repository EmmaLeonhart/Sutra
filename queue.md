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

### A. Object encapsulation — finish the language feature (`todo.md` §"Object encapsulation")

The encapsulation design is partially shipped (class-as-namespace methods, `SUT0144`). Remaining pieces,
in order. **First step each time: check the current state** — `22_class_with_fields.su` is already in the
valid corpus, so parsing may be partly there; build on what exists, don't rebuild.

1. **Field declarations (`field name: type;`) — immutable, axon-backed.** Design call (mine, consistent
   with Sutra being purely functional + classes-as-axons): a field is an IMMUTABLE named slot set at
   construction; an instance is an axon keyed by field name; `g.field` lowers to `axon_item(g, "field")`.
   No mutable per-instance state (that would break the functional substrate). Steps: confirm/extend the
   parser for `field` decls in class bodies; lower construction to `axon_add` per field; lower `g.field`
   read to `axon_item`; fixture that constructs an instance, reads fields back (RUN, compare to ground
   truth), substrate-verified.
2. **Instance-syntax dispatch on typed variables (`g.method(args)` for `Greeter g`).** Needs variable
   type tracking through codegen so `g.method(...)` resolves to the class method with `g` as `this`.
3. **Non-static loops with `this` threading** (after fields land — `this` as an implicit state param on
   non-static class loops).

### B. First-class function values (`todo.md` §"First-class function values") — BIG leg, decompose first

The single biggest unlock: it gates the full async/await Stage-1 desugar (multi-await chains,
`try/await/catch`), higher-order list ops (`map`/`filter`/`reduce`), AND the NTM `ramRead`/`ramWrite`
inline surface. Today arrow functions hoist to top-level decls; a function name can't appear in a value
position. **Before writing code: write a design/decomposition doc** (parser arrow-as-value, a function
arrow type, codegen emitting Python closures / named-helper indirection) and split into bounded steps —
this is explicitly "its own focused session," so prefer a worktree and small verified increments.

### C. Measurement gates — state-locus + signal-separation (`todo.md` §"Promote the three measurement checks")

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
