# Tutorials

A guided walk into Sutra. The tutorials are written in the spirit of the *TypeScript Handbook* — short, runnable, code on the left, explanation on the right. No prior knowledge of Vector Symbolic Architectures, Hyperdimensional Computing, or embedding spaces is assumed; the [vision page](../vision.md) is the only thing you should read first, and only if you have not yet had the *"oh, embeddings are spatial, not graphs"* moment land in your head.

Each tutorial is a single `.su` file plus a walkthrough explaining what it does and why every line is the way it is.

## Order of operations

1. **[Hello Sutra](01-hello-sutra.md)** — install, validate your first source file, see the syntax. The "does my toolchain work?" sanity check.
2. **[Bind and unbind](02-bind-and-unbind.md)** — the two operations that make Sutra useful. Why the textbook Hadamard binding fails on natural embedding spaces, and how rotation binding (Sutra's current runtime mechanism) recovers correct fillers.
3. **[Snap-to-nearest](03-snap-to-nearest.md)** — the cleanup step. How long Sutra computations stay numerically stable instead of degrading into noise.

That's it for v1 of the tutorials. More are coming as we go: cone traversal, fuzzy conditionals, the IntelliJ debugger walkthrough, and the embedding-space visualizer pane once it ships.

## Prerequisites

Everything below assumes:

- **Python 3.13** for the reference compiler. Use Immanuelle's interpreter on Windows, not ambie's.
- **A clone of the Sutra repository.** All paths are relative to the repo root.
- **(Optional) JDK 21** if you want to run the IntelliJ plugin sandbox via `!editor.bat`. Not required for any of the command-line tutorials.

The compiler lives at `sdk/sutra-compiler/` and runs as a Python module:

```bash
cd sdk/sutra-compiler
python -m sutra_compiler --help
```

If that prints a usage message, you have everything you need to start.
