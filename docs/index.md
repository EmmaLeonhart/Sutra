# Sutra

**Sutra is a geometrically compiled language where logical operations over vector spaces are resolved at compile time into matrix multiplications.**

Sutra source looks like TypeScript — functions, classes, variables, `&&` / `||`, string and numeric literals. The compiler emits self-contained Python that calls a small runtime implementing the Sutra primitives: `bundle`, `bind`, `unbind`, `similarity`, `argmax_cosine`, `select`, `loop`. Each primitive is a tensor operation. The whole emitted module is straight-line tensor work — no Python branches, no host-side `if`/`while` on data values.

## Why this is interesting

The composition is what matters. Once every value has the same shape (a vector) and every operation is a tensor op on that shape, the compiler can read a whole program as one tensor expression. Chains of bind/unbind/bundle reduce to chains of matrix multiplies. The simplifier folds those chains into cached matrices at compile time, and the runtime executes the result as a single sequence of tensor ops.

A typical Sutra value is a vector in a frozen LLM embedding space. The current default substrate is `nomic-embed-text` (768-d, mean-centered, served via Ollama). Strings auto-embed in vector contexts: `vector v = "cat"` means "embed the string through the substrate." The runtime caches embeddings and batches the embedding round-trips at module init.

The language has loops and conditionals, but neither compiles to a host-side branch. A conditional is a softmax-weighted sum across all options. A loop is a declared function whose parameters are the recurrent state and whose body is one cell tick; the cell unrolls to a fixed-length tensor-op chain on the substrate, and a soft-halt mask freezes the state when the termination condition is met. The "loop counter" is the angular position on a helix in the substrate, not a host variable.

## What runs today

A reference compiler that emits PyTorch tensor ops (picking CUDA at module init if available), an IntelliJ plugin with syntax highlighting, completion, and an external annotator, a VS Code extension with TextMate grammar and snippets, and a set of demo `.su` programs that compile and execute end-to-end through the smoke test.

```bash
git clone https://github.com/EmmaLeonhart/Sutra
cd Sutra
python examples/_smoke_test.py
```

The compiler, the runtime, the example programs, and the smoke-test harness all live in [the repository](https://github.com/EmmaLeonhart/Sutra).
