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

## Emma says do this now (2026-05-30)

1. **Switch to Gemma for generating the training-data code** (task #17,
   ACTIVE). Use Gemma (LLM via ollama) to generate new Sutra program
   variations for the weights↔code corpus, instead of / on top of the
   fixed structure-template grammar in `experiments/weight_to_code_corpus.py`.
   Validate each generated `.su` compiles + runs on the substrate; keep the
   valid ones; attach randomized/trained weights + IO. Investigate gemma
   availability in ollama + the generation API first. **Open design point
   to confirm with Emma: does Gemma replace the template grammar entirely,
   or augment it?** (next AskUserQuestion if she's away.)
2. **Clear up the queue** — addressed by the 2026-05-30 rewrite (this file).
   Root cause was my discipline failure (left SHIPPED logs instead of
   deleting completed items), NOT a lost rule.
3. **Check CLAUDE.md queue rules** — DONE: the rules are intact (lines
   59-61, 72, 313: remove completed items in the same commit; queue is not
   a status snapshot; deleted on completion). No "cube"/"queue" rule was
   lost. The bloat came from me not following them; fixed going forward.

## Active

- **#10 — bake the trained d=768 category matrix to a `load_matrix` .su.**
  The category matrix beat identity on held-out retrieval (80% vs 62%,
  `experiments/trainable_category_matrix.py`). Bake the trained weights to
  a CSV, emit a `load_matrix`-backed `.su` (`apply(vector x){ matrix M =
  load_matrix("…csv"); return Tensor.MatrixMul(M, x); }`), recompile, run
  held-out word embeddings through it, verify top-1 retrieval reproduces —
  the weight→legible-Sutra-source loop on a real semantic operator. 768²
  CSV is large (write to a scratch/HF dir, don't commit the bulk).
  A `--bake` path in the experiment + a finding.

- **Self-propagation corpus (weights↔code) — built; now scaling/diversity.**
  Shipped: optional `llm_model`, `load_matrix`, the generator (10 structures
  × weight-kinds incl. trained_rotation/trained_perm), the `corpus/` submodule
  (`EmmaLeonhart/sutra-w2c-corpus`, public) + HF dataset mirror
  (`experiments/mirror_corpus_to_hf.py`). Workflow: generate into `corpus/`
  → commit+push submodule → mirror to HF → bump the Sutra pointer. Open:
  Gemma-generated code (#17 above); scale N (more seeds/K); a category/
  semantic trained kind (needs embeddings). Detail: DEVLOG 2026-05-29.

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
