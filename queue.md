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

## ▶ RESTART NOTICE — 2026-05-20

This session's predecessor crashed when the computer restarted around 16:00 local on 2026-05-20. Four parallel agentic sessions died at the same time; the local cron jobs they had scheduled (in-memory, not `durable: true`) died with them. Nothing on disk was lost — only chat context and in-memory schedules.

**Prior session transcript:** `crashed_session_2026-05-20.md` at this repo's root (extracted from saved HTML; corresponds to claude.ai session `01UxpPZzWGGUxPuCJFY9v6WH`). The cross-repo context is at `C:\Users\Immanuelle\Documents\Github\SESSION_RESTART_2026-05-20.md`.

**📋 The `chat archive` block(s) below this notice are LOAD-BEARING — read them, do not delete.** Emma manually pasted excerpts of the pre-crash session conversation directly into this `queue.md` to capture execution detail past where the auto-extract truncated. This is the *intended pattern* for recovering from session-crash context loss: paste the relevant chat into the queue so the next session has it inline rather than chasing auth-gated session URLs. The bullet summary in this notice is a navigation aid; the archive below is the substance. Leave the archive in place until the recovery is visibly complete (queue items reconciled, next steps executed); then it can be deleted alongside this notice.

**Where the session actually left off** (per the in-line archive the user pasted below, which goes further than the auto-extract):
1. Discovered Audit REAL LEAK #3 (`await_value`) was *already fixed* 2026-05-17 (4/4 substrate-pure tests green). Created the watchdog + local hourly cron `e133262d` (at :23) to keep verifying; `durable: true` wasn't being honored.
2. Then **JSO ordered comparisons shipped + pushed (`ef93db36`)**: `js_lt`/`js_gt`/`js_le`/`js_ge` with full ECMAScript Abstract Relational Comparison semantics (both-string → lex; otherwise numeric on AXIS_REAL; NaN → false on all four). Numeric + string-lex paths green; full test suite green. Side-effect fix: `_as_any_vector(str)` now routes through `make_string` instead of `embed`, closing a latent bug in `js_add`/`js_loose_eq`/`js_typeof`/`js_truthy` for string operands.
3. **Egglog CSE pass** was queued as the next barrel item (item 0 in queue.md) with a detailed 5-step plan (cost model + `find_repeated_subexprs` + `cse_let_form` + tests + commit). Session had just finished reading `simplify_egglog.py` when it stopped.
4. **Dead cron:** `9297ce13` one-shot fires 2026-05-20 ~14:26 Vancouver (~1 hr after session end) — pull main, read queue.md item 0, execute the CSE plan, commit + push, remove item 0. Session-only; died with the crash.

**Resume by:** **(0) Clear the bloated queue first — see warning below.** (1) Verify the JSO push `ef93db36` is on `origin/main`; (2) execute the egglog CSE plan that's queued as item 0 (or re-create cron `9297ce13` with `durable: true`); (3) confirm the watchdog + hourly cron are restored; (4) create the requested remote 24h audit routine via the `schedule` skill if not yet done. Skip Item 1 (0-d projection drop, deliberate gated) and any "Audit REAL LEAK #3 / promise await" item still here (already fixed — delete it).

**⚠ Clear the bloated queue before adding new work.** Both `queue.md` and `todo.md` accumulated items across many sessions and the crash didn't reconcile them against `git log`. Walk every item below against `git log --since="2026-05-19"` and **delete** anything already shipped (per CLAUDE.md: queue is delete-only — no checkmarks, no "done" markers, no progress narration). Items the prior session itself flagged as already-fixed are top candidates. This is the FIRST step, before any new execution.

If a queued item calls for a cron job, re-create it locally and immediately per the new CLAUDE.md §"Cron requests" rule (pinned 2026-05-20). Prefer `durable: true`.

Delete this notice and `crashed_session_2026-05-20.md` once the queue has visibly resumed.

chat archive

Are you able to barrel through any more right now?

Honest answer: the safe, queue-defined barrel work is done. What's left needs your direction on scope. Let me check one thing — whether there are any stale open-questions I can close fast.


Read a file, used a tool
Not safely. Here's the honest state:

Genuinely barrel-able only with your call on scope:

