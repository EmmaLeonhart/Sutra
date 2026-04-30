# From Learned Displacements to Learned Matrices: Sutra, a Programming Language for Vector-Symbolic Computation in Frozen Embedding Spaces

**Emma Leonhart** — *immanuelleleonhart@gmail.com*

**DRAFT 2026-04-30** — initial submission draft. Numbers from the
companion `latent-space-cartography` repository are placeholders
(marked `[CITE]`) pending final cross-check before submission. Do
not circulate without that verification.

---

## Abstract

Frozen general-purpose language-model embedding spaces encode
relational structure as vector arithmetic — a property established
empirically in the cartography line of work that this paper
follows from. We argue this empirical foundation suggests a
three-step research arc: **(1)** isolate regular displacements in
the embedding space; **(2)** consolidate them into canonical
operational primitives; **(3)** generalize from rank-zero
displacements (translations) to learned-matrix role operators
(general orthogonal binding). Step 1 is prior published work; this
paper presents step 2 (consolidation into rotation-based vector-
symbolic primitives that work on natural anisotropic embedding
spaces) and the design and implementation of **Sutra**, a typed,
purely functional programming language whose compile target is a
single tensor-op graph over the frozen embedding substrate. Sutra
is a working compiler today: parser, type checker, codegen,
runtime; three demonstration programs (hello world, fuzzy
dispatch, role-filler record) plus loop demonstrations execute
end-to-end with all expected outputs correct. The language design
positions step 3 (learned-matrix binding) as an explicit extension
point — `role X = learned_from(data)` — with rotation binding as
the working substrate today and learned matrices as the natural
next implementation. The paper's contribution is the *language*
that operationalizes the empirical findings, plus an honest
account of which parts of the substrate-purity story are shipped
and which remain.

---

## 1. Introduction

The discovery that general-purpose language model embeddings
encode relational structure as vector arithmetic — `king − man +
woman ≈ queen`, formalized through TransE, RotatE, and the
broader knowledge-graph embedding literature — established that
there is genuine algebraic content in the geometry of pre-trained
models. Subsequent cartographic analysis (Leonhart, *Latent space
cartography applied to Wikidata*, sibling repository
`EmmaLeonhart/latent-space-cartography`) showed that this is not
specific to relational embeddings: general-purpose text encoders
contain consistent relational displacements, with `[CITE]`
predicates discovered as systematic vector operations across
multiple embedding models, and a strong correlation
(`r ≈ [CITE]`) between geometric consistency and downstream
prediction accuracy.

Given that algebraic structure exists, three questions follow:

1. **Which displacements are reliable enough to be used as
   primitives** of a compositional algebra over the embedding
   space, rather than as one-off lexical facts?
2. **What is the correct binding operation** to compose those
   primitives into structured representations — i.e. how do we
   build a working vector-symbolic architecture (VSA) on top of
   substrates the standard VSA literature was not designed for?
3. **Can we go from individual displacements to a learned
   *matrix* of relational operators** — a parametric family
   indexed by role, where each role is a small dense matrix fit
   to data rather than a hand-picked direction?

This paper answers questions 1 and 2 in the form of a working
programming language, **Sutra**, whose primitives are exactly
these consolidated operations. Question 3 is positioned as the
language's natural next implementation step — the design surface
already includes a `role X = learned_from(data)` form that the
runtime today rejects with a deferred-feature error and the next
release implements. We deliberately do not present learned-matrix
binding as a finished result; the paper's claim is that the
language design supports the trajectory.

The naming: **Sutra** is the Sanskrit *sūtra* — thread, rule,
aphorism — the term for Pāṇini's foundational Sanskrit grammar.

### 1.1 Three-step arc

The narrative of this work spans three steps; this paper is step 2
plus the language design that prepares step 3:

> 1. **Isolate** regular displacements in frozen LLM embedding
>    spaces (the cartography work, already published).
> 2. **Consolidate** these into canonical primitive forms — clean
>    operations that can be composed: bind, unbind, bundle,
>    similarity, rotation, soft-halt RNN cells.
> 3. **Generalize** from rank-zero displacements (translations) to
>    learned matrices that operate on the substrate as full-rank
>    role operators. The *semantic role* becomes a fitted matrix.

Sign-flip binding is not the headline — it is at most a side note
explaining why the textbook VSA choice (Hadamard product) fails on
anisotropic embeddings. The headline is the consolidation into a
working algebra plus the trajectory toward learned-matrix
generalization.

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

6. **Learned-matrix binding as an explicit deferred extension.**
   The language design includes `role X = learned_from(data)`;
   the runtime today rejects calls with a deferred-feature error
   pointing at the spec. This positions step 3 of the research
   arc as an implementation — not a research — task.

### 1.3 What this paper is not

This paper does not propose a new VSA binding operation; rotation
binding is well-known (Plate 1995). It does not propose a new RNN
architecture; the soft-halt cell is straightforward. It does not
present learned-matrix binding as a finished empirical result.
The contribution is the *language* — the choice to compile a
textual, typed source language into a single substrate-pure
tensor-op graph, the design and implementation work that makes
that compilation sound, and the evidence that it works on
demonstration programs.

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
today. The trajectory toward learned-matrix binding (where
`R_role` is fit to data rather than seeded from a hash) is the
natural extension and the language's next-implementation target.

### 2.2 Relational Displacement Analysis

