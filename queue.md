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

1. Run Yantra's substrate-facing tests against the CURRENT SutraDev compiler (not the installed pin):
   `test_axon_serialise` (most exposed to the axon_add change), `test_calc*`, `test_kernel*`,
   `test_apps_echo`. PYTHONPATH must point at `sdk/sutra-compiler` so Yantra sees this session's
   compiler, not Github\Sutra's.
2. For any regression, root-cause on the substrate and fix (compiler or the Yantra `.su`); the
   committed precompile caches (`.<stem>.compiled-sutra<ver>-<hash>.py`) are keyed on the codegen
   hash, so they regenerate against the new compiler — confirm they do.
3. Once green, pull the next concrete Yantra integration step (runtime ABI / multi-process / axon
   spec alignment) from `todo.md`, decompose here, execute.

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
