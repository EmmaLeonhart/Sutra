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

## ACTIVE — barrel top to bottom

### ⭐ v0.2 symbol table / name resolution (H1) — GREEN-LIT by Emma 2026-07-06

Emma green-lit the deferred v0.2 name-resolution milestone — the proper fix that unblocks BOTH
the REPL bare-string crash AND the opaque `similarity("cat","dog")` error (same root cause: no
symbol table). Finding: `planning/findings/2026-06-24-h1-name-resolution-is-deferred-v0.2.md`.
Barrel the rungs top to bottom; each is bounded and verified against the valid corpus. **The bar
is ZERO false positives** — the v0.1 validator is deliberately lenient and a naive diagnostic
warns on existing valid code (`03_methods.su` references `Animal`/`Cat` declared in no file), so
every diagnostic rung must scan `examples/*.su` ∪ `tests/corpus/valid/*.su` and fire on none.

**Rungs 1–3 SHIPPED 2026-07-06** — `sutra_compiler/symbol_table.py` + `tests/test_symbol_table.py`
(14 tests, PASS): (1) file-scope collector (user classes + members, top-level functions + methods +
arity); (2) local-scope tracking — `local_names(decl)` returns params ∪ every var/const in the body
(nested blocks via a generic dataclass `_walk`), so first-class function-valued locals are in scope;
(3) stdlib + builtins resolution — `is_known_*` now fold in `BUILTINS`, `stdlib_function_names()`
(qualified + bare), `intrinsic_names()`, and `stdlib_class_parents()` (making them diagnostic-grade,
over-inclusive for the zero-false-positive bar). Measured the type gaps: `float` added (it is the
parent of `JavaScriptFloat` — a real type). Pure, still no diagnostics wired. `include_extern=False`
restricts queries to module scope for tests.

**Cross-file / external-type handling SHIPPED 2026-07-06** (21 tests, PASS) — measured the exact
type-position false-positive surface over the full corpus (109 files): `['Animal','Array','Cat','List',
'function']`. Three fixes, each measured: (a) `function` IS a real type in TYPE position — the
first-class function-value annotation (`function f` params) — correcting rung 3's keyword-only note;
(b) container names now match case-INSENSITIVELY, so `List<T>`/`Array<int,10>` resolve like `list`;
(c) the genuinely-undeclared sibling types `Animal`/`Cat` are handled by open-world scoping —
`is_reportable_unknown_type` reports a LOWERCASE unresolved name (a primitive typo, `vec`→`vector`,
the H1 surface) but NOT a PascalCase one (a possible sibling `.su` object file), keyed off the
measured convention that every primitive is lowercase and every class is PascalCase. `closed_world`
mode + `build_project_symbol_table(modules, file_type_names)` union sibling files so PascalCase
unknowns become reportable once the whole project is present. **GATE MET: full-corpus scan = 0
reportable false positives** (test `test_full_valid_corpus_zero_reportable_false_positives`).

