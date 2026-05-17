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

### A. Task #15 — per-doc verdict triage of `planning/open-questions/`  (IN PROGRESS, this run)

Spec-level `planning/sutra-spec/open-questions.md` already triaged
(parts 1–2, commits `411939ba`/`a0244682`). The per-doc directory is
**not**: only 2 of 24 docs carry a verdict banner.

Deliverable: every doc in `planning/open-questions/` gets a one-line
top banner — **RESOLVED** (cite spec/todo.md/finding/commit; reduce
the doc to a pointer if its substance is already in the spec),
**GENUINELY OPEN** (one-sentence precise undecided sub-question + what
would close it), or **STALE** (superseded design — mark for
archive/delete). Honest verdicts only: verify each against the spec,
do not blanket-stamp RESOLVED. One doc per pass, commit the verdicts.

### B. Verify the shipped transcendentals realize the stored-constants vision

From the user's 2026-05-17 voice-vision (verbatim at
`planning/exploratory/2026-05-17-voice-vision-transcendental-constants.md`):
the design is "store three transcendental constants — tau at a runtime
binding point; cross-talk-exploiting log table + exp table as the two
leaves." Read the *emitted* code / runtime and confirm the shipped
transcendentals literally do this (tau bound in the runtime; the two
leaves are genuine cross-talk-exploiting lookup tables, not a
libm/torch elementwise call). Report the honest delta. If it does not
match the vision, that gap is OPEN — do not paper over it.

## Open design question raised this run — needs a user decision

### C. Cosine as its own transcendental function?

`planning/open-questions/cosine-as-its-own-transcendental.md`
(GENUINELY OPEN). The user's 2026-05-17 position — cos as its own
substrate-pure transcendental, with the imaginary part of complex
`cos` built geometrically — contradicts the shipped
`cos = real(cexp(iθ))` boundary. Cannot be silently kept-as-is or
silently implemented; needs a user ruling on which boundary is
canonical. Surfaced, not guessed.

## Structural — deliberate, gated; explicitly NOT a rushed autonomous edit

### D. Audit REAL LEAK #3 + #4

`Audit.md` is the running substrate-leak catalogue. After the
2026-05-15/16 work, #1, #2, #5, #6, #7, #8 are resolved+verified
(see `Audit.md` / git log). Genuinely open, structural, high
regression surface:

- **#3** Promise `await_value` host `for _ in range(100)` → the
  substrate `while_loop` two-channel halt vector
  (`planning/sutra-spec/promises.md`).
- **#4** generic loop runtime `for _t in range(max_iters)` → the
  iteration mechanism `loop`/`while` lower to; spec says
  `state ← R·state` on the substrate. `rotate_slot` (#1) is now
  pure so the eigenrotation primitive exists; replacing the host
  driver loop is a control-flow-lowering rework.

Fix shape = the `21a9ff77` model (tensors in → tensor ops → tensors
out; saturate, don't raise). Do these with the loop-runtime /
promise test suite as the gate, in a deliberate session — not a
rushed autonomous edit, per CLAUDE.md safety rules.

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