0-d projection drop on exp/cos/sin (queue item, end of Active). I traced it earlier — not the "mechanical migration" the spec finding hoped for; rotate_slot/defuzzify_trit/atan2 all consume scalars and would need ._re() extractions, plus the transcendentals tests compare to Python floats. Risky enough that you explicitly moved it to the end.
Slot codegen integration (todo.md, ~200 lines). Surface syntax slot TYPE name = expr; parses but codegen rejects with SUT0150. Would close the imperative-reversible-via-slots story. No paper risk; paper doesn't cite slots.
JSO ordered-comparison operators (todo.md, OS-blockers). </>/<=/>= with JS coercion rules (lexical for strings, numeric otherwise). Mechanical, JS-spec-driven, no paper risk.
Egglog CSE pass (todo.md, sub-200 lines). Adjust the cost model in simplify_egglog.py to charge per-use; emit Python let-bindings for repeated subexpressions.
Gated:

All paper/paper.md polish — frozen through May (lifts 2026-06-01).
Master branch delete — needs explicit yes.
Already-done verification:

The hourly cron + daily cloud routine handle substrate-purity + spec-drift checks; me running the watchdog manually here is the same work twice.
The other todo.md sections (first-class functions, ontology / class fields, learned-matrix binding, Sutra-NumPy, MCP-exposed docs, etc.) are multi-session items that need your design judgment, not barrel material.

If you want me to keep going: which of the four barrel candidates above? Or point me at something else.

Yeah can you please do the GSO ordered comparison operators? Can you please do the GSO? Barrel through the GSO ordered comparison operators and barrel through the egg log CSE pass.


Used 4 tools
Start by reading the existing JSO operators to mirror the pattern.


Searched code, read 2 files
Now let me check where the TS transpiler emits comparison operators.


Searched code, read a file
Now I have enough to write the JSO ordered comparisons. Let me also check the _as_any_vector helper and string_length.


Searched code, read a file
Now I have enough context. Let me add the four ordered comparisons right after js_loose_neq:

Edited
codegen_pytorch.py
+118
-0
Now update the stdlib JSO class declaration to declare the new intrinsics, and the TS lower.py to emit them on </>/<=/>= when JSO is involved.

Edited
javascript_object.su
+10
-0
Now the TS lower — </>/<=/>= should dispatch to JavaScriptObject.js_* when JSO is involved.

Edited
lower.py
+16
-0
Let me verify the JSO change compiles + run the existing tests before moving to egglog.


Ran 2 commands
String lex comparisons return -1 instead of +1. Need to trace wrap("apple") — likely doesn't preserve string flag.


Read a file, ran 3 commands, searched code
The _as_any_vector is used only by js_* and eq_synthetic/neq_synthetic — none want a semantic embedding for a string. Routing strings through make_string fixes my new methods AND latent string-flag bugs in js_add/js_loose_eq/js_typeof/js_truthy.


Edited a file, ran a command
All four string-lex paths green. Now run the full existing test suite to confirm I haven't regressed anything.

Ran
Run full test suite
Tests running in background. Let me start on the egglog CSE while waiting.


Read 4 files, ran 2 commands
64 passed. Let me also hit the corpus + smoke + simplify tests, then move to CSE.

Ran
Run corpus + simplify tests
Let me check the corpus tests result before continuing.


Read 2 files, ran 4 commands, searched code
Stopping. Committing the JSO work, updating queue.md with the CSE handoff, and scheduling a cron to pick it up in 1 hour.


Ran 4 commands, edited a file, used 3 tools
Pushed (ef93db36). Now the 1-hour cron.


Used 2 tools
Done. Stopping here as requested.

Shipped this session, pushed:

ef93db36 — JSO ordered comparisons (js_lt/js_gt/js_le/js_ge) with full ECMAScript Abstract Relational Comparison semantics. Both-string → lex compare; otherwise numeric on AXIS_REAL; NaN → false on all four. Tested numeric + string-lex paths green; full test suite green. Side effect fix: _as_any_vector(str) now routes through make_string instead of embed, which closed a latent bug in js_add/js_loose_eq/js_typeof/js_truthy for string operands.
Handed off via queue.md:

Egglog CSE is now item 0 in queue.md with a detailed 5-step pragmatic plan (cost model + find_repeated_subexprs + cse_let_form + tests + commit). I had just finished reading simplify_egglog.py when usage got tight.
Crons:

