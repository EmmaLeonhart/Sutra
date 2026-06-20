# Sutra — Work Queue

**This file is a queue, not a state snapshot.** It lists what is being worked on now
and what is next, in execution order — barrel it top to bottom. **Finished work is
REMOVED from this file in the same commit it ships** (history lives in `git log`,
`DEVLOG.md`, and `planning/findings/`). `todo.md` is longer-horizon; items migrate
`todo.md` → `queue.md` → deleted on completion.

**Big-leg order (Emma 2026-06-19): FV spectral-gap → Yantra OS → WASM.** The three
sections below are in execution order. Do them top to bottom; do not start a lower
one until the one above is shipped (or explicitly parked).

---

## Context (read first, do not work on)

- **`paper/paper.md` is UNFROZEN** (Emma 2026-06-07); `paper/neurips/` freeze RETIRED 2026-06-18.
  Measured numbers only; no overclaiming.
- **NEVER use `Math.mod`** (measured vector-collapse/NaN). Use complex rotation for wrap/periodic.
- **GUI is on Emma's SEPARATE branch** — OUT of this queue. Do NOT re-add GUI items.
- **Substrate purity is non-negotiable**: every op runs on the substrate, NO host readout
  (`.item()`/`float(tensor)`) inside operations.

---

## 1. FV spectral-gap / mixing-rate proof (Lean) — ACTIVE

Extend the formal-verification Lean work with the one named-but-not-yet-mechanised piece: the
**t→∞ mixing RATE** (how fast the gadget's Gibbs chain reaches the already-proven unique
stationary measure). Spec: `planning/sutra-spec/formal-verification.md` §"Still the mathlib step".
Existing base: `fv-lean/mathlib/GibbsMathlib.lean` (detailed balance + stationarity +
`stationary_unique_two_state`). Tractable concrete target = the **2-state clamped-decode chain**,
where the spectral gap is closed-form: the transition matrix has eigenvalues `1` and `λ₂ = 1−p−q`
(`p = P false→true`, `q = P true→false`), so the deviation from stationarity contracts by exactly
`1−p−q` per step and TV distance decays as `|1−p−q|^t`. No heavy spectral theory needed — the same
`linear_combination`/`linarith` machinery as `stationary_unique_two_state`.

Steps (in `fv-lean/mathlib/GibbsMathlib.lean`):
1. **One-step contraction** `two_state_step_contraction`: for a row-stochastic 2-state `P`, a
   stationary `π` (mass 1), and any `μ` (mass 1), `(stepP μ) true − π true = (1−p−q)·(μ true − π true)`.
   This isolates the spectral-gap multiplier `1−p−q` as the second eigenvalue.
2. **Geometric decay** `two_state_geometric_mixing`: iterating the step `t` times gives
   `(stepP^[t] μ) true − π true = (1−p−q)^t · (μ true − π true)` (induction on `t` using step 1).
3. **TV form** `two_state_tv_mixing`: TV(μ_t, π) = `|1−p−q|^t · TV(μ_0, π)` (2-state TV = `|dev|`),
   the explicit mixing-rate / spectral-gap statement.
4. **Instantiate for the Gibbs kernel**: specialise to `gibbsKernel` (p,q from the Boltzmann
   weights) so the gadget chain gets an explicit rate; `#print axioms` (no `sorry`); `lake build`
   green locally; update the FV spec + `paper/formal-verification/paper.md` to cite the mechanised rate.

Build: `fv-lean/mathlib/` is an isolated Lake project (mathlib v4.30.0; `.lake` gitignored, heavy).
CI: `.github/workflows/fv-lean-ci.yml` path-filtered to `fv-lean/**`.

---

## 2. Yantra OS integration — NEXT (do after §1 ships)

Downstream consumer work: wire more of the Sutra substrate into the vendored `external/Yantra/` OS.
Not yet decomposed — pull the concrete first step from `todo.md` § Yantra / the GUI-substrate-surface
pattern when §1 is done, decompose into steps here, then execute. (Division of responsibility +
the substrate-window GUI pattern are in `CLAUDE.md` § "Cross-repo workflow".)

---

## 3. WASM source frontend — LAST (do after §2)

The `WASM/`-subtree source→Sutra path (Phase 3 in `todo.md`). Several sub-parts are CI/clang-blocked
on this clone (need `uv`/`clang`/`wat2wasm`); route those through CI. Decompose from `todo.md`
§"Phase 3 — WASM" + the `WASM/` agenda when §2 is done.

---

## Pointers

- Substrate-leak catalogue: `Audit.md`. Longer-horizon: `todo.md`. Findings: `planning/findings/`.
  Open design questions: `planning/open-questions/`. Devlog: `DEVLOG.md`.
- Transpiler edge cases (low-value, leave-on-WASM-fallback): `planning/wasm-fallback-edge-cases.md`.
- Corpus: `github.com/EmmaLeonhart/sutra-w2c-corpus` (submodule `corpus/`) + HF mirror.
- Yantra (downstream OS): vendored in-tree at `external/Yantra/`.

## Session bracket

- The autonomous loop is the self-timed `ScheduleWakeup` form (not the old three-cron playbook).
