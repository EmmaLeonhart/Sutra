# Sutra — Work Queue

**This file is a queue, not a state snapshot.** It lists what is being worked on now and
what is next, in execution order — barrel it top to bottom. **Finished work is REMOVED in the
same commit it ships** (history lives in `git log`, `DEVLOG.md`, `planning/findings/`).
`todo.md` is the longer-horizon backlog; items migrate `todo.md` → here → deleted on completion.

**⭐ CLEARING the queue is the SAFE default (Emma 2026-06-21).** When an item is done, DELETE the
line — **version control + `DEVLOG.md` already hold the entire history, so nothing is ever lost by
removing it.** Deleting a finished item is NEVER the risky move; the git log is the safety net.
The UNSAFE thing is letting done work accumulate — a "Recently shipped" pointer block,
`~~struck-through~~` lines, "DONE"/"✓" markers, or a paragraph summarizing what shipped. That bloat
buries the open work and is exactly what keeps re-growing this file. The queue holds ONLY
not-yet-done work; the moment something ships, it leaves. **Do not defer work to a clock time either**
— if nothing else is in flight, just do it now (no "do this at 2pm" scheduling).

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
- **Version: 0.9.1** (Emma 2026-06-21) — `pyproject.toml` + `__init__.py` bumped to a fresh `0.9.1` (a clean
  patch past the `v0.9.0` milestone tag, rather than forcing the package to exactly match the old tag).
  Publish via a `sutra-dev-v0.9.1` tag (trusted-publisher → PyPI `sutra-dev`). **v1.0.0 is deferred** until
  codegen/stdlib go a stretch with NO source-breaking changes (Emma's call — too soon right after this
  week's arithmetic-semantics changes). No hard blocker; it's a source-compat-stability commitment.

## ⭐ FV PAPER — narrow + probabilistic spine (Emma 2026-06-27): frame + remaining legs

**Frame (binding):** the FV paper verifies **Sutra-the-language as an ISA on a *probabilistic*
substrate** — keep it NARROW (per-contract, non-learned trusted base); do NOT re-grow "verify the
whole neuro-symbolic system". Recurring project failure mode = overambition.

**Shipped 2026-06-27 → 2026-07-04** (full history: `DEVLOG.md` + `git log`; clawRxiv reached
**Accept** 2026-07-01): trim pass; Z-transform loop-convergence criterion (measured); continuous-time
sampler-convergence measurement (γ=0.0397, 8-state); `GibbsMultiState` foundation; spectral capstone;
Z-transform unification; mean-zero composition + 2-state discharged instance; convergence-to-
stationarity limit; Dirichlet bridge; Poincaré⇒decay engine; conductance blocks + uniform- and
general-π Poincaré; lazy-uniform n-state instance; and the concrete 8-state AND-gadget heat-bath
instance (`GibbsGadget.lean`, κ=1/16 exact — the exp(−βE) factors cancel in the per-edge ratio).

**REMAINING (Emma green-lit both legs 2026-07-03; (a2) landed 2026-07-04):**
1. **(c) continuous-space overdamped Langevin** `dX=−∇U dt+√(2/β)dW` — needs SDE/measure theory,
   likely at/beyond mathlib's frontier; SCOPE HONESTLY before building (spec + tiering:
   `planning/findings/2026-06-29-lean-gap-audit.md` item 3). Cite no numbers until proved.
2. *(named, NOT green-lit — do not start without Emma):* a Lean gap for the literal
   **single-spin-flip** kernel needs the canonical-paths comparison method (a per-edge conductance
   bound cannot see a kernel with zero entries); until built, the measured γ=0.0397 stays a
   measurement. See DEVLOG 2026-07-04.

**Guardrails:** nothing is proven until `lean` accepts it (no `sorryAx`); every
`paper/formal-verification/paper.md` push triggers the clawRxiv resubmit CI (intended). Mathlib-layer
work is verified via the `fv-lean-mathlib-ci` Linux job (local Windows builds hit MAX_PATH; remote
containers cannot reach the toolchain/cache hosts — iterate via branch pushes).

---

## ACTIVE — barrel top to bottom

**Theme (Emma 2026-06-22/23): USABILITY.** Make Sutra easy for an outside person to install, run,
and learn. The backlog elsewhere is all substrate-correctness; none of it is usability. The
in-process-embedding change (drop the Ollama daemon) shipped 2026-06-22. Barrel these top to bottom;
delete each on completion + append to `DEVLOG.md` in the same commit.

