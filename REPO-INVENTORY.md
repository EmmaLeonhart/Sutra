# 📜 Repository Inventory

What is in this repository, what it is for, and whether it is still
in active use. For the **narrative history** of how the repo got to
this layout, read [`DEVLOG.md`](DEVLOG.md). This file is a
point-in-time snapshot of the tree as of the current commit.

The Sutra ecosystem is a monorepo spanning a programming language, a
vector database, a reference compiler, two IDE plugins, a website,
and two papers. The scroll emoji 📜 is the ecosystem's branding across
all of it — Sanskrit *sūtra* ("thread/aphorism/grammar") and
SutraDB already adopted a scroll favicon in March 2026.

---

## Language + compiler + runtime

### `sutra-paper/`
**The main paper** for Claw4S 2026. *"Sutra: A Vector Programming
Language for Computation in Embedding Spaces."* Language design,
three-tier operation model, sign-flip binding breakthrough, empirical
initiation, fly-brain extension. Source in `paper.md`; reproduction
recipe in `SKILL.md`. Historical review fetches in `reviews/`
(v1/v2/v3). Experiment scripts in `scripts/`.

### `fly-brain-paper/`
**The compile-to-brain paper.** *"Running Sutra on a Simulated Fly
Brain."* Same compiler (`sutra_compiler`) targeting a Brian2 spiking
simulation of the *Drosophila melanogaster* mushroom body. 16/16
decisions correct across four program variants × four input
conditions. Source in `paper.md`, reviews (v1–v4) in `reviews/`.

### `fly-brain/`
Runtime and experiments for the biological substrate. Brian2 LIF
circuit (`mushroom_body_model.py`), hypervector ↔ spike bridge
(`vsa_operations.py`), `FlyBrainVSA` class, the four-state conditional
demo, the programmer-control proof (`programmer_control_demo.py`,
4 programs × 4 inputs = 16 executions), and the AST→brain end-to-end
test (`test_codegen_e2e.py`). `STATUS.md` is the living status doc
for this substrate; `DOOM.md` is the now-legendary "how far from
playing Doom on a fly brain" gap analysis.

### `sdk/`

- **`sdk/sutra-compiler/`** — the reference compiler.
  `sutra_compiler` Python package with hand-written lexer, parser,
  syntactic validator, AST nodes, diagnostics, workspace loader
  (`workspace.py`, parses `atman.toml`), and the `codegen_flybrain`
  backend. CLI: `python -m sutra_compiler <file.su>` or the
  `sutrac` console-script alias. 101 unit tests covering the parser,
  lexer, validator, and workspace model.
- **`sdk/intellij-sutra/`** — IntelliJ Platform plugin. Kotlin
  package `org.sutra.intellij.*`. File type + language registration
  for `.su`, hand-written lexer, color settings page, brace
  matcher, commenter, quote handler, keyword/primitive/builtin
  completion, live templates, external annotator shelling out to
  `sutra_compiler --json` for diagnostics, Settings → Tools → Sutra
  `Configurable`, embedding-space and fly-brain visualizer tool
  windows (JCEF + Canvas 2D), and the Sutra Workspace tool window
  for `atman.toml` project browsing. Build with `./gradlew runIde`
  or `!editor.bat` from the repo root on Windows.
- **`sdk/vscode-sutra/`** — VS Code extension. TextMate grammar,
  snippets, commands for validate-file and validate-workspace,
  diagnostic wire-up. The IntelliJ plugin is the reference IDE; the
  VS Code extension is the lighter convenience option.

### `examples/`
Hand-written `.su` programs illustrating the language. Six
numbered tutorials covering objects/methods, functions-vs-methods,
types/casts, control flow, operators/strings, and executable files.
Plus `examples/workspace/` — a two-project example workspace
(`corpus`, `similarity`) demonstrating the `atman.toml` format end
to end.

### `sutra-demo-program.su`
The repo-root demo program, loaded by `!editor.bat` into the
sandbox IDE to smoke-test the plugin.

---

## Database

### `sutraDB/`
**SutraDB**, the vector-native RDF-star triplestore. Merged into
this monorepo as a git subtree on 2026-04-10 with full history
preserved (see DEVLOG for the subtree-merge commit `16e71d6`).

Core crates:
- `sutra-core/` — LSM storage, IRI interning, SPO/POS/OSP indexes,
  RDF-star quoted triple IDs
- `sutra-hnsw/` — HNSW vector index, predicate registry
- `sutra-sparql/` — SPARQL 1.1 parser, planner, executor, SPARQL+
  extensions (VECTOR_SIMILAR, property paths, pseudo-tables)
- `sutra-proto/` — HTTP server, SPARQL Protocol, Graph Store Protocol
- `sutra-cli/` — `sutra serve`, query, import, export, health, mcp
- `sutra-ffi/` — C FFI for Sutra Studio

