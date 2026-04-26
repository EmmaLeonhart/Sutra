# 📜 Sutra

**Sutra is a geometrically compiled language where logical operations over vector spaces are resolved at compile time into matrix multiplications.**

🌐 **Website: <https://sutralang.dev>** — vision, demos, tutorials, language reference. Built from `docs/` by [`pages.yml`](.github/workflows/pages.yml). SutraDB's docs are mounted at [`/SutraDB/`](https://sutralang.dev/SutraDB/) on the same site.

## What Sutra is

Sutra source looks like TypeScript. It parses to an AST, gets simplified, validated, and emitted as self-contained Python that calls into a small runtime class (`_VSA`) implementing the Sutra primitives — `bundle`, `bind`, `unbind`, `similarity`, `argmax_cosine`, `select`, `loop`. Those primitives are tensor operations: matmul, elementwise multiply/add, cosine, softmax-weighted sum. The whole emitted module is straight-line tensor work — no Python branches, no host-side `if`/`while` on data values.

The composition is the point. Once a whole program has the same shape — values are vectors, operations are tensor ops on vectors — the compiler can read the program as one tensor expression and fold chains of operations into cached matrices at compile time. A chain of bind/unbind/bundle reduces to a sequence of matrix multiplies that the simplifier can fuse. That's the win the language is structured around.

A typical Sutra value is a vector in a frozen LLM embedding space. The current default substrate is `nomic-embed-text` (768-d, mean-centered, served via Ollama). Strings auto-embed in vector contexts, so `vector v = "cat"` means "embed the string 'cat' through the substrate and bind it to `v`." The runtime caches embeddings and batches Ollama round-trips at module init.

## What runs today

Two backends, both produce a self-contained Python module:

- **`codegen.py`** — emits numpy-flavored Python. Used by the in-repo smoke test as the reference path.
- **`codegen_pytorch.py`** — emits torch tensor ops, picks CUDA at module init if available, falls back to CPU.

The CLI is `python -m sutra_compiler`. Validate a file: `sutrac path/to/file.su`. Emit the generated torch module to stdout: `sutrac --emit path/to/file.su`. Compile and run: `sutrac --run path/to/file.su`.

The demo programs live in [`examples/`](examples/). The smoke test [`examples/_smoke_test.py`](examples/_smoke_test.py) compiles and executes 13 of them end-to-end:

| `.su` program | What it exercises |
|---|---|
| `hello_world.su` | embed + retrieve, the minimal program |
| `fuzzy_branching.su` | weighted-superposition conditional, 4 program variants × 4 inputs |
| `role_filler_record.su` | structured record as a flat vector via `bundle(bind(role, filler))` |
| `classifier.su` | bundled-prototype classifier, 3 classes × 3 examples |
| `analogy.su` | associative pair memory, capital → country |
| `knowledge_graph.su` | bundled triples, compositional query |
| `predicate_lookup.su` | multi-object superposition, member/non-member separation |
| `fuzzy_dispatch.su` | N-way dispatch returning structured records |
| `nearest_phrase.su` | 20-phrase codebook, clean and noisy retrieval |
| `sequence.su` | position-bound 5-token sequence, decode any position |
| `loop_rotation.su` | `loop(cond)` as eigenrotation with terminal `argmax_cosine` |
| `counter_loop.su` | `loop(cond)` as a helical counter — Turing-complete loop demonstration |
| `concept_search.su` | `loop(cond)` over a richer codebook |

## Repo layout

| Directory | What it is |
|---|---|
| [`sdk/sutra-compiler/`](sdk/sutra-compiler/) | The reference compiler. Hand-written lexer, parser, simplifier, validator, codegen. CLI entrypoint: `python -m sutra_compiler`. |
| [`sdk/intellij-sutra/`](sdk/intellij-sutra/) | IntelliJ Platform plugin. Lexer, syntax highlighting, brace matching, completion, live templates, settings UI, external annotator wired to `sutrac --json`. Build with `./gradlew runIde` or run [`!editor.bat`](editor.bat) from the repo root. |
| [`sdk/vscode-sutra/`](sdk/vscode-sutra/) | VS Code extension — TextMate grammar plus snippets. The IntelliJ plugin is the reference IDE; this is the lighter option. |
| [`planning/sutra-spec/`](planning/sutra-spec/) | The language specification: vision, operations, binding, control flow, equality and defuzzification, types, program structure, concurrency, open questions. |
| [`planning/findings/`](planning/findings/) | Dated experimental findings — what was measured, with raw numbers and what they mean. Includes negative results. |
| [`planning/open-questions/`](planning/open-questions/) | Known design gaps where the implementation has made a choice the spec doesn't yet justify. |
| [`examples/`](examples/) | Demo `.su` programs and the smoke-test harness. |
| [`docs/`](docs/) | Source for the website at <https://sutralang.dev>. |
| [`sutraDB/`](sutraDB/) | SutraDB — embedded vector database, brought in as a git subtree. |
| [`chats/`](chats/) | Design conversations preserved as historical record. |

The empirical foundation that motivated Sutra — relational-displacement structure in frozen embedding spaces — lives in [`EmmaLeonhart/latent-space-cartography`](https://github.com/EmmaLeonhart/latent-space-cartography).

## File types

| Name | Belongs to | What it is |
|---|---|---|
| `.su` | Sutra | Source code. |
| `atman.toml` | Sutra | Workspace / project manifest. Fixed filename, one per workspace or project root. Spec: [`planning/sutra-spec/program-structure.md`](planning/sutra-spec/program-structure.md). |
| `.sdb` | SutraDB | Binary database file. Analogous to a SQLite `.db`. |

## Get started

```bash
git clone https://github.com/EmmaLeonhart/Sutra
cd Sutra
python examples/_smoke_test.py
```

To inspect the generated Python for a single example:

```bash
python -m sutra_compiler --emit examples/hello_world.su
```

To open the repo in an IDE with syntax support, run [`!editor.bat`](editor.bat) (Windows) — a sandbox IntelliJ IDEA Community boots with the Sutra plugin preinstalled.

## CI

| Workflow | Triggers on | What it does |
|---|---|---|
| [`pages.yml`](.github/workflows/pages.yml) | Push to master touching `docs/`, `mkdocs.yml`, `README.md`, or `planning/sutra-spec/` | Builds the website with MkDocs Material and deploys to GitHub Pages. |
| [`sutradb-ci.yml`](.github/workflows/sutradb-ci.yml) | Push to master touching `sutraDB/` | Runs the SutraDB Rust tests. |

## License

Open source. Same license across the language, the compiler, the IntelliJ plugin, and the runtime.
