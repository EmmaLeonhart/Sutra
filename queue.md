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
- **Version: 0.9.1** (Emma 2026-06-21) — `pyproject.toml` + `__init__.py` bumped to a fresh `0.9.1` (a clean
  patch past the `v0.9.0` milestone tag, rather than forcing the package to exactly match the old tag).
  Publish via a `sutra-dev-v0.9.1` tag (trusted-publisher → PyPI `sutra-dev`). **v1.0.0 is deferred** until
  codegen/stdlib go a stretch with NO source-breaking changes (Emma's call — too soon right after this
  week's arithmetic-semantics changes). No hard blocker; it's a source-compat-stability commitment.

## ACTIVE — barrel top to bottom

**Theme (Emma 2026-06-22/23): USABILITY.** Make Sutra easy for an outside person to install, run,
and learn. The backlog elsewhere is all substrate-correctness; none of it is usability. The
in-process-embedding change (drop the Ollama daemon) shipped 2026-06-22. Barrel these top to bottom;
delete each on completion + append to `DEVLOG.md` in the same commit.

_Batches 1–2 drained 2026-06-23 (in-process embeddings, first-run UX, package verify, semantic-FAQ +
tutorial 05, list-ops, `sutrac repl`; tutorial 01/04 fixes, stale-count sweep, onboarding polish).
History in `DEVLOG.md` / `git log`._

_Batch 3 (ALIAS + AFFORDANCE sweep) DONE 2026-06-23: `truth_value`/`complex_number`/`real_number` →
`make_*`; `basis_vector` → `embed` (builtin deleted, collect renamed); `unk` → `unknown`; `scalar` type
→ `number` (fully removed incl. the parser/static-method sites); `iff` → `xnor` (removed from BOTH lexer
AND parser tables). `embed`/`make_*`/`number`/`unknown`/`xnor` are the single canonical spellings. Other
logical-connective spellings stay (Emma). All verified (compiler 811, smoke PASS, demos 224). History in
DEVLOG + git log. CLAUDE.md § "Deprecate aliases aggressively" records the rules + carve-outs._

_Batch 4 (stale-reference cleanup from the post-alias audit) DONE 2026-06-23: stdlib comments
(`embed.su`/`vectors.su` block deleted/`axons.su`/`README`/`logic.su`), docs (`operators`/`capabilities`/
`logical-operations` — `iff` dropped/→`xnor`, `basis_vector` past-tense), codegen prose comments, and the
dead `basis_vector` branch in thrml `_basis_atoms` all cleaned. Verified: 62 tests pass, site builds.
A few trivial historical-prose mentions of "basis_vector"/"scalar" remain in internal codegen/egglog
comments (referencing the removed spelling as history) — not misleading, left as-is._

## Batch 5 — newcomer-usability audit (2026-06-23, post-alias)

Fresh readability/usability audit (onboarding + error messages + real-program reach). `iff` on the public
`docs/primitive-classes.md` page (a Batch-4 miss) was fixed inline.

_Batch 5 concrete items DRAINED 2026-06-24: the `snap` trap (M5 — SUT0151 validator warning + backend-
accurate codegen message + tutorial-03 future sidebar, all steering to `argmax_cosine`); the no-I/O
host-bridge concept page (M6 — `docs/host-bridge.md`, wired into tutorials 01/05 + index; a live-input
primitive FLAGGED as Emma's open call, not built); `dict<K,V>` discoverability (L11 — surface-syntax
section added to `docs/memory.md` + a keyed-collection link from `docs/list-operations.md`). History in
DEVLOG + git log. → Run the PINNED TAIL audit to refill._

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

## Batch 6 — fresh readability/usability audit (2026-06-24, post-Batch-5)

Audit from an outsider trying to install, run, and read Sutra. Surfaced concrete gaps — barrel top
to bottom; delete each on completion + append to `DEVLOG.md` in the same commit.

_Done 2026-06-24 (history in DEVLOG): (docs accuracy) `docs/index.md` "string I/O" → string *operations* +
host-bridge pointer; (error messages) the CLI now catches `CodegenNotSupported` at the single
`_compile_to_python` choke point and prints a clean `file:line:col: codegen: <msg>` diagnostic (exit 1)
instead of an uncaught Python traceback — `--run`/`--emit` on `snap` verified, test_snap_diagnostic covers it._

1. **`pip install` onboarding can't actually run a program — examples aren't shipped + a bare string
   return mis-decodes (M/H, onboarding — needs a packaging/semantics call).** MEASURED 2026-06-24 while
   auditing the landing page: (a) the wheel ships only `sutra_compiler` + `stdlib/*.su` (`pyproject.toml`
   §packages.find / package-data; no MANIFEST, no force-include), so `examples/` is **repo-root only** —
   a pip-only user has no `examples/hello_world.su`, yet tutorials 01 & 05 *and* tutorials/index tell them
   to `sutrac --run examples/…`. That path 404s without a clone. (b) The obvious pip-friendly substitute
   doesn't work either: `function string main() { return "hello world"; }` run via `sutrac --run` prints
   **`104.0`** (= codepoint of 'h') — a bare string-literal `main` return is a make_string codepoint-array
   tensor and the terminal decode reads its REAL axis as a number. Only a *codebook/map-returned* string
   stays a host `str` and prints as text (that's why tutorial 01's hello-world works — it returns
   `PHRASE_NAME[winner]`). Net: "pip install and run your first program in <5 min" is not currently true.
   Resolution is a call (FLAG, don't guess): ship `examples/*.su` in the wheel (packaging change — they sit
   outside the package dir, so it needs force-include/relocate + doc-path updates), and/or make `main`'s
   string-literal return decode back to text, and/or make onboarding explicitly clone-based. The landing
   page's current git-clone path *works* (it gets examples), so don't replace it with a broken pip-run claim
   until this is decided.

2. **Early unimplemented-builtin warning covers only `snap` (LOW, error messages).** `snap` now warns at
   validate-time (SUT0151) + a codegen hint, but the sibling spec'd-but-unimplemented builtins
   `make_rotation` / `compile_prototypes` / `geometric_loop` (`codegen.py` `_UNSUPPORTED_BUILTINS`) still
   validate clean and die with a hint-less deep codegen error. Generalise: a validator warning for them too
   + `_UNSUPPORTED_BUILTIN_HINTS` entries pointing at the implemented alternative (or, where there is none,
   saying so plainly). Lower newcomer-exposure than snap (none are taught), but the same trap shape.

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
