# Sutra: A Programming Language for Vector-Symbolic Computation in Frozen Embedding Spaces

**Emma Leonhart** — *EmmaLeonhart999@gmail.com*

---

## Abstract

Frozen general-purpose language-model embedding spaces encode
relational structure as vector arithmetic — a property established
across the knowledge-graph-embedding literature (TransE, RotatE,
the word-analogy line). Taking that as given, this paper presents
the design and implementation of **Sutra**, a typed, purely
functional programming language whose compile target is a single
tensor-op graph over a frozen LLM embedding substrate. The
contribution is algorithmic: a consolidated set of vector-symbolic
primitives (bind, unbind, bundle, similarity, rotation,
soft-halt RNN cells) that work on natural anisotropic embedding
spaces where the textbook Hadamard-product VSA fails, plus a
compiler that lowers the whole program to one fused tensor-op
graph. Sutra is a working compiler today: parser, type checker,
codegen, runtime; the example corpus is a smoke test of 13
demonstration programs covering hello-world embedding round-trips,
fuzzy dispatch, role-filler records, knowledge graphs, classifier
decision rules, sequence reduction, naive analogy, predicate
lookup, nearest-phrase retrieval, the imperative-reversible
pattern, the do-while adder, the rotation hashmap, the rotation
record, and a tutorial — all executing end-to-end with expected
outputs. The full `examples/` directory holds 23 `.su` files
including legacy and feature demos. We give an honest account of
which parts of the substrate-purity story are shipped and which
remain.

---

## 1. Introduction

The discovery that general-purpose language model embeddings
encode relational structure as vector arithmetic — `king − man +
woman ≈ queen`, formalized through TransE, RotatE, and the
broader knowledge-graph embedding literature — established that
there is genuine algebraic content in the geometry of pre-trained
models. Given that algebraic structure exists, two questions
follow:

1. **Which operations on these embeddings are reliable enough to
   be used as primitives** of a compositional algebra over the
   embedding space, rather than as one-off lexical facts?
2. **What is the correct binding operation** to compose those
   primitives into structured representations — i.e. how do we
   build a working vector-symbolic architecture (VSA) on top of
   substrates the standard VSA literature was not designed for?

This paper answers both questions in the form of a working
programming language, **Sutra**, whose primitives are exactly
these consolidated operations.

The naming: **Sutra** is the Sanskrit *sūtra* — thread, rule,
aphorism — the term for Pāṇini's foundational Sanskrit grammar.

### 1.1 Two contributions

This paper presents two contributions:

> 1. **Consolidation** of the algebraic structure of frozen
>    embedding spaces into canonical primitive forms that can be
>    composed: bind, unbind, bundle, similarity, rotation,
>    soft-halt RNN cells.
> 2. **A programming language** whose compile target is a single
>    tensor-op graph over those primitives — the algorithms above,
>    realized as a typed, purely functional language with a working
>    compiler and runtime.

Sign-flip binding is not the headline — it is at most a side note
explaining why the textbook VSA choice (Hadamard product) fails on
anisotropic embeddings. The headline is the consolidation into a
working algebra plus the language that operationalizes it.

### 1.2 Contributions

1. **A typed, purely functional programming language whose compile
   target is a single tensor-op graph over a frozen LLM embedding
   substrate.** `.su` source parses, type-checks, compiles to
   PyTorch tensor ops, and executes; the runtime runs on CPU or
   CUDA depending on what's available at module init.

2. **A substrate-pure operational core.** Bind (rotation), unbind
   (rotation transpose), bundle (normalized sum), similarity
   (cosine on truth axis), arithmetic on canonical synthetic axes,
   and soft-halt RNN cells for runtime data-dependent recurrence
   — all execute as tensor operations on the substrate, with no
   host-Python compute on the runtime path. The compiler is the
   safety boundary because the runtime has no error channel by
   mechanism: a value with the wrong geometry doesn't crash, it
   produces meaningless output.

