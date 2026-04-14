# 📜 Sutra

**A vector programming language whose primitives are hypervectors in embedding space.**

The 📜 scroll is Sutra's project-wide branding — the Sanskrit *sūtra* is literally a thread/string of aphorisms, the word used for Pāṇini's foundational Sanskrit grammar (the earliest known formal grammar of any language), and the scroll is the physical artifact that grammars like Pāṇini's were recorded on. SutraDB (the database side of the ecosystem) already adopted a scroll favicon on 2026-03-14, so the brands align across the language and the store.

🌐 **Website: <https://emmaleonhart.github.io/Sutra>** — vision, interactive demos, tutorials, and the papers that ground the language. Built from `docs/` by [`pages.yml`](.github/workflows/pages.yml) and deployed automatically on every push. SutraDB's own docs are mounted at [`/SutraDB/`](https://emmaleonhart.github.io/Sutra/SutraDB/) on the same site — one integrated ecosystem, one domain.

Conventional languages compile to machine instructions that execute on silicon. Sutra compiles to *vector operations* that execute inside a pre-trained embedding space — making the execution environment fundamentally semantic rather than symbolic. Where silicon arithmetic has no inherent meaning, the geometry of an embedding space *does*. Sutra is the first programming language designed to exploit that as a first-class computational substrate.

**Sutra has no control flow.** Every branch is a continuous weighted blend (`select`, softmax over options), every loop is a geometric rotation that keeps moving, and every loop exit is a gate on a defuzzified trajectory state — not a jump, not a back-branch, not a stop-check-test. Two primitives (`select` and `gate`) replace the entire `if`/`else`/`while`/`for`/`switch` family. The consequences are the pitch: **GPU-native and connectionist-native execution** (no branch predictor, no divergent warps — everything is a matmul, a sum, or a cosine), **end-to-end differentiable** (the things that normally break backprop are not in the language), and **decompilable in principle** from trained connectionist systems (the primitives are geometric, so a trained system can be characterized as a composition of them). See [`planning/sutra-spec/26-select-and-gate.md`](planning/sutra-spec/26-select-and-gate.md) for the canonical framing.

The name comes from the Sanskrit *sūtra* — "thread" / "rule" / "aphorism," the word used for Pāṇini's foundational grammar of Sanskrit. A programming language descended etymologically from the earliest known formal grammar is a better fit than the language's original name (*ākaśa*, "aether/space"), which is preserved throughout `DEVLOG.md` and the `chats/` archive as the earlier identity. The rename happened on 2026-04-11 — see the DEVLOG entry for that date for the full commit-by-commit breakdown.

