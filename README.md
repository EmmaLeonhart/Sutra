# 📜 Sutra

**Website · [sutra.topazcomputing.com](https://sutra.topazcomputing.com)**

**Sutra is a geometrically compiled language where logical operations over vector spaces are resolved at compile time into matrix multiplications.**

🌐 **Website: <https://sutra.topazcomputing.com>** — a static site built from the Markdown under [`docs/`](docs/) (one page per file: the homepage plus the concept guides and tutorials) and the paper from [`paper/paper.md`](paper/paper.md) by [`scripts/build_site.py`](scripts/build_site.py), deployed by [`pages.yml`](.github/workflows/pages.yml). It includes the readable paper at `/paper/`, with downloadable PDFs and a reproduction zip.

## What Sutra is

Sutra source looks like TypeScript. It parses to an AST, gets simplified, validated, and emitted as self-contained Python that calls into a small runtime class (`_VSA`) implementing the Sutra primitives — `bundle`, `bind`, `unbind`, `similarity`, `argmax_cosine`, `select`, `loop`. Those primitives are tensor operations: matmul, elementwise multiply/add, cosine, softmax-weighted sum. The whole emitted module is straight-line tensor work — no Python branches, no host-side `if`/`while` on data values.

The composition is the point. Once a whole program has the same shape — values are vectors, operations are tensor ops on vectors — the compiler can read the program as one tensor expression and fold chains of operations into cached matrices at compile time. A chain of bind/unbind/bundle reduces to a sequence of matrix multiplies that the simplifier can fuse. That's the win the language is structured around.

A typical Sutra value is a vector in a frozen LLM embedding space. The current default substrate is `nomic-embed-text` (768-d, mean-centered). The runtime loads that frozen model **in-process** (`sentence-transformers`), so semantic programs run with **no Ollama daemon** — a plain `pip install` is enough. Ollama remains available as an alternate backend via `SUTRA_EMBED_BACKEND=ollama` (the two realizations differ slightly in geometry; see [`sutra_compiler/embedding.py`](sdk/sutra-compiler/sutra_compiler/embedding.py)). Strings auto-embed in vector contexts, so `vector v = "cat"` means "embed the string 'cat' through the substrate and bind it to `v`." The runtime caches embeddings to disk (keyed by model, dim, and backend) and batches the fetches at module init.

## What runs today

Two backends, both produce a self-contained Python module:

- **`codegen_pytorch.py`** — **canonical.** Emits torch tensor ops, picks CUDA at module init if available, falls back to CPU. Axons, the full `Math.*` namespace, the codepoint-array String model, and the rotation-hashmap `dict<K, V>` all live here.
- **`codegen.py`** — numpy backend, **deprecated**. The PyTorch backend is canonical; newer features (axons, the codepoint-array String model, lookup-table transcendentals, the rotation-hashmap `dict<K, V>`) live there and have no numpy equivalent.

The CLI is `python -m sutra_compiler`. Validate a file: `sutrac path/to/file.su`. Emit the generated torch module to stdout: `sutrac --emit path/to/file.su`. Compile and run: `sutrac --run path/to/file.su`. Explore interactively: `sutrac repl` — type an expression and see the result (a number shows its real value; a concept decodes to the nearest known string), with declarations ending in `;` or `}` accumulating as session state.

The demo programs live in [`examples/`](examples/). The smoke test [`examples/_smoke_test.py`](examples/_smoke_test.py) compiles and executes 15 of them end-to-end:

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
| `content_addressed_read.su` | NTM-style content-addressed read head: associative recall |
| `semantic_faq.su` | paraphrased query → right answer by meaning (`embed` + `argmax_cosine`) |
| `strings_and_formatting.su` | concat + interpolation + `int_to_string` |
| `fizzbuzz.su` | `select` superposition + `num_eq` zero-test over a real 1..15 loop |
| `loop_forms.su` | all three loop call forms: by-reference statement, expression, tuple destructure |

Loops use the declared-function form (`do_while_adder.su`, plus `loop_forms.su` for the three call forms — statement by reference, expression `int x = loop f(...)`, tuple destructure `(a, b) = loop g(...)`), exercised by the `test_loop_function_decl.py` and `test_loop_call_expr.py` suites. See [`docs/loops.md`](docs/loops.md) for the shape.

## Repo layout

| Directory | What it is |
|---|---|
| [`sdk/sutra-compiler/`](sdk/sutra-compiler/) | The reference compiler. Hand-written lexer, parser, simplifier, validator, codegen. CLI entrypoint: `python -m sutra_compiler`. |
| [`sdk/intellij-sutra/`](sdk/intellij-sutra/) | IntelliJ Platform plugin. Lexer, syntax highlighting, brace matching, completion, live templates, settings UI, external annotator wired to `sutrac --json`. Build with `./gradlew runIde` or run [`editor.bat`](sdk/intellij-sutra/editor.bat). |
| [`sdk/vscode-sutra/`](sdk/vscode-sutra/) | VS Code extension — TextMate grammar plus snippets. The IntelliJ plugin is the reference IDE; this is the lighter option. |
| [`planning/sutra-spec/`](planning/sutra-spec/) | The language specification: vision, operations, binding, control flow, equality and defuzzification, types, program structure, concurrency, open questions. |
| [`planning/findings/`](planning/findings/) | Dated experimental findings — what was measured, with raw numbers and what they mean. Includes negative results. |
| [`planning/open-questions/`](planning/open-questions/) | Known design gaps where the implementation has made a choice the spec doesn't yet justify. |
| [`examples/`](examples/) | Demo `.su` programs and the smoke-test harness. |
| [`docs/`](docs/) | Hand-written Markdown source for the website at <https://sutra.topazcomputing.com> — the homepage plus concept guides (capabilities, compilation, loops, operators, vision, …) and tutorials. One HTML page per file. |
| [`sutraDB/`](sutraDB/) | SutraDB — embedded vector database, brought in as a git subtree. |

The empirical foundation that motivated Sutra — relational-displacement structure in frozen embedding spaces — lives in [`EmmaLeonhart/latent-space-cartography`](https://github.com/EmmaLeonhart/latent-space-cartography).

## File types

| Name | Belongs to | What it is |
|---|---|---|
| `.su` | Sutra | Source code. |
| `atman.toml` | Sutra | Workspace / project manifest. Fixed filename, one per workspace or project root. Spec: [`planning/sutra-spec/program-structure.md`](planning/sutra-spec/program-structure.md). |
| `.sdb` | SutraDB | Binary database file. Analogous to a SQLite `.db`. |

## Get started

The fast path — install from PyPI, no daemon, no model server, no clone (requires **Python 3.11+**):

```bash
pip install "sutra-dev[runtime,embed]"   # compiler + torch runtime + in-process embedder
printf 'function string main() { return "hello world"; }\n' > hello.su
sutrac --run hello.su                     # -> hello world
```

(The `examples/*.su` programs ship in this source tree, not in the pip package — from a
clone, `sutrac --run examples/hello_world.su` runs the semantic hello; its first run
downloads the frozen embedding model once.)

`[embed]` pulls the in-process embedding backend (`sentence-transformers`), which loads the same frozen `nomic-embed-text` model directly — so you do **not** need Ollama. (Programs that only use `make_real` / matrices / arithmetic embed nothing and need neither extra.) To use Ollama instead, set `SUTRA_EMBED_BACKEND=ollama` and run a daemon with the model pulled.

From a clone, the demo harness compiles and runs the bundled examples end-to-end:

```bash
git clone https://github.com/EmmaLeonhart/Sutra
cd Sutra
python examples/_smoke_test.py
```

To inspect the generated Python for a single example:

```bash
python -m sutra_compiler --emit examples/hello_world.su
```

To open the repo in an IDE with syntax support, run [`sdk/intellij-sutra/editor.bat`](sdk/intellij-sutra/editor.bat) (Windows) — a sandbox IntelliJ IDEA Community boots with the Sutra plugin preinstalled.

## CI

| Workflow | What it does |
|---|---|
| [`compiler-ci.yml`](.github/workflows/compiler-ci.yml) | The main test gate — runs the Sutra compiler test suite. |
| [`demos-ci.yml`](.github/workflows/demos-ci.yml) | Runs the substrate GUI and font demo tests under [`demos/`](demos/). |
| [`daily-audit.yml`](.github/workflows/daily-audit.yml) | Scheduled audit run that keeps [`Audit.md`](Audit.md) current. |
| [`pages.yml`](.github/workflows/pages.yml) | Renders the website pages and deploys them (with the paper PDFs + reproduction zip) to GitHub Pages. |
| [`publish-sutra-compiler.yml`](.github/workflows/publish-sutra-compiler.yml) | Publishes the `sutra-dev` compiler package to PyPI. |
| [`sutradb-ci.yml`](.github/workflows/sutradb-ci.yml) · [`sutradb-integration.yml`](.github/workflows/sutradb-integration.yml) | Run the SutraDB Rust unit + integration tests. |
| `papers-ci.yml` · `submit-papers.yml` · `pull-reviews.yml` · `paper-pdf.yml` | Paper pipeline: submit the paper to clawRxiv on edit, pull back AI reviews, and build the PDFs. |
| [`fv-paper-ci.yml`](.github/workflows/fv-paper-ci.yml) | Auto-submits the formal-verification paper ([`paper/formal-verification/paper.md`](paper/formal-verification/paper.md)) to clawRxiv on edit. |

## License

**GNU AGPL-3.0-only** (see [`LICENSE`](LICENSE)) — the same license across the language, the compiler, the IntelliJ plugin, and the runtime.
