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

### A. Task #15 — open-question pruning pass  (banners DONE 2026-05-17; pruning is what remains)

The triage itself is fully delivered: spec-level
`planning/sutra-spec/open-questions.md` triaged (parts 1–2,
`411939ba`/`a0244682`); every doc in `planning/open-questions/` now
carries a `> **VERDICT — …**` top banner (21 stamped 2026-05-17 +
binding-kind's existing RESOLVED header + the new cosine doc's own
verdict). Citations spot-verified against the spec (`types.md`,
`control-flow.md` §Loops, `strings.md`, commit `6d25f232`), not
blanket-stamped.

Remaining (deliberate, NOT folded into the banner run to avoid losing
rationale mid-session): the **pruning pass** — for each RESOLVED/STALE
doc, confirm its rationale is captured in the cited spec file, then
delete/archive the doc per `planning/open-questions/README.md` rule 3.
Genuinely-OPEN docs stay. This is the next concrete sub-item, not yet
started.

### B. Verify the shipped transcendentals realize the stored-constants vision  — ✅ DONE (finding written)

Read-only audit of the emitted runtime done; finding at
`planning/findings/2026-05-17-transcendentals-realize-stored-constants-vision.md`.
Answer to the user's anxiety ("did you lie about the crosstalk
tables?"): **No — the cross-talk-exploiting exp + ln lookup tables are
real and on the runtime hot path** (`_lerp` triangular-kernel matmul,
no libm/torch.exp on the hot path; the only torch.exp/log are the
legitimate init-time codebook builds). TAU is bound at a runtime point
(`self.TAU`/`self._TWO_PI`). Independently re-verified from the code,
not trusted from a prior claim. Surfaced one self-correction → item C.


## Structural — deliberate, gated; explicitly NOT a rushed autonomous edit

### D. Audit REAL LEAK #3 only (#4 reclassified NOT-a-leak 2026-05-17)

`Audit.md` is the running substrate-leak catalogue. #1, #2, #5,
#6, #7, #8 resolved+verified. **#4 was reclassified as NOT a leak**
(Emma 2026-05-17): the generic loop runtime is a fixed-T tensor-op
eigenrotation unroll (`_TorchVSA.loop`/`_step`) — no `.item()`, no
`if`/`break` on data; the `for _t in range(max_iters)` is a
structural unroll counter = the spec's substrate loop. Hoisting it
to a straight-line codegen unroll is an optional compile-time
optimization, not a purity fix. No fix owed. See `Audit.md` #4.

Genuinely open, narrow:

- **#3** Promise `await_value` — `for _ in range(100): if
  self.isPending(p) <= 0.5: break`. The `if … break` is a real
  host Python branch on a predicate (unlike #4, which has none).
  Spec wants it as a substrate `while_loop` two-channel halt
  vector (`planning/sutra-spec/promises.md`) — the same branchless
  soft-halt tensor gate `_step` already uses. Fix shape = the
  `21a9ff77` model; deliberate, promise-test-gated. Not yet
  started.

### E. Task #12 tail — `scalar` keyword → `number`, drop the 0-d projection

Conceptually "scalar vs number" is RESOLVED (`b50dc5d0`;
`planning/findings/2026-05-16-scalar-is-not-an-open-question.md`): a
number IS a vector (value on the number axis, zeros elsewhere). The
remaining tail is the mechanical-but-risky migration — rename the
`scalar` keyword to `number`, drop the 0-d projection so
exp/cos/sin return the number-vector — a call-site/test migration
gated on the 135-passed / 103-subtest + smoke suite. Not a safe
rushed autonomous barrel; needs a deliberate gated session.

## Open user decision (destructive / outward — needs an explicit yes)

### F. Delete the now-unused `master` branch?

CI master→main migration is done+pushed (`5ea853ef`/`b318791e`).
The local+remote `master` (`origin/master` @ `cdcdf7ff`) is now
unused. Deleting it is destructive + outward-facing; CLAUDE.md and
this queue require an explicit user yes. Do not delete without one.

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
  via `scripts/build_site.py`; live deploy verified 2026-05-17
  (Pages run for `34009c9e` green; home / `/paper/` / `/neurips-2026/`
  / conceptual pages all serve 200). Aspirational polish in
  `todo.md` → "Docs / website".

## Pointers

- Substrate-leak catalogue: `Audit.md` (work REAL LEAK first).
- Longer-horizon agenda: `todo.md`.
- Findings (dated): `planning/findings/`.
- Open design questions: `planning/open-questions/`.
- 2026-05-17 voice-vision (verbatim):
  `planning/exploratory/2026-05-17-voice-vision-transcendental-constants.md`.
- Devlog (full history): `DEVLOG.md`.
- Yantra: `../Yantra/`.
