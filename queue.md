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

## ACTIVE — barrel top to bottom

_Done legs (numbers-on-substrate + its 2026-06-21 scalar-position fixes, perf/fusion, multi-process, FV
surface + measurement-claim gates, await core, the NeurIPS-frozen-layer removal, the email + paper-Background
work) live in `DEVLOG.md`, `git log`, and `planning/findings/` — not here. Open work below._

### C. Background → a short "Preliminaries" after Related Work (Emma 2026-06-21; metabolised from the data-lake chat)

**Metabolised** from the data-lake chat "Adding background section to paper with prior work" (Emma + Opus 4.8;
metabolised, not committed — the HTML stays in `data_lake/`). The refined direction:
- **A short `Preliminaries` placed AFTER Related Work, before §3** (Consolidation into Canonical Primitives) —
  NOT a sprawling survey, ~a page. It does exactly two things: (a) consolidate the VSA primitive definitions
  (bind/bundle/unbind/similarity) in one clean place (pull up from §3.1/Appendix A so they're stated before
  heavy use); (b) **ground Kleene three-valued logic** — the load-bearing-AND-obscure case: a few sentences on
  Kleene's strong 3-valued system, the truth tables, and the Gödel min/max t-norm framing, so when §3.6
  backprops through AND-of-NOTs the ML-leaning reader has ground under them. Stop there.
- Triage rule: "if I cut this, does a §3/4 derivation become UNFOLLOWABLE? → Preliminaries. Else → Related Work
  or a one-line citation." Depth tracks reader difficulty, not field importance.
- **Anisotropy stays INLINE** (§1/§2.1/§3.7, at point of use), NOT in Preliminaries. **RNN Turing-completeness**
  = the one-line Siegelmann–Sontag cite already in §3.4, not a subsection.
- **Shaw et al. (arXiv 2501.05368v2, "VSAs via Category Theory")** → cite in **Related Work §2.1, NOT
  Preliminaries.** Framing: their §5 / footnote 3 names "a VSA that is purely functional (in the programming
  sense)" as a significant open engineering direction; Sutra is a realization of it, arrived at independently
  (engineering-first). Positioning, not machinery. (Emma: "worth citing but not critical.")
- **Schmidhuber 1990 "Making the World Differentiable"** (FKI-126-90) → LEAVE OUT of paper one (future research:
  RL/planning/world-models, Extropic). Back pocket.

**State / supersedes:** my edit `1f0544db` moved Background to AFTER the Intro but BEFORE Related Work, with VSA +
anisotropy content. That is now SUPERSEDED: move it to AFTER Related Work as `Preliminaries`, swap the anisotropy
framing for the Kleene grounding (keep VSA consolidation), and add the Shaw et al. citation to Related Work.
Substantive paper content + another clawRxiv resubmit. Integrity: measured claims only, no honest/genuinely
buzzwords. (The NeurIPS task that used to be item C.2 is GONE — the frozen paper was removed `2c17ef12`.)

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
