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

### T. Pre-arXiv feedback execution  (2026-05-18; plan written, in progress)

Emma collected pre-arXiv feedback (Discord reviewer maniospas — who
endorsed the paper — + 8 LLM passes) in `paper/feedback before
arXiv/`. Consolidated, de-duplicated, and **verified against live
`paper.md`** into `paper/feedback before arXiv/SYNTHESIS.md` — that
doc is the working plan (P0/P1/P2, repo-constraint cross-checks,
already-decided items not to re-litigate).

P0 DONE + pushed (`3e03a96c`, `494a8e85`): SYNTHESIS.md written;
gitignore for the saved-page blobs; AI-use statement (Emma's
candid wording); ESM-2/Lin et al. + Kingma&Ba refs added (audit
found ESM-2 cited-but-absent; both web-verified); 3 claims
softened; §3.6 in-sample framing sentence; grounded labelled
Limitations subsection; LLM-artifact scan clean; 4 URLs live.

REMAINING:
- Self-overlap vs paper #1: RESOLVED 2026-05-18 — cloned into
  gitignored `comparisons/`, ran `overlap.py`: 0.071% verbatim
  8-gram overlap, 0 strong sentence dups (only a shared biblio
  line). No risk; no rephrasing. SYNTHESIS §1 updated.
- §4.2 restructure: DONE light 2026-05-18 (Emma chose subsection-
  header tagging only — method/experiment tags + roadmap line in
  Consolidation, numbering-neutral, zero cross-ref churn). Full
  split still deferred to next venue.
- clawRxiv submission error: FIXED + VERIFIED GREEN 2026-05-18.
  Two stacked bugs: (1) clawRxiv API changed — script now uses
  POST /api/posts/{id}/revise (create_post/revise_post split) and
  self-heals off the 409 data.duplicateId; (2) papers-ci
  commit-back crashed (exit 128) on the scrapped
  docs/theory-and-paper.md — stale path removed. End-to-end
  green run 26069104957: revise→post 2580, review v62 fetched,
  commit-back pushed (attempt 2, race-resilient), .post_id
  persisted to 2580 on main (HEAD 33add5db). Drift structurally
  resolved — pointer advances + commits back each run.
- P1 DONE 2026-05-18 (`pushed below`): `.su` snippet (verbatim
  role_filler_record encode/decode core) + fuzzy-NN Related-Work
  subsection with 3 web-verified refs (Zadeh 1965, Jang 1993,
  Buckley&Hayashi 1994).
- P1 std + plot: DONE 2026-05-18 (real 5-seed run, seeds 0–4,
  faithful; differentiable_training.py untouched). Measured:
  ep50 95.2±0.1%, ep299 95.3±0.0%, loss 1.154±0.000, knee ep22,
  post-knee s.d. 0.03pp, grad 0.94–4.29 — seed-invariant,
  corroborates single run. Abstract/§3.6/table → n=5 mean±s.d.;
  plain-TikZ figure (real coords, build-safe). Finding:
  `planning/findings/2026-05-18-differentiable-training-multiseed.md`.
  Word-count provenance RESOLVED: paper's "992 distinct" is
  correct (1000 pairs, 992 unique strings, 8 cross-cat dups).
  All pre-arXiv P0+P1 now done; only the deferred §4.2 (Emma:
  next-venue) and optional P2 remain.
- P2: ablation table, typo/precision sweep (nuanced — see
  SYNTHESIS), polynomial-interpolant-rationale paragraph.
SYNTHESIS.md is the canonical plan.

### 0. Implicit tail-recursive loop  (count form SHIPPED 2026-05-17; gated)

`loop(expr){ body }` (Emma's invented implicit-tail-recursion
sugar) now compiles + runs correctly on both backends. Desugars
before codegen into the existing tail-recursive loop-function
machinery: implicit axon = body-mutated vars + bound free vars
(invariant); each captured var's `VarDecl` is flipped to `slot`
(slot routing is transparent in the existing codegen, so this is
correct by construction); a synthesized `iterative_loop`
`LoopFunctionDecl` + `LoopCallStmt` replace the `LoopStmt`.