3. **First-class declared loop functions with branchless control.**
   Loops are declared as `do_while NAME(...)`, `while_loop
   NAME(...)`, `iterative_loop NAME(...)`, or `foreach_loop
   NAME(...)`; the body uses `pass values` (or, equivalently,
   `return NAME(args)` tail recursion) for the recurrent step.
   Each loop compiles to a fixed-T soft-halt RNN cell with
   substrate-pure halt detection (heaviside step → cumulative
   monotone halt → soft-mux state freeze). Halt completion
   propagates through nested calls to the program's final output:
   a loop that fails to converge wipes the program's result.

4. **Embedded SutraDB as the codebook.** Every embedded string in
   a compiled program goes into a SutraDB (sibling RDF + HNSW
   triplestore project) at compile time. The runtime decode path
   `_VSA.nearest_string(query)` returns the nearest string label
   for any vector — closing the loop between vector-space
   computation and human-readable output. Embeddings live in the
   `.sdb` file, not the Python module's data section.

5. **Honest scoping of the substrate-purity claim.** Five boundary
   leaks where Python touched the substrate at control-flow seams
   were enumerated and three fixed; two remain (rotation cache
   lookup, loop tick counter); both have known fix paths. The
   paper's substrate-purity claim is correctly scoped, not
   overclaimed.

### 1.3 What this paper is not

This paper does not propose a new VSA binding operation; rotation
binding is well-known (Plate 1995). It does not propose a new RNN
architecture; the soft-halt cell is straightforward. The
contribution is the *language* — the choice to compile a textual,
typed source language into a single substrate-pure tensor-op
graph, the design and implementation work that makes that
compilation sound, and the evidence that it works on demonstration
programs.

---

## 2. Related Work

### 2.1 Vector Symbolic Architectures

VSA is a family of algebraic frameworks for computing with high-
dimensional vectors (Kanerva 2009; Plate 1995; Gayler 2003). The
standard VSA development assumes hypervectors drawn from a
controlled random distribution designed for the algebra; bind is
typically Hadamard product or circular convolution. Frozen LLM
embedding spaces are not designed for VSA — they are correlated
and anisotropic — and the textbook bind operations do not transfer
cleanly. Rotation binding (`R_role @ filler` for a role-seeded
Haar-random orthogonal `R_role`) does, and is what Sutra uses
today.

### 2.2 Differentiable Programming, AOT Compilation, and Knowledge
Compilation

The closest design ancestors are partial-evaluation systems that
specialize programs at compile time (the Futamura projections),
differentiable programming systems that treat programs as
differentiable functions (JAX), AOT compilation of neural networks
(TVM, XLA), and knowledge compilation in symbolic AI (Darwiche &
Marquis 2002). Sutra differs from each: TVM/XLA start from a
network, not toward one; JAX treats programs as differentiable but
does not bake source literals into weights; partial evaluation
specializes for compile-time-known values but does not target a
neural-network-shaped artifact; knowledge compilation targets
Boolean circuits, not continuous embedding spaces. Sutra's
combination — fold source literals into the weight structure,
compile control flow to RNN cells, run the whole program as one
tensor-op graph over a *continuous* substrate — is the novel
position.

---

## 3. Consolidation into Canonical Primitives

The central design move: hold the operation interface fixed
(`bind`, `unbind`, `bundle`, `similarity`, `rotate`) and find a
binding implementation that works on natural anisotropic embedding
spaces. Standard VSA's Hadamard product fails because correlated
embeddings produce destructive crosstalk under elementwise
multiply. Rotation binding succeeds: each role gets a Haar-random
orthogonal matrix, seeded by a hash of the role-vector content,
and `bind(filler, role) = R_role @ filler`. Unbind is the matrix
transpose. The rotation acts as a near-orthogonal scrambling that
is invertible by construction.

