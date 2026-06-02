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

1. **Runtime: attachable RAM device + `ram_read`/`ram_write` on `_VSA`.**
   Port `experiments/ntm_ram/ram_device.py` into the runtime as an
   optional `_VSA.ram`. `ram_read(ptr_vec)` decodes ptr at the I/O wire
   (`real()`), reads the device, returns the value vector; `ram_write`
   the mirror. Host attaches the device (the orchestrator's role).
2. **Codegen: recognize `ramRead`/`ramWrite` builtins.** `ramRead(ptr)`
   emits a RAM-pending `Promise` carrying ptr; `ramWrite(ptr,data)` emits
   `_VSA.ram_write(...)`. Additive — new builtin names only.
3. **`await_value` resolves RAM-pending promises via the attached device**
   (the producer), leaving regular-promise behavior unchanged (KEEP
   `test_await_substrate_pure` 4/4). No device attached → stays
   pending / clear error, never a fake value.
4. **Test:** an inline `.su` (`number x = await ramRead(ptr); ...`) +
   `ramWrite` round-trip against an attached device; reproduce stored
   values exactly. Substrate audits: model-free → tiny dim; ptr is a VRAM
   number; RAM access is IO at the boundary (not claimed substrate).
5. **Migrate a demo** (`experiments/ntm_ram` read head) to the inline
   surface; confirm same measured output.

Open follow-up (todo.md): model-free hash-keyed-role axon for the mailbox
dim cost; multi-program/Yantra separable-orchestrator mailbox (the demos'
recur+axon pattern stays valid for that).

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
