# Sutra

**Sutra is a geometrically compiled language where logical operations over vector spaces are resolved at compile time into matrix multiplications.**

Write a program in a TypeScript-shaped language. The compiler turns the *entire* program — control flow included — into one straight-line sequence of tensor operations. What comes out is, at the same time, a logic program you can read and a neural network you can train.

## Why Sutra

- **Write logic, get a network.** A Sutra program is simultaneously a readable symbolic program and a differentiable model. Train it with ordinary PyTorch autograd — the rule graph never changes; gradient descent only moves the embeddings it reasons over. A symbolic fuzzy-rule classifier trains from chance to 95% accuracy without touching a line of the program.
- **One tensor-op graph, no glue.** The whole program — conditionals, loops, string operations — compiles to a single tensor expression that runs all at once. No interpreter, no host-side `if`/`while` on data, no Python in the hot path. The program *is* the computation graph. Because it runs synchronously in one pass, I/O attaches at the boundaries — the start and end of the program and of its loops — not mid-computation (see [the I/O model](host-bridge.md)).
- **Substrate-agnostic.** Values live in a frozen embedding space. The same source recompiles against a different model — a text encoder, a protein language model, any dense encoder — and the binding algebra stays exact where textbook vector-symbolic operators fall apart.
- **Symbolic and sub-symbolic without a bridge.** Fuzzy three-valued logic, role binding, rotation hash-maps, recurrent loops — all native. Straight-line programs are differentiable end to end (measured: a fuzzy-rule classifier trains through autograd); loop termination is forward-only today — a surrogate gradient for the halt step is future work. No separate neural front-end stitched to a symbolic back-end.

## How it works

Every value is a vector; every operation — `bundle`, `bind`, `unbind`, `similarity`, `select`, `loop` — is a tensor op on that shape. Because the shape never changes, the compiler reads a whole program as one tensor expression: chains of bind/unbind/bundle collapse into chains of matrix multiplies, the simplifier folds those into cached matrices at compile time, and the runtime executes the result as one sequence of tensor ops.

A Sutra value is a vector in a frozen LLM embedding space (default substrate: `nomic-embed-text`, 768-d). Strings auto-embed in vector contexts — `vector v = "cat"` embeds the string through the substrate. Conditionals are softmax-weighted sums; loops are recurrent cells that unroll to a fixed-length tensor-op chain with a soft-halt mask, the loop counter being angular position on a helix in the substrate rather than a host variable.

## Hardware

Sutra compiles to self-contained PyTorch and runs on an NVIDIA GPU (CUDA, selected automatically at module init) or on CPU — the same emitted module, no code change. Because the entire program is one tensor-op graph with no host-side control flow, it maps straight onto GPU execution: the program is the kernel sequence, not a script that calls into one. Requirements are just Python and PyTorch; the default embedding substrate loads in-process (`pip install "sutra-dev[runtime,embed]"`), so no separate model server is needed. Ollama is supported as an alternate backend for anyone who prefers it.

## Get started

Install from PyPI and run your first program — no clone, no server:

```bash
pip install "sutra-dev[runtime,embed]"
printf 'function string main() { return "hello world"; }\n' > hello.su
sutrac --run hello.su          # -> hello world
```

`pip install sutra-dev` alone gives you the validator + codegen (`sutrac hello.su` to
check a file); the `[runtime,embed]` extras add PyTorch and the in-process embedding
model so programs actually run. New to the ideas? Follow **[the tutorials](tutorials/index.md)**
(a guided six-part walk, starting with
[01 — Hello Sutra](tutorials/01-hello-sutra.md)), or open **[the
interactive REPL](repl.md)** (`sutrac repl`) to try expressions live.

**Working from source** (the full `examples/*.su` set, the smoke tests, the IntelliJ
plugin, and the VS Code extension) lives in [the repository](https://github.com/EmmaLeonhart/Sutra):

```bash
git clone https://github.com/EmmaLeonhart/Sutra
cd Sutra
python examples/_smoke_test.py
```

The example programs the tutorials walk through (`examples/*.su`) ship in that source
tree, not in the pip package — with a pip-only install, save the source shown in each
tutorial to a local file (as with `hello.su` above) or clone the repo.

## Read more

- **[Tutorials](tutorials/index.md)** — the guided walk: hello world, bind/unbind, cleanup, TypeScript transpilation, a semantic FAQ matcher, strings & formatting.
- **Reading with an AI agent?** Fetch [/llms.txt](/llms.txt) — a plain-markdown index; every docs page is also served as raw markdown at its URL plus `.md` (e.g. `/loops.md`).
- **[What Sutra implements](capabilities.md)** — the exhaustive inventory: every keyword, operator, runtime primitive, and diagnostic.
- **[Operations and operators](operators.md)** — the formal definitions.
- **[Papers](papers.md)** — the Sutra papers, with PDFs and venue links.
- **[A worked product example](example.md)** — a self-optimizing landing-page button.
- **[Drawing pixels](gui.md)** — a window whose picture is computed on the substrate.
- **[TypeScript → Sutra](typescript-to-sutra.md)** — the syntax mapping, construct by construct.
- **[Neural WebAssembly](neural-webassembly.md)** — the sibling research artifact.
- **[History](history.md)** — where the name and the ideas come from.