The compiler emits role rotations as cached matrices, pre-warmed
at module init from the codebook so the runtime never pays the
QR-construction cost on the hot path. Binding becomes a single
matmul against a precomputed matrix — the GPU-friendly shape that
fuses with surrounding tensor ops.

### 3.1 The extended-state-vector layout

Every value in a Sutra program is a vector with a fixed extended
layout: `[semantic | synthetic]`. The semantic block holds the
LLM embedding for vector-shaped values; the synthetic block
reserves canonical axes for primitive types and slot machinery:

| Index             | Purpose                                  |
|-------------------|------------------------------------------|
| `synthetic[0]`    | `AXIS_REAL` (real component for int/float/complex) |
| `synthetic[1]`    | `AXIS_IMAG` (imaginary component for complex) |
| `synthetic[2]`    | `AXIS_TRUTH` (fuzzy truth scalar, used by bool/comparisons) |
| `synthetic[3]`    | `AXIS_CHAR_FLAG` (marks char primitives) |
| `synthetic[4]`    | `AXIS_LOOP_DONE` (substrate-side completion flag) |
| `synthetic[5..]`  | `SLOT_BASE` — disjoint 2D Givens slots for variable storage |

The uniformity is load-bearing: every value has the same shape, so
every operation is one tensor op, and the compiler can treat the
whole program as a dataflow graph of tensor operations. There is
no type dispatch at the leaves.

### 3.2 First-class loops as RNN cells

Runtime data-dependent loops compile to fixed-T soft-halt cells.
Each tick: snapshot pre-step state, evaluate the halt condition
on the substrate (truth-axis read → heaviside step → cumulative
saturating sum), run the body which uses `pass values` (or
equivalently `return NAME(args)` tail recursion) to update state
locals, then a soft-mux freezes state at the pre-step value once
halt saturates. T is fixed at compile time (currently 50);
optional `torch.compile` wrapping unrolls the meta-iteration at
trace time.

Each loop returns a halt-cum scalar in `[0, 1]` indicating
completion confidence. A `_program_halt` accumulator multiplies
into every loop call's halt-cum and into every function's return
value: a loop that fails to converge wipes program output to
near-zero, providing substrate-pure detection of unconverged
computation.

### 3.3 Embedded codebook in SutraDB

Every embedded string in a Sutra program is inserted into SutraDB
(a sibling RDF+HNSW triplestore project) at compile time, with
the embedding as the object of a triple typed
`<http://sutra.dev/f32vec>`. The runtime decode operation
`_VSA.nearest_string(query)` is the inverse of `embed`: given any
vector, return the nearest-string label from the substrate-resident
codebook. Strings declared but unused in expressions are still
inserted, so they remain decodable. The compiled module's Python
data section never carries the embeddings.

---

## 4. The Sutra Compiler

The compiler is a five-stage pipeline:

1. **Lex + parse** — `.su` source → AST.
2. **Inline + simplify** — stdlib operator definitions inlined; an
   egglog-based simplifier folds equivalent expressions and runs
   common-subexpression elimination over the algebra.
3. **Codegen** — AST → Python source emitting PyTorch tensor ops.
   The emitted module includes the runtime class (`_TorchVSA`) as
   inline source so the artifact is self-contained.
4. **Compile-time substrate population** — embed_batch fetches
   embeddings for every string literal; `populate_sutradb` pushes
   the codebook into SutraDB; `prewarm_rotation_cache` precomputes
   role rotations.
5. **Execute** — emitted module loaded; chosen device (CUDA or
   CPU) initialized at module import; `main()` called; result
   returned.

The runtime class is emitted inline rather than imported because
the emitted module *is* the substrate-pure tensor-op graph; the
compile-time decisions (extended-state-vector dimensions, codebook
contents, role rotations, SutraDB path, optional `torch.compile`)
are all baked into the emitted source. Re-running a compiled
module hits the disk-cached embeddings and the precomputed
rotations on second-and-later runs.

