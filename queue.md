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

- *(none open — W2C coefficient-wall direction decided 2026-05-31: bigger
  model/corpus; now the live item under "Active — W2C".)*

## Context (read first, do not work on)

- **`paper/paper.md` is on arXiv and FROZEN through May 31, 2026.** Lock
  lifts automatically **2026-06-01**. Do not edit it (typos, findings,
  next-venue polish) until then. `paper/neurips/` is under its own
  separate **permanent** freeze. If a later result contradicts either,
  stop and tell Emma — don't silently amend. (DEVLOG 2026-05-20.)
- **Promise/await is fit-to-spec** (verified 2026-05-20;
  `test_await_substrate_pure.py` 4/4). Guarded by the watchdogs below.

## Active — RAM pointers → Neural Turing Machine (Emma 2026-06-01, barrel through)

Spec: `planning/sutra-spec/ram-pointers.md`. Sutra gets pointers to RAM
(host memory, distinct from VRAM), accessed as an I/O device via a
modified `await`. An **orchestrator** (the first external `await`
producer — `axon-io.md` left this open) bridges VRAM mailbox slots to
host RAM. Surface: `number x = await ramRead(pointer);` /
`ramWrite(pointer, data);`. **Read the spec's "honesty line" before
implementing** — the program is substrate-pure on VRAM; the
orchestrator does host I/O + decode/encode at the wire only.

**Read runtime DONE** (`259b1765`, `f354a523`; DEVLOG 2026-06-01). The
orchestrator (first external `await`/I/O producer), the host RAM device,
and BOTH addressing modes run on the substrate and recover text exactly:
sequential scan (`text_scan.su` → "HELLO, RAM!") and data-dependent
pointer-chase (`chase.su` → "WORLD" at non-sequential addresses
[0,5,2,9,4]). Audits clean; regression guard
`sdk/sutra-compiler/tests/test_ntm_ram.py` (3 passing). Remaining:

1. **Runtime: the `ramWrite` path.** Orchestrator services a write
   mailbox → host RAM write. Faithful version has the program control
   BOTH pointer and data; the clean substrate encoding is `make_complex`
   (data in real, address in imag) mirroring the chase read — but
   emitting independently-chosen (data, addr) from `.su` needs either a
   source-level `real()`/`imag()` accessor or a `swap_ri` primitive
   exposed (non-halting-loop.md notes the missing accessor). DECIDE:
   expose the small primitive vs. orchestrator-sequential write address
   for v1. Build it, RUN it (write a substrate-generated sequence to
   RAM, read it back, verify exact), then extend `test_ntm_ram.py`.
2. **Surface: parse + validate `ramRead` / `ramWrite`.** `number x =
   await ramRead(ptr);` and `ramWrite(ptr, data);` lex/parse/validate,
   lowering `ramRead` through the `await`→`Promise`→`while_loop` path
   (`promises.md`) with the orchestrator as producer. Today the demos
   wire the orchestrator by hand around a `recur` loop; the surface
   sugar is what makes `await ramRead(pointer)` write as Emma specced.
3. **Finding: NTM-RAM vs substrate-RNN text-gen.** Same task (emit a
   string), two architectures — external addressable RAM vs internal
   recurrence. Write up under `planning/findings/`; the payoff Emma
   named. (The RAM-read half is demonstrated; pair it against the
   substrate-RNN text-gen demo.)

Deferred (todo.md): reservoir computing (OS-era); differentiable/soft
addressing for the *trainable* NTM (open question — hard addressing
first, do not substitute soft now).

## Active — W2C weight→code (option A hardening complete; next levers)

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

**LIVE — scale model + corpus (Emma 2026-05-31 decision).** Test whether the
coefficient wall is **capacity-bound** rather than architectural.
1. ~~Bigger model~~ **DONE — NOT capacity-bound.** d256/L6 (≈4–8× params) left
   the probe flat (~0.60) and coeff-family IO flat-to-down (0.31→0.23); decoder
   unchanged. Finding § "Capacity test". Points at the readout architecture, not
   capacity.
2. **Bigger corpus** (IN FLIGHT — background job running since 2026-06-01).
   Generate 2× (`--seeds 0,..,19`, 7200 programs) to SCRATCH (NO submodule/HF
   push — measure first), re-prepare, retrain d128/L3 detached-probe
   (`--coeff-aux-w 0.5 --coeff-detach`), re-measure probe + coeff-family IO.
   Expected (given model-null): also flat → wall is architectural, not data. If
   it DOES help, do the official regen + push + HF + pointer bump.
   - **Detached background pipeline:** `experiments/w2c_seq2seq/_drive_2x.sh`
     (gitignored scratch). It waits for the scratch corpus, then prepare→train→
     eval. Progress/results land in `experiments/w2c_seq2seq/_drive_2x.log`
     (ends with a `DONE` line); generation log `_scratch_gen.log`. `prepare`
     clobbers the regenerable `data/` baseline (its metrics are in the
     coeff-head finding) — fine.
   - **Next cron tick:** if `_drive_2x.log` ends in `DONE`, harvest the eval
     numbers (decoder exact / canonical-exact-IO / probe coeff_a,b / `io_base`
     coeff-family IO) into the coeff-head finding under a "Bigger-corpus test"
     section, draw the architectural-vs-data conclusion, delete this item; if
     still running, report "w2c 2x in flight" and do NOT relaunch.

## Corpus (built & at scale — not active work)

The weights↔code corpus is built and at **3600 programs** (15 structures ×
6 K {4,6,8,10,12,16} × 4 weight-kinds × 10 seeds), on the `corpus/`
submodule (`EmmaLeonhart/sutra-w2c-corpus`) + HF mirror (in sync, `d464fdb`),
both consistency-guarded (`test_weight_to_code_corpus.py`, `test_gemma_codegen_corpus.py`).
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
