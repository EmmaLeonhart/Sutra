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

## Context (read first, do not work on)

- **`paper/paper.md` is on arXiv and FROZEN through May 31, 2026.** Lock
  lifts automatically **2026-06-01**. Do not edit it (typos, findings,
  next-venue polish) until then. `paper/neurips/` is under its own
  separate **permanent** freeze. If a later result contradicts either,
  stop and tell Emma — don't silently amend. (DEVLOG 2026-05-20.)
- **Promise/await is fit-to-spec** (verified 2026-05-20;
  `test_await_substrate_pure.py` 4/4). Guarded by the watchdogs below.

## Handoff — START HERE (fresh session)

The session pivoted to the **weight→code seq2seq** build (Emma 2026-05-30
AskUserQuestion: *source generation*). Ticks 1 (data prep) + 2 (model+train)
are done + pushed; **tick 3 (substrate-grounded eval) is next — task #21.**
A new session's first moves, in order:

1. **Start the four local crons** (CLAUDE.md §"Autonomous productivity
   loop"): work-loop `3 * * * *`, auto-flush `15 * * * *`, status-report
   `42 * * * *`, AskUserQuestion blocker-sweep `50 * * * *` — all
   `durable: false`. A fresh session has none running; create them first.
2. **Ensure the corpus submodule is present** — `git submodule update
   --init corpus` (the dataset source lives there; tick 2 needs it).
3. **Regenerate the gitignored dataset** — `py
   experiments/w2c_seq2seq/prepare.py`. `data/` is NOT committed, so a fresh
   clone won't have it. Confirm `data/{train,val}.jsonl` + `vocab.json`
   appear (2160 / 240 / vocab 45). Sanity: `pytest
   experiments/w2c_seq2seq/test_prepare.py` → 4/4.
4. **Do task #21 — tick 3, substrate-grounded eval** (the Active item
   below). The trained checkpoint `data/model.pt` is also gitignored, so a
   fresh session must first `py experiments/w2c_seq2seq/model.py` to retrain
   (~minutes on GPU; converges to ~0.84 val exact-match) before running the
   tick-3 eval over the val split.

**A.0 — decisions blocked on Emma:** none right now. (The big one is
already answered: model approach = source generation / seq2seq.) If a fork
appears mid-build, surface it via AskUserQuestion, don't guess.

## Active — weight→code seq2seq (Emma: source generation)

The end goal: a model that GENERATES `.su` source from a program's weights
+ IO — real decompilation, Emma's explicit pick over a structure classifier.
Host-side ML (torch/CUDA) over the corpus — analysis/training, NOT a Sutra
substrate op (the substrate enters only at tick 3, on *generated* source).
Three bounded ticks:

1. ~~Data prep~~ **DONE** (`experiments/w2c_seq2seq/prepare.py` +
   `test_prepare.py`, 4/4, `eb8140a9`): reads `corpus/corpus.jsonl`,
   NORMALIZES the source (`load_matrix("<csv>")` → `load_matrix("<weight
   name>")` so the filename that encodes the answer is canonicalized out of
   the generation target; the weight VALUES become the model input), char
   tokenizer (vocab 45), split BY id → 2160 train / 240 val, max target 261.
2. ~~Model + training~~ **DONE** (`model.py` + `test_model.py`, `f9a7ef14`):
   1.48M-param Transformer seq2seq (weights+IO → source). 40-epoch CUDA run,
   converged held-out (n=240): val_loss 0.0028, token-acc 0.9991, greedy
   **exact-match 0.842**. Checkpoint → gitignored `data/model.pt`.
3. **Substrate-grounded eval — NEXT (task #21).** The metric that makes
   "weight→code" real: take the GENERATED source, re-substitute the real CSV
   (reverse the `load_matrix("M0")` normalization), compile, run on the
   substrate, and check it **reproduces the held-out program's IO** =
   decompilation accuracy. An 84%-exact-match generation should mostly pass,
   but tick 3 MEASURES it on the substrate rather than assuming it. Report
   the gap between exact-match and IO-reproduction (the non-exact-match
   generations that still reproduce IO are the interesting wins).

Caveat to measure honestly (don't paper over): the template source space is
constrained (10 structures + load_matrix refs), so v0 generation is close to
structure-inference + templating; the Gemma free-form entries + the IO-
reproduction eval (tick 3) are what keep it non-trivial. Report real numbers.

## Corpus (built & at scale — not active work)

The weights↔code corpus is built and at **2400 programs** (10 structures ×
6 K {4,6,8,10,12,16} × 4 weight-kinds × 10 seeds), on the `corpus/`
submodule (`EmmaLeonhart/sutra-w2c-corpus`) + HF mirror, both consistency-
guarded (`test_weight_to_code_corpus.py`, `test_gemma_codegen_corpus.py`).
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