### 4.1 Substrate-purity invariants

Three invariants the compiler enforces:

1. **Every primitive runs on the substrate.** Numpy is allowed
   only at compile time (codebook construction, role-rotation
   pre-warm, SutraDB ingestion) and in monitoring/decoding
   (cosine for debugging output). Numpy on the runtime hot path
   is forbidden.
2. **No scalar extraction inside an operation.** Operations may
   not pull a Python float out of a substrate vector, do scalar
   arithmetic on it, and pack the result back. Historical bug
   fixed: complex multiplication had been implemented with
   scalar extraction; correct implementation is three cached
   matrices and two tensor multiplies.
3. **No Python control flow inside an operation.** `if`, `for`,
   `while` on scalar predicates break uniformity. Loop halt uses
   substrate primitives (`heaviside`, `saturate_unit`) instead of
   Python ternaries.

### 4.2 Boundary leak enumeration

Five places where Python crossed the substrate↔Python boundary
were enumerated; three were fixed in the work this paper reports
(loop halt check via `_VSA.truth_axis` + `_VSA.heaviside` +
`_VSA.saturate_unit`; `slot_load` returning a substrate scalar
instead of `float()`; `array_get` returning a substrate scalar).
Two remain: the rotation cache dictionary lookup (mitigated by
compile-time pre-warm so the runtime always hits a cached entry,
but the lookup itself is still Python `dict.__contains__`); the
loop tick counter `for _t in range(50)` (Python iteration that
`torch.compile` unrolls at trace time when enabled, but is
literally Python in the source). Both have known fix paths and
neither has the substrate compute the wrong thing — each touches
a Python scalar at a control-flow seam after the substrate has
already done the work.

The substrate-purity claim is correctly scoped: *every Sutra
operation runs as a tensor operation on the substrate; control-
flow primitives cross into Python at five enumerated seams, with
known fix paths, and `torch.compile` (opt-in via
`SUTRA_TORCH_COMPILE=1`) traces past two of them at runtime.*
This is qualitatively different from claiming "no Python ever
runs in the runtime" (which would be wrong) and from claiming the
substrate computes anything other than what the spec says it
should — the latter being the failure mode the project's safety
guidelines exist to prevent.

---

## 5. Demonstration Programs

The smoke test (`examples/_smoke_test.py`) runs 13 demonstration
programs end-to-end against the compiler+runtime pipeline; the
full `examples/` directory holds 23 `.su` files including legacy
syntax tours and feature demos. The 13 smoke-tested programs are:
hello-world, fuzzy branching, role-filler record, classifier,
analogy, knowledge graph, predicate lookup, fuzzy dispatch,
nearest-phrase retrieval, sequence reduction, loop rotation,
concept search, and counter loop. Each exercises a different part
of the language; the subsections below describe four canonical
examples in detail.

### 5.1 Hello world

```sutra
function vector main() {
    return embed("hello world");
}
```

Compiles to a single-call program that returns the
`nomic-embed-text` embedding of the literal string. The compile-
time disk cache makes second-run cost approximately zero.

### 5.2 Fuzzy dispatch

A program that compares an input string's embedding against
several prototype embeddings via similarity, then routes through
a soft-mux on the resulting truth-axis scores. All arithmetic is
substrate-pure; the dispatch is differentiable end-to-end (every
intermediate is a tensor on the substrate).

### 5.3 Role-filler record

A bundled role-filler structure (`agent: "cat", action: "sit"`)
that supports unbind-snap retrieval. Demonstrates that the VSA
algebra works as a structured-data primitive in the language:
construction, retrieval, and multi-hop composition (extract a
filler from one structure, insert it into another, retrieve from
the second) all return correct results.

### 5.4 Loop demonstrations

The loop demos confirm substrate-pure recurrent computation:

