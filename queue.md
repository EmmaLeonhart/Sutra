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

## Active

- **Self-propagation corpus (weights↔code) — built; scale PROGRAMMATICALLY.**
  Shipped: optional `llm_model`, `load_matrix`, the template generator (10
  structures × weight-kinds incl. trained_rotation/trained_perm), Gemma
  free-form codegen (`gemma_codegen_corpus.py`), the `corpus/` submodule
  (`EmmaLeonhart/sutra-w2c-corpus`) + HF mirror. **Emma 2026-05-30 steer:
  programmatic (template) generation is the workhorse for scaling NOW
  (fast, deterministic, clean (code,weights,IO) at volume); Gemma is good
  but FUTURE — keep it built, don't make it the near-term volume path.**
  So scaling = grow the PROGRAMMATIC generator: more structures, K, seeds,
  weight-kinds → big N. **Emma 2026-05-30: scale the corpus much larger
  BEFORE modeling** — generator default bumped to thousands-scale (10
  structures × 6 K {4,6,8,10,12,16} × 4 kinds × 10 seeds = 2400 programs).
  Workflow: generate into `corpus/` → commit+push submodule → mirror to HF
  → bump the Sutra pointer + dataset-card stats. Corpus now at 2400+ (10
  structures × 6 K × 4 kinds × 10 seeds). THEN (her chosen order) the
  weight→code **seq2seq** model (see section below). Also open: a category/
  semantic trained kind (needs embeddings). Detail: DEVLOG 2026-05-29/30.
  (Both corpora have consistency guards.)

## Weight→code seq2seq model (Emma 2026-05-30 AskUserQuestion: source generation)

The corpus is at scale (2400+); now the end goal — a model that GENERATES
`.su` source from a program's weights + IO (real decompilation, not a
structure classifier; Emma's explicit pick). Host-side ML (torch/CUDA) over
the corpus — analysis/training, NOT a substrate op. Build in bounded ticks:

1. ~~Data prep~~ **DONE** (`prepare.py` + `test_prepare.py`, 4/4): reads
   `corpus/corpus.jsonl`, NORMALIZES the source (`load_matrix("<csv>")` →
   `load_matrix("<weight name>")` so the unguessable filename that encodes
   the answer is canonicalized), char tokenizer (vocab 45), split by id
   → 2160 train / 240 val, max target 261 chars. `data/` is a gitignored
   build artifact (regenerate with `py experiments/w2c_seq2seq/prepare.py`).
2. **Model + training (NEXT).** Small seq2seq transformer (torch): encode the
   numeric weights+IO, decode source tokens. Train on the split.
3. **Substrate-grounded eval.** The key metric: generated source, compiled
   with the given weights, **reproduces the held-out program's IO** (the
   corpus consistency invariant applied to GENERATED code) = decompilation
   accuracy; plus token/exact-match. This is what makes "weight→code" real,
   not just plausible-looking source.

Caveat to measure honestly: the template source space is constrained (10
structures + load_matrix refs), so v0 generation is close to structure-
inference + templating; the Gemma free-form entries + the IO-reproduction
eval are what keep it from being trivial. Report the real numbers.

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

- **A. Ensure the three crons run** (`CronList`; re-create work-loop :03,
  auto-flush :15, status-report :42 if missing; `durable: false`).
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
