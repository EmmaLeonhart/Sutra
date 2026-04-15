# 📜 Sutra

**A vector programming language whose primitives are hypervectors in embedding space.**

The 📜 scroll is Sutra's project-wide branding — the Sanskrit *sūtra* is literally a thread/string of aphorisms, the word used for Pāṇini's foundational Sanskrit grammar (the earliest known formal grammar of any language), and the scroll is the physical artifact that grammars like Pāṇini's were recorded on. SutraDB (the database side of the ecosystem) already adopted a scroll favicon on 2026-03-14, so the brands align across the language and the store.

🌐 **Website: <https://emmaleonhart.github.io/Sutra>** — vision, interactive demos, tutorials, and the papers that ground the language. Built from `docs/` by [`pages.yml`](.github/workflows/pages.yml) and deployed automatically on every push. SutraDB's own docs are mounted at [`/SutraDB/`](https://emmaleonhart.github.io/Sutra/SutraDB/) on the same site — one integrated ecosystem, one domain.

**Sutra is a purely functional programming language whose values are hypervectors and whose programs compile to straight-line matrix operations.** There is no `print`, no IO primitive, no side effect a function body can invoke — every computation is a deterministic vector-to-vector map, and the only escape from the pure region is a final name lookup at the program's edge. This is the same structural property that makes a Haskell program "partial" in the sense that values leave the pure body only at the IO boundary.

**Sutra has no control flow.** Every branch is a continuous weighted blend (`select`, softmax over options), every loop is a geometric rotation, and every loop exit is a gate on a defuzzified trajectory state — not a jump, not a back-branch. Two primitives (`select` and `gate`) replace the entire `if`/`else`/`while`/`for`/`switch` family. Because nothing compiles to a machine branch, programs lower to sequences of matmuls, sums, and cosines — which makes the compilation target **GPU-native** in principle (no branch predictor, no divergent warps) and **end-to-end differentiable** (the things that normally break backprop are not in the language). See [`planning/sutra-spec/26-select-and-gate.md`](planning/sutra-spec/26-select-and-gate.md) for the canonical framing.

The working runtime today is **pure numpy on CPU** (`sdk/sutra-compiler/sutra_compiler/codegen_numpy.py`). The same compiler pipeline admits a PyTorch/GPU backend as a refactor target — the generated code is already matrix-only, so the port is mechanical. A separate experimental backend targets a *Drosophila* mushroom-body spiking simulator; that work lives in [`fly-brain/`](fly-brain/) and its own paper, and is not the language's substrate or the primary demo.

The name comes from the Sanskrit *sūtra* — "thread" / "rule" / "aphorism," the word used for Pāṇini's foundational grammar of Sanskrit. A programming language descended etymologically from the earliest known formal grammar is a better fit than the language's original name (*ākaśa*, "aether/space"), which is preserved throughout `DEVLOG.md` and the `chats/` archive as the earlier identity. The rename happened on 2026-04-11 — see the DEVLOG entry for that date for the full commit-by-commit breakdown.

📖 **Architectural overview: [`ARCHITECTURE.md`](ARCHITECTURE.md)** — what Sutra is, what `.su` source looks like, what the compiler does with it, what the emitted code runs on. Also mirrored on the website at [`/architecture/`](https://emmaleonhart.github.io/Sutra/architecture/).

---

## What's in this repo

| Directory | What it is |
|---|---|
| [`language-paper/`](language-paper/) | The **Sutra language paper**: *"Sutra: A Control-Flow-Free Programming Language for Hyperdimensional Computing"*. The language, the compiler, the numpy runtime, the three demo programs. Source: `paper.md`. |
| [`sutra-paper/`](sutra-paper/) | The **embedding-operations paper**: *"Sign-Flip Binding and Vector Symbolic Operations on Frozen LLM Embedding Spaces"*. Empirical characterization of which VSA operations work on natural LLM embeddings (sign-flip binding 14/14 across GTE/BGE/Jina). Establishes the operation set; does not propose a language. Source: `paper.md`. |
| [`fly-brain-paper/`](fly-brain-paper/) | Separate experimental paper — *"Running Sutra on the Drosophila Hemibrain Connectome"*. Sign-flip binding + fuzzy branching executed on a Brian2 mushroom-body spiking simulator. An alternative substrate for the operation set, not the language's primary runtime. |
| [`fly-brain/`](fly-brain/) | Runtime for the fly-brain paper: Brian2 LIF circuit, hypervector ↔ spike bridge, `FlyBrainVSA` class. Segregated from the language's demo path. |
| [`sdk/sutra-compiler/`](sdk/sutra-compiler/) | The reference compiler. Hand-written lexer, parser, validator, two codegen backends: `codegen_numpy.py` (demo path, self-contained matrix ops) and `codegen_flybrain.py` (fly-brain-specific). CLI: `python -m sutra_compiler`. |
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

| Paper | Local source |
|---|---|
| Sutra: A Control-Flow-Free Programming Language for Hyperdimensional Computing | [`language-paper/paper.md`](language-paper/paper.md) |
| Sign-Flip Binding and Vector Symbolic Operations on Frozen LLM Embedding Spaces | [`sutra-paper/paper.md`](sutra-paper/paper.md) |
| Running Sutra on the Drosophila Hemibrain Connectome | [`fly-brain-paper/paper.md`](fly-brain-paper/paper.md) |
| Latent Space Cartography (Strong Accept, clawRxiv [post 1127](http://18.118.210.52/posts/1127)) | [`EmmaLeonhart/latent-space-cartography`](https://github.com/EmmaLeonhart/latent-space-cartography) (separate repo) |

---

## Three programs that run today

The demo path — source through the numpy backend to named output. All three run under `python examples/_smoke_test.py`; 23/23 outputs match the committed reference.

1. **[`examples/hello_world.su`](examples/hello_world.su)** — the minimal program. Embed a greeting, retrieve it from a codebook by cosine similarity. No control flow; the single escape from the pure region is the final name lookup.
2. **[`examples/fuzzy_branching.su`](examples/fuzzy_branching.su)** — branches without branching. A 4-way fuzzy conditional encoded as a weighted superposition (`Σ wᵢ · behaviorᵢ`) with `wᵢ = similarity(query, prototypeᵢ)`. Four program variants × four inputs = 16 decisions, all correct.
3. **[`examples/role_filler_record.su`](examples/role_filler_record.su)** — structured records as flat vectors. `record = bundle(bind(role_i, filler_i))`; `decode_field(record, role) = argmax_cosine(unbind(record, role), codebook)`. Textbook VSA demonstration with zero control flow at decode time.

---

## Get started

```bash
git clone https://github.com/EmmaLeonhart/Sutra
cd Sutra
python examples/_smoke_test.py
```

One command, no setup beyond numpy. Expected output: `PASS` and 23 individual `OK` lines. The runner compiles each `.su` source through `sdk/sutra-compiler` to self-contained Python and executes it.

To see the generated Python for any example:

```bash
PYTHONIOENCODING=utf-8 python -m sutra_compiler --emit-numpy examples/hello_world.su
```

You can also open the repo in an IDE with syntax support: run `!editor.bat` from the repo root (Windows) and a sandbox IntelliJ IDEA Community boots with the Sutra plugin preinstalled.

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
