# Agents — start here

This file is the index for AI agents and contributors landing in the Sutra repository. It is **not** for humans browsing the website — humans read `sutra.noldor.tech` (sourced from `docs/`). See §"Audiences" in `CLAUDE.md` for the split.

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
| `sdk/sutra-from-ts/` | The TypeScript→Sutra transpiler — the most-developed frontend and Yantra's downstream gate (19 fixtures). |
| `sdk/sutra-from-{ocaml,rust,scala,clojure,elixir,erlang,fsharp,haskell,c}/` | Additional language frontends, in active development — each a fixture-tested lowering pass that compiles AND runs its fixtures on the substrate against ground truth. Maturity (fixtures, 2026-06-15): OCaml 45 (the reference frontend), Rust 10, Scala/Clojure/Elixir 9, Fsharp/Haskell 8, Erlang 6, C 2 (parked). All nine share the same lowering shapes — functions → `function`, `if`/`match` → defuzz blend, tail recursion → `while_loop`, foldable non-tail recursion → CPS accumulator trampoline. The "TS is the sole transpiler" framing is retired. |
| `sdk/intellij-sutra/` | IntelliJ plugin (syntax highlighting, completion, external annotator, settings). |
| `sdk/vscode-sutra/` | VS Code extension (TextMate grammar, snippets). |
| `examples/` | `.su` programs. The smoke-tested ten plus reference material. `examples/_smoke_test.py` is the end-to-end driver. |
| `demos/` | Substrate GUI and font demos. `demos/font/` holds `font.su`, the `font_bound*.su` family, the `cycle_step` substrate-RNN, and font tests; `demos/gui/` holds `count.su`, `toggle.su`, `frame.su`, `window.py`, and GUI tests. Has its own CI: `.github/workflows/demos-ci.yml`. |
| `experiments/` | One-off scripts that aren't part of the main pipeline. |
| `tests/` | Top-level integration tests; per-component tests live next to their component. |
| `sutraDB/` | The bundled vector database (subtree). Less mature than the compiler. |
| `scripts/` | Utility scripts (paper submission, reference fetching, etc.). |
| `sutrac.py` | Top-level compiler entry-point shim. |

### Planning, spec, and findings

| Path | What's there |
|---|---|
| `planning/sutra-spec/` | Canonical language spec. Authoritative for what each operation computes. |
| `planning/findings/` | Dated experimental results. Negative and mixed findings live here too — they are required, not optional. |
| `planning/open-questions/` | Design gaps where the implementation made a call the spec doesn't justify yet. |
| `planning/exploratory/` | Ideas not yet tried. |
| `planning/issues/` | Tracked design/implementation issues. |
| `planning/semantic-corrections.md` | Pinned corrections to wording / framing the user has flagged before. Honor these. |

### Paper

| Path | What's there |
|---|---|
| `paper/neurips/` | The camera-ready NeurIPS 2026 submission (`paper.md`, `paper.tex`, supplementary). The edit-freeze was **retired 2026-06-18** — editable to fix factual drift (don't rewrite the submitted science). The immutable record is git commit `ea6f8a01`. See `CLAUDE.md` §"NeurIPS freeze is LIFTED". |
| `paper/paper.md` | The live, evolving paper (next-venue draft); the website's `/paper/` renders from this. **Time-boxed arXiv freeze through May 2026** — see `CLAUDE.md`. |
| `paper/supplementary/` | Live supplementary docs. The frozen NeurIPS copy is under `paper/neurips/supplementary/`. |
| `paper/reviews/` | clawRxiv AI peer review responses, auto-committed by the CI workflow. Signal, not verdicts. |
| `paper/.post_id` | Tracks the latest clawRxiv post in the supersedes chain. |
| `paper/formal-verification/` | The **second, LIVE paper** — formal verification (`paper.md` + `reviews/` + its own `.post_id`). Distinct from the frozen `paper/neurips/`: it is kept in sync with the FV work as obligations land. Auto-submits on push via `.github/workflows/fv-paper-ci.yml`. Ground truth: `planning/sutra-spec/formal-verification.md`. |

### Website source

| Path | What's there |
|---|---|
| `docs/` | Hand-written Markdown for `sutra.noldor.tech`. **Human audience.** Do not embed internal-scratchpad references (`queue.md`, `todo.md`, `planning/...`, deep `sdk/...` paths) into these files. If you find such a reference, strip it — it's the cross-leakage that the 2026-05-07 sweep (commit `b98b795`) was about. |
| `scripts/build_site.py` | Static-site generator for `sutra.noldor.tech` — renders every `docs/*.md` + `paper/paper.md`. No MkDocs. |

## How to work in this repo

The full rules are in `CLAUDE.md` §"Workflow Rules". Short version:

- **Commit early, often, and push immediately.** No local-only work.
- **Update `queue.md` in the same commit as the work.** Stale `queue.md` = lost context for the next session.
- **Mirror queue items into the task tool** (`TaskCreate`, `TaskUpdate`). The task tool and `queue.md` are two views of the same list.
- **Do not enter planning-only modes.** All thinking must produce files and commits.
- **Deprecate, don't remove** unless the old thing actively misleads.

## What this repo is *not* for

- Editing the paper. It is frozen.
- Reading the website. The website is for humans at `sutra.noldor.tech`; agents read the repo Markdown directly.
- Implementing Yantra (the Sutra-based OS). That has its own repo at `../Yantra/`. Yantra is downstream of Sutra and of the TypeScript transpiler (its GUI gate) — it does not live here.

## When in doubt

`CLAUDE.md` is authoritative. If `AGENTS.md` and `CLAUDE.md` disagree, `CLAUDE.md` wins and `AGENTS.md` should be fixed. Same for any disagreement with `planning/sutra-spec/` on language semantics — the spec wins.