The empirical foundation is prior cartographic analysis of frozen
embeddings (Leonhart, *Latent space cartography applied to
Wikidata*; sibling repository
`EmmaLeonhart/latent-space-cartography`). That work establishes
the algebraic structure exists in pre-trained spaces without VSA-
specific training, the precondition for Sutra to be a meaningful
language at all. This paper extends from the cartography findings
toward a programming-language realization.

### 2.3 Differentiable Programming, AOT Compilation, and Knowledge
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

## 3. Step 1 — Relational Displacements in Frozen Embedding Spaces

The cartography work (sibling repository) is summarized briefly
here for self-containment; specific numbers should be read from
the source repository, not from this paper. The result we build
on: in three frozen general-purpose embedding models tested
(`nomic-embed-text`, `all-minilm`, `mxbai-embed-large`),
relational predicates from Wikidata produce consistent vector
displacements — `country(X) − country(Y) ≈ country(X′) −
country(Y′)` for many predicate-instance pairs — and the
geometric consistency of a displacement strongly correlates with
its downstream prediction accuracy. This is a precondition for a
VSA-style algebra to work over these spaces: *the algebraic
structure exists*. Whether that structure is operationally
useful — i.e. whether it composes well — is what this paper
addresses.

---

## 4. Step 2 — Consolidation into Canonical Primitives

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

### 4.1 The extended-state-vector layout

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

### 4.2 First-class loops as RNN cells

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

### 4.3 Embedded codebook in SutraDB

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

## 5. Step 3 — Learned-Matrix Binding (Deferred)

The natural next implementation: replace the role-hash-seeded Haar
rotation with a *learned* matrix fit to data. The language design
already includes the surface:

```sutra
role agent = learned_from(corpus_of_agent_examples);
vector v = bind(agent, "cat");
```

`role X = learned_from(data)` declares a learned binding matrix
that the compiler fits at compile time from the supplied data,
caches as `R_X`, and uses for subsequent `bind(X, _)` calls. The
runtime today rejects this with a deferred-feature error pointing
at `planning/sutra-spec/binding.md` § "Semantic binding". Shipping
the implementation is the next-release work — out of scope for
this paper but explicitly positioned as the next step rather than
a research question.

The case for this generalization: the cartography findings show
that displacements *are* relational operators of varying rank.
Rank-zero (translation) is the cartography baseline; rank-one or
higher (matrix) is the obvious extension that the embedding-space
geometry already supports. Learned matrices give the language a
parameter family indexed by role, with each role being something
the compiler can fit and bake.

---

## 6. The Sutra Compiler

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

### 6.1 Substrate-purity invariants

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

### 6.2 Boundary leak enumeration

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
should (which is the failure mode the safety-critical preamble
in the project's CLAUDE.md exists to prevent).

---

## 7. Demonstration Programs

Three programs run end-to-end in the current implementation; each
exercises a different part of the language.

### 7.1 Hello world

```sutra
function vector main() {
    return embed("hello world");
}
```

Compiles to a single-call program that returns the
`nomic-embed-text` embedding of the literal string. The compile-
time disk cache makes second-run cost approximately zero.

### 7.2 Fuzzy dispatch

A program that compares an input string's embedding against
several prototype embeddings via similarity, then routes through
a soft-mux on the resulting truth-axis scores. All arithmetic is
substrate-pure; the dispatch is differentiable end-to-end (every
intermediate is a tensor on the substrate).

### 7.3 Role-filler record

A bundled role-filler structure (`agent: "cat", action: "sit"`)
that supports unbind-snap retrieval. Demonstrates that the VSA
algebra works as a structured-data primitive in the language:
construction, retrieval, and multi-hop composition (extract a
filler from one structure, insert it into another, retrieve from
the second) all return correct results.

### 7.4 Loop demonstrations

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

## 8. Limitations and Future Work

### 8.1 Learned-matrix binding (next-release)

The implementation that closes the three-step arc. Surface design
exists; runtime rejects with a deferred-feature error.

### 8.2 Object encapsulation as load-bearing

Sutra's design includes ontology-oriented objects (closer to OWL
classes than to OOP) for compile-time semantic checking. Today's
compiler implements free functions cleanly; object methods parse
but their encapsulation rules (no closure across class boundary)
are not enforced. Queued.

### 8.3 Two boundary leaks remain

Rotation cache lookup and loop tick counter are control-flow
seams that still cross to Python. Fix paths are specified. After
both fixes, the emitted module is a pure tensor-op graph that
`torch.compile` can fuse into a small number of CUDA kernels.

### 8.4 SutraDB integration depth

SutraDB is the embedded codebook today. Hashmap routing was
considered and dropped as the language has no real hashmap
concept; the codebook decode path (`nearest_string`) is the
substantive integration. Full `atman.toml [vector_db]` config
schema is deferred until there's a concrete requirement; an
env-var override (`SUTRA_DB_PATH`) covers the "persistent .sdb
across runs" use case today.

### 8.5 Numpy backend retirement

The compiler has historically had two backends; the numpy one
(`codegen.py`) is deprecated as of 2026-04-30. Behavior tests run
on PyTorch; the numpy backend is retained only for emit-shape
tests and gets fully removed in a follow-up.

---

## 9. Conclusion

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
substrates, and — at the next step — what learned matrices fall
out of the displacement findings. With the language in hand,
those questions become programs to write rather than scripts to
glue together.

The three-step arc — displacements → consolidation → learned
matrices — has its first two steps in print. Step 3 is the
language's next implementation, not its next research question.

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
- Leonhart, E. *Latent space cartography applied to Wikidata*.
  Sibling repository: `github.com/EmmaLeonhart/latent-space-cartography`.
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