**Unknown-TYPE diagnostic SUT0200 SHIPPED 2026-07-06** — `validator.py` builds the symbol table in
`visit_module` and `_record_type_usage` (already called at every type position, recursing type_args)
emits a SUT0200 WARNING when `is_reportable_unknown_type` fires. Warning, not error — the source is
still valid v0.1 Sutra, so the valid corpus stays error-clean (corpus test = errors-only). Verified:
`vec`/`scalar` warn, `Animal`/`vector`/`function`/`List<T>` don't; new `tests/test_unknown_type_
diagnostic.py` + a corpus sweep assert 0 SUT0200 across every valid file (31 tests PASS w/ corpus).

**Unknown-FUNCTION diagnostic SUT0201 SHIPPED 2026-07-06** — measured the bare-call FP surface first
(25 names across the corpus): unlike types, the case heuristic FAILS — unresolved lowercase names are
also legitimate (`matrix_rows()` stub, `await network_lookup(q)` external producer), and PascalCase
cross-file method calls (`Cosine`,`Bind`,`Blend`) are everywhere. So a plain unresolved→warn rule can't
hit zero FP. Instead SUT0201 is a **"did you mean" typo detector**: warn only when an unresolved
LOWERCASE bare call is within Levenshtein ≤2 of a known lowercase function. Measured gap is decisive —
real typos 1-2 (`argmaxcosine`→`argmax_cosine`=1, `bundel`→`bundle`=2), legitimate externals 7-9
(`matrix_rows`, `network_lookup`) — so 0 corpus FPs with wide margin. Resolves through the local-scope
table first (first-class function values skipped) + classes + type params. `validator.visit_Call` emits
it; `symbol_table.unknown_function_suggestion` / `function_typo_suggestion` do the work.
`test_unknown_function_diagnostic.py` (10) + a corpus sweep assert 0 SUT0201 on every valid file.
(The Python-builtin host-escape-hatch datum from `2026-07-04-python-builtin-fallthrough.md` is a
SEPARATE concern — a blacklist, not typo detection — and is deliberately not folded in here.)

**Arity checking SUT0202 SHIPPED 2026-07-06** — `validator.visit_Call` warns when a call to a
file-declared FUNCTION passes the wrong arg count. Safe by construction: `Param` has no default value
and the parser has no varargs/optional/spread, so Sutra functions are fixed-arity and `len(args) ==
arity` is exact. Scoped to plain functions (methods thread implicit `this`; builtins have no table
arity) via `symbol_table.function_arity`. Measured: 0 mismatches across the 111 file-declared-function
calls in the corpus. `test_arity_diagnostic.py` (6) + corpus sweep; 53 validator-touching tests green.

### ⭐ Expression type inference — GREEN-LIT by Emma 2026-07-06 (chose "build full type inference")

Emma chose the largest-scope path for the last two H1 items: build a real expression-type-inference
subsystem, then do items 7 (REPL) and 8 (wrong-arg-type) on top. Same measured discipline as rungs 1-6
— every diagnostic rung scans the valid corpus and fires on NONE (0 false positives), and inference is
CONSERVATIVE (return None/unknown rather than ever guess a wrong type). Barrel top to bottom:

T1. **FunctionSig return types + callee return-type table.** Add `return_type` to `FunctionSig`
    (build_symbol_table already sees `FunctionDecl.return_type`/`MethodDecl.return_type`); fold in builtin
    + stdlib-intrinsic return types so a call's result type is queryable. Pure; unit-tested.
T2. **`infer_type(expr, symbols, local_types) -> Optional[str]`** — conservative bottom-up inference:
    literals (StringLiteral→string, Int/Float→int/number, bool), `embed(...)`→vector, casts→target type,
    calls→callee return type, identifiers→local var/param type, operators→operand-derived. Unknown→None.
    Unit tests over representative expressions; NO diagnostic wired yet.
**T1+T2+T3 SHIPPED 2026-07-06.** T1: `FunctionSig` return/param types + `extern_signatures()` (stdlib
intrinsic types, bare+qualified) + `call_return_type`/`param_types_of`. T2: conservative `infer_type`
(literals, `embed`→vector, casts, parenthesised, identifiers via `local_type_env`, calls via callee
return type; else None). T3: **wrong-arg-type SUT0203** — `validator.visit_Call` warns when an arg's
inferred type conflicts with the callee's declared param type. Measured the conflict surface first (16
legit mismatches on valid code: generic `T`, the vector-ish family, method `this`-misalignment), then
scoped the conflict to the ONE safe case — `string` ↔ concrete-non-text primitive (`arg_type_conflict`),
Identifier-callee only, per-enclosing-decl type env — giving 0 corpus FP while flagging both args of
`similarity("cat","dog")`. `test_type_inference.py` (10) + `test_wrong_arg_type_diagnostic.py` (6);
63 validator-touching tests green.
**T4+T5 SHIPPED 2026-07-06 — item 7 done, H1 milestone COMPLETE.** T4: `repl._decode_string` reconstructs
text from a string's codepoint-array tensor using the runtime's own `is_string`/`string_length`/
`string_char_at` accessors (a raw codepoint read at the sanctioned terminal DISPLAY boundary, distinct
from the codebook-nearest decode); wired into `_decode_result` before the concept path. T5: `run_repl`
infers each expression's type (`_infer_eval_type`) and types the `__eval__` wrapper accordingly — a string
expr now wraps as `function string` and decodes to its text, so the bare-string crash is fixed by REAL
evaluation (`"hello"`→`"hello"`), replacing the old embed() steer (removed, with the now-dead
`_bare_string_literal`/`_BARE_STRING_RE`/`import re`). Numbers (`= 5`) and concepts (`~ "hello" cos 1.00`)
still display via the existing paths (wrapper override gated to the verified `_EVAL_WRAP_TYPES={string}`).
Newcomer-driven end-to-end + `test_repl.py` (9, incl. a codepoint round-trip). 78 tests green across the
inference/diagnostic/repl surface.

(The Python-builtin host-escape-hatch datum, `2026-07-04-python-builtin-fallthrough.md`, remains a
SEPARATE blacklist concern — not folded into the above; it is the one H1-adjacent item still open.)

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

## ⭐ NEURAL UNIX UTILITIES — the big Unix tools on a completely neural computer (Emma 2026-07-06)

Ordered AFTER the doable items above and BEFORE the FV paper, per Emma's 2026-07-06 sequencing
(echo first → other doable items → the rest of the Unix stuff → FV last). **GOAL: neural
implementations of all the big Unix utilities, in order of difficulty**, on a **completely neural
computer — NTM-style, RAM AND disk, NOT an RNN — an entire filesystem** (external addressable
memory, the NTM/DNC route, not substrate-recurrence). **If a utility is too hard or needs a
prerequisite, BUILD the prerequisite — a prerequisite or issue is the signal for the next thing to
build.** Verbatim intervention in `DEVLOG.md`. Substrate already in hand: external RAM device +
orchestrator + VRAM mailbox (`experiments/ntm_ram/`, spec `planning/sutra-spec/ram-pointers.md`);
the `WASM/` argmax-attention NTM; finding `2026-06-06-iso5-ram-based-machine-dispatch-works.md`.

**Rung 1 `echo` SHIPPED 2026-07-06** — `experiments/ntm_ram/run_echo.py`: lays the echo output
bytes into the RAM device, the compiled substrate read-head (`text_scan.su`) scans + emits them,
decoded stream == real coreutils `echo.exe` char-for-char (5/5 cases incl. `-n`). Establishes the
P0 stdin/stdout path. (Honest scope: echo is the passthrough base case — the substrate work is the
scan/emit; real transforms start at `wc`/`tr`.)

### Prerequisites — build/verify as the utilities force them (order = first need)
- **P0 — stdin/stdout as boundary axons.** DONE. Read/emit shipped via rung 1 (echo); the streamed
  STDIN axon shipped via rung 2 (cat) — `_stream_load` feeds RAM in chunks (as a pipe delivers), the
  substrate scans the assembled stream, `--stdin` mode consumes a real pipe.
- **P1 — external DISK device + filesystem namespace.** Persistent addressable regions + a
  path→region map, serviced by the orchestrator like RAM but persistent. Forced first by `cat FILE`
  / `ls`; spec it in `planning/sutra-spec/` before building.
- **P2 — neural regex / NFA matcher.** Forced by `grep`/`sed`: compile a pattern to an on-substrate
  argmax-attention state machine over the stream.

### Utilities, ordered by difficulty — barrel top to bottom; each verified decoded-output == coreutils ground truth
Tier A — pure stream transforms (RAM buffer only, no filesystem):
1. `cat` **SHIPPED 2026-07-06** — `experiments/ntm_ram/run_cat.py`: streamed stdin (`_stream_load`, 8-byte
   chunks) → substrate scan/emit read head → decoded stdout == coreutils `cat.exe` byte-for-byte (7/7
   cases: multi-line, empty, punctuation, multi-chunk-boundary; `--stdin` consumes a real pipe). Honest
   scope: still a passthrough (no substrate transform over echo) — the new work is the P0 stdin axon.
   Regression guard in `test_ntm_ram.py::test_neural_cat_streams_stdin_passthrough`.
2. `wc` **SHIPPED 2026-07-06** — `run_wc.py` + `wc_heads.su`: the first REAL transform. Substrate
   streaming accumulators (recurring VRAM vectors, updated by substrate tensor ops every tick — the
   count survives across calls as a vector, never a host counter) compute (lines, words, bytes) exactly:
   10/10 vs coreutils `wc` (tabs, multi-space, empty, no-trailing-newline, blank lines); `--stdin` mode
   matches on a real pipe. Key primitive: EXACT codepoint indicator `is_cp(c,center)=relu(1-|c-center|)`
   — MEASURED gap 1.0 (exactly 1 at center, hard 0 elsewhere; the relu clamp avoids the exp/tanh
   saturation residual that would accumulate). words packs count+prev-nonspace into one complex recurring
   slot (v1 = one recurring slot/function). Guard: `test_ntm_ram.py::test_neural_wc_counts_match_
   coreutils_exactly`.
3. `head` / `tail -n` **SHIPPED 2026-07-06** — `run_head_tail.py` + `filter_heads.su`: substrate
   line-gated stream filters. A recurring line accumulator + an EXACT integer gate (`ge1(x)=1 iff x>=1`,
   built from relu) mask each emitted codepoint (`served * gate`); head gates `line_idx < N`, tail counts
   the total on the substrate (pass 1) then gates `line_idx >= total-N`. 72/72 checks vs coreutils
   head/tail (6 inputs × 6 N × 2 utils), incl. unterminated last line (+1 boundary correction) and blank
   lines. `--head`/`--tail -n K` pipe modes. Guard: `test_ntm_ram.py::test_neural_head_tail_line_gated_
   filters`.
4. `tr` **SHIPPED 2026-07-06** — `run_tr.py`: per-byte substrate codebook map. Each byte's output is a
   weighted sum of EXACT codepoint indicators — `out(c) = Σ is_cp(c,key_i)*val_i + c*(1-Σ is_cp(c,key_i))`
   — so matched codepoints become their paired value, unmatched pass through; `-d` masks matches to 0.
   The codebook (SET1→SET2 codepoints, ranges expanded, SET2 padded like coreutils) is baked into a
   generated `.su` compiled per translation. 7/7 vs coreutils `tr` (a-z/A-Z both ways, translate, vowels,
   -d digits/letters, SET2-padding); pipe modes `tr a-z A-Z` / `tr -d 0-9`. Guard:
   `test_ntm_ram.py::test_neural_tr_codebook_translate_and_delete`.
5. `rev` / `tac` **SHIPPED 2026-07-06** — `run_rev.py` + `rev_head.su`: reverse permutations over a RAM
   buffer, computed on the substrate. A recurring cursor counts up and the head emits
   `pointer = limit - cursor`, so the served address sequence runs DOWN (reverse order) via one substrate
   subtract/tick. rev reverses codepoints per line; tac reverses line order. 14/14 checks (rev vs a
   per-line reference — coreutils `rev` is util-linux, absent on Windows; tac vs coreutils `tac.exe`):
   multi-line, no-trailing-newline, empty, uneven lengths. `--rev`/`--tac` pipe modes. Guard:
   `test_ntm_ram.py::test_neural_rev_tac_reverse_permutation`.
6. `cut` **SHIPPED 2026-07-06 (cut -c) — Tier A COMPLETE** — `run_cut.py`: per-column gated emit. A
   recurring column counter increments per char and RESETS at each newline; each char is emitted iff its
   column is in the selected range set (`ge1` exact integer steps; ranges OR-ed via `ge1(Σ)`; newlines
   always pass + reset). 8/8 vs coreutils `cut -c` (ranges, open `3-`/`-3`, comma `1,3,5`, short lines);
   `-c LIST` pipe mode. Ranges baked into a generated `.su`. Guard:
   `test_ntm_ram.py::test_neural_cut_c_column_gated_emit`. (`cut -f` field mode = a follow-on: delimiter
   field counting.)

Tier B — ordering / comparison / dedup (more RAM, comparison networks):
7. `uniq` **SHIPPED 2026-07-06** — `run_uniq.py` + `uniq_head.su`: collapse ADJACENT identical lines via
   a substrate prev-vs-current comparison. `line_cmp` accumulates a MISMATCH count over exact per-position
   char indicators (`+= 1 - is_cp(a_i,b_i)`); the shorter line is padded with a sentinel no codepoint
   equals, so length differences register too; mismatch==0 iff identical. 8/8 vs coreutils `uniq`
   (adjacent runs, all-distinct, length-diff adjacency, unterminated last line, empty). `--uniq` pipe
   mode. First Tier-B rung — COMPARES two buffered lines. Guard:
   `test_ntm_ram.py::test_neural_uniq_adjacent_dedup`.
8. `sort` **SHIPPED 2026-07-06 — Tier B COMPLETE** — `run_sort.py` + `sort_head.su`: full-buffer
   comparison network whose comparator is the substrate. `line_less_step` streams two lines' codepoints
   and latches, at the first differing position, whether A<B via `ge1(b_i-a_i)`, packing (decided,result)
   into one complex recurring slot; shorter prefix-equal line sorts first via a sentinel pad below every
   codepoint. The host sequences the comparisons (network) + moves lines (I/O); every ordering decision
   is the neural comparator. 9/9 vs coreutils `sort` LC_ALL=C (lexical numeric 1/10/2/3, C-locale case,
   prefix a/ab/abc, dups). `--sort` pipe mode. Guard:
   `test_ntm_ram.py::test_neural_sort_substrate_comparator`.

Tier C — pattern matching (needs P2 — neural regex/NFA; `grep` fixed-string needs only substring match):
9. `grep` (fixed string) **SHIPPED 2026-07-06** — `run_grep.py` + `grep_head.su`: print lines CONTAINING
   the pattern via a substrate substring match. A sliding window's all-equal test is a PRODUCT of exact
   codepoint indicators (`*= is_cp(line_c, pat_c)`) — 1 iff the window equals the pattern, 0 at the first
   mismatch. Host slides the window (I/O) + OR's per-window results; the length-|pattern| attention is
   substrate. 9/9 vs coreutils `grep -F` (multi-match lines, overlapping windows `aa`/`aaa`, `-v` invert,
   empty pattern/input). `PATTERN` / `-v PATTERN` pipe modes. Guard:
   `test_ntm_ram.py::test_neural_grep_substring_match`.
10. **P2 — neural regex/NFA matcher. SHIPPED 2026-07-06** — spec `planning/sutra-spec/neural-regex-nfa.md`
    + `experiments/ntm_ram/neural_regex.py`. Thompson-constructs the pattern to an NFA (compile-time,
    host), then simulates it on the substrate: the active-state SET is an N-dim 0/1 buffer stepped by
    `s' = ge1(E @ (M_dot @ s + Σ_lit is_cp(c,lit)·(M_lit·s)))` — transition + epsilon-closure MATMULS
    (`_VSA.matmul`), char-class coefficients assembled on the substrate via the exact `relu(1-|c-lit|)`
    indicator (a 0-d device scalar), `ge1` collapse (no residual). First rung using vector-valued substrate
    state. Subset: literals, `.`, `[...]`/`[^...]`/ranges, `* + ?`, `|`, `( )`, `^ $` — **29/29 vs Python
    `re`**. Guard: `test_ntm_ram.py::test_neural_regex_nfa_matches_python_re`.
