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

### (await leg — CORE shipped 2026-06-20; remainder Yantra-I/O-gated, see PARKED)

The practically-useful core landed: mid-function `await x` lowers + **Promises/A+ rejection
propagation** now works (awaiting a rejected promise used to silently FULFIL — fixed via a
substrate-pure `Promise.propagate` tanh blend; verified fulfill-flows-through + reject-stays-rejected;
`test_await_midfunction.py`). The remaining piece — the full Stage-2 gated `while_loop` with a LIVE
external-axon producer (the orchestrator that actually resolves the promise over time) — is Yantra I/O
work and is parked below; `await_value` stays the β-reduced no-producer form until then. Awaits buried in
nested control-flow also still fall through. Next active leg:

### A. All numbers on the SUBSTRATE — CORE SHIPPED 2026-06-21 (`44127510`); refinements below

**Runtime `int`/`number`/`scalar` arithmetic now runs on the substrate number axis (AXIS_REAL), not host
floats.** Shipped: `+ - * /` → `_VSA.num_add/sub/mul/div` (real-axis ops); augmented assignment `+= -= *= /=`
and postfix `++ --` → substrate; comparisons already were; loop counters via the slot round-trip stay on
the substrate (fib/trib/pell native loops verified == ground truth). `addp(2,3)` now returns a SUBSTRATE
TENSOR decoding to 5.0; `i=5; i+=3; i*=2; i-=1` = 15.0 tensor. `.item()` baseline held at 18 (no new
readouts — the added `float(x)` are the host→substrate ENTRY boundary, not readouts). Caught + fixed an
FV-checker regression (the Lagrange `!(a&&b)` veto: numeric-literal coefficients over truth-axis vectors
stay element-wise so `num_mul` doesn't project a truth vector). Full suite 788 passed, independently
re-verified (659 non-VM + 129 VM). Finding `planning/findings/2026-06-20-int-scalar-is-host-not-substrate.md`
(now: gap CLOSED for runtime arithmetic).

**Remaining (refinements, NOT blockers):**
- **PERMUTATION-encoded integers (Emma's mechanism) — not yet done; the core uses real-axis magnitude
  instead.** Emma 2026-06-20: a counter/iteration is a PERMUTATION on a dimension (a ring counter — step by
  permuting; the count is the accumulated permutation state). The shipped work meets the GOAL (counters are
  substrate, via real-axis `num_add`) but uses a magnitude representation, NOT the permutation/position
  encoding. If Emma wants integers represented as permutation/rotation state (the canonical substrate
  integer, differentiable matmul/gather), that's a representation change on top of the working core.
- **Compile-time constant folding** (`return 20/4` between two literals) folds to a host constant — minor
  β-reduction edge, not the runtime path. **Structural literals** (array sizes `var[N]`, `loop(N)` unroll
  counts) stay host — compile-time codegen directives, consumed before runtime. **numpy backend** keeps
  host floats (deprecated, no number-axis runtime).

---

## PARKED — gated or owned elsewhere (do NOT start on this clone)

- **await Stage-2 — full gated `while_loop` with a LIVE external-axon producer — Yantra-I/O-gated.**
  The await CORE shipped 2026-06-20 (mid-function lowering + Promises/A+ rejection propagation, substrate-
  pure). What remains is the poll loop spinning on a promise an EXTERNAL producer resolves over time — i.e.
  the orchestrator (Yantra) writing the resolved value into the awaited axon. `await_value` stays the
  β-reduced no-producer form until there's a real producer to test against. Also: awaits buried in nested
  control-flow still fall through to the codegen rejection. Resume when wiring Yantra's promise producer.
- **(historical) Full async/await Stage-1 desugar — was DESIGN-BLOCKED; the await MODEL is now settled.** First-class
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