📖 **Architectural overview: [`ARCHITECTURE.md`](ARCHITECTURE.md)** — the "under the hood" tour. What Sutra is, what `.su` source looks like, what the compiler does with it, what the emitted code actually runs on (numpy, Brian2 spiking, real connectome), the three-tier operation model, how control flow works, and the VSA math foundations. Also mirrored on the website at [`/architecture/`](https://emmaleonhart.github.io/Sutra/architecture/).

---

## What's in this repo

| Directory | What it is |
|---|---|
| [`sutra-paper/`](sutra-paper/) | The **embedding-operations paper**: *"Sign-Flip Binding and Vector Symbolic Operations on Frozen LLM Embedding Spaces"*. Empirical characterization of which VSA operations work on natural embeddings and at what capacity (sign-flip binding 14/14 across GTE/BGE/Jina, etc.). Despite the directory name this is not the Sutra language paper — the language paper is on hold pending the connectionist-computer substrate work; see STATUS.md. Source: `paper.md`. |
| [`fly-brain-paper/`](fly-brain-paper/) | The compile-to-brain paper — *"Running Sutra on the Drosophila Hemibrain Connectome"*. Same compiler targeting a Brian2 mushroom-body simulation, 16/16 decisions correct across four program variants. |
| [`fly-brain/`](fly-brain/) | Runtime: Brian2 LIF circuit, hypervector ↔ spike bridge, FlyBrainVSA class, the compile-to-brain demos, the e2e test. |
| [`sdk/sutra-compiler/`](sdk/sutra-compiler/) | The reference compiler. Hand-written lexer, parser, validator, AST → FlyBrainVSA codegen, JUnit-style test corpus. CLI: `python -m sutra_compiler`. |
| [`sdk/intellij-sutra/`](sdk/intellij-sutra/) | IntelliJ Platform plugin (v0.2 scaffold). Lexer, syntax highlighting, brace matching, completion, live templates, settings UI, external annotator wired to `sutrac --json`. Build with `./gradlew runIde` or, from the repo root, `!editor.bat`. |
| [`sdk/vscode-sutra/`](sdk/vscode-sutra/) | Lighter VS Code extension — TextMate grammar + snippets. The IntelliJ plugin is the reference IDE; this is the convenience option. |
| [`planning/sutra-spec/`](planning/sutra-spec/) | The language specification: design principles, operation model, control flow, type system, runtime architecture, lambda calculus encoding, Turing-completeness argument, embedding pathologies, IDE architecture, VSA builtins. |
| [`planning/`](planning/) | Architecture/strategy docs (sutra pivot, fly-brain architecture, fly-brain visualizer, competition analyses, paper strategy). |
| [`examples/`](examples/) | Hand-written `.su` source examples — language tour. |
| [`docs/`](docs/) | Source for the GitHub Pages website at <https://emmaleonhart.github.io/Sutra>. |
| [`scripts/`](scripts/) | Repo-wide scripts: `paper_submit_and_fetch.py` (clawRxiv submission + review polling), competition analysis fetchers. |
| [`sutraDB/`](sutraDB/) | The lightweight bundled vector database, brought in as a git subtree. *"SQLite-of-vector-databases"* — embedded, zero-config, optimized for the kinds of queries Sutra emits. |
| [`chats/`](chats/) | Design conversations and notes. The Sutra vision page on the website is built from `chats/sutra-vision-graph-to-vector-leap.md`. |

The **Latent Space Cartography** paper (*"...Reveals a Silent Tokenizer Defect in mxbai-embed-large"*) — the empirical foundation that motivated the Sutra pivot — lives in its own repo at [`EmmaLeonhart/latent-space-cartography`](https://github.com/EmmaLeonhart/latent-space-cartography) and as clawRxiv [post 1127](http://18.118.210.52/posts/1127) (Strong Accept). The previous stale snapshot under `VSA-paper/` has been removed from this repo; cite as (Leonhart, 2026) when referenced.

## File types

| Extension / filename | Belongs to | What it is |
|---|---|---|
| `.su` | Sutra language | Source code. The language's primary unit of compilation. Every `.su` file is either an object declaration, a module, or a standalone executable. |
| `atman.toml` | Sutra language | Workspace / project manifest. Fixed filename (not an extension) — every Sutra workspace and project root has exactly one. `[workspace]` table = multi-project workspace; `[project]` table = single project. Spec: [`planning/sutra-spec/22-workspaces.md`](planning/sutra-spec/22-workspaces.md). |
| `.sdb` | SutraDB | Binary database file. The on-disk storage format for a SutraDB instance — analogous to a SQLite `.db` file. Never committed; ignored via `.gitignore`. |
| `.post_id` | CI / clawRxiv | One-line file containing the integer post ID assigned by clawRxiv after a paper is first submitted. Written by `papers-ci.yml`; consumed by subsequent submissions to route updates to the correct post. |

**Historical / renamed:**

| Old extension | Replaced by | Notes |
|---|---|---|
| `.ak` | `.su` | Akasha (pre-rename) source files. Renamed 2026-04-11 when the language was renamed from Ākaśa to Sutra. |
| `.aksln` / `.akproj` | `atman.toml` | Old workspace / project manifest formats from the Akasha era. |

## Papers live on clawRxiv

| Paper | clawRxiv post | Local source |
|---|---|---|
| Sign-Flip Binding and Vector Symbolic Operations on Frozen LLM Embedding Spaces | [post 1542](http://18.118.210.52/posts/1542) | [`sutra-paper/paper.md`](sutra-paper/paper.md) |
| Running Sutra on the Drosophila Hemibrain Connectome | [post 1541](http://18.118.210.52/posts/1541) | [`fly-brain-paper/paper.md`](fly-brain-paper/paper.md) |
| Latent Space Cartography (Strong Accept) | [post 1127](http://18.118.210.52/posts/1127) | [`EmmaLeonhart/latent-space-cartography`](https://github.com/EmmaLeonhart/latent-space-cartography) (separate repo) |

---

## Three things Sutra can do today

1. **Run programs on LLM embedding spaces.** Sign-flip binding achieves 14/14 correct recoveries at 14 bundled role-filler pairs across GTE-large, BGE-large, and Jina-v2. Sustains 10/10 chained bind-unbind-snap cycles. Multi-hop composition across structures works. See [`sutra-paper/`](sutra-paper/) and the website's [Bind and unbind](https://emmaleonhart.github.io/Sutra/tutorials/02-bind-and-unbind/) tutorial.
2. **Compile programs onto a fly brain.** The same compiler targets a Brian2 spiking simulation of the *Drosophila melanogaster* mushroom body. 16/16 decisions correct across four program variants × four input conditions. To our knowledge this is the first programming language whose conditional semantics compile mechanically onto a connectome-derived spiking substrate. See [`fly-brain-paper/`](fly-brain-paper/) and [`fly-brain/`](fly-brain/).
3. **Open up in an IDE.** Run `!editor.bat` from the repo root (Windows) and a sandbox IntelliJ IDEA Community boots with the Sutra plugin preinstalled and the project tree open. Drop a `.su` file into it for highlighting, completion, live templates, and `sutrac` diagnostics.

---

## Get started

```bash
git clone https://github.com/EmmaLeonhart/Sutra
cd Sutra/sdk/sutra-compiler
python -m sutra_compiler ../../examples/01-objects-and-methods.su
```

That validates one example file with zero diagnostics.

The full reference workflow — vision page, tutorials, interactive widget, papers, and the rest of the docs — is at <https://emmaleonhart.github.io/Sutra>.

---

## CI workflows

| Workflow | Triggers on | What it does |
|---|---|---|
| [`papers-ci.yml`](.github/workflows/papers-ci.yml) | Push to master that touches `sutra-paper/` or `fly-brain-paper/`; manual `workflow_dispatch` | Submits the changed paper(s) to clawRxiv via [`scripts/paper_submit_and_fetch.py`](scripts/paper_submit_and_fetch.py), polls for the AI peer review, and commits the review back into the paper's `reviews/` directory. |
| [`pages.yml`](.github/workflows/pages.yml) | Push to master that touches `docs/`, `mkdocs.yml`, `README.md`, or `planning/sutra-spec/` | Builds the website with MkDocs Material and deploys it to GitHub Pages. |
| [`sutradb-ci.yml`](.github/workflows/sutradb-ci.yml) | Push to master that touches `sutraDB/` | Runs the SutraDB Rust tests (check, test, clippy) so the subtree stays green. |
| [`submit-papers.yml`](.github/workflows/submit-papers.yml) | Manual `workflow_dispatch` only | Legacy single-paper submission workflow. Kept around for one-off backfills; the day-to-day path is `papers-ci.yml`. |

---

## License

Open source. Same license across the language, the compiler, the IntelliJ plugin, the runtime, and the papers.
