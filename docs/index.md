# Sutra

**Sutra is a geometrically compiled language where logical operations over vector spaces are resolved at compile time into matrix multiplications.**

Write a program in a TypeScript-shaped language. The compiler turns the *entire* program — control flow included — into one straight-line sequence of tensor operations. What comes out is, at the same time, a logic program you can read and a neural network you can train.

## Why Sutra

- **Write logic, get a network.** A Sutra program is simultaneously a readable symbolic program and a differentiable model. Train it with ordinary PyTorch autograd — the rule graph never changes; gradient descent only moves the embeddings it reasons over. A symbolic fuzzy-rule classifier trains from chance to 95% accuracy without touching a line of the program.
- **One tensor-op graph, no glue.** The whole program — conditionals, loops, string I/O — compiles to a single tensor expression. No interpreter, no host-side `if`/`while` on data, no Python in the hot path. The program *is* the computation graph.
- **Substrate-agnostic.** Values live in a frozen embedding space. The same source recompiles against a different model — a text encoder, a protein language model, any dense encoder — and the binding algebra stays exact where textbook vector-symbolic operators fall apart.
- **Symbolic and sub-symbolic without a bridge.** Fuzzy three-valued logic, role binding, rotation hash-maps, recurrent loops — all native, all differentiable end to end. No separate neural front-end stitched to a symbolic back-end.

## How it works

Every value is a vector; every operation — `bundle`, `bind`, `unbind`, `similarity`, `select`, `loop` — is a tensor op on that shape. Because the shape never changes, the compiler reads a whole program as one tensor expression: chains of bind/unbind/bundle collapse into chains of matrix multiplies, the simplifier folds those into cached matrices at compile time, and the runtime executes the result as one sequence of tensor ops.

A Sutra value is a vector in a frozen LLM embedding space (default substrate: `nomic-embed-text`, 768-d). Strings auto-embed in vector contexts — `vector v = "cat"` embeds the string through the substrate. Conditionals are softmax-weighted sums; loops are recurrent cells that unroll to a fixed-length tensor-op chain with a soft-halt mask, the loop counter being angular position on a helix in the substrate rather than a host variable.

## Hardware

Sutra compiles to self-contained PyTorch and runs on an NVIDIA GPU (CUDA, selected automatically at module init) or on CPU — the same emitted module, no code change. Because the entire program is one tensor-op graph with no host-side control flow, it maps straight onto GPU execution: the program is the kernel sequence, not a script that calls into one. Requirements are just Python and PyTorch; the default embedding substrate loads in-process (`pip install "sutra-dev[runtime,embed]"`), so no separate model server is needed. Ollama is supported as an alternate backend for anyone who prefers it.

## Get started

```bash
git clone https://github.com/EmmaLeonhart/Sutra
cd Sutra
python examples/_smoke_test.py
```

Read `examples/*.su` for the language itself. The compiler, runtime, IntelliJ plugin, and VS Code extension all live in [the repository](https://github.com/EmmaLeonhart/Sutra).
