---
title: What is Sutra?
description: A plain-language explanation of what Sutra actually does.
---

# What is Sutra?

Sutra is a **geometrically compiled language where logical operations over vector spaces are resolved at compile time into matrix multiplications.** Source code parses, compiles, and executes — but the compilation target is not machine instructions. It is a sequence of tensor operations on vectors in a geometric substrate: matrix multiplies, elementwise multiplies, additions, cosines, softmax-weighted sums. Every value in a Sutra program is a vector — a coordinate in that substrate. Every operation moves the program through the substrate's geometry. The compiler's job is to take the program's surface logic — branches, loops, structured records — and resolve it down to a chain of matrix multiplications before the runtime ever touches a value.

## What the compiler does

The Sutra compiler is a normal compiler in shape — lexer, parser, simplifier, validator, code generator. It reads a `.su` source file and emits a self-contained Python module. That module imports a small runtime class (`_VSA`) and calls into it for the language's primitives:

| Primitive | What it computes |
|---|---|
| `basis_vector("name")` | embed the string through the substrate |
| `bundle(a, b, ...)` | sum the vectors and L2-normalize |
| `bind(role, filler)` | rotation binding: `Q_role @ filler` |
| `unbind(role, record)` | inverse rotation: `Q_role^T @ record` |
| `similarity(a, b)` | cosine similarity |
| `argmax_cosine(query, [candidates])` | nearest codebook entry |
| `select([scores], [options])` | softmax-weighted superposition |
| `loop(condition) { … }` | apply a fixed rotation `R` until condition is met |

These are tensor operations. Bundle is a sum. Bind and unbind are matrix multiplies against orthogonal matrices. Similarity is a dot product. Argmax_cosine is a matrix-vector multiply followed by an argmax. Select is a softmax-weighted sum. Loop is iterated matrix-vector multiplication with a similarity check.

The current default substrate is `nomic-embed-text` (768-dimensional vectors, mean-centered, served via Ollama). String literals in `vector` contexts auto-embed: `vector v = "cat"` is short for "embed the string 'cat' and bind the result to `v`." The runtime caches embeddings and batches Ollama round-trips at module init.

## Why no host-side control flow

Sutra has functions, conditionals, and loops in its surface syntax, but none of them lower to a Python `if` or `while` on data values:

- **Conditionals** lower to a softmax-weighted sum across all options. All branches contribute to the result; the weights decide how much. The commitment to a discrete answer happens at the final `argmax_cosine` or map lookup at the program's edge.
- **Loops** of the form `loop[N]` unroll at compile time — the compiler emits `N` repeated applications of the body, no runtime iteration.
- **Loops** of the form `loop(condition)` compile to a fixed rotation matrix `R` applied iteratively. The "loop counter" is the angular position on a helix in the substrate; termination is a similarity check against a target prototype.

The reason this matters: a program with no host-side branches lowers to straight-line tensor work, which lets the simplifier read the whole program as one tensor expression and fold chains of operations into cached matrices. Compile a chain of `bundle(bind(r1, f1), bind(r2, f2))`, and the simplifier can stack the binds into one matmul.

## Why composition is the win

The interesting thing is not that `1 + 1` happens to be a vector add. The interesting thing is that *every* operation has the same shape, so the compiler can compose them. A chain of bind/unbind/bundle/similarity on real LLM embeddings folds into a matrix expression at compile time. Conditionals embed into the same expression as softmax weights. Loops embed as iterated rotations.

Locally, this looks wasteful — `1 + 1` doing 768-d vector addition is more arithmetic than `1 + 1` needs. The trade is that the *whole program* has uniform shape, so there is no type-dispatch layer, no JIT, no branch predictor in the hot path, and the simplifier can fuse chains end-to-end.

## What's a Sutra program for

The thing a Sutra program is good at is computing in the geometry of an embedding space: looking up structured records by role, computing analogies as displacement-plus-bind, classifying against bundled prototypes, walking a trajectory until it lands in a basin. The 13 demo programs in [`examples/`](https://github.com/EmmaLeonhart/Sutra/tree/master/examples) show the surface — embed/retrieve, fuzzy branching, role-filler records, bundled triples, position-bound sequences, eigenrotation loops.

What it isn't good at is being a portable general-purpose language. You do not write a web server in Sutra, or a filesystem walker, or a UI event loop. The language is for the part of a system that lives in vector space.

## What about the other substrates

Earlier Sutra work explored compiling to a Brian2 spiking simulation of the *Drosophila* mushroom body, and later to the Shiu et al. 2024 whole-brain LIF model. That research line was retired on 2026-04-26 — the substrate work outpaced the language's maturity, and keeping the half-finished compile-to-connectome path in the repo wasn't paying for itself. Findings from that work (real FlyWire weight matrices do not function as rotation operators; CX ring-attractor circuits did not discriminate direction on real connectivity) are preserved under [`planning/findings/`](https://github.com/EmmaLeonhart/Sutra/tree/master/planning/findings) as historical record.

The current compile target is PyTorch on the frozen-LLM semantic subspace, and that is the substrate the language reference and the demos describe.

## Where to go next

- [**The vision page →**](vision.md) — why frozen embedding spaces give Sutra primitives geometric meaning, and what the displacement-vector cartography work showed.
- [**Hello Sutra →**](tutorials/01-hello-sutra.md) — write your first `.su` program by hand.
- [**Compilation →**](compilation.md) — how the compiler progressively strips surface sugar down to polynomial and matrix arithmetic.
- [**Demos →**](demos.md) — the 13 programs in the smoke test, what each one exercises.