- `do_while addNumber(x < 11, int x) { return addNumber(x + 1); }`
  starting from `x = 9` returns `11` after the soft-halt cell
  runs to convergence.
- An `iterative_loop` with count = 1000 and `T = 50` does not
  converge: the local computation runs but `_program_halt ≈ 0`,
  so the function's `return total * _program_halt` wipes program
  output to zero, signaling "this didn't finish" via a
  substrate-side mechanism rather than a host-side exception.

---

## 6. Limitations and Future Work

### 6.1 Object encapsulation as load-bearing

Sutra's design includes ontology-oriented objects (closer to OWL
classes than to OOP) for compile-time semantic checking. Today's
compiler implements free functions cleanly; object methods parse
but their encapsulation rules (no closure across class boundary)
are not enforced. Implementing the encapsulation pass and the
class-boundary closure check is straightforward future work.

### 6.2 Two boundary leaks remain

Rotation cache lookup and loop tick counter are control-flow
seams that still cross to Python. Fix paths are specified. After
both fixes, the emitted module is a pure tensor-op graph that
`torch.compile` can fuse into a small number of CUDA kernels.

### 6.3 SutraDB integration depth

SutraDB is the embedded codebook today. Hashmap routing was
considered and dropped as the language has no real hashmap
concept; the codebook decode path (`nearest_string`) is the
substantive integration. Full `atman.toml [vector_db]` config
schema is deferred until there's a concrete requirement; an
env-var override (`SUTRA_DB_PATH`) covers the "persistent .sdb
across runs" use case today.

### 6.4 Numpy backend retirement

The compiler has historically had two backends; the numpy one
(`codegen.py`) is deprecated. Behavior tests run on PyTorch; the
numpy backend is retained only for emit-shape tests and gets
fully removed in a follow-up.

---

## 7. Conclusion

Sutra demonstrates that a programming language whose compile
target is a single tensor-op graph over a frozen embedding
substrate is a tractable design — not a research thought
experiment but a working compiler with running demonstration
programs. The design choice that makes it tractable is uniform
shape: every value is the same vector layout, every operation is
one tensor op, the compiler treats the whole program as a
dataflow graph with no type dispatch at the leaves.

The substrate-purity story is what makes the language useful for
the empirical question we built it to address: which embedding
operations actually compose, at what capacity, on which
substrates. With the language in hand, those questions become
programs to write rather than scripts to glue together.

---

## Acknowledgments

[REDACTED for double-blind review where applicable]

## References

- Bordes, A., Usunier, N., García-Durán, A., Weston, J., &
  Yakhnenko, O. (2013). Translating embeddings for modeling
  multi-relational data. *NeurIPS*.
- Darwiche, A., & Marquis, P. (2002). A knowledge compilation
  map. *JAIR* 17:229–264.
- Gayler, R. W. (2003). Vector symbolic architectures answer
  Jackendoff's challenges for cognitive neuroscience. *Joint
  International Conference on Cognitive Science*.
- Kanerva, P. (2009). Hyperdimensional computing: An introduction
  to computing in distributed representation with high-dimensional
  random vectors. *Cognitive Computation* 1(2):139–159.
- Mikolov, T., Chen, K., Corrado, G., & Dean, J. (2013). Efficient
  estimation of word representations in vector space. *ICLR
  Workshop*.
- Plate, T. A. (1995). Holographic reduced representations. *IEEE
  Transactions on Neural Networks* 6(3):623–641.
- Smolensky, P. (1990). Tensor product variable binding and the
  representation of symbolic structures in connectionist systems.
  *Artificial Intelligence* 46(1–2):159–216.
- Sun, Z., Deng, Z. H., Nie, J. Y., & Tang, J. (2019). RotatE:
  Knowledge graph embedding by relational rotation in complex
  space. *ICLR*.
- Wang, Z., Zhang, J., Feng, J., & Chen, Z. (2014). Knowledge
  graph embedding by translating on hyperplanes. *AAAI*.
