# Agents — start here

This file is the index for AI agents and contributors landing in the Sutra repository. It is **not** for humans browsing the website — humans read `sutralang.dev` (sourced from `docs/`). See §"Audiences" in `CLAUDE.md` for the split.

## What Sutra is, in one sentence

A purely functional programming language whose primitives are tensor operations on frozen-LLM embedding vectors. Source files (`.su`) compile to self-contained PyTorch Python that calls a small runtime; every operation is a tensor op on the substrate.

The fuller story is in `CLAUDE.md` §"Project Overview". The full empirical and design story is in `paper/paper.md`.

## Read these first, in order

1. **`CLAUDE.md`** — the rules of engagement. Safety constraints, math discipline (no shortcuts, no numpy at runtime), paper-frozen status, planning-folder conventions, audience split.
2. **`queue.md`** — what is being worked on right now. Top of stack. Always update in the same commit as the work.
3. **`todo.md`** — longer-horizon agenda. Items migrate `todo.md` → `queue.md` → deleted on completion.
4. **`planning/sutra-spec/`** — the canonical language spec. Read the file relevant to the operation you are touching before you touch it. `planning/sutra-spec/README.md` is the entry point.

If you only have time for two files: `CLAUDE.md` and `queue.md`.

## File-by-file map

### Operating-rules files (top level)

| File | Audience | Purpose |
|---|---|---|
| `CLAUDE.md` | agents, contributors | Safety rules, math discipline, paper status, planning folder conventions, audience split. **Authoritative.** |
| `AGENTS.md` | agents, contributors | This file. Top-level index. |
| `README.md` | anyone | Short repo overview. Less load-bearing than `CLAUDE.md`. |
| `queue.md` | agents, contributors | Active work, in strategic order. Top item is the current focus. |
| `todo.md` | agents, contributors | Longer-horizon agenda. |
| `DEVLOG.md` | agents, contributors | Full devlog history. Append-only. |

### The language and runtime

| Path | What's there |
|---|---|
| `sdk/sutra-compiler/` | The compiler. `sutra_compiler/` is the Python package; `tests/` is the test suite; `stdlib/` holds the `.su` standard library that gets inlined into user code. |
| `sdk/intellij-sutra/` | IntelliJ plugin (syntax highlighting, completion, external annotator, settings). |
| `sdk/vscode-sutra/` | VS Code extension (TextMate grammar, snippets). |
| `examples/` | `.su` programs. The smoke-tested ten plus reference material. `examples/_smoke_test.py` is the end-to-end driver. |
| `experiments/` | One-off scripts that aren't part of the main pipeline. |
| `tests/` | Top-level integration tests; per-component tests live next to their component. |
| `sutraDB/` | The bundled vector database (subtree). Less mature than the compiler. |
| `scripts/` | Utility scripts (paper submission, reference fetching, etc.). |

### Planning, spec, and findings

| Path | What's there |
|---|---|
| `planning/sutra-spec/` | Canonical language spec. Authoritative for what each operation computes. |
| `planning/sutra-spec-deprecated/` | Read-only reference. Older spec drafts kept for cross-checking. |
| `planning/findings/` | Dated experimental results. Negative and mixed findings live here too — they are required, not optional. |
| `planning/open-questions/` | Design gaps where the implementation made a call the spec doesn't justify yet. |
| `planning/exploratory/` | Ideas not yet tried. |
| `planning/semantic-corrections.md` | Pinned corrections to wording / framing the user has flagged before. Honor these. |

### Paper

| Path | What's there |
|---|---|
| `paper/paper.md` | **FROZEN.** The canonical NeurIPS 2026 submission. Do not edit any part of it. See `CLAUDE.md` §"Paper is FROZEN" for the precise rule. |
| `paper/supplementary/` | The NeurIPS supplementary archive. Same freeze rule. |
| `paper/reviews/` | clawRxiv AI peer review responses, auto-committed by the CI workflow. Signal, not verdicts. |
| `paper/.post_id` | Tracks the latest clawRxiv post in the supersedes chain. |

### Website source

| Path | What's there |
|---|---|
| `docs/` | Hand-written Markdown for `sutralang.dev`. **Human audience.** Do not embed internal-scratchpad references (`queue.md`, `todo.md`, `planning/...`, deep `sdk/...` paths) into these files. If you find such a reference, strip it — it's the cross-leakage that the 2026-05-07 sweep (commit `b98b795`) was about. |
| `mkdocs.yml` | Site config. |

## How to work in this repo

The full rules are in `CLAUDE.md` §"Workflow Rules". Short version:

- **Commit early, often, and push immediately.** No local-only work.
- **Update `queue.md` in the same commit as the work.** Stale `queue.md` = lost context for the next session.
- **Mirror queue items into the task tool** (`TaskCreate`, `TaskUpdate`). The task tool and `queue.md` are two views of the same list.
- **Do not enter planning-only modes.** All thinking must produce files and commits.
- **Deprecate, don't remove** unless the old thing actively misleads.

## What this repo is *not* for

- Editing the paper. It is frozen.
- Reading the website. The website is for humans at `sutralang.dev`; agents read the repo Markdown directly.
- Implementing Yantra (the Sutra-based OS). That has its own repo at `../Yantra/`. Yantra is downstream of Sutra and downstream of both transpilers — it does not live here.

## When in doubt

`CLAUDE.md` is authoritative. If `AGENTS.md` and `CLAUDE.md` disagree, `CLAUDE.md` wins and `AGENTS.md` should be fixed. Same for any disagreement with `planning/sutra-spec/` on language semantics — the spec wins.
