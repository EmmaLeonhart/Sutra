# Sutra — Work Queue

**This file is a queue, not a state snapshot.** It lists what is being worked on now and
what is next, in execution order — barrel it top to bottom. **Finished work is REMOVED in the
same commit it ships** (history lives in `git log`, `DEVLOG.md`, `planning/findings/`).
`todo.md` is the longer-horizon backlog; items migrate `todo.md` → here → deleted on completion.

**⭐ CLEARING the queue is the SAFE default (Emma 2026-06-21).** When an item is done, DELETE the
line — **version control + `DEVLOG.md` already hold the entire history, so nothing is ever lost by
removing it.** Deleting a finished item is NEVER the risky move; the git log is the safety net.
The UNSAFE thing is letting done work accumulate — a "Recently shipped" pointer block,
`~~struck-through~~` lines, "DONE"/"✓" markers, or a paragraph summarizing what shipped. That bloat
buries the open work and is exactly what keeps re-growing this file. The queue holds ONLY
not-yet-done work; the moment something ships, it leaves. **Do not defer work to a clock time either**
— if nothing else is in flight, just do it now (no "do this at 2pm" scheduling).

**Owned + autonomous (Emma 2026-06-20):** the agent organises this queue itself — pulls items from
`todo.md`/findings/specs, orders by value, decomposes into concrete steps, prunes done work, and
executes top-to-bottom WITHOUT asking. Report via commits + DEVLOG, not questions.

---

## Stuff to  do in session

Okay, so the queue is extremely bloated, and I'm not sure what stuff there actually is in it. I think the reason, but this is important. What I'm saying here actually is the priority.

Just to be clear, the queue is a mess. It's extremely bloated. It has turned into a narrative and lost a phase. We moved into in Devlog. Whatever it is that is currently being done in the session is a thing that should be at the front of the queue. Stuff that's already finished or whatever should be put in the Devlog.

I don't know what's going on with the formal verification paper, but it should be put at the end of the queue, at the end of the real queue, so it's the last thing that's executed. We're going to be working on stuff that we're going to be trying to get the Linux command line environment working with a completely neural computer. This goes at the end of the queue because it's supposed to happen after the other stuff that we're doing, and this intervention that I'm adding to the queue is supposed to be taken as an intervention for the active session. 

I think fv paper is finished but not sure

decompose this to neural inplementation of all the big unix utikities in order of difficulty

if one is too hard or requires prerequidites you gotta make them

prerequisites or issues are signal that we need a thing

