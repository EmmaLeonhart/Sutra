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

### 0. Implicit tail-recursive loop + await-as-minimal-instance  (IN PROGRESS — Emma "barrel through" 2026-05-17)

Emma's consolidated model: `async`/`promise`/`await` is **just a
loop with a bare-minimal implicit axon** — one input slot that can
be mutated, plus a flag. So the implicit-loop desugar and the #3
await fix are **ONE build**, await being the degenerate (1-slot +
flag) instance.

Concrete plan (gated, units committed; queue is the live truth):

1. **Parser/AST**: confirm the node `loop(expr){body}` produces
   today (it parses, codegen rejects). No surface change — revive
   semantics, not syntax.
2. **Variable-capture analysis**: collect the recurrent state =
   vars the body assigns/mutates (+ outer vars it references that
   must thread). That set + the loop control (`expr`/bound) IS the
   implicit axon. (1b follow-on: minimize it to mutated-only.)
3. **Desugar**: instead of `raise CodegenNotSupported`, synthesize
   the existing **working** tail-recursive loop-function form with
   that state, and emit its call + write-back. Compile-time unroll
   stays preferred when the bound is a literal.
4. **Gate (must be green, no fakery):** `test_branchless_loop` +
   `test_loop_function_decl` + `test_codegen` + `test_parser` +
   corpus + smoke, plus a NEW end-to-end test: single-var loop,
   the multi-var `n1/n2` example returns correct values, literal
   bound still unrolls.
5. **await as the minimal instance (#3):** once 1–4 are green,
   re-lower `await_value` as a 1-slot implicit axon + arrival flag
   = soft-halt, deleting the host `if self.isPending(p)<=0.5:
   break`. Conform to `planning/sutra-spec/promises.md` + the
   formal async/promise spec. Gate: promise fixtures + smoke.

Deliberate, high-blast-radius (whole control-flow surface). Each
unit committed+pushed; queue.md updated same commit so an
interrupt loses nothing.

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

### E. `scalar` → `number` rename — ✅ DONE 2026-05-17 (3 commits, gated)

User-authorized 2026-05-17. `number` is now the canonical type
everywhere user-facing; `scalar` is a deprecated parse alias kept
only for the frozen NeurIPS archive. Shipped in 3 gated commits:
`8a5d12a7` (compiler: number first-class, scalar alias + equivalence
test), `b34a275b` (stdlib .su dogfood, 57 type tokens), `f21fdffa`
(docs + canonical-vs-alias note). Concept/0-d prose deliberately
kept as "scalar" (it's the correct word there — the user's own
distinction). Existing `scalar` programs + frozen examples remain
valid (alias regression-guarded).

**Remaining, SEPARATE, NOT done (deliberately not bundled):** drop
the 0-d projection so `exp`/`cos`/`sin` return the number-vector
instead of a 0-d tensor. This is the riskier half — it changes
observable return shape and could regress paper-cited `cos`/`sin`/
`exp`. Tracked here, not faked as done. Needs its own deliberate,
test-gated session with explicit attention to paper-code
durability. (Conceptual basis already RESOLVED: `b50dc5d0` /
`planning/findings/2026-05-16-scalar-is-not-an-open-question.md`.)

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
