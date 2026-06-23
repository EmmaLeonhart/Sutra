# Tutorials

A guided walk into Sutra. The tutorials are written in the spirit of the *TypeScript Handbook* — short, runnable, code on the left, explanation on the right. No prior knowledge of Vector Symbolic Architectures, Hyperdimensional Computing, or embedding spaces is assumed; the [vision page](../vision.md) is the only thing you should read first, and only if you have not yet had the *"oh, embeddings are spatial, not graphs"* moment land in your head.

Each tutorial is a single `.su` file plus a walkthrough explaining what it does and why every line is the way it is.

## Order of operations

1. **[Hello Sutra](01-hello-sutra.md)** — install, validate your first source file, see the syntax. The "does my toolchain work?" sanity check.
2. **[Bind and unbind](02-bind-and-unbind.md)** — the two operations that make Sutra useful. Why the textbook Hadamard binding fails on natural embedding spaces, and how rotation binding (Sutra's current runtime mechanism) recovers correct fillers.
3. **[Snap-to-nearest](03-snap-to-nearest.md)** — the cleanup step. How long Sutra computations stay numerically stable instead of degrading into noise.
4. **[From TypeScript and JavaScript](04-from-typescript.md)** — take real `.ts` / `.js` source through the `ts2su` transpiler into running Sutra, and see where the substrate shows through.
5. **[Build a semantic FAQ matcher](05-semantic-faq.md)** — a small, genuinely useful program: a user asks a question in their own words and gets the right canned answer, matched by *meaning* rather than keywords. Your first program where the embedding substrate does real work.

More are coming as we go: cone traversal, fuzzy conditionals, the IntelliJ debugger walkthrough, and the embedding-space visualizer pane once it ships.

## Prerequisites

Everything below assumes Python 3.11 or newer.

Install the compiler from PyPI:

```bash
pip install sutra-dev                    # validator + codegen only
pip install "sutra-dev[runtime]"         # adds torch so --emit / --run can execute the generated module
pip install "sutra-dev[runtime,embed]"   # also loads the embedding model in-process — no Ollama daemon
```

The `[embed]` extra is what makes tutorial 05 (and any program that calls `embed`) run with **no separate model server**: the frozen `nomic-embed-text` model loads in-process. The first such run downloads the model once (a few hundred MB) and prints a one-line notice; after that it is cached. (Tutorials 01–03 use random `basis_vector` atoms and need no model at all.) If you would rather use an [Ollama](https://ollama.com) daemon, set `SUTRA_EMBED_BACKEND=ollama` and `ollama pull nomic-embed-text`.

After install, the `sutrac` command is on your `$PATH`:

```bash
sutrac --help
```

If that prints a usage message, you have everything you need to start.

**(Optional) JDK 21** if you want to run the IntelliJ plugin from a checkout of the source repository — not required for any of the command-line tutorials.
