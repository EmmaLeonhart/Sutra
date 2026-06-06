# Sutra — Work Queue

**This file is a queue, not a state snapshot.** It lists what is being
worked on right now and what is next. Finished work lives in `git log`,
`DEVLOG.md`, and `planning/findings/` — NOT here. If you catch yourself
writing "✅ DONE / SHIPPED / RESOLVED" status in this file, stop: delete
the item instead and let git log / DEVLOG / a finding hold the history.
That CRUD is exactly what bloats this queue (2026-05-30 cleanup). Remove
completed items in the same commit as the work (CLAUDE.md §Workflow Rules).

`todo.md` is longer-horizon. Items migrate `todo.md` → `queue.md` →
deleted on completion. Keep the task tool in sync with this file.

---

## 🟢 HANDOFF — READ THIS FIRST (Emma restarting computer 2026-05-30)

**What this session did, in plain terms.** The track is "weight→code" —
recovering a program's source from its learned weights, and building the
training data for that. Two things finished today:

1. **The corpus is built, hardened, and at scale.** Now 3600 small Sutra
   programs (15 structures, incl. 5 inference-forcing families) whose
   behavior is carried by matrices, each paired with its weight matrices
   (CSV files) and its substrate input→output behavior. It lives in its own
   git repo as the `corpus/` submodule (`EmmaLeonhart/sutra-w2c-corpus`).
   Every entry is self-consistency-checked, GitHub + HF mirror in sync.

2. **A first weight→code model works end-to-end.** A small Transformer
   (`experiments/w2c_seq2seq/`) reads a program's weights + IO and GENERATES
   its `.su` source. Trained on 2160 programs, tested on 240 held-out:
   - regenerates the correct source for **202 / 240 = 84.2%**;
   - verified on the real substrate — the generated source, recompiled and
     run, reproduces the held-out IO for the **same 202 / 240**;
   - **0 compile failures.** The 38 misses are all one bug-class: the model
     gets the matrix multiply right but drops the `+x` / `−x` correction
     term in the `diff` / `residual` program families.
   Write-up: `planning/findings/2026-05-30-w2c-seq2seq-substrate-eval.md`.
   Shas: data prep `eb8140a9`, model+train `f9a7ef14`, substrate eval
   `8648a24f`.

**Option A (harden + retrain) — DONE and measured.** All three ticks shipped:
harder families, full 3600-program regen (GitHub `03336b9` + HF `d464fdb`),
retrain + substrate re-eval. The 84.2% *was* templating: on the harder space
exact-match drops to **0.678**, substrate IO-repro to **0.706**, with the
collapse localized entirely to the coefficient families (`chain4` still 1.0).
Write-up: `planning/findings/2026-05-30-w2c-tick3-hardened-corpus-eval.md`.
Next levers (corpus canonicalization, coefficient head) in the "Active — W2C"
section below.

**About the restart.** The hourly crons (work-loop / auto-flush / status /
blocker-sweep) are session-local — restarting the computer kills them and
this session, so the next session must recreate them (see Pinned tail). All
work is committed and pushed. `data/` (dataset + model checkpoint) is
gitignored, so re-running the model means: `git submodule update --init
corpus` → `py experiments/w2c_seq2seq/prepare.py` → `…/model.py` →
`…/eval_substrate.py`.

## A.0 — Ask Emma (drain via AskUserQuestion; phone notification)