**Usability audit CONVERGED across Batches 1–11 (2026-07-01).** All shippable bounded items
drained; per the delete-on-done rule the batch records are cleared from this file — full history in
`DEVLOG.md` + `git log` (queue.md's own history holds the batch text). Re-run the PINNED TAIL audit
next session to refill if usability re-opens.

### ⭐ FV-Lean — the THRML chain's continuous-time decay (audit item 2; Emma reframe 2026-07-04)

**Emma (2026-07-04, AskUserQuestion): "are we not using THRML for the formal verification lol?"
— the verification target is the thrml compile target's actual sampler.** `codegen_thrml.py`
executes discrete-state block-Gibbs over spin registers; its continuous-time law is the finite-state
jump process `dp/dt = Qᵀp` that `fv_sampler_convergence.py` measures. Consequences (finding:
`planning/findings/2026-07-04-langevin-lean-scoping.md`):
- **Continuous-space Langevin is OUT OF SCOPE for the substrate** (and out of proof-assistant reach
  anyway — no SDE/Fokker–Planck exists in any prover). Dropped; paper §7 says scoped-out.
- **DO NOW — machine-check the thrml chain's continuous-time master-ODE decay:** `df/dt = Qf` ⇒
  `d/dt‖f_t‖²_π = 2⟨Qf_t,f_t⟩_π = −2·E_Q(f_t) ≤ −2γ‖f_t‖²_π` ⇒ `‖f_t‖²_π ≤ e^{−2γt}‖f_0‖²_π`
  (exp-factor monotonicity instead of a Gronwall import; generator Dirichlet identity by the same
  algebra as `dirichlet_eq`, rows sum to 0). γ VALUE stays measured (0.0397). Verify via
  `fv-lean-mathlib-ci` branch pushes (local/remote builds blocked; shallow-clone mathlib4 v4.30.0
  for lemma-name grepping). No `sorryAx`; nothing proven until `lean` accepts it.
- *(named, NOT green-lit)* the literal single-site block-Gibbs kernel's own discrete-time gap still
  needs canonical paths (zeros between non-neighbours).

### A1 demo — SHIP step = the web wrapper (Emma 2026-07-03, via AskUserQuestion)

The gui-training A1 demo (1a θ render, 1b SPSA, 1c steering+window, 1d soak — DEVLOG 2026-06-14) is
complete and measured; Emma has decided **the optional web wrapper IS the ship step**. Build the web
wrapper for the steering demo: browser-served surface over the existing substrate demo (start from
`demos/gui/` + `experiments/gui_steering_eval.py`; the host-surface pattern is
`demos/gui/button_substrate_server.py` ↔ `external/Yantra/apps/gui-button/button_surface.py` — a
web page replaces the desktop surface as I/O host; substrate stays the compute). Also still flagged
from 1d: reward EMA smoothing (currently raw ±1 two-sided). Honest rails: render substrate-side,
host does I/O only; measure before claiming.

> **H1 (unknown-type/function diagnostics) RECLASSIFIED 2026-06-24 → the deferred v0.2 name-resolution
> milestone, NOT a quick batch item.** `validator.py:21-29` EXPLICITLY defers name resolution to "v0.2+
> once we have a symbol table." A measured false-positive scan (`scratchpad/h1_recon.py`) confirms a naive
> diagnostic warns on EXISTING VALID code: `03_methods.su` (valid corpus) references undeclared `Animal`/
> `Cat` types; the arrow-fn examples call first-class function-valued LOCALS (`f`,`scale`) — both need the
> real symbol table + local-scope tracking, not an allowlist. (Also `float`/`function` are missing from
> `PRIMITIVE_TYPE_NAMES` — real gaps to fix WHEN the symbol table lands.) The newcomer gap is already
> mitigated at the doc level (Batch 5.1 tutorial-01 note: v0.1 doesn't do name resolution, on the roadmap).
> Building the v0.2 symbol table is Emma's call (language-direction; it tightens the deliberately-lenient
> validator). Finding: `planning/findings/2026-06-24-h1-name-resolution-is-deferred-v0.2.md`.

---

## ⭐ PINNED TAIL — readability + usability audit → REFILL (self-perpetuating; Emma 2026-06-23)

**This item never gets deleted — it regrows the queue.** When items 1..N above are all done, run a fresh
**readability + usability audit** of Sutra from the perspective of an outsider trying to read, install,
run, and learn it, and **atomise the findings into 3–6 new concrete items at the TOP of this ACTIVE
list**, then keep barrelling. Repeat every time the concrete items drain. Audit surfaces, rotating:
- **Onboarding:** can a stranger `pip install` and run their first program in <5 min? Where do they get stuck?
- **Docs readability:** are the tutorials/concept pages clear, in order, free of repo-internal jargon and
  dead links? Does the website read well to a newcomer? (Website discipline: keep `docs/` free of
  `queue.md`/`todo.md`/`planning/...` references.)
- **Error messages:** are `SUT####` diagnostics + runtime errors actionable, pointing at the fix?
- **Language readability:** is `.su` source itself readable? Are the example programs idiomatic and
  well-commented? Is the stdlib surface discoverable?
- **Real-program reach:** what can't a newcomer build yet that they'd expect to? (stdlib gaps, missing
  ergonomics) — name precisely; don't fake reach.
- **Aliases + affordances (Emma 2026-06-23):** internal redundancy — two Sutra-native names for one op,
  legacy entry points, escape hatches that mislead the next agent. Deprecate aggressively toward one
  canonical spelling (CLAUDE.md § "Deprecate aliases aggressively"); exclude the foreign-ecosystem carve-out.

**THE GOAL IS V1, AND V1 IS EMMA'S MANUAL CALL — NOT THE LOOP'S.** Keep making Sutra more readable +
usable; do NOT bump the version to 1.0.0, do NOT declare "V1-ready," do NOT tag a v1 release. Emma
approves the V1 transition manually. The loop's job is to keep closing usability/readability gaps until
she says it's there. (Consistent with the v1.0.0-deferred note in Context above.)

## Session bracket — autonomous loop (self-timed)

- Run as the self-timed `ScheduleWakeup` loop (NOT the three-cron playbook). Each wake: SYNC
  (`git fetch` + ff/rebase) → WORK the top `queue.md` item → HARD RAILS (never fake/weaken a test; RUN +
  measure before claiming green; name hard things plainly) → COMMIT (delete done item + DEVLOG entry,
  same commit) + push → schedule the next wake. When items 1..N drain, run the PINNED TAIL audit to
  refill, then continue — the loop is self-sustaining toward V1 (Emma's manual gate). Report via commits
  + DEVLOG, not questions.

---

## PARKED — real but gated (cannot implement on this clone)

_2026-06-21 audit: these are real, not phantom-PR. The async/await Stage-1 item was RETIRED (its
"only-tail-position-works / model-blocked" premise is now false — mid-function await shipped 2026-06-20).
The rest are genuinely gated on resources this clone lacks._

- **await Stage-2 — full gated `while_loop` with a LIVE external producer — desktop-I/O-gated.**
  The await CORE shipped 2026-06-20 (mid-function lowering + Promises/A+ rejection propagation, substrate-
  pure; `test_await_midfunction.py` green). What remains is the poll loop spinning on a promise an EXTERNAL
  producer resolves over time — i.e. the I/O orchestrator (**Sutra for Windows**, the desktop-I/O layer
  vendored in-tree at `external/Yantra/`) writing the resolved value into the awaited axon. `await_value`
  stays the β-reduced no-producer form until there's a real producer to test against; awaits buried in
  nested control-flow still fall through to the codegen rejection. Resume when wiring the desktop-I/O promise
  producer. (The await *model* — Emma 2026-05-17's implicit-axon-input + arrival-flag vs `promises.md`'s
  gated-while-loop — is still unsettled in the spec, but only governs this unbuilt producer path, not the
  shipped core. The old "async/await Stage-1 desugar" item was retired here: mid-function await shipped, so
  its "only-tail-position-works" premise is false.)
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
- Sutra for Windows (the desktop-I/O layer, formerly called "Yantra"): vendored in-tree at `external/Yantra/`
  (directory keeps the legacy name for now).

## Session bracket

- The autonomous loop is the self-timed `ScheduleWakeup` form (not the old three-cron playbook).
- Own the queue, barrel through, report via commits + DEVLOG — no questions.
