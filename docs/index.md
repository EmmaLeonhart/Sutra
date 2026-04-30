---
title: Sutra
description: Sutra is a geometrically compiled language where logical operations over vector spaces are resolved at compile time into matrix multiplications.
hide:
  - navigation
  - toc
---

# 📜 Sutra

**Sutra is a geometrically compiled language where logical operations over vector spaces are resolved at compile time into matrix multiplications.**

[:material-file-pdf-box: Paper (PDF)](paper.pdf){ .md-button .md-button--primary }
[:material-text-box: Paper (HTML)](theory-and-paper.md){ .md-button }
[:material-cloud-upload: clawRxiv submission](https://clawrxiv.io/abs/2604.02148){ .md-button }


Sutra source looks like TypeScript — functions, classes, variables, `&&` / `||`, string and numeric literals. The compiler emits self-contained Python that calls a small runtime (`_VSA`) implementing the Sutra primitives: `bundle`, `bind`, `unbind`, `similarity`, `argmax_cosine`, `select`, `loop`. Each primitive is a tensor operation. The whole emitted module is straight-line tensor work — no Python branches, no host-side `if`/`while` on data values.

## Why this is interesting

The composition is what matters. Once every value has the same shape (a vector) and every operation is a tensor op on that shape, the compiler can read a whole program as one tensor expression. Chains of bind/unbind/bundle reduce to chains of matrix multiplies. The simplifier folds those chains into cached matrices at compile time, and the runtime executes the result as a single sequence of tensor ops.

A typical Sutra value is a vector in a frozen LLM embedding space. The current default substrate is `nomic-embed-text` (768-d, mean-centered, served via Ollama). Strings auto-embed in vector contexts: `vector v = "cat"` means "embed the string through the substrate." The runtime caches embeddings and batches Ollama round-trips at module init.

The language has loops and conditionals, but neither compiles to a host-side branch. A conditional is a softmax-weighted sum across all options. A `loop(condition)` compiles to a fixed rotation matrix `R` applied iteratively until a similarity threshold is met — the loop counter is the angular position on a helix in the substrate.

[**Read the vision page →**](vision.md) for why this is grounded in measurable structure in frozen embedding spaces, not metaphor.

---

## What runs today

A reference compiler with two emitter backends (numpy-flavored and PyTorch tensor ops, the latter picking CUDA at module init if available), an IntelliJ plugin with syntax highlighting / completion / external annotator, a VS Code extension with TextMate grammar and snippets, and 13 demo `.su` programs that compile and execute end-to-end through the smoke test.

```bash
git clone https://github.com/EmmaLeonhart/Sutra
cd Sutra
python examples/_smoke_test.py
```

To see what the compiler actually emits for a single program:

```bash
python -m sutra_compiler --emit examples/hello_world.su
```

[**Demos →**](demos.md) lists every program in the smoke test and what it exercises.

---

## What you can do with it

<div class="grid cards" markdown>

-   :material-vector-line:{ .lg .middle } __Run programs on LLM embedding spaces__

    ---

    Sutra programs operate directly on vectors from frozen LLM embedding spaces. The compiler wires `embed("string")` to the substrate (currently Ollama). Bind, unbind, bundle, similarity, argmax_cosine all execute as tensor ops on those vectors.

    [→ Demos](demos.md)

-   :material-school:{ .lg .middle } __Learn the language__

    ---

    Tutorials walk through writing your first `.su` file, the bind/unbind operation that makes structured records possible, and the cleanup operations that make long compositions stable. No prior VSA or HDC background required.

    [→ Hello Sutra](tutorials/01-hello-sutra.md)

-   :material-file-document-outline:{ .lg .middle } __Read the spec__

    ---

    The language specification — vision, operations, binding, control flow, equality and defuzzification, types, program structure — is in the repo at `planning/sutra-spec/` and is the source of truth for what each operation computes.

    [→ Compilation](compilation.md)

</div>

---

## What it isn't

Sutra is not a portable general-purpose language. You don't write a web server in it, or a GUI event loop, or a filesystem walker. What you write in it is a substrate-resident program — a conditional, a pattern lookup, a structured record decode, a bounded trajectory — running as tensor operations on whichever embedding substrate the program targets.

It is also not a neural network. The compiler does not learn anything; it lowers a `.su` source file into a fixed sequence of tensor ops. The substrate it targets may have been trained, but the program itself is deterministic compiled code.

---

## Project status

Sutra is **research-grade** software. The work-in-progress queue lives in [`queue.md`](https://github.com/EmmaLeonhart/Sutra/blob/master/queue.md). The paper that grounds the language is on the [Theory and Paper page](theory-and-paper.md). The language, the compiler, and the IntelliJ plugin are open source and live in one repo: [github.com/EmmaLeonhart/Sutra](https://github.com/EmmaLeonhart/Sutra).
