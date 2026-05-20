# Sutra — Work Queue

**This file is a queue, not a state snapshot.** It lists what is
being worked on right now and what is next. Finished work lives in
`git log` and `planning/findings/`; longer-horizon work lives in
`todo.md`. If you find yourself writing "✅ DONE / ANSWERED /
Recently shipped" status here, it belongs in git log or a finding,
not in this file — that is the CRUD this queue is not for.

See CLAUDE.md §"Workflow Rules" for how queue.md and the task tool
stay in sync.

---

## Active

### 1. Drop the 0-d projection on `exp`/`cos`/`sin`  (deferred, needs gated session)

User-authorized `scalar` → `number` rename shipped 2026-05-17
(`8a5d12a7`, `b34a275b`, `f21fdffa`). The remaining, separate,
**riskier** half is dropping the 0-d projection so `exp`/`cos`/`sin`
return the full number-vector instead of a 0-d tensor. Changes
observable return shape; could regress paper-cited `cos`/`sin`/`exp`
(NeurIPS-frozen paper's examples must keep producing the same
outputs — CLAUDE.md §"Paper-code durability"). Needs its own
deliberate, test-gated session, not bundled with adjacent work.

### 2. `loop while_loop` equality / negation bounds  (out-of-scope, tracked)

`==`, `!=`, `!` bounds inherit the pre-existing FUZZY numeric-equality
truth-axis lowering. Documented in `loop_desugar.py` + the
2026-05-17 finding. Tracked under
equality-and-defuzzification, not a desugar bug — surfaces here so
it does not get lost.

### 3. Pre-arXiv P2 polish  (optional, next-venue)

From `paper/feedback before arXiv/SYNTHESIS.md` ROUND-4 canonical
plan: ablation table; abstract simplify; polynomial-interpolant-
rationale paragraph; Le Chat's section-granular AI-use breakdown;
arXiv submit-metadata comments-field note (submit-time, not a paper
edit). All optional, all next-venue. Frozen `paper/neurips/`
untouched.

## Open user decision (destructive / outward — needs explicit yes)

### 4. Delete the now-unused `master` branch?

CI `master`→`main` migration is done + pushed (`5ea853ef`,
`b318791e`). The local + remote `master` (`origin/master` @
`cdcdf7ff`) is now unused. Deleting it is destructive +
outward-facing; CLAUDE.md and this queue require an explicit user
yes. Do not delete without one.

## Parked

- C → Sutra transpiler skeleton (`sdk/sutra-from-c/`): parked
  2026-05-08, stays in tree, do not delete.
- Yantra (the OS) is downstream of the TS transpiler; its own repo
  (`../Yantra/`) with its own queue. Sutra's queue ends at the
  transpiler.
- Promises Stage-3 closure capture, container method dispatch,
  multi-statement try/catch: longer-horizon, in `todo.md`.
- TS transpiler closeout (module imports, multi-program axon):
  substantive pieces shipped; remaining polish in `todo.md`.
- Website visual remake (LONG-TERM, website-only — never touches the
  language/math/substrate). Site is now two+conceptual static pages
  via `scripts/build_site.py`. Aspirational polish in `todo.md`
  → "Docs / website".

## Pointers

- Substrate-leak catalogue: `Audit.md` (work REAL LEAK first).
- Longer-horizon agenda: `todo.md`.
- Findings (dated): `planning/findings/`.
- Open design questions: `planning/open-questions/`.
- 2026-05-17 voice-vision (verbatim):
  `planning/exploratory/2026-05-17-voice-vision-transcendental-constants.md`.
- Devlog (full history): `DEVLOG.md`.
- Yantra: `../Yantra/`.