- *(none open — the HF flat-CSV orphans were over-escalated; resolved to the
  sensible default: LEAVE them, they're harmless unreferenced duplicates and
  block nothing. Prune only if Emma later wants the tidy-up. See "Active —
  W2C".)*

## Context (read first, do not work on)

- **`paper/paper.md` is on arXiv and FROZEN through May 31, 2026.** Lock
  lifts automatically **2026-06-01**. Do not edit it (typos, findings,
  next-venue polish) until then. `paper/neurips/` is under its own
  separate **permanent** freeze. If a later result contradicts either,
  stop and tell Emma — don't silently amend. (DEVLOG 2026-05-20.)
- **Promise/await is fit-to-spec** (verified 2026-05-20;
  `test_await_substrate_pure.py` 4/4). Guarded by the watchdogs below.

## Active — RAM inline `await ramRead` surface syntax (Emma chose 2026-06-01)

### 🔍 Daily substrate-honesty audit — 2026-06-06

Auto-prepended by .github/workflows/daily-audit.yml. The next autonomous-loop session should, as its first action: review every commit landed since the previous daily audit against CLAUDE.md § "Subtler substrate breaches — measurement-required": (a) for each commit touching a .su or its compile path, verify runtime_dim matches what the .su actually needs (count basis_vector calls; no basis_vector → tiny dim); (b) for any commit that frames work as "recurrent" / "RNN" / "substrate-pure" / "verified", verify the claim against measurement, not against earlier session framing; (c) for any commit shipping a substrate classifier or decision function, verify the measured gap = min(positive_class) - max(negative_class) is in the commit or planning doc. If anything is amiss, write a finding under planning/findings/ and a fix item under queue.md BEFORE doing other queue work. Then delete this item.

Goal: `number x = await ramRead(pointer);` / `ramWrite(pointer, data);`
compile + run directly in `.su` (today only the hand-wired
`experiments/ntm_ram` harness does it). **Studied 2026-06-02:** the
Stage-1 desugar (`promise_desugar.py`) ALREADY lowers inline `await x` →
`Promise.await_value(x)` and handles the `v = await x; return g(v)`
continuation — so no new continuation transform is needed. The gap is the
**external producer**: `await_value` currently short-circuits to
`value(p)` (no producer wired). Per `promises.md` (await resolves when an
external producer populates the slot) + `ram-pointers.md` (the RAM
device/orchestrator is that producer), the spec-grounded design — NOT a
substituted synchronous variant — is:

**DONE (steps 1-2 + tests, 0587e6b8 + this commit):** `_VSA.ram` device +
`ram_read`/`ram_write` (round-to-nearest, OOB→zero); `ramRead`/`ramWrite`
codegen builtins. Measured working + guarded (`test_ntm_ram.py`
`TestRamInlineSurface`, 4 cases):
- synchronous `ramRead(ptr)` / `ramWrite(ptr, data)` (any function);
- `number x = await ramRead(ptr)` inside an **async** function (flows
  through the existing promise desugar → `await_value` passes the
  already-resolved device read through — no `await_value` change needed,
  `test_await_substrate_pure` 4/4 intact);
- the **NTM read head as a `recur` loop using *synchronous* `ramRead`**:
  per-tick reads advance on the substrate (cursor is a recurring VRAM
  tensor; `real()` is the I/O-wire address decode — state-locus holds).

**Realization note (honesty):** the inline surface compiles to a
synchronous read of the host-attached `_VSA.ram` device (matches Emma's
"RAM is a discrete IO device you read/write" framing). The separable-
orchestrator VRAM-mailbox model (request emitted as substrate data for a
*separate* process) is the distinct `experiments/ntm_ram` harness, kept
for the multi-program/Yantra IPC story.

**Remaining:**
1. **`await` inside a non-async `recur` (Emma's exact read-head example)
   — BLOCKED on the await-lowering phase.** Measured: it hits
   `CodegenNotSupported` ("await lowering to a gated while_loop not yet
   implemented"; promises.md). The synchronous-`ramRead`-in-`recur` form
   above already gives the NTM read head functionally; the `await`
   keyword in non-async recur is sugar pending the await→while_loop
   lowering (the larger async/recur-composition work). Do NOT hack the
   desugar to process non-async recur without settling that semantics.
2. ~~Migrate a demo to the inline surface~~ **DONE:**
   `experiments/ntm_ram/text_scan_inline.su` + `run_inline_demo.py` — a
   `recur` read head calling inline `ramRead(cur)` against a host-attached
   `_VSA.ram`; decodes "HELLO, RAM!" exact (guarded by `test_ntm_ram.py`,
   11/11).

Open follow-up (todo.md): await→while_loop lowering for recur+await;
model-free hash-keyed-role axon for the mailbox dim cost.

## Active — W2C weight→code (option A hardening complete; next levers)

### HF mirror — DONE (7200 sharded corpus live); orphan cleanup low-priority (default: leave)

Resolved the HF 10000-files/dir rejection by sharding into 20 per-seed
subdirs (`s{seed}/`). Submodule `3b33e5e9` (GitHub) + generator + migration
`experiments/shard_corpus_to_subdirs.py`. HF re-mirror succeeded (commit
`6ffae459`): the 7200-program sharded corpus is on HF and referenced by
`corpus.jsonl` — usable. Verified spot-check 6/6 IO + full `prepare`
(6480/720), no path errors.

**Loose end (low priority — default = leave):** `upload_folder` doesn't
delete, so 5760 flat CSVs from the old 1× layout remain on HF as
unreferenced orphans (harmless duplicate cruft + 2× storage; the dataset
is fully usable via `corpus.jsonl`). Not blocking anything. If a tidy-up
is wanted later: precise explicit-path delete of the flat files (NOT a
`*.csv` wildcard — recursive, would nuke the sharded CSVs) + harden
`mirror_corpus_to_hf.py` to prune stale files on each mirror.

Hardening done (all 3 ticks): generator harder families, full 3600-program
regen + GitHub + HF, **and retrain + substrate re-eval**. Result measured and
written up: `planning/findings/2026-05-30-w2c-tick3-hardened-corpus-eval.md`.
Headline: exact-match 0.842→**0.678**, substrate IO-repro 0.842→**0.706**, 0
compile/run fails, first **10 behavioral wins**. The drop is localized to the
coefficient axis — `chain4` (deepest chain) is solved 1.0, every coefficient
family collapses (`scaled_res` 0.083, `scaled_diff` 0.125, `gen_affine` 0.25,
`two_mat_affine` 0.33 exact). Unit-coeff cases exact 0.000 (model correctly
simplifies `1.0 *` away — corpus artifact); non-unit cases exact 0.241 (real
inference, mostly fails). This validates option A: structure transfers, scalar
coefficients do not.

**Follow-up #1 — DONE (eval-side canonicalization).** `eval_substrate.py` now
reports `exact_match_canonical` (strips redundant `1.0 *`) + per-structure
`exact_canon_rate`; guard `canonicalize_source` test in `test_eval_substrate.py`
(6/6). Measured: canonical exact 244→**254 = IO-repro exactly**, in every one of
the 15 families — so the "10 behavioral wins" were a pure scoring artifact, not
equivalent-code diversity (tick-3 finding Corrected). Generator-side
canonicalization is now optional (corpus cleanliness only, no metric impact);
deferred unless we regen for another reason.

**Follow-up #2 — DONE (coefficient WALL, 3 levers exhausted).** The coefficient
head diagnostic + both follow-on levers are written up in
`planning/findings/2026-05-30-w2c-coeff-head-diagnostic.md`. Net: the coefficient
is only ~½ decodable from the encoder rep (~0.60 probe / ~0.30 coeff-family IO),
and all three architecture levers came back negative/null — aux loss (hurts the
decoder), post-hoc substitution (0.61 head too weak), matmul input feature (no
movement). weight→code recovers *structure* near-perfectly (chain4 = 1.0) but
scalar coefficients are a wall for this architecture.

**Scale model + corpus (Emma 2026-05-31 decision) — both halves DONE & measured.**
1. **Bigger model — NOT capacity-bound.** d256/L6 (≈4–8× params) left the probe
   flat (~0.60), coeff-family IO flat-to-down (0.31→0.23). Readout, not capacity.
2. **Bigger corpus (2×, 7200) — HELPED, contradicts the architectural read.**
   Same d128/L3, 40 epochs, 2× data: decoder exact 0.689→**0.811**, canonical/IO
   0.714→**0.825**, coeff-family IO 0.31→**0.41**. The coefficient wall is at
   least partially **data-bound**, not purely architectural. Still far from
   solved (0.41) and the gain bundles more-data + more-steps. Written up in the
   coeff-head finding § "Bigger-corpus test". Scratch only — NOT pushed to
   submodule/HF (the official-push decision is Emma's; see A.0).

## Corpus (built & at scale — not active work)

The weights↔code corpus is built and at **7200 programs** (15 structures ×
6 K {4,6,8,10,12,16} × 4 weight-kinds × 20 seeds; scaled 1×→2× 2026-06-01,
submodule `3b33e5e9`, CSVs sharded into `s{seed}/` subdirs), on the
`corpus/` submodule (`EmmaLeonhart/sutra-w2c-corpus`) + HF mirror
(commit `6ffae459`, 7200 corpus live + referenced; 5760 old-layout flat
orphans remain to be pruned — see A.0). Consistency-guarded
(`test_weight_to_code_corpus.py`, `test_gemma_codegen_corpus.py`).
Scale further = one-flag bump (`--seeds`/`--ks`) on
`experiments/weight_to_code_corpus.py` → push submodule →
`experiments/mirror_corpus_to_hf.py` → bump the Sutra pointer + card stats.
Open/deferred: a category/semantic *trained* weight-kind (needs embeddings;
heavy 768²/nomic, uncertain value at small K). Detail: DEVLOG 2026-05-29/30.

## Formal verification (roadmap lives in formal-verification.md + todo.md)

Discharged set + open obligations are authoritative in
`planning/sutra-spec/formal-verification.md` (key-soundness discharged
2026-05-29). Remaining substantive work, in order: (1) k=8 → real capacity
curve; (2) PIT term-count honesty; (3) widen/tighten the decided fragment;
(4) general obligation checker. These are longer-horizon → `todo.md`.
Keep `paper/formal-verification/paper.md` updated as each lands (CI
auto-submits to clawRxiv on push).

## Watchdogs (verification, not new work)

- Hourly local cron: runs `test_await_substrate_pure.py` + greps
  `codegen_pytorch.py` for the `await_value` leak signatures; reopens an
  item here if anything regresses.
- Daily remote routine (claude.ai cloud): spec-audit pass over
  `planning/sutra-spec/*.md` vs the runtime; commits findings.
- Daily substrate-honesty audit (`.github/workflows/daily-audit.yml`)
  prepends an audit item; discharge it (review commits since the last
  audit vs CLAUDE.md §"Subtler substrate breaches") then delete it.

## Next-venue paper polish (FROZEN through May 31; resumes 2026-06-01)

Blocked by the `paper/paper.md` freeze; do not start until June. Ablation
table; polynomial-interpolant-rationale paragraph (prose in `git show
41fa446b`); Le Chat section-granular AI-use breakdown; optional Futamura
1971 bib entry.

## Transpiler track (source -> Sutra; OCaml first) — 1pm cron, owns this section only

Roadmap: todo.md §"Multi-language transpiler frontends".

**PRIORITY ORDER (Emma 2026-06-05):**
**(1) OCaml first** — keep advancing it; it fits Sutra best and is the most
complete *verified-running* frontend, so it's the reference impl for the rest.
**(2) Fix TypeScript** (the axon-`.real()` runtime bug below).
**(3) The other languages**, in roadmap order: **Scala -> F# -> Elixir/Erlang
-> Clojure -> Haskell -> then Rust -> then WASM.** Each is scaffolded below so
it's documented even before work starts; new frontends model on
`sutra-from-ocaml` (not `-ts`, which has the latent axon bug).

This section is driven by the 1pm transpiler work-loop cron; it pulls+rebases
first and never touches the RAM/W2C sections above.

### Priority 1 — OCaml frontend (`sdk/sutra-from-ocaml/`)
- [ ] (optional) File the Sutra `(atom) <binop>` → cast (`CastExpr`) parser
  ambiguity as an open-question — both frontends now work around it with
  fully-grouped blends, but the grammar ambiguity itself is unresolved.
- [ ] `let rec` — **tail-recursive accumulator shape DONE** (`let rec f p… =
  if COND then BASE else f a…` → Sutra `while_loop`; substrate-verified
  `sum_to 0 5 = 15`). Remaining: (a) **non-tail recursion** (factorial-shape,
  recursive call inside a larger expression) — still correctly UNSUPPORTED; needs
  a bounded-depth encoding, open question. (b) Non-comparison halt conditions
  (`&&`/bool) — needs a Sutra `not`/negation. [Simultaneous swap-update: DONE —
  temp-based update, substrate-verified `swaploop 7 9 2 = 7`.]
- [ ] `match … with`: **literal + trailing `_` DONE** (`classify 1 = 200`) and
  **nullary-constructor patterns DONE** (variant match, `label Green = 200`,
  substrate-verified; last case is the base, exact for exhaustive variant matches).
  Remaining: constructor-with-args / record-destructuring / or- / guarded patterns;
  `match` that binds a name in the catch-all (`| x -> …`).
- [ ] **Records -> axons: DONE for numeric fields** (substrate-verified
  `getx (mk 7 9) = 7.0`). `type X = {…}` erased + record-name prepass; record-typed
  params -> `Axon`; construction `{x=a;y=b}` -> `Axon r; r.add("x",a); …`; field
  access `p.x` -> `p.item("x").real()`. Key finding (`planning/findings/2026-06-05-
  axon-field-reads-need-real-projection.md`): numeric axon field reads REQUIRE
  `.real()` — without it they return zeros on the substrate. No type-tracking layer
  was needed (OCaml `p.x` is unambiguously a record field via `field_get_expression`).
  Remaining: tuples, non-numeric record fields (field-type-aware `.real()` off the
  record decl), record literals in argument position. (Nullary **variants** ->
  enum ints + constructor-pattern `match`: DONE — `label Green = 200`. Parameterised
  constructors `C of t` still UNSUPPORTED.)
### Priority 2 — fix TypeScript (`sdk/sutra-from-ts/`)
- [ ] **FIX sutra-from-ts: interface field reads return zeros at runtime.** The TS
  `interface`->axon path emits `p.item("x")` without `.real()`, so `interface_pass`
  COMPILES but returns a zero vector instead of 25 (the harness only compile-tests,
  never runs — that's how it hid). Add `.real()` to numeric axon field reads AND a
  run-on-substrate test so it can't regress silently. See the finding above. (The
  if/else CastExpr + dropped-else bugs were already fixed; this axon bug is the
  remaining known TS defect.)

### Priority 3 — new-language frontends (each `sdk/sutra-from-<lang>/`, model on `sutra-from-ocaml`)
Each: source reader (`tree-sitter-<lang>`) -> `lower.py` -> `.su` emission ->
fixtures that compile **AND run on the substrate** (the OCaml harness's
`_RUNNABLE_FIXTURES` pattern, not the TS compile-only bar). Functional first
(they map cleanly), then Rust, then WASM.
- [ ] **Scala** — `sdk/sutra-from-scala/` (`tree-sitter-scala`).
- [ ] **F#** — `sdk/sutra-from-fsharp/` (ML-family, close cousin of OCaml — should reuse much of the OCaml lowering shape).
- [ ] **Elixir / Erlang** — `sdk/sutra-from-erlang/` (the BEAM pair; immutable, message-passing maps onto the axon IPC story).
- [ ] **Clojure** — `sdk/sutra-from-clojure/` (Lisp; homoiconic, persistent data structures).
- [ ] **Haskell** — `sdk/sutra-from-haskell/` (purest; laziness + typeclasses are the hardest edges — last of the functional set).
- [ ] **Rust** — `sdk/sutra-from-rust/` (the imperative language that maps cleanly: expression-oriented, immutable-by-default, algebraic enums + exhaustive match).
- [ ] **WASM** — Phase 3 (todo.md), tied to the `WASM/` subtree once integrated.

### Cross-cutting (any frontend)
- [ ] End-to-end verification: each fixture's `.su` compiles AND runs AND
  reproduces ground-truth output (beyond the parse+codegen syntax check the TS
  harness does today). [OCaml's `_RUNNABLE_FIXTURES` already does this — the
  pattern to extend to every frontend.]
- [ ] CI: no workflow currently runs the `sdk/sutra-from-*` frontends. Consider a
  `transpilers-ci.yml` that installs the tree-sitter grammars + runs every
  `sutra-from-*` test suite. Scope decision — not auto-started.

## Pinned tail (always present — bracket every session)

Per CLAUDE.md §"Autonomous productivity loop" lifecycle: a fresh session
starts the three crons up front; the tail ensures they're still running +
summarizes. Not consumed between fires.

- **A. Ensure the crons run** (`CronList`; re-create work-loop :03,
  auto-flush :15, status-report :42, AskUserQuestion blocker-sweep :50 if
  missing; `durable: false`). See the Handoff section at the top.
- **B. End-of-session status report** (reporting only, no commits): what
  advanced (shas + one-line), queue state, how the rails held, blockers,
  test health.

## Parked / longer-horizon (in todo.md)

C → Sutra transpiler (`sdk/sutra-from-c/`, parked, keep in tree); Promises
Stage-3 / container-method-dispatch / multi-statement try-catch; TS
transpiler closeout; website visual remake; Yantra migration tail (dim-audit
`examples/*.su`; migrated-demo docs/headers; lessons-learned writeup).

## Pointers

- Substrate-leak catalogue: `Audit.md`. Longer-horizon: `todo.md`.
- Findings (dated): `planning/findings/`. Open design questions:
  `planning/open-questions/`. Devlog: `DEVLOG.md`.
- Corpus repo: `github.com/EmmaLeonhart/sutra-w2c-corpus` (submodule
  `corpus/`) + `huggingface.co/datasets/EmmaLeonhart/sutra-w2c-corpus`.
- Yantra (downstream OS): `../Yantra/`.