9297ce13 — one-shot, fires 2026-05-20 ~14:26 Vancouver (~1 hr from now). Pulls main, reads queue.md item 0, executes the CSE plan, commits + pushes, removes item 0.
e133262d — hourly promise/await fit-to-spec watchdog (already running, silent no-op on clean).
Caveat: the harness shows both as [session-only] despite durable: true — they die if Claude exits. The daily cloud routine (trig_01XwkdFuy5meCt8nreBSJDSJ, 09:13 UTC) survives session shutdown and runs the broader spec audit; the CSE-pickup one-shot is local-only. If Claude exits before 14:26, the CSE work just sits in queue.md item 0 ready for your next session.

---

## Context (read first, do not work on)

**`paper/paper.md` is on arXiv and FROZEN through May 2026** (lock
added 2026-05-20). `paper/paper.md` was restored to commit
`e7cca673` (the arXiv-fitting abstract trim, 2026-05-19) so the
repo state matches what was uploaded. The lock lifts automatically
on **2026-06-01** and the live paper resumes being the
free-to-evolve next-venue draft. **Do not edit `paper/paper.md`
through May 31.** See CLAUDE.md §"🔒 `paper/paper.md` is also
FROZEN through May 2026" for the full rule. `paper/neurips/` stays
under its own separate, permanent freeze. See `DEVLOG.md` 2026-05-20
entry.

**Promise/await is fit-to-spec (verified 2026-05-20).** Audit REAL
LEAK #3 was already fixed 2026-05-17 — `await_value(p)` returns
`self.value(p)`, the exact algebraic reduction of the spec-2
`while_loop` lowering for the no-external-producer runtime, per
`planning/sutra-spec/promises.md` Stage 2 + `axon-io.md` (input slot
starts as zero-vector; `arrived = norm(slot) > eps`; halt channels
set by `resolve`/`reject` at construction in the current synchronous
runtime). `tests/test_await_substrate_pure.py` 4/4 green. The
Yantra-side extension (real `while_loop` gating on
`norm(slot) > eps` once an external axon producer wires in) is the
future hook, deliberately NOT mocked as a no-op loop. An hourly
local cron and a daily remote audit guard this against regression —
see §"Watchdogs" below.

## Active

### 0. Egglog CSE pass — IN PROGRESS, picked up by 1-hour cron 2026-05-20

**State at handoff (2026-05-20, mid-session):** JSO ordered
comparisons (`js_lt`/`js_gt`/`js_le`/`js_ge`) shipped + tested 4/4
on numeric and string lex paths. Egglog CSE is the next item; I had
just started reading `simplify_egglog.py` when usage ran low.

**Spec (from todo.md §"Egglog — CSE pass"):**
- Adjust `matrix_chain_cost_model` (or add a new
  `cse_aware_cost_model`) in `sdk/sutra-compiler/sutra_compiler/simplify_egglog.py`
  to charge per-use rather than per-node.
- Emit Python `let`-bindings (a temporary variable) for any
  subexpression that appears more than once in the extracted form,
  instead of inlining.
- Sub-200 lines total. Adjacent prior art: JuliaSymbolics hash
  consing reports 3.2× speedup + 5× faster codegen.

**Pragmatic approach for the cron-driven session:**
The current `simplify_egglog.simplify_ast_vec` / `simplify_ast_num`
operate on single expressions. Real CSE needs scope (a statement
context to insert let bindings). Recommended scope for the cron run:
1. Add `cse_aware_cost_model(egraph, expr, children_costs)` next
   to `matrix_chain_cost_model`. Either delegates to it or adds an
   explicit per-use multiplier (egglog's tree extraction already
   counts each occurrence, so the cost is effectively per-use; the
   new name makes the intent explicit and lets future tuning live
   in one place).
2. Add `find_repeated_subexprs(extracted, min_size=15)` — walk the
   extracted egglog expression's str() form, identify substrings
   matching balanced parens that appear ≥ 2 times. Return list of
   `(substring, count)` sorted by length desc.
3. Add `cse_let_form(extracted)` — returns `(bindings, body_str)`.
   bindings is `[(temp_name, sub_str), ...]`; body_str is the
   extracted str with each repeated sub_str replaced by its
   temp_name. The codegen integration is deferred — surface the
   primitive + tests, then wire when there's a concrete demo.