Shipped + gated + pushed: `loop_capture.py` (capture analysis +
`free_identifiers`), `loop_desugar.py` (the pass), wired into both
`translate_module`s. Gate: 186 passed / 83 subtests + codegen_pytorch
/inliner/transcendentals 38/33 + smoke PASS, zero regression. Full
record: `planning/findings/2026-05-17-implicit-tail-recursive-loop-desugar.md`.
Revert point if needed: tag `v0.5.0` (`84b5ca45`).

Remaining (tracked, NOT faked as done):
- `while_loop` kind: relational bounds (`< > <= >=`) DONE + gated
  both backends 2026-05-17. Equality/negation bounds (`== != !`)
  inherit the pre-existing FUZZY numeric-equality truth-axis
  lowering (out of scope here, documented in `loop_desugar.py` +
  the finding; tracked under equality-and-defuzzification, not a
  desugar bug);
- class-method bodies: ✅ DONE 2026-05-17 (torch verified; numpy
  has a pre-existing deprecated-backend class-instance gap
  unrelated to loops). Synthesized loop fns go top-level before
  the `ClassDecl`; loops touching `this`/fields raise a clear
  `CodegenNotSupported` (no receiver in a top-level fn) — fail-safe;
- scope-shadowing: ✅ ADDRESSED 2026-05-17 — a captured name
  declared more than once now raises a clear `CodegenNotSupported`
  (not lexical-scope-aware yet, so it refuses rather than silently
  flip the wrong decl). param/`var`-inferred captured names also
  raise clearly. All fail-safe, test-verified — never a miscompile;
- **await-as-minimal-instance (#3)**: ✅ DONE 2026-05-17 (both
  backends). `await_value` host poll-loop+branch replaced by the
  exact algebraic reduction of the spec-2 while_loop (no external
  producer ⇒ spin is a no-op ⇒ await ≡ `value(p)`). 0 leak
  signatures; `async_promise_runtime.su` main()=3.0 both backends;
  227 passed + smoke. Finding:
  `planning/findings/2026-05-17-await-substrate-pure.md`.

### A. Task #15 — open-question pruning pass  (banners DONE 2026-05-17; pruning is what remains)

The triage itself is fully delivered: spec-level
`planning/sutra-spec/open-questions.md` triaged (parts 1–2,
`411939ba`/`a0244682`); every doc in `planning/open-questions/` now
carries a `> **VERDICT — …**` top banner (21 stamped 2026-05-17 +
binding-kind's existing RESOLVED header + the new cosine doc's own
verdict). Citations spot-verified against the spec (`types.md`,
`control-flow.md` §Loops, `strings.md`, commit `6d25f232`), not
blanket-stamped.

Pruning — bounded safe slice DONE 2026-05-17: the 2 unambiguously
STALE-superseded dossiers archived (renamed `_archived-`, rationale
preserved, NOT deleted) — `loop-surface-redesign.md`,
`tier2-bundle-substrate-vs-algebra.md`. RESOLVED dossiers
intentionally LEFT (already VERDICT-bannered/self-describing;
aggressive deletion is the rationale-loss call the README reserves
as deliberate — not done). Task #15 effectively closed; any further
RESOLVED-doc deletion is a deliberate Emma call, not queued work.

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

### D. Audit REAL LEAK — all resolved (no open structural leak)

`Audit.md` is the running substrate-leak catalogue. As of
2026-05-17 **no REAL LEAK is open**: #1, #2, #5, #6, #7, #8
resolved+verified earlier; **#4 reclassified NOT-a-leak** (fixed-T
tensor-op tail-recursive cell, no host branch on data — see
`Audit.md` #4); **#3 FIXED** (await_value reduced to the exact
spec-2 `value(p)`, both backends, 0 leak signatures, semantics
preserved — `Audit.md` #3 +
`planning/findings/2026-05-17-await-substrate-pure.md`). Remaining
Audit content is observations/borderline notes, not open leaks.
One recorded non-#3 observation: `Promise.is*` predicate
accessors still return host floats (their own
predicate-accessor-boundary question; not on the await path).

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
