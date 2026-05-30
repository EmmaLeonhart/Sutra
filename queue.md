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
   Every entry is self-consistency-checked. HF mirror lags one regen (Active
   step 2 — pending Emma's okay on the outward publish).

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

**Decision made (Emma, AskUserQuestion 2026-05-30): (A) Harden the corpus +
retrain.** The 84.2% is inflated by a small, templated program space, so the
model is largely template-matching, not inferring. Add harder families
(deeper chains, mixed scaled+residual, varied coefficients) so weights→code
needs real inference and the ±x failure gets stress-tested. See the
"Active — W2C corpus hardening (Emma: option A)" section below for the plan.

**About the restart.** The hourly crons (work-loop / auto-flush / status /
blocker-sweep) are session-local — restarting the computer kills them and
this session, so the next session must recreate them (see Pinned tail). All
work is committed and pushed. `data/` (dataset + model checkpoint) is
gitignored, so re-running the model means: `git submodule update --init
corpus` → `py experiments/w2c_seq2seq/prepare.py` → `…/model.py` →
`…/eval_substrate.py`.

## Context (read first, do not work on)

- **`paper/paper.md` is on arXiv and FROZEN through May 31, 2026.** Lock
  lifts automatically **2026-06-01**. Do not edit it (typos, findings,
  next-venue polish) until then. `paper/neurips/` is under its own
  separate **permanent** freeze. If a later result contradicts either,
  stop and tell Emma — don't silently amend. (DEVLOG 2026-05-20.)
- **Promise/await is fit-to-spec** (verified 2026-05-20;
  `test_await_substrate_pure.py` 4/4). Guarded by the watchdogs below.

## Active — W2C corpus hardening (Emma: option A)

Goal: make weights→code require **inference**, not template-matching, and
stress-test the measured failure (model drops the additive `±x` term). Add
harder program families to `experiments/weight_to_code_corpus.py`, regen,
retrain, re-eval, compare numbers. Bounded ticks:

1. ~~Generator: harder families~~ **DONE** (`test_harder_families.py` 10/10,
   existing corpus consistency 2/2). Added `COEFFS=[0.5,1,1.5,2,3]` drawn
   per-program (deterministic from id) + 5 families: `chain4`, `scaled_res`
   (`a·M@x + x`), `gen_affine` (`a·M@x + b·x`), `scaled_diff` (`a·M@x − b·x`),
   `two_mat_affine` (`a·M0@x + b·M1@x`) — 15 structures total. Each verified
   to compute its intended formula on the substrate (output vs host
   reference < 1e-4) and to emit its coefficient as a source literal.
   Existing 10 families untouched (committed 2400 corpus + tests stay valid).
2. ~~Regen full corpus + push~~ **DONE on GitHub** (corpus `03336b9`, Sutra
   pointer bumped). 3600 programs (15 structures × 6 K × 4 kinds × 10 seeds),
   5760 weight CSVs, 14400 IO pairs; consistency test 2/2 on the substrate;
   README card stats updated. **HF mirror PENDING Emma authorization** — the
   auto-mode classifier blocked the outward publish (`mirror_corpus_to_hf.py`)
   as an unverified-destination external push; re-run it once Emma okays it
   (auth is cached, `whoami`=EmmaLeonhart). Does NOT block step 3.
3. **Retrain + re-eval, compare** (NOW ACTIONABLE). Re-run prepare/model/eval_substrate.
   Report the new exact-match + substrate IO-reproduction vs the 0.842
   baseline, and specifically whether the coeff families recover `a`/`b`
   (per-family breakdown). Honest expected outcome: exact-match likely DROPS
   (the space is now harder) — that drop is the point (it shows the v0 was
   templating). Update the finding.

## Corpus (built & at scale — not active work)

The weights↔code corpus is built and at **3600 programs** (15 structures ×
6 K {4,6,8,10,12,16} × 4 weight-kinds × 10 seeds), on the `corpus/`
submodule (`EmmaLeonhart/sutra-w2c-corpus`; HF mirror lags by one regen —
see Active step 2), both consistency-guarded (`test_weight_to_code_corpus.py`, `test_gemma_codegen_corpus.py`).
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