4. Add `tests/test_simplify_egglog_cse.py` — at least one test
   showing `find_repeated_subexprs` finds shared bind expressions,
   one showing `cse_let_form` produces sane bindings.
5. Run `python -m pytest tests/test_simplify_egglog.py tests/test_simplify_egglog_cse.py -v` to verify; commit + push.

**Files involved:**
- `sdk/sutra-compiler/sutra_compiler/simplify_egglog.py` (main work)
- `sdk/sutra-compiler/tests/test_simplify_egglog_cse.py` (new)

**Do NOT touch in this session:** paper.md (May freeze through June 1).

**After CSE lands** (or if blocked), the cron should mark item 0
DONE / BLOCKED in queue.md and stop. Do not chain into the 0-d
projection drop — Emma moved that explicitly to the bottom.

### 1. `loop while_loop` equality / negation bounds  (out-of-scope, tracked)

`==`, `!=`, `!` bounds inherit the pre-existing FUZZY numeric-equality
truth-axis lowering. Documented in `loop_desugar.py` + the
2026-05-17 finding. Tracked under
equality-and-defuzzification, not a desugar bug — surfaces here so
it does not get lost.

### 2. Drop the 0-d projection on `exp`/`cos`/`sin`  (deferred to end of Active per Emma 2026-05-20)

User-authorized `scalar` → `number` rename shipped 2026-05-17
(`8a5d12a7`, `b34a275b`, `f21fdffa`). The remaining, separate,
**riskier** half is dropping the 0-d projection so `exp`/`cos`/`sin`
return the full number-vector instead of a 0-d tensor. Changes
observable return shape; could regress paper-cited `cos`/`sin`/`exp`
(NeurIPS-frozen paper's examples must keep producing the same
outputs — CLAUDE.md §"Paper-code durability"). Needs its own
deliberate, test-gated session, not bundled with adjacent work. Moved
to the end of Active 2026-05-20 per Emma.

## Watchdogs (verification, not new work)

- **Hourly local cron** (`CronCreate`, durable so it survives
  session restart): every hour, runs
  `tests/test_await_substrate_pure.py` + greps `codegen_pytorch.py`
  for the leak signatures `for _ in range(100)` and `if self.isPending`
  inside `await_value`. If anything regresses, reopens an entry here
  + commits + pushes.
- **Daily remote routine** (claude.ai cloud, 24h): full spec-audit
  pass — walks `planning/sutra-spec/*.md` against the runtime, reports
  drift, commits findings. Set up via `RemoteTrigger`; the routine
  survives session shutdown because it runs in the cloud.

## Next-venue polish (FROZEN through May 2026; resumes 2026-06-01)

All paper polish items below touch `paper/paper.md` and are
**blocked by the May-2026 freeze** above. Listed here so they
don't get forgotten; do not start any of them until June.

- **Ablation table.** Per-primitive contribution to the §3.6 result.
- **Polynomial-interpolant-rationale paragraph.** Why Lagrange on
  $\{-1, 0, +1\}$ over softer alternatives. (Drafted + pushed
  2026-05-20 in commit `41fa446b`, reverted 2026-05-20 when the
  May freeze landed; the prose is in `git show 41fa446b -- paper/paper.md`
  when the freeze lifts.)
- **Le Chat's section-granular AI-use breakdown.** Tie each AI
  contribution to a specific §. Heavier than the round-4 additive
  sentence; the existing §"AI-use statement" covers the
  moderator-risk surface.
- **Optional Futamura 1971 bib entry.** Currently named-concept-only
  alongside JAX/TVM/XLA (no bib entry for any of them) — consistent
  authorial choice. Adding Futamura would create inconsistency
  unless JAX/TVM/XLA also get entries; left to Emma's call.

## Open user decision (destructive / outward — needs explicit yes)

### 3. Delete the now-unused `master` branch?

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

- Substrate-leak catalogue: `Audit.md`.
- Longer-horizon agenda: `todo.md`.
- Findings (dated): `planning/findings/`.
- Open design questions: `planning/open-questions/`.
- 2026-05-17 voice-vision (verbatim):
  `planning/exploratory/2026-05-17-voice-vision-transcendental-constants.md`.
- Devlog (full history): `DEVLOG.md` (2026-05-20 entry covers
  May 6 → arXiv upload).
- Yantra: `../Yantra/`.