SDKs in `sutraDB/sdks/`: Python, Go, TypeScript, Java with
client-side OWL validation enabled by default. Protégé plugin in
`sutraDB/protege-plugin/`. Flutter client (Sutra Studio) in
`sutraDB/sutra-studio/`. Static HTML landing site in
`sutraDB/pages/`, mounted on the main Sutra Pages deploy at
`/SutraDB/` by `.github/workflows/pages.yml`.

SutraDB maintains its own `CLAUDE.md`, `README.md`, and `DEVLOG`.
Because GitHub Actions only runs workflows at the root of the
repo, SutraDB's internal `.github/workflows/*.yml` are NOT picked
up; the root-level `sutradb-ci.yml` and `sutradb-integration.yml`
mirror the essential jobs.

---

## Specification + planning

### `planning/sutra-spec/`
Formal language specification, one Markdown file per topic. 23
files in the current layout:
- `01-design-principles.md` through `19-substrate-candidates.md` —
  the language's mathematical and semantic backbone
- `20-ide-architecture.md` — the IDE vision (visualizers, MCP
  surface, PSI parser, solution/workspace model)
- `21-builtins.md` — formal signatures for every VSA builtin
  (`bind`, `unbind`, `bundle`, `similarity`, `permute`, `compose`,
  `basis_vector`, `permutation_key`, `identity_permutation`,
  `snap`, `argmax_cosine`)
- `22-workspaces.md` — the `atman.toml` workspace/project format
  spec

### `planning/` (root, not in `sutra-spec/`)
Architecture/strategy/status documents that aren't part of the
formal spec:
- `fly-brain-architecture.md`, `fly-brain-visualizer.md` — design
  documents for the biological substrate and its IDE visualizer
- `competition-analysis-*.md` — time-stamped snapshots of the
  Claw4S 2026 leaderboard (daily and ad-hoc), plus
  `competition-analysis-latest.md` regenerated every 6 hours by
  `.github/workflows/competition-cron.yml`
- `akasha-pivot.md`, `akasha-paper-strategy.md` — frozen historical
  records of the Akasha-era decisions, preserved under the old
  name as time-stamps

### `sutra-syntax-decisions.md`, `sutra-language-comparisons.md`
Root-level design docs about why the language looks the way it
does (C# baseline, fuzzy semantics, geometric truthiness,
defuzzy-on-cast, class system not runtime-special).

### `fly-brain-program-plan.md`
Original plan for "what does running Sutra on a simulated fly brain
look like" — literal *Drosophila* connectome, 8-line program, four
program variants. Still the north star for the fly-brain paper.

---

## Website + docs

### `docs/`
MkDocs Material source for the Sutra language website. Built by
`.github/workflows/pages.yml` on every push and deployed to
`https://emmaleonhart.github.io/Sutra/`.

- `index.md` — landing page
- `vision.md` — "the graph-to-vector leap"
- `interactive/graph-to-linear-algebra.md` — interactive widget
- `tutorials/01-hello-sutra.md`, `02-bind-and-unbind.md`,
  `03-snap-to-nearest.md`
- `papers.md` — links to both papers
- `assets/js/graph-to-vector.js` — interactive widget JavaScript

### `mkdocs.yml`
MkDocs configuration. Nav includes a `SutraDB: /Sutra/SutraDB/`
entry that jumps out of the MkDocs tree to the mounted SutraDB
static site (copied from `sutraDB/pages/` by the pages workflow).
The full `/Sutra/SutraDB/` path is required because MkDocs treats
a leading slash as domain-root-absolute, and the GitHub Pages
site is served at `emmaleonhart.github.io/Sutra/`, so SutraDB
lives at `/Sutra/SutraDB/`, not `/SutraDB/`.

---

## Historical / reference

### `VSA-paper/`
**Locked at Strong Accept.** The FOL discovery paper, *"Latent
Space Cartography Applied to Wikidata Reveals a Silent Tokenizer
Defect in mxbai-embed-large"*, currently at Strong Accept on
clawRxiv as post 1127 (v15+). The primary source of truth for this
paper lives in its own repo at `EmmaLeonhart/latent-space-cartography`;
the copy here is a frozen snapshot. Provides the empirical
foundation for Sutra: 86 predicates as vector ops, r=0.861
consistency-accuracy correlation, mxbai [UNK] defect discovery.
**Do not touch** without coordinating with the other repo.

### `chats/`
Design conversation archive. ~20 markdown transcripts of Claude
conversations that produced the Sutra design ideas, named by
topic (sutra-vision-graph-to-vector-leap,
running-akasha-on-fly-brain, akasha-programming-language-pronunciation,
logit-lens-and-mechanistic-interpretability, etc.). These are
historical; filenames preserve the Akasha-era identity.

### `many-to-many/`
Sutra-adjacent research. A three-part matching primitive for
embedding spaces (directional selection + orthogonal projection +
residual similarity) addressing many-to-many relations that
cosine similarity conflates. Perfect precision in 6/9 experiments
across 3 datasets × 3 models. Maps directly to Sutra's
"computation is geometry" philosophy.

