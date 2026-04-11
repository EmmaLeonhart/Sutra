# Sutra

**A vector programming language whose primitives are hypervectors in embedding space.**

🌐 **Website: <https://emmaleonhart.github.io/Sutralang>** — vision, interactive demos, tutorials, and the papers that ground the language. Built from `docs/` by [`pages.yml`](.github/workflows/pages.yml) and deployed automatically on every push.

Conventional languages compile to machine instructions that execute on silicon. Sutra compiles to *vector operations* that execute inside a pre-trained embedding space — making the execution environment fundamentally semantic rather than symbolic. Where silicon arithmetic has no inherent meaning, the geometry of an embedding space *does*. Sutra is the first programming language designed to exploit that as a first-class computational substrate.

The name comes from the Sanskrit *ākaśa* — the primordial medium that pervades all things. The language operates in the continuous semantic space that pervades trained embedding models.

---

## What's in this repo

| Directory | What it is |
|---|---|
| [`sutra-paper/`](sutra-paper/) | The white paper *"Sutra: A Vector Programming Language for Computation in Embedding Spaces"* — language design, three-tier operation model, sign-flip binding, empirical initiation, fly-brain extension. Source: `paper.md`. Reproduction recipe: `SKILL.md`. |
| [`fly-brain-paper/`](fly-brain-paper/) | The compile-to-brain paper — *"Running Sutra on a Simulated Fly Brain"*. Same compiler targeting a Brian2 mushroom-body simulation, 16/16 decisions correct across four program variants. |
| [`fly-brain/`](fly-brain/) | Runtime: Brian2 LIF circuit, hypervector ↔ spike bridge, FlyBrainVSA class, the compile-to-brain demos, the e2e test. |
| [`sdk/sutra-compiler/`](sdk/sutra-compiler/) | The reference compiler. Hand-written lexer, parser, validator, AST → FlyBrainVSA codegen, JUnit-style test corpus. CLI: `python -m sutra_compiler`. |
| [`sdk/intellij-sutra/`](sdk/intellij-sutra/) | IntelliJ Platform plugin (v0.2 scaffold). Lexer, syntax highlighting, brace matching, completion, live templates, settings UI, external annotator wired to `sutrac --json`. Build with `./gradlew runIde` or, from the repo root, `!editor.bat`. |
| [`sdk/vscode-sutra/`](sdk/vscode-sutra/) | Lighter VS Code extension — TextMate grammar + snippets. The IntelliJ plugin is the reference IDE; this is the convenience option. |
| [`planning/sutra-spec/`](planning/sutra-spec/) | The language specification: design principles, operation model, control flow, type system, runtime architecture, lambda calculus encoding, Turing-completeness argument, embedding pathologies, IDE architecture, VSA builtins. |
| [`planning/`](planning/) | Architecture/strategy docs (sutra pivot, fly-brain architecture, fly-brain visualizer, competition analyses, paper strategy). |
| [`examples/`](examples/) | Hand-written `.su` source examples — language tour. |
| [`docs/`](docs/) | Source for the GitHub Pages website at <https://emmaleonhart.github.io/Sutralang>. |
| [`scripts/`](scripts/) | Repo-wide scripts: `paper_submit_and_fetch.py` (clawRxiv submission + review polling), competition analysis fetchers. |
| [`sutraDB/`](sutraDB/) | The lightweight bundled vector database, brought in as a git subtree. *"SQLite-of-vector-databases"* — embedded, zero-config, optimized for the kinds of queries Sutra emits. |
| [`chats/`](chats/) | Design conversations and notes. The Sutra vision page on the website is built from `chats/sutra-vision-graph-to-vector-leap.md`. |

A historical snapshot of the **Latent Space Cartography** paper (*"...Reveals a Silent Tokenizer Defect in mxbai-embed-large"*) lives in `VSA-paper/`. That paper's primary source of truth is its own repo at [`EmmaLeonhart/latent-space-cartography`](https://github.com/EmmaLeonhart/latent-space-cartography) — it is currently at **Strong Accept** on clawRxiv as [post 1127](http://18.118.210.52/posts/1127). The snapshot here is for cross-referencing only and is not maintained from this repo.

## Papers live on clawRxiv

| Paper | clawRxiv post | Local source |
|---|---|---|
| Sutra: A Vector Programming Language for Computation in Embedding Spaces | [post 1542](http://18.118.210.52/posts/1542) | [`sutra-paper/paper.md`](sutra-paper/paper.md) |
| Running Sutra on a Simulated Fly Brain | [post 1541](http://18.118.210.52/posts/1541) | [`fly-brain-paper/paper.md`](fly-brain-paper/paper.md) |
| Latent Space Cartography (Strong Accept) | [post 1127](http://18.118.210.52/posts/1127) | [`VSA-paper/paper.md`](VSA-paper/paper.md) (stale snapshot) |

---

## Three things Sutra can do today

1. **Run programs on LLM embedding spaces.** Sign-flip binding achieves 14/14 correct recoveries at 14 bundled role-filler pairs across GTE-large, BGE-large, and Jina-v2. Sustains 10/10 chained bind-unbind-snap cycles. Multi-hop composition across structures works. See [`sutra-paper/`](sutra-paper/) and the website's [Bind and unbind](https://emmaleonhart.github.io/Sutralang/tutorials/02-bind-and-unbind/) tutorial.
2. **Compile programs onto a fly brain.** The same compiler targets a Brian2 spiking simulation of the *Drosophila melanogaster* mushroom body. 16/16 decisions correct across four program variants × four input conditions. To our knowledge this is the first programming language whose conditional semantics compile mechanically onto a connectome-derived spiking substrate. See [`fly-brain-paper/`](fly-brain-paper/) and [`fly-brain/`](fly-brain/).
3. **Open up in an IDE.** Run `!editor.bat` from the repo root (Windows) and a sandbox IntelliJ IDEA Community boots with the Sutra plugin preinstalled and the project tree open. Drop a `.su` file into it for highlighting, completion, live templates, and `sutrac` diagnostics.

---

## Get started

```bash
git clone https://github.com/EmmaLeonhart/Sutralang
cd Sutra/sdk/sutra-compiler
python -m sutra_compiler ../../examples/01-objects-and-methods.su
```

That validates one example file with zero diagnostics.

The full reference workflow — vision page, tutorials, interactive widget, papers, and the rest of the docs — is at <https://emmaleonhart.github.io/Sutralang>.

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
