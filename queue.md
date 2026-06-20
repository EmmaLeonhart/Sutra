# Sutra — Work Queue

**This file is a queue, not a state snapshot.** It lists what is being worked on now
and what is next, in execution order — barrel it top to bottom. **Finished work is
REMOVED from this file in the same commit it ships** (history lives in `git log`,
`DEVLOG.md`, and `planning/findings/`). Leaving completed work here as status markers
is the bloat that destroys the queue's job as an ordered execution list (Emma
2026-06-17). `todo.md` is longer-horizon; items migrate `todo.md` → `queue.md` →
deleted on completion.

---

## Context (read first, do not work on)

- **`paper/paper.md` is UNFROZEN** (Emma 2026-06-07) — live revision target. The `paper/neurips/`
  edit-freeze was **RETIRED 2026-06-18** (Emma: "give up on the NeurIPS freeze") — it is now editable
  for factual fixes; the immutable record is git commit `ea6f8a01`. Measured numbers only; no overclaiming.
- **NEVER use `Math.mod`** (worst-implemented; measured vector-collapse/NaN). Use complex
  rotation for wrap/periodic (finding `2026-06-12-rotation-mod-vector-collapse-…`).
- **GUI is on Emma's SEPARATE branch** — OUT of this queue. The Adam-RLHF GUI demo + paper
  stay built on main, but no GUI *agenda* here. Do NOT re-add GUI items.
- **Promise/await is fit-to-spec** (verified; `test_await_substrate_pure.py` 4/4).

---

## Done this session (DRAINED 2026-06-19)

The bounded, locally-actionable work is all done. This session shipped the
OCaml option-payload rework (all five gaps), Elixir/Erlang non-tail + guarded multibase, the
repo-wide doc audit, the Q1–Q5 quantum exploration (incl. Q5 VQE-to-Sutra), the FV paper arXiv pass
(References + em-dash removal + accuracy fixes + Background), the comprehensive substrate audit (REAL
LEAK #11 `js_strict_eq` fix + calc signal-separation gap table + the **direct-RAM rework** + the
dimension-audit warning), the papers' Background sections, and regression guards for every substrate
change. See `DEVLOG.md` for the shas.

Everything still open is **deferred** and lives elsewhere, because it needs a toolchain this clone
lacks, is a longer-horizon big leg, or is lowest-priority:

- **`todo.md` § "Deferred from queue.md cleanup (2026-06-19)"** — the consolidated index of what's
  left, grouped by what unblocks it: CI/toolchain-blocked WASM items (wat2wasm cross-check, ISO-5
  opcodes, pruned-transformer oracle, E3 opcode, hull path — need `uv`/`clang`); F#/Clojure fixtures
  (grammar DLL won't build on this clone); big legs (WASM source frontend, Python via Pyodide, Yantra
  OS integration); blocked/lowest-priority (`await`-in-`recur`, FV spectral-gap proof, irregular
  recursion).
- **`planning/wasm-fallback-edge-cases.md`** — the transpiler edge-case catalogue (Erlang
  list-comprehensions, multi-arg non-tail multibase, F#/Scala breadth, OCaml `Array.make` non-zero
  fill, the Haskell/Rust int-local-in-expression limit). Few cycles each; leave on the WASM fallback
  if not clean.

When a new bounded, actionable task appears (from Emma, or pulled + decomposed from `todo.md`), add it
here as a concrete step and barrel it.

---

## Pointers

- Substrate-leak catalogue: `Audit.md`. Longer-horizon: `todo.md`. Findings: `planning/findings/`.
  Open design questions: `planning/open-questions/`. Devlog: `DEVLOG.md`.
- Corpus: `github.com/EmmaLeonhart/sutra-w2c-corpus` (submodule `corpus/`) + HF mirror.
- Yantra (downstream OS): vendored in-tree at `external/Yantra/`.

## Session bracket

- **End-of-session status report** (reporting only, no commits): what advanced (shas + one-line),
  queue state, blockers, test health. (The autonomous loop is the self-timed `ScheduleWakeup` form
  now, not the old three-cron playbook — Emma 2026-06-19.)