### `old-stuff/`
All superseded content consolidated here on 2026-04-09:

| Subdirectory | What |
|---|---|
| `vsa-paper-old/` | Former `VSA-paper/old/` — 165 files of old scripts, competition analyses, `redoing-paper/` prototype code (semantic topology, syllogism gap, taxonomic direction, Linnaean hierarchy, word2vec projections) |
| `competition-analysis/` | Early Claw4S competitor analyses |
| `papers/` | Earlier paper versions (economics, mxbai-undersymbolic) |
| `planning/` | Original project vision, roadmap, strategic discussion |
| `mxbai-diacritic-glitch/` | Standalone demo of the mxbai [UNK] collapse defect |

### `inquisitive-transformer/`
Independent paper directory that was kept after the 2026-04-09
cleanup decided it should be deleted — current state of the
directory is unclear and the user may have changed their mind.
Not part of the active Sutra tree either way.

---

## Scripts + CI

### `scripts/`
Repo-wide Python scripts, mostly for clawRxiv interaction:
- `paper_submit_and_fetch.py` — submit a paper to clawRxiv and
  poll for the AI review
- `fetch_all_papers.py`, `fetch_reviews.py`, `fetch_top_papers.py`
  — pull competition data from clawRxiv
- `write_competition_summary.py` — regenerate
  `planning/competition-analysis-latest.md` from the fetched JSON
- `competition_analysis_raw.json`, `competition_reviews.json` —
  cached clawRxiv data, refreshed every 6 hours by competition-cron

### `.github/workflows/`
| Workflow | Path filter | What it does |
|---|---|---|
| [`papers-ci.yml`](.github/workflows/papers-ci.yml) | `sutra-paper/**`, `fly-brain-paper/**` | Auto-submits the changed paper(s) to clawRxiv, polls for the AI review, commits the review back. Skip with `Skip-Submit: true` trailer. |
| [`pages.yml`](.github/workflows/pages.yml) | `docs/**`, `mkdocs.yml`, `README.md`, `planning/sutra-spec/**`, `sutraDB/pages/**` | Builds the MkDocs site, rsyncs `sutraDB/pages/` into `_site/SutraDB/`, deploys to GitHub Pages. |
| [`sutradb-ci.yml`](.github/workflows/sutradb-ci.yml) | `sutraDB/**` | Runs SutraDB Rust `check` / `test` / `clippy` against the subtree. |
| [`sutradb-integration.yml`](.github/workflows/sutradb-integration.yml) | `sutraDB/**` | Builds `sutra` binary, starts the server, inserts N-Triples fixture, verifies SPARQL roundtrips, runs Python/Go/TypeScript SDK test suites against the live DB. |
| [`competition-cron.yml`](.github/workflows/competition-cron.yml) | schedule: `0 4,10,16,22 * * *` UTC (4x/day) | Fetches fresh paper + review data from clawRxiv, regenerates `competition-analysis-latest.md`, auto-commits with `Skip-Submit: true` trailer. |
| [`submit-papers.yml`](.github/workflows/submit-papers.yml) | `workflow_dispatch` only | Legacy single-paper submission workflow. Day-to-day path is `papers-ci.yml`. |

---

## Top-level files

| File | Purpose |
|---|---|
| `README.md` | User-facing overview — what the project is, what's in it, how to get started. |
| `CLAUDE.md` | Agent-facing project instructions. Read by every Claude Code session. |
| `DEVLOG.md` | **Full narrative history** of the repository from its initial commit to now. Read front-to-back for the story of how the current layout emerged. |
| `REPO-INVENTORY.md` | This file. |
| `todo.md` | Open work items and pending decisions. |
| `sutra-demo-program.su` | The canonical demo program loaded into the sandbox IDE. |
| `!editor.bat` | Windows launcher for the IntelliJ plugin sandbox. |
| `!runClaude.bat` | Windows launcher for Claude Code. |

---

## Summary table

| Area | Status | Core to Sutra? |
|---|---|---|
| `sutra-paper/`, `fly-brain-paper/` | Active | Core (Claw4S papers) |
| `sdk/sutra-compiler/` | Active | Core (reference compiler) |
| `sdk/intellij-sutra/` | Active | Core (reference IDE) |
| `sdk/vscode-sutra/` | Active | Convenience |
| `fly-brain/` | Active | Core (substrate) |
| `planning/sutra-spec/` | Active | Core (language spec) |
| `examples/` | Active | Core (tutorial corpus) |
| `sutraDB/` | Active (in maintenance) | Core (storage) |
| `docs/` | Active | Core (website) |
| `scripts/` | Active | Infrastructure |
| `.github/workflows/` | Active | Infrastructure |
| `VSA-paper/` | Locked | Foundation (Strong Accept) |
| `many-to-many/` | Reference | Adjacent research |
| `chats/` | Archive | Historical |
| `DEVLOG.md` | Active | Historical narrative |
| `old-stuff/` | Archive | Historical |
| `inquisitive-transformer/` | Unclear | Not Sutra |