and to be clear this means running with ram and disk NTM style no rnn entire filesystem

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
- **Version: 0.9.2** (on PyPI; `pyproject.toml` + `__init__.py` match — verified by a fresh-venv
  `pip install "sutra-dev[runtime,embed]"` 2026-07-04). Publish via `sutra-dev-vX.Y.Z` tags
  (trusted-publisher → PyPI `sutra-dev`). **v1.0.0 is deferred** until codegen/stdlib go a stretch
  with NO source-breaking changes (Emma's call). No hard blocker; a source-compat-stability commitment.

## ⭐ FV PAPER — narrow + probabilistic spine (Emma 2026-06-27): frame + remaining legs

**Frame (binding):** the FV paper verifies **Sutra-the-language as an ISA on a *probabilistic*
substrate** — keep it NARROW (per-contract, non-learned trusted base); do NOT re-grow "verify the
whole neuro-symbolic system". Recurring project failure mode = overambition.

**Shipped 2026-06-27 → 2026-07-04** (full history: `DEVLOG.md` + `git log`; clawRxiv reached
**Accept** 2026-07-01): trim pass; Z-transform loop-convergence criterion (measured); continuous-time
sampler-convergence measurement (γ=0.0397, 8-state); `GibbsMultiState` foundation; spectral capstone;
Z-transform unification; mean-zero composition + 2-state discharged instance; convergence-to-
stationarity limit; Dirichlet bridge; Poincaré⇒decay engine; conductance blocks + uniform- and
general-π Poincaré; lazy-uniform n-state instance; and the concrete 8-state AND-gadget heat-bath
instance (`GibbsGadget.lean`, κ=1/16 exact — the exp(−βE) factors cancel in the per-edge ratio).

**REMAINING (after 2026-07-04: (a2) landed; Langevin SCOPED OUT per Emma's thrml reframe —
the substrate object is the discrete block-Gibbs chain, finding
`planning/findings/2026-07-04-langevin-lean-scoping.md`; the continuous-TIME master-ODE decay
landed same day, `GibbsFlow.lean` CI-green):**
1. *(named, NOT green-lit — do not start without Emma):* a Lean gap **value** for the literal
   **single-spin-flip** kernel/generator needs the canonical-paths comparison method (a per-edge
   conductance bound cannot see zeros between non-neighbours); until built, the measured γ=0.0397
   stays a measurement. See DEVLOG 2026-07-04.

**Guardrails:** nothing is proven until `lean` accepts it (no `sorryAx`); every
`paper/formal-verification/paper.md` push triggers the clawRxiv resubmit CI (intended). Mathlib-layer
work is verified via the `fv-lean-mathlib-ci` Linux job (local Windows builds hit MAX_PATH; remote
containers cannot reach the toolchain/cache hosts — iterate via branch pushes).

---

## ACTIVE — barrel top to bottom

### 🔍 Daily substrate-honesty audit — 2026-07-06

Auto-prepended by .github/workflows/daily-audit.yml. The next autonomous-loop session should, as its first action: review every commit landed since the previous daily audit against CLAUDE.md § "Subtler substrate breaches — measurement-required": (a) for each commit touching a .su or its compile path, verify runtime_dim matches what the .su actually needs (count basis_vector calls; no basis_vector → tiny dim); (b) for any commit that frames work as "recurrent" / "RNN" / "substrate-pure" / "verified", verify the claim against measurement, not against earlier session framing; (c) for any commit shipping a substrate classifier or decision function, verify the measured gap = min(positive_class) - max(negative_class) is in the commit or planning doc. If anything is amiss, write a finding under planning/findings/ and a fix item under queue.md BEFORE doing other queue work. Then delete this item.

### 🔍 Daily substrate-honesty audit — 2026-07-05

Auto-prepended by .github/workflows/daily-audit.yml. The next autonomous-loop session should, as its first action: review every commit landed since the previous daily audit against CLAUDE.md § "Subtler substrate breaches — measurement-required": (a) for each commit touching a .su or its compile path, verify runtime_dim matches what the .su actually needs (count basis_vector calls; no basis_vector → tiny dim); (b) for any commit that frames work as "recurrent" / "RNN" / "substrate-pure" / "verified", verify the claim against measurement, not against earlier session framing; (c) for any commit shipping a substrate classifier or decision function, verify the measured gap = min(positive_class) - max(negative_class) is in the commit or planning doc. If anything is amiss, write a finding under planning/findings/ and a fix item under queue.md BEFORE doing other queue work. Then delete this item.

### ⭐ v0.2 symbol table / name resolution (H1) — GREEN-LIT by Emma 2026-07-06

Emma green-lit the deferred v0.2 name-resolution milestone — the proper fix that unblocks BOTH
the REPL bare-string crash AND the opaque `similarity("cat","dog")` error (same root cause: no
symbol table). Finding: `planning/findings/2026-06-24-h1-name-resolution-is-deferred-v0.2.md`.
Barrel the rungs top to bottom; each is bounded and verified against the valid corpus. **The bar
is ZERO false positives** — the v0.1 validator is deliberately lenient and a naive diagnostic
warns on existing valid code (`03_methods.su` references `Animal`/`Cat` declared in no file), so
every diagnostic rung must scan `examples/*.su` ∪ `tests/corpus/valid/*.su` and fire on none.

**Rung 1 SHIPPED 2026-07-06** — `sutra_compiler/symbol_table.py` + `tests/test_symbol_table.py`
(6 tests, PASS): the file-scope collector (user classes + members, top-level functions + methods
+ arity), pure, no diagnostics, nothing imports it yet. Foundation for the rest.

1. **Local-scope tracking.** Extend the table with a scope stack: function/method params,
   `var`/`const` bindings, and first-class function-valued locals (the arrow-fn `f`/`scale`
   case — a local holding a function is legitimately callable, so the unknown-function diagnostic
   must not fire on it). Tests over the arrow-function examples.
2. **Stdlib + builtins resolution.** Fold in `BUILTINS`, intrinsic names, stdlib function names,
   and `stdlib_class_parents()` so `is_known_*` become diagnostic-grade. Add the measured
   primitive-type gaps `float` + `function` to the type allowlist ONLY after confirming they
   appear as type annotations in the valid corpus (measure first — CLAUDE.md canonical-`number`
   rule; `float` may be an alias to reject, not add).
3. **Cross-file / external-type handling.** Resolve or scope so intentionally-open corpus files
   (`03_methods.su`) stay clean. Gate: full valid-corpus scan = 0 false positives.
4. **Unknown-TYPE diagnostic** (new SUT02xx, warning) using rungs 1–3. Verify 0 corpus false positives.
5. **Unknown-FUNCTION diagnostic** (warning, incl. the `argmaxcosine` typo case) using the
   local-scope table for first-class functions. Verify 0 corpus false positives.
6. **Arity checking** on calls to known functions/methods.
7. **REPL return-type inference** (supersedes round-12 item 1): pick `__eval__`'s return type from
   the expression's type via the symbol table, fixing the bare-string REPL crash properly; needs
   the codepoint→text display path in `planning/findings/2026-07-04-repl-first-run-newcomer.md`.
8. **Precise wrong-arg-type diagnostic for `similarity("cat","dog")`** (supersedes round-12 item 2);
   fold in the Python-builtin escape-hatch call (`planning/findings/2026-07-04-python-builtin-fallthrough.md`).

---

**Theme (Emma 2026-06-22/23): USABILITY.** Make Sutra easy for an outside person to install, run,
and learn. The backlog elsewhere is all substrate-correctness; none of it is usability. The
in-process-embedding change (drop the Ollama daemon) shipped 2026-06-22. Barrel these top to bottom;
delete each on completion + append to `DEVLOG.md` in the same commit.

**Usability audit CONVERGED across Batches 1–11 (2026-07-01).** All shippable bounded items
drained; per the delete-on-done rule the batch records are cleared from this file — full history in
`DEVLOG.md` + `git log` (queue.md's own history holds the batch text). Re-run the PINNED TAIL audit
next session to refill if usability re-opens.

### Usability audit round 12 (2026-07-04, pip-only onboarding) — remaining atomised items

Round-12 evidence so far (fresh venv, PyPI 0.9.2): install clean; website `docs/index.md`
quickstart verbatim-works (1.5s to "hello world"); the semantic hello runs correctly; the
missing-semicolon diagnostic is precise (`SUT0100` with file:line:col). Fixed in this round:
README fast-path referenced a repo path a pip-only user lacks (now inline-hello, matching the
website); queue version note was stale (0.9.1 → 0.9.2). Remaining bounded items, in order:

1. **Bare string literal crashes the REPL — ROOT CAUSE FOUND 2026-07-04
   (needs a design call, not a quick patch).** `run_repl` wraps EVERY
   expression as `function vector __eval__() { return <expr>; }` (repl.py:199),
   hardcoding the return type as `vector`. A Sutra string is a codepoint-array
   vector, and the `vector`-typed codegen path does vector math on the raw str
   → `TypeError: can't multiply sequence by non-int`. Measured: the SAME
   expression wrapped as `function string __eval__()` compiles + runs fine and
   returns the string's codepoint tensor (h=104,e=101,l,l,o=111 on the axes).
   So the real fix needs the REPL to pick the return type from the expression's
   TYPE — which is the deferred v0.2 name-resolution/symbol-table work
   (`2026-06-24-h1-name-resolution-is-deferred-v0.2.md`) — OR a targeted
   "try vector, catch that TypeError, retry as string" fallback PLUS a new
   synthetic-axis codepoint→text decoder for display (no such decoder is
   exposed today; `nearest_string` is codebook-lookup, not raw decode). Both
   are real work in sensitive codegen/string-layout territory; neither is a
   2-line patch. Emma's call on approach (v0.2 vs fallback). Finding:
   `planning/findings/2026-07-04-repl-first-run-newcomer.md`.
2. **Naive `similarity("cat","dog")` (string args) gives an opaque
   `linalg_norm ... not str`** — a fresh newcomer-facing symptom of the deferred
   H1 type-check gap (folds into
   `2026-06-24-h1-name-resolution-is-deferred-v0.2.md`, no new work unless H1
   is green-lit).
3. **Tag `sutra-dev-v0.9.3`** after this branch merges so pip users get the
   no-main / unknown-name / wrong-type diagnostic fixes already at HEAD; also
   the Python-builtin fall-through (`2026-07-04-python-builtin-fallthrough.md`,
   folded into H1).

### A1 web wrapper — VERIFIED + EMA closed 2026-07-04; remaining = public deploy (Emma's account)

The wrapper itself already existed (`demos/gui/hero_server.py` + `hero_page.html`, shipped
2026-07-01) — 2026-07-04 this session VERIFIED it in a real Chromium (page loads, WARMER/COLDER
click, 6 presses = 3 SPSA steps, the substrate frame visibly morphs, headline re-renders; only
console noise is the browser's automatic `/favicon.ico` 404) and CLOSED the flagged 1d item:
reward EMA smoothing (`HeroSteering(ema_alpha=…)`, default 1.0 = raw, `--ema` on the server/window;
4 new tests incl. an exact ×0.5-damping check; 1d soak numbers reproduce unchanged). DEVLOG
2026-07-04. **What remains is only the public URL:** deploying per `demos/gui/DEPLOY.md`
(HF Spaces Docker recommended) needs Emma's hosting account — her step, not an agent's.

> **H1 (unknown-type/function diagnostics) RECLASSIFIED 2026-06-24 → the deferred v0.2 name-resolution
> milestone, NOT a quick batch item.** `validator.py:21-29` EXPLICITLY defers name resolution to "v0.2+
> once we have a symbol table." A measured false-positive scan (`scratchpad/h1_recon.py`) confirms a naive
> diagnostic warns on EXISTING VALID code: `03_methods.su` (valid corpus) references undeclared `Animal`/
> `Cat` types; the arrow-fn examples call first-class function-valued LOCALS (`f`,`scale`) — both need the
> real symbol table + local-scope tracking, not an allowlist. (Also `float`/`function` are missing from
> `PRIMITIVE_TYPE_NAMES` — real gaps to fix WHEN the symbol table lands.) The newcomer gap is already
> mitigated at the doc level (Batch 5.1 tutorial-01 note: v0.1 doesn't do name resolution, on the roadmap).
> Building the v0.2 symbol table is Emma's call (language-direction; it tightens the deliberately-lenient
> validator). Finding: `planning/findings/2026-06-24-h1-name-resolution-is-deferred-v0.2.md`.
> **NEW severity datum (2026-07-04, measured):** unknown call-position names lower to bare Python
> names, so ALL Python builtins are silently callable from `.su` (`print` mid-function, `str(len(…))`
> — an accidental host escape hatch, against the no-mid-computation-I/O identity). The v0.2 decision
> should weigh that, not just late-failing typos:
> `planning/findings/2026-07-04-python-builtin-fallthrough.md`. No interim blacklist shipped
> (it would be a second name-resolution mechanism H1 would have to unwind).

---

## ⭐ PINNED TAIL — readability + usability audit → REFILL (self-perpetuating; Emma 2026-06-23)

**This item never gets deleted — it regrows the queue.** When items 1..N above are all done, run a fresh
**readability + usability audit** of Sutra from the perspective of an outsider trying to read, install,
run, and learn it, and **atomise the findings into 3–6 new concrete items at the TOP of this ACTIVE
list**, then keep barrelling. Repeat every time the concrete items drain. Audit surfaces, rotating:
- **Onboarding:** can a stranger `pip install` and run their first program in <5 min? Where do they get stuck?
- **Docs readability:** are the tutorials/concept pages clear, in order, free of repo-internal jargon and
  dead links? Does the website read well to a newcomer? (Website discipline: keep `docs/` free of
  `queue.md`/`todo.md`/`planning/...` references.)
- **Error messages:** are `SUT####` diagnostics + runtime errors actionable, pointing at the fix?
- **Language readability:** is `.su` source itself readable? Are the example programs idiomatic and
  well-commented? Is the stdlib surface discoverable?
- **Real-program reach:** what can't a newcomer build yet that they'd expect to? (stdlib gaps, missing
  ergonomics) — name precisely; don't fake reach.
- **Aliases + affordances (Emma 2026-06-23):** internal redundancy — two Sutra-native names for one op,
  legacy entry points, escape hatches that mislead the next agent. Deprecate aggressively toward one
  canonical spelling (CLAUDE.md § "Deprecate aliases aggressively"); exclude the foreign-ecosystem carve-out.

**THE GOAL IS V1, AND V1 IS EMMA'S MANUAL CALL — NOT THE LOOP'S.** Keep making Sutra more readable +
usable; do NOT bump the version to 1.0.0, do NOT declare "V1-ready," do NOT tag a v1 release. Emma
approves the V1 transition manually. The loop's job is to keep closing usability/readability gaps until
she says it's there. (Consistent with the v1.0.0-deferred note in Context above.)

## Session bracket — autonomous loop (self-timed)

- Run as the self-timed `ScheduleWakeup` loop (NOT the three-cron playbook). Each wake: SYNC
  (`git fetch` + ff/rebase) → WORK the top `queue.md` item → HARD RAILS (never fake/weaken a test; RUN +
  measure before claiming green; name hard things plainly) → COMMIT (delete done item + DEVLOG entry,
  same commit) + push → schedule the next wake. When items 1..N drain, run the PINNED TAIL audit to
  refill, then continue — the loop is self-sustaining toward V1 (Emma's manual gate). Report via commits
  + DEVLOG, not questions.

---

## PARKED — real but gated (cannot implement on this clone)

_2026-06-21 audit: these are real, not phantom-PR. The async/await Stage-1 item was RETIRED (its
"only-tail-position-works / model-blocked" premise is now false — mid-function await shipped 2026-06-20).
The rest are genuinely gated on resources this clone lacks._

- **await Stage-2 — full gated `while_loop` with a LIVE external producer — desktop-I/O-gated.**
  The await CORE shipped 2026-06-20 (mid-function lowering + Promises/A+ rejection propagation, substrate-
  pure; `test_await_midfunction.py` green). What remains is the poll loop spinning on a promise an EXTERNAL
  producer resolves over time — i.e. the I/O orchestrator (**Sutra for Windows**, the desktop-I/O layer
  vendored in-tree at `external/Yantra/`) writing the resolved value into the awaited axon. `await_value`
  stays the β-reduced no-producer form until there's a real producer to test against; awaits buried in
  nested control-flow still fall through to the codegen rejection. Resume when wiring the desktop-I/O promise
  producer. (The await *model* — Emma 2026-05-17's implicit-axon-input + arrival-flag vs `promises.md`'s
  gated-while-loop — is still unsettled in the spec, but only governs this unbuilt producer path, not the
  shipped core. The old "async/await Stage-1 desugar" item was retired here: mid-function await shipped, so
  its "only-tail-position-works" premise is false.)
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
- Sutra for Windows (the desktop-I/O layer, formerly called "Yantra"): vendored in-tree at `external/Yantra/`
  (directory keeps the legacy name for now).

## Session bracket

- The autonomous loop is the self-timed `ScheduleWakeup` form (not the old three-cron playbook).
- Own the queue, barrel through, report via commits + DEVLOG — no questions.