11. `grep` (regex) **SHIPPED 2026-07-06** — `run_grep_regex.py`: `grep -E` on the substrate NFA (one NFA
    per pattern, reused per line). **10/10 vs coreutils `grep -E`** (`colou?r`, `[0-9]+`, `gr[ae]y`,
    `cat|dog`, `^`/`$`, `-v`). Pipe `-E PATTERN` / `-v -E PATTERN`. Guard:
    `test_ntm_ram.py::test_neural_grep_regex_matches_coreutils`. **NEXT: `sed`** (needs match-span
    extraction — spec open-question 1: carry the earliest start position on the winning path) → `awk`
    (a whole language — the Sutra compiler is the engine; far out). Then Tier D (filesystem, needs P1).

Tier D — filesystem (needs P1):
11. `cat FILE` → `ls` → `cp`/`mv`/`rm` → `find` — file read, directory listing, mutation, recursion.

---

## ⭐ FV PAPER — LAST in the queue (Emma 2026-07-06: execute after everything above)

Emma 2026-07-06: "I think fv paper is finished but not sure" — moved to the END; do it only after
the neural-Unix-utilities work above. **First action when this item is reached: verify whether it's
actually finished** (clawRxiv reached **Accept** 2026-07-01; shipped legs are in `DEVLOG.md` +
`git log`). If finished, delete this item. Frame (binding): the FV paper verifies Sutra-the-language
as an ISA on a *probabilistic* substrate — keep it NARROW (per-contract, non-learned trusted base);
do NOT re-grow "verify the whole neuro-symbolic system" (recurring overambition failure mode).

Only remaining leg (**named, NOT green-lit — do not start without Emma**): a Lean gap **value** for
the literal single-spin-flip kernel needs the canonical-paths comparison method (a per-edge
conductance bound can't see zeros between non-neighbours); until built, the measured γ=0.0397 stays
a measurement (DEVLOG 2026-07-04). Guardrails: nothing proven until `lean` accepts (no `sorryAx`);
every `paper/formal-verification/paper.md` push triggers the clawRxiv resubmit CI; Mathlib work
verified via `fv-lean-mathlib-ci` (local Windows hits MAX_PATH — iterate via branch pushes).


## Fix the failing tests

We have a few tests that have just been consistently failing constantly, and I don't know why it is we haven't addressed them, but we probably should fix them here. I'm a bit confused about the general rule about why it is we haven't fixed them, especially since we distinguish between an X fail and a regular fail, but there are some that we just have not been fixing up. 

And to be clear, this is at the end of the queue. It means you don't start it. It means you don't jump onto it just because of the fact that this is recently added. 

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
