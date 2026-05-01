# Sutra: A Programming Language for Vector-Symbolic Computation in Vector Embedding Spaces

**Emma Leonhart** — *EmmaLeonhart999@gmail.com*

---

## Abstract

**Sutra** is a typed, purely functional programming language
whose values are vectors in a dense embedding space and whose
compile target is a single tensor-op graph. The contribution is
algorithmic: a consolidated set of vector-symbolic primitives
(rotation binding, unbind, bundle, similarity, soft-halt RNN
cells, polynomial Kleene three-valued logic) lowered through a
compiler that beta-reduces the whole program to tensor normal
form. The substrate is *any* dense high-dimensional vector
space — empirically validated on three frozen LLM embeddings
(nomic-embed-text, all-minilm, mxbai-embed-large) and on ESM-2
protein-language-model embeddings, with the same characteristic
rotation-vs-Hadamard separation in every case. Sutra is a
working compiler: parser, type checker, codegen, runtime,
embedded SutraDB codebook, opt-in `torch.compile` wrapping. The
example corpus is a 13-program smoke test (with 23 `.su` files
total), and 237 passing unit tests. We report honest negative
results alongside the positive ones — most notably the §3.1.1
crosstalk analysis, which scopes the rotation-binding capacity
claim to single-cycle records, and we close with §3.6, which
demonstrates that symbolic if-then rules built from those
primitives remain end-to-end differentiable through standard
PyTorch autograd.

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

The headline is the consolidation into a working algebra plus
the language that operationalizes it. The choice of binding
operation is an implementation concern (rotation works on the
substrates we tested; Hadamard tends not to — see §3.1) rather
than the contribution.

### 1.2 Contributions

The four core technical contributions of this paper are:

1. **Polynomial fuzzy logic via Lagrange interpolation of
   Kleene's three-valued truth tables, with functional completeness.**
   The truth axis encodes three values: T = +1, U = 0, F = −1.
   The logical connectives are taken from Kleene's strong
   three-valued logic (Kleene 1952): on the discrete grid
   {−1, 0, +1}, AND is the minimum of its operands, OR is the
   maximum, NOT is negation. This is the same choice that **Gödel
   fuzzy logic** makes for its t-norm and t-conorm in the
   continuous setting (AND = min, OR = max), as opposed to
   Łukasiewicz logic (AND = max(0, x+y−1), OR = min(1, x+y)) or
   product logic (AND = x·y, OR = x+y−xy); see Hájek (1998) for
   the standard t-norm-fuzzy-logic survey. The min/max choice is
   correct as stated, but is piecewise-linear and non-
   differentiable at the diagonal `a = b`, which breaks gradient
   flow when the connectives compose with the rest of the
   tensor-op graph — a well-known issue in the differentiable
   fuzzy logic literature (van Krieken, Acar & van Harmelen 2022
   survey several t-norm-derived operators in the
   neural-symbolic context).

   Sutra resolves this by Lagrange-interpolating each operator's
   truth table as a polynomial that is *exact* on the {−1, 0, +1}²
   grid and C^∞ everywhere else. For two operands, a 2-D Lagrange
   interpolant on a 3×3 grid is uniquely determined by the nine
   values it must take, so each connective has a single closed
   polynomial form.

   **Basis.** {AND, OR, NOT} is the basis from which every other
   Kleene-valid connective derives. Their closed polynomials are:

   - `AND(a, b) = (a + b + ab − a² − b² + a²b²) / 2`
   - `OR(a, b)  = (a + b − ab + a² + b² − a²b²) / 2`
   - `NOT(a)    = −a`

   On the discrete grid these match Gödel fuzzy logic's min/max
   behavior exactly; off the grid they are smooth interpolants
   rather than piecewise functions.

   **Derived connectives.** Every other connective in the Kleene
   fragment is both a logical composition of the basis and a
   closed polynomial in its own right:

   | Connective   | Derivation in {AND, OR, NOT}        | Closed polynomial |
   |---|---|---|
   | `NAND(a, b)` | `NOT(AND(a, b))`                    | `−(a + b + ab − a² − b² + a²b²) / 2` |
   | `NOR(a, b)`  | `NOT(OR(a, b))`                     | `−(a + b − ab + a² + b² − a²b²) / 2` |
   | `XOR(a, b)`  | `OR(AND(a, NOT(b)), AND(NOT(a), b))` | `−ab` |
   | `XNOR(a, b)` | `NOT(XOR(a, b))`                    | `ab` |

   The XOR and XNOR rows are the surprise of the table: their
   3×3 Lagrange interpolant collapses to a single multiplicative
   term because the value is zero whenever either input is the
   unknown U=0 and bilinear in the remaining {−1, +1} corners.
   So `&&`, `||`, `!`, and any derived Kleene-valid connective
   are polynomial tensor-op-graph fragments — gradient-compatible,
   branchless, and exact on the discrete-logic regime. The
   differentiability of these polynomials is what lets fuzzy
   logic compose with the rest of the substrate-pure runtime: a
   symbolic if-then rule built from these gates is one fused
   subgraph that PyTorch autograd can backprop through end-to-
   end (§3.6).

2. **Beta reduction to tensor normal form, used as the compiler
   architecture.** Sutra inverts what conventional compilers do:
   instead of progressively lowering a high-level program toward
   machine instructions, the compiler aggressively *expands* the
   program — inlining operator definitions, unfolding constants,
   beta-reducing through bound names — until the residual is a
   straight-line algebraic expression over the VSA primitives.
   That residual is then algebraically reduced to *tensor normal
   form*: a fused sequence of matmul / element-wise / nonlinear
   tensor ops with no remaining named bindings or function calls.
   In the recurrent case the form generalizes to *recurrent
   tensor normal form*, where the RNN cell body is itself in
   tensor normal form and the recurrence is a separate top-level
   operator.

3. **Tail recursion as the loop primitive, eliminating control
   flow, with O(1) memory in recursion depth.** Loops are not
   `for`/`while` constructs over a host-side iterator. They are
   tail-recursive function declarations (`do_while`, `while_loop`,
   `iterative_loop`, `foreach_loop`) whose body's
   `return NAME(args)` becomes the recurrent step. Each loop
   compiles to a fixed-T soft-halt RNN cell with substrate-pure
   halt detection (heaviside step → cumulative monotone halt →
   soft-mux state freeze). The state vector h_t carries the entire
   execution context in superposition over a fixed-width vector,
   so memory overhead is **constant in recursion depth**: a Sutra
   program can specify deeper recurrence (a larger T at compile
   time, §1.2 manifest setting) without expanding the runtime
   memory budget. There is no per-iteration stack frame, no
   growing context, no heap allocation keyed by depth — the loop
   body updates the same state tensor T times. Halt completion
   propagates through nested calls to the program's final output:
   a loop that fails to converge wipes the program's result.

4. **Synthetic-dimension rotation binding as an angular hash map.**
   The compiler maps a high-dimensional codebook onto a set of
   reserved synthetic dimensions and uses Haar-random orthogonal
   rotations (seeded from the role's content hash) to bind keys
   to slots. This is, to the authors' knowledge, the first use of
   a high-dimensional rotation pattern as the substrate for a
   functional hash-map primitive. After binding, the resulting
   structure participates in the same beta-reduction pass as the
   rest of the program and is reduced to (recurrent) tensor
   normal form alongside everything else.

These four primitives are integrated into a single working
compiler that lowers `.su` source to a self-contained PyTorch
module and runs on CPU or CUDA. Loops are **self-halting**:
each iteration computes a halt-cum scalar, and the Python loop
driver breaks the moment that scalar saturates. There is no
compile-time iteration cap and no runtime budget parameter —
programs terminate when their halt condition fires, exactly the
way any other programming language's `while` loop terminates.

In addition to the four technical contributions above, this paper
also reports an **engineering / execution result**:

- **End-to-end string I/O through the substrate, via a
  compile-time codebook + nearest-string decode.** Every embedded
  string in a `.su` program is embedded once at compile time via
  the project's configured frozen LLM and stored in an embedded
  codebook store alongside its label. At runtime, the inverse
  operation `nearest_string(vector)` returns the label whose
  embedding is closest to the queried vector. The frozen LLM is
  load-bearing for this design: a deterministic, reproducible,
  dense-enough string-to-vector map is what makes the codebook
  practical and the inverse decode reliable. Replacing the
  embedding with the random hypervectors that classical VSA
  literature assumes would still yield a working algebra but
  would leave the language with no I/O story — strings would have
  no canonical mapping to vectors and the substrate would have
  nowhere to decode labels from. To the authors' knowledge, Sutra
  is therefore the only HDC implementation that ships a practical
  end-to-end string-in / string-out path as a built-in compiler
  concern. Existing HDC libraries (TorchHD and similar) expose
  the algebra over user-supplied hypervectors but require users
  to maintain their own string-to-vector mapping and codebook
  by hand; that boilerplate is what makes most HDC code stay
  research-tooling-shaped rather than program-shaped. This is
  not a new theoretical primitive but a working integration: the
  compiler, the runtime, the embedded codebook, and 13
  demonstration programs in the smoke test (with 23 `.su` files
  in the `examples/` directory) exercise the end-to-end pipeline.

### 1.3 What this paper is not

This paper is not a survey of VSA binding operations; the
contribution is *not* a new binding scheme in isolation, but the
integration of the four primitives in §1.2 into a single typed,
purely functional language with a working compiler. The
soft-halt RNN cell is straightforward in the abstract; what is
not straightforward is making it the loop primitive of a
programming language whose entire program lowers to one
tensor-op graph through beta reduction. The paper is neither a
deep-learning architecture paper nor a pure programming-language
theory paper; it is the specific construction that ties the two
together.

---

## 2. Related Work

### 2.1 Vector Symbolic Architectures

VSA is a family of algebraic frameworks for computing with high-
dimensional vectors (Kanerva 2009; Plate 1995; Gayler 2003). The
standard VSA development assumes hypervectors drawn from a
controlled random distribution designed for the algebra; bind is
typically Hadamard product or circular convolution. Frozen LLM
embedding spaces are not designed for VSA, and the textbook bind
operations do not always transfer cleanly to them. Rotation
binding (`R_role @ filler` for a role-seeded Haar-random
orthogonal `R_role`) is the choice that worked across the
substrates we tested, and is what Sutra uses today; §3.1
reports the per-substrate measurements supporting that choice.

The closest software peer in the VSA space is **TorchHD**
(Heddes et al. 2023), a PyTorch library that exposes VSA
primitives (bind, bundle, similarity) as tensor operations.
Sutra and TorchHD differ on what the user writes and what the
compiler does:

- **TorchHD is a *library*.** The user writes Python code that
  calls TorchHD primitives; control flow is host-side Python;
  there is no source-language layer above the primitives, no
  compile step, and no algebraic reduction across primitive
  calls. Each primitive call is a tensor op, but the program
  itself is a Python function with whatever control flow the
  user wrote.
- **Sutra is a *language with a compiler*.** The user writes
  `.su` source which the compiler beta-reduces to tensor normal
  form (§1.2-2): a single straight-line tensor-op graph with no
  Python control flow. Loops are tail-recursive function
  declarations that lower to soft-halt RNN cells; conditionals
  are differentiable fuzzy interpolations rather than Python
  `if`. Hash-map structure is implemented via synthetic-dimension
  rotation, not via a host-side dictionary.

This is not a "TorchHD is bad" claim; TorchHD is the right tool
for using VSA primitives as a library in a Python program. Sutra
is the construction that compiles a separate source language to
the same primitive set with no host-side residue, which TorchHD
is not designed to do.

A second axis on which the two systems differ, and where to the
authors' knowledge Sutra is uniquely positioned within the broader
HDC ecosystem, is **string I/O**. TorchHD and other HDC libraries
expose the algebra over user-supplied hypervectors: the user
constructs random or hash-derived vectors for whatever they want
to represent, maintains a `dict[str, hypervector]` mapping by
hand, and decodes by cosine similarity against a manually
assembled codebook tensor. There is no built-in path from external
strings into the substrate or from the substrate back to strings.
Sutra's compile-time codebook (§3.4) closes that loop: every
embedded string in `.su` source is embedded once at compile time
via the configured frozen LLM (e.g. `nomic-embed-text`, 768-d) and
stored in the project's `.sdb` codebook, and the runtime
`nearest_string` operation is the inverse — given any vector, it
returns the nearest known label. The frozen LLM embedding is
load-bearing for this: it is what gives the compile-time codebook
a deterministic, reproducible, and dense-enough mapping for
nearest-neighbor decode to be practical. Replacing the embedding
with random hypervectors would still yield a working VSA algebra
but would have no I/O story — strings would have no canonical
mapping to vectors and decoding would have nowhere to look up
labels. To the authors' knowledge, Sutra is the only HDC
implementation that ships an end-to-end string-in / string-out
path as a built-in compiler concern rather than as user-supplied
boilerplate.

A side-by-side comparison concretizes the difference. The same
role-filler-record task — encode a 3-field record (name, color,
shape) as a single bundled vector, then decode the color field —
written in both systems:

**Sutra** (`examples/role_filler_record.su`, the entire program):

```sutra
vector r_name  = basis_vector("role_name");
vector r_color = basis_vector("role_color");
vector r_shape = basis_vector("role_shape");

vector f_alice  = basis_vector("filler_alice");
vector f_red    = basis_vector("filler_red");
vector f_circle = basis_vector("filler_circle");
// (... three more fillers omitted ...)

map<vector, string> FILLER_NAME = {
    f_alice: "alice", f_red: "red", f_circle: "circle",
    /* ... */
};

function vector make_record(vector name, vector color, vector shape) {
    return bundle(
        bind(r_name, name), bind(r_color, color), bind(r_shape, shape)
    );
}

function string decode_field(vector record, vector role) {
    vector recovered = unbind(role, record);
    vector winner = argmax_cosine(recovered,
        [f_alice, f_red, f_circle, /* ... */]);
    return FILLER_NAME[winner];
}

function string main() {
    vector rec = make_record(f_alice, f_red, f_circle);
    return decode_field(rec, r_color);
}
```

The compiler reduces this whole program to a fused tensor-op
graph: every `basis_vector` call is resolved at compile time
(strings embedded into the substrate, stored in the compile-time
codebook); `bind` and `unbind` lower to a single matmul each;
`argmax_cosine` lowers to one cosine-similarity matmul plus an
argmax; the `FILLER_NAME` map lowers to the substrate-resident
codebook. The runtime decodes by `nearest_string` against the
embedded codebook — the string `"red"` comes out without the
program ever leaving the tensor graph at the program-semantics
level.

**TorchHD equivalent** (`experiments/role_filler_record_torchhd.py`,
abridged):

```python
import torch, torchhd

torch.manual_seed(42)

# 1. MANUAL hypervector creation. There is no "embed string";
#    the user maintains the string-to-vector mapping.
roles = {n: torchhd.random(1, 768, vsa="MAP")
         for n in ["name", "color", "shape"]}
fillers = {n: torchhd.random(1, 768, vsa="MAP")
           for n in ["alice", "bob", "red", "blue", "circle", "square"]}

# 2. MANUAL codebook tensor for decoding.
filler_names = ["alice", "bob", "red", "blue", "circle", "square"]
codebook = torch.cat([fillers[n] for n in filler_names], dim=0)

# 3. Build the record (Python control flow).
record = torchhd.bundle(
    torchhd.bind(roles["name"],  fillers["alice"]),
    torchhd.bundle(
        torchhd.bind(roles["color"], fillers["red"]),
        torchhd.bind(roles["shape"], fillers["circle"]),
    ),
)

# 4. Decode (Python control flow).
recovered = torchhd.bind(record, torchhd.inverse(roles["color"]))
sims = torchhd.cosine_similarity(recovered, codebook)
result = filler_names[int(torch.argmax(sims))]
```

Both programs return `"red"`. The differences are structural:

- The Sutra program contains no Python; the TorchHD program *is*
  Python with library calls.
- The Sutra string-to-vector mapping is automatic via
  `basis_vector("filler_alice")`; in TorchHD the user constructs
  hypervectors and maintains a `dict[str, hypervector]` by hand.
- The Sutra codebook is implicit (the compiler constructs it from
  the literals in the source); in TorchHD the user stacks vectors
  into a codebook tensor explicitly.
- The Sutra program lowers to one tensor-op graph; the TorchHD
  program is a Python function whose control flow stays in Python
  even after the library calls dispatch to PyTorch.

These are differences in *what kind of artifact* the user
writes, not in *which library is faster*. The CUDA kernels both
systems eventually call into are largely the same — it's the
shape of the program before it hits CUDA that differs.

### 2.2 Comparison to other neuro-symbolic languages

The closest neuro-symbolic-language peer is **Scallop** (Li et
al. 2023), a Datalog-based language with PyTorch bindings whose
differentiability comes from an extended provenance-semiring
framework over relational queries. Scallop's architectural shape
is a two-stage pipeline: a neural model `M_θ` extracts discrete
symbols `r` from raw input, and a Datalog program `P` performs
logical reasoning over those symbols to produce the output. The
boundary between perception and reasoning is sharp; the symbols
that flow between them are typed relations.

Sutra's shape is different at the same architectural level. There
is no perception-then-reasoning split: the substrate is a
continuous embedding space throughout, and primitives like
`bind`, `unbind`, `bundle`, and similarity operate on vectors
end-to-end. There is no discrete symbolic layer to extract into
or reason over. The whole program — including what would in
Scallop be the logic program — compiles to a single fused
tensor-op graph through beta reduction (§1.2-2). Differentiability
is inherited from the tensor-op graph itself; there are no
provenance semirings because there is no relational layer to
annotate.

The two systems are good at different things. Scallop is the
right tool when an application's problem structure is naturally
relational — scene-graph queries, knowledge-graph reasoning,
combinatorial search over typed entities — and the perception
side can be cleanly factored out into a separate neural module.
Sutra is the right tool when computation is best expressed as
algebra on vectors and the substrate is a frozen LLM embedding
space the program reads strings into and decodes strings out of.
Neither subsumes the other; they answer different
"what kind of program does the user want to write?" questions.

The other named neuro-symbolic peers — DeepProbLog (Manhaeve et
al. 2018), Logic Tensor Networks (Serafini & Garcez 2016;
Badreddine et al. 2022), and NeurASP (Yang et al. 2020) — share
Scallop's perception-then-reasoning shape and differ similarly
from Sutra. DeepProbLog grounds neural predicates in a ProbLog
proof tree; LTN compiles first-order-logic formulas into
differentiable t-norm losses over learned embeddings; NeurASP
extends Answer Set Programming with neural predicates. All three
treat symbols as a separate stratum from the neural layer.

The HDC-side comparison is sparser. The closest HDC peer with
compiler infrastructure is HDCC (Vergés et al. 2023), which
translates a description-file DSL into self-contained C for
embedded classification. HDCC ships random and level
hypervectors only (no LLM substrate), supports no general
control flow (no loops, no recursion, no conditionals beyond
the encode-then-classify pipeline), and is scoped to
classification rather than general-purpose programming. The
TorchHD library and OpenHD / HDTorch frameworks similarly do
not expose loops as a language primitive — control flow lives
in the host Python.

To the authors' knowledge, no published HDC system targets the
specific configuration that Sutra occupies: a single tensor-op
graph folding the whole program — including substrate I/O and
tail-recursive loops with constant memory overhead in recursion
depth (§3.3) — over a frozen externally-trained embedding
substrate. The combination of (a) one fused tensor-op graph as
the compile target, (b) HDC primitives as the operations, (c) a
frozen vector embedding space as the substrate (the demonstrations
use LLM embeddings, but any frozen embedding of comparable
dimensionality applies — see §1 abstract), and (d) tail-recursive
loops compiled to soft-halt RNN cells over a fixed-width state
vector is what distinguishes Sutra from each of these peers, not
any one of those four properties in isolation.

A consequence of (a)–(d) the paper does not lean on but is worth
noting: because the compiled artifact is itself a tensor-op
graph against an externally-supplied vector substrate, a Sutra
program can in principle be wired into an existing trained
neural network as a neural API — reading activations from a
designated layer of a CNN, MLP, or transformer as its input
substrate, and emitting tensor-op outputs that the surrounding
network consumes. Demonstrating this composition with a real
host network is left as future work, but the construction does
not rely on the substrate being a language model.

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

## 3. Consolidation into Canonical Primitives

The central design move: hold the operation interface fixed
(`bind`, `unbind`, `bundle`, `similarity`, `rotate`) and pick a
binding implementation that works on the LLM substrates we use.
Standard VSA's Hadamard product is not robust here because
elementwise multiplication of correlated real-valued vectors
produces destructive crosstalk on bundled retrieval (§3.1
measures this directly). Rotation binding works: each role gets
a Haar-random orthogonal matrix, seeded by a hash of the
role-vector content, and `bind(filler, role) = R_role @ filler`.
Unbind is the matrix transpose. The rotation is invertible by
construction and stays well-conditioned on the substrates we
tested.

The compiler emits role rotations as cached matrices, pre-warmed
at module init from the codebook so the runtime never pays the
QR-construction cost on the hot path. Binding becomes a single
matmul against a precomputed matrix — the GPU-friendly shape that
fuses with surrounding tensor ops.

The role of the LLM substrate in Sutra is to provide a
deterministic I/O mapping: a string in the source program embeds
to a specific 768-d vector via the configured frozen LLM, and at
runtime the inverse `nearest_string` lookup decodes any vector
back to the closest known label. The substrate is what makes
program input and output expressible as ordinary strings while
the runtime computes in vector space. Sutra does not depend on
any particular semantic property of the embedding beyond the
mapping being stable and the dimensionality being fixed; the
binding, bundling, and similarity primitives operate on the
vectors as opaque dense tensors and are correct under any
substrate that ships the same dimensionality.

### 3.1 Capacity of rotation versus Hadamard binding across substrates

We measure decode accuracy as a function of bundle width k on
real embeddings — not on random fillers — across **four
substrates spanning two modalities**: three frozen LLM text
encoders (nomic-embed-text, all-minilm, mxbai-embed-large) and
one frozen protein language model (ESM-2 small,
`facebook/esm2_t6_8M_UR50D`). The protein-LM substrate
embeds an 84-sequence amino-acid vocabulary (canonical signal
peptides, cell-penetrating peptides, antimicrobial peptides,
classic affinity-tag motifs, and deterministic random k-mers);
the LLM substrates each embed the same 84-word noun vocabulary
(animals, foods, objects, places, abstract nouns) via Ollama.
All embeddings are unit-normalized; nomic-embed-text and ESM-2
are additionally mean-centered. For each bundle width and each
binding scheme we run 10 trials, each sampling k random (role,
filler) pairs without replacement, forming the bundle, and
decoding by unbind + argmax-cosine against the full codebook.
The two binding schemes compared are *rotation binding*
(`R_role @ filler`, role-seeded Haar-random orthogonal `R_role`)
and *Hadamard binding* (elementwise product `role .* filler`,
the textbook MAP-VSA choice).

**nomic-embed-text (768-d, mean-centered):**

| k | rotation accuracy | rotation signal cos | Hadamard accuracy | Hadamard signal cos |
|---:|---:|---:|---:|---:|
| 2  | 100.0% | +0.703 | 95.0% | +0.488 |
| 4  | 100.0% | +0.497 | 95.0% | +0.400 |
| 8  | 100.0% | +0.354 | 87.5% | +0.307 |
| 16 | 100.0% | +0.251 | 84.4% | +0.230 |
| 24 | 100.0% | +0.203 | 60.8% | +0.189 |
| 32 |  99.1% | +0.176 | 63.1% | +0.167 |
| 48 |  93.3% | +0.144 | 48.3% | +0.136 |

**all-minilm (384-d):**

| k | rotation accuracy | rotation signal cos | Hadamard accuracy | Hadamard signal cos |
|---:|---:|---:|---:|---:|
| 2  | 100.0% | +0.711 | 45.0% | +0.386 |
| 4  | 100.0% | +0.506 | 10.0% | +0.335 |
| 8  | 100.0% | +0.356 |  7.5% | +0.315 |
| 16 |  92.5% | +0.252 |  3.1% | +0.299 |
| 24 |  76.2% | +0.203 |  2.9% | +0.300 |
| 32 |  66.9% | +0.179 |  2.5% | +0.297 |
| 48 |  42.3% | +0.144 |  1.7% | +0.294 |

**mxbai-embed-large (1024-d):**

| k | rotation accuracy | rotation signal cos | Hadamard accuracy | Hadamard signal cos |
|---:|---:|---:|---:|---:|
| 2  | 100.0% | +0.708 | 15.0% | +0.311 |
| 4  | 100.0% | +0.500 |  2.5% | +0.304 |
| 8  | 100.0% | +0.353 |  2.5% | +0.295 |
| 16 |  98.8% | +0.251 |  1.2% | +0.294 |
| 24 |  95.8% | +0.203 |  0.8% | +0.293 |
| 32 |  85.3% | +0.176 |  0.9% | +0.292 |
| 48 |  72.1% | +0.146 |  1.0% | +0.291 |

**ESM-2 small protein language model (320-d, mean-centered) —
non-LLM, non-text substrate:**

| k | rotation accuracy | rotation signal cos | Hadamard accuracy | Hadamard signal cos |
|---:|---:|---:|---:|---:|
| 2  | 100.0% | +0.713 | 75.0% | +0.470 |
| 4  | 100.0% | +0.501 | 50.0% | +0.323 |
| 8  | 100.0% | +0.349 | 28.7% | +0.257 |
| 16 |  90.6% | +0.252 | 16.2% | +0.185 |
| 24 |  77.1% | +0.205 | 11.2% | +0.171 |
| 32 |  61.9% | +0.174 |  6.2% | +0.141 |
| 48 |  44.2% | +0.143 |  4.2% | +0.117 |

ESM-2 (Lin et al., Science 2023) is a frozen protein language
model trained on UniRef sequences with no exposure to natural-
language text; its embedding space encodes amino-acid context,
not word semantics. The reproduction script is
`experiments/rotation_binding_capacity_bioinformatics.py`. The
same rotation-vs-Hadamard separation appears in this entirely
different modality: rotation holds 100% accuracy through k=8
and degrades gracefully thereafter; Hadamard collapses fast.

**Reversibility round-trip (rotation):** mean
‖unbind(R, bind(R, x)) − x‖ = 1.5 × 10⁻¹⁵ across the same trials
on every substrate, i.e. floating-point round-off. Haar-random Q
is orthogonal so Qᵀ Q = I; reversibility is exact modulo
numerical error.

**Interpretation.** Rotation binding works across all four
substrates — 100% decode accuracy up through k=8 in every case,
with graceful degradation thereafter. Hadamard binding does not:
on `mxbai-embed-large` even k=2 yields 15% accuracy (worse than
chance for a target-versus-83-distractors decode); on
`all-minilm` Hadamard is at 45% for k=2 and 1.7% by k=48; on
ESM-2 protein embeddings Hadamard starts at 75% and collapses
to 4.2% by k=48; on nomic-embed-text Hadamard is in the same
band as rotation only at very small k and falls behind sharply
by k≥24. The signal cosine for Hadamard is comparable to
rotation's, but the noise floor is much higher because the
elementwise product of correlated real-valued embeddings
produces a result that overlaps with many distractors in the
codebook rather than near-orthogonally with one.

The substrate-agnosticism claim is not a hedge — the same
characteristic shape (rotation: graceful degradation; Hadamard:
fast collapse) reproduces on a dense vector space produced by a
protein language model that has never seen natural-language
text. Sutra's rotation primitive is sensitive to whether the
substrate is dense and high-dimensional, not to whether the
substrate was trained on words. Reproducing experiments:
`experiments/rotation_binding_capacity_llm.py` (LLM substrates)
and `experiments/rotation_binding_capacity_bioinformatics.py`
(ESM-2). Raw JSON is committed alongside.

#### 3.1.1 Noise accumulation across chained bind/unbind cycles

The §3.1 protocol measures *one* cycle of bind+bundle+unbind.
Real records can nest: a recovered filler can become the role
of a sub-record. Each nested level adds bundle noise. We
quantified that.

For each substrate, chain length L ∈ {1, 2, 4, 8, 16, 32}, 20
trials, bundle width 4 (3 distractors per cycle): pick a
starting filler, forward-bind through L role rotations bundling
3 distractor (role, filler) pairs at each step, then unbind in
reverse and decode. Two flavors: **raw** (no cleanup) and
**snap** (argmax-cosine cleanup against the codebook after each
unbind step).

| substrate | L=1 raw | L=2 raw | L=4 raw | L=1 snap | L=2 snap | L=4 snap |
|---|---:|---:|---:|---:|---:|---:|
| nomic-embed-text | 100% | 100% | 20% | 100% | 10% | 0% |
| all-minilm | 100% | 100% | 5% | 100% | 0% | 0% |
| mxbai-embed-large | 100% | 100% | 5% | 100% | 0% | 0% |

By chain length 8 raw accuracy is at chance (1/84) on all three
substrates. **The crosstalk floor is real**: deep nested
bind+bundle compositions hit it well before any language-design
ceiling. This is the right scope statement for the §3.1
capacity claim — the demonstrated regime is single-cycle
records (the actual shape of `role_filler_record.su`,
`knowledge_graph.su`, the soft-dispatch and predicate-lookup
demos), not record-of-record-of-record at depth 4+.

Snap is *worse* than raw past chain length 1: a hard codebook
commitment converts soft noise into a high-confidence wrong
answer that the next unbind cannot recover from. This matters
for compiler design — the runtime does not implicitly snap
between operations; cleanup is an explicit step the program
schedules where it knows the codebook is the right reference.

**Distinction from the soft-halt RNN cell (§3.3).** The soft-
halt cell's per-tick update is `state ← R · state` with a halt-
gate component update — *no per-tick bundle of distractors*.
Pure rotation chains are exact: the §3.1 reversibility
round-trip is 1.5 × 10⁻¹⁵ per cycle. T=50 iterations
accumulate floating-point round-off, not crosstalk; the noise
mechanism measured in this subsection does not apply to the
loop-cell regime. The reproduction script is
`experiments/crosstalk_chain.py`; raw JSON in
`experiments/crosstalk_chain_results.json`.

### 3.2 The extended-state-vector layout

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

### 3.3 First-class loops as RNN cells

Runtime data-dependent loops compile to **self-halting RNN
cells**. Each tick: snapshot pre-step state, evaluate the halt
condition on the substrate (truth-axis read → heaviside step →
cumulative saturating sum), run the body which uses `pass values`
(or equivalently `return NAME(args)` tail recursion) to update
state locals, then a soft-mux blends pre-step and new-step state
weighted by the halt accumulator. The loop driver is a Python
`while True:` that **breaks the moment `halt_cum` saturates**.
There is no compile-time iteration cap and no runtime budget
parameter — programs terminate when their halt condition fires,
exactly the way any other programming language's `while` loop
terminates. The halt-cum scalar that drives the break is one
boundary read per iteration, the same kind of boundary operation
as the codebook's `nearest_string` decode (§3.4).

**Loop body vs loop driver.** Sutra's "tensor normal form"
applies to the *body* of each loop tick: one fused chunk of
tensor ops with no Python control flow inside any operation.
The *loop itself* is a Python `while True: … break` driver that
invokes that fused body until it self-halts. We do **not** claim
the loop is unrolled into the body's tensor graph at compile
time. Standard PyTorch tracing handles a Python while-loop
wrapping pure tensor ops fine — autograd records each
iteration's operations as it executes (this is the mechanism
§3.6 relies on for end-to-end backprop through the cell). The
`torch.compile` wrapping (opt-in, §3.5) may further fuse the
per-call iteration at trace time, but the language semantics do
not require that fusion: the default runtime is a Python loop
calling normal-form bodies until convergence.

(The recurrent computational substrate that emerges from this
construction is the same shape Siegelmann & Sontag (1992)
analyzed when they showed recurrent neural networks with rational
weights can compute any Turing-machine-computable function. We
mention this for completeness — the result is well-established
and assumed for any general-purpose programming language; we do
not lean on it as a contribution.)

**Constant memory in recursion depth.** The state vector the
loop body updates is fixed-width: `[semantic | synthetic]`,
total dimensionality set at compile time and unchanged across
all iterations. A tail-recursive loop in Sutra therefore consumes
**O(1) memory in the state vector** regardless of how many
iterations it runs — no per-step stack frame, no growing context,
no heap allocation keyed by depth. Compute scales linearly in
the number of iterations actually executed (each tick runs the
fused body once), and during training the autograd tape grows
linearly in the number of iterations executed up to the
`backward()` call (standard PyTorch behavior, freed after the
backward pass). So a more honest summary is: **O(1) state, O(N)
compute, O(N) gradient tape during training**, where N is
*iterations actually executed* rather than a compile-time budget.
For inference (no training) the gradient tape is not built and
the only memory cost is the fixed-width state vector. Compared
with sequence models that accumulate a context window linearly
with input length and with stack-based recursive languages whose
memory footprint grows with call depth, Sutra's recurrent-tail-
recursive form folds an arbitrary execution trajectory into a
single fixed-width vector via VSA superposition.

To the authors' knowledge, no other HDC system or HDC compiler
exposes user-program-level recursion at all (HDCC compiles
classification pipelines only, with no general control flow;
TorchHD requires the user to write Python loops over
hypervectors, which are not constant-memory in either depth or
context).

### 3.4 Embedded codebook store

The compile-time codebook is stored in an embedded vector
database (internally called SutraDB) that ships as part of the
compiler — analogous to SQLite being embedded in an application
rather than run as a separate service. It holds the (embedding,
label) pairs that arise from `basis_vector("...")` and
`embed("...")` calls in the source. The data model is RDF
triples with f32-vector literals as the object position, indexed
by a built-in HNSW index for nearest-neighbor decode. The
on-disk format is a `.sdb` file that travels alongside the
compiled Python module. There is no external service, no
separate install, and no network dependency.

Every embedded string in a Sutra program is inserted into the
compile-time `.sdb` codebook, with the embedding as the object
of a triple typed `<http://sutra.dev/f32vec>`. The runtime decode
operation `_VSA.nearest_string(query)` is the inverse of `embed`:
given any vector, return the nearest-string label from the
substrate-resident codebook. Strings declared but unused in
expressions are still inserted, so they remain decodable. The
compiled module's Python data section never carries the
embeddings — they live in the `.sdb` file, which is an artifact
of compilation, not a service the runtime contacts.

**Decode complexity.** `nearest_string` runs over an HNSW
(Hierarchical Navigable Small World) approximate-nearest-neighbor
graph maintained by the triplestore. HNSW (Malkov & Yashunin,
TPAMI 2020) is a well-established ANN structure with **O(log N)
expected query time and O(log N) worst-case query time** under
standard graph-construction parameters — it has displaced
linear scan as the default ANN index in Faiss, Milvus, Weaviate,
Qdrant, and most production vector databases for this exact
reason. So a 100-string codebook and a 100,000-string codebook
have comparable decode latency at runtime, modulo the HNSW's
tunable `M` (graph degree) and `ef_search` (beam width)
parameters; the cost difference is roughly one extra graph hop
per 10× growth in N.

**HNSW is a boundary operation, not part of the in-graph tensor
pipeline.** The body-vs-driver distinction from §3.3 applies
here too: the tensor-op graph computes a query vector; the HNSW
lookup happens at the *output boundary*, returning a host string
that hands off to Python the way any compiled program returns a
host value. Calling out to a well-engineered Rust ANN library
for the codebook decode is the same shape as calling out to
PyTorch for a matmul — both are the runtime's substrate, neither
is "host-side control flow" of the kind substrate purity forbids.

### 3.5 Project manifest (`atman.toml`)

A Sutra project is described by an `atman.toml` manifest at the
project root. The manifest declares the entry source file, the
embedding substrate (provider, model, dimensionality, and whether
to mean-center), and compile-time settings. A minimal example:

```toml
[project]
name = "sutra-examples"
entry = "hello_world.su"
substrate = "silicon"

[project.embedding]
provider = "ollama"
model = "nomic-embed-text"
dim = 768
mean_center = true
```

The compiler reads `[project.embedding]` to know which LLM to
query for `embed("...")` and `basis_vector("...")` calls at
compile time and to fix the dimensionality of the runtime
tensor-op graph. Changing the substrate (e.g. swapping
`nomic-embed-text` for a different 768-d model, or for a 1536-d
model with a corresponding `dim` update) re-runs the embed step
at compile time and produces a different `.sdb` codebook; the
source code does not change. The manifest format is
intentionally narrow — it covers what the compiler needs to
deterministically produce a `.sdb` and emit a PyTorch module,
and nothing else.

### 3.6 End-to-end differentiable training through Sutra operations

Sutra's fuzzy conditionals depend on embedding comparisons,
which are inherently uncertain — the similarity between two
embeddings is a continuous value, not a crisp truth. This is
a feature, not a limitation: because the fuzzy logic gates
(AND, OR, NOT) are Lagrange polynomials over continuous truth
values, gradient descent can optimize the parameters that drive
those truth values *while preserving the symbolic program
structure unchanged*.

**Setup.** 15 words from three categories (animals, vehicles,
foods) are embedded via nomic-embed-text (768-d, frozen). Three
learnable prototype vectors are initialized randomly. The
classifier computes cosine similarity between an input and each
prototype, then applies Lagrange-interpolated fuzzy AND/NOT gates
to produce per-class scores:

    rule_i = AND(sim(x, proto_i), AND(NOT(sim(x, proto_j)),
                                      NOT(sim(x, proto_k))))

The symbolic structure — three fuzzy if-then rules composed of
AND and NOT gates — is fixed throughout training and remains
human-readable. What changes are the prototype embeddings that
the gates evaluate against. The rule still says "classify as
category *i* if similar to prototype *i* and not similar to the
others"; training teaches the prototypes *what those categories
look like in the embedding space* so the fuzzy truth values align
with the intended classification. This is the neuro-symbolic
proposition: the symbolic layer (the program, its rules, its
logic gates) provides interpretability and structure; the neural
layer (the embedding comparisons) provides learnability.

**Results.** Before training (random prototypes), accuracy is 40%
(chance = 33%). After 300 epochs, accuracy reaches 100%. Gradient
norms for all three prototypes are nonzero at every step,
confirming that backpropagation reaches every learnable parameter
through the full chain of Sutra operations: `similarity` (cosine
dot product) -> `fuzzy_not` (Kleene negation) -> `fuzzy_and`
(Lagrange min polynomial) -> cross-entropy.

| Phase  | Accuracy | Loss   |
|--------|----------|--------|
| Before |     40%  |  1.93  |
| After  |    100%  |  0.04  |

The symbolic content of the program — three AND/NOT rules over
three prototypes — is identical before and after training.
The program is as readable at epoch 300 as at epoch 0. Only the
prototype embeddings moved, and they moved because the
polynomial fuzzy gates transmitted gradient information from the
classification loss all the way back to the embedding vectors.
No Sutra-specific autograd machinery is required; standard
`torch.autograd` suffices because the compiler emits only
operations that PyTorch already knows how to differentiate.

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

### 4.2 Compile-time resolution to tensor normal form

Two compile-time mechanisms are central to how the compiler
achieves tensor normal form:

1. **Precomputed rotation matrices.** Every role rotation is
   constructed at compile time (`prewarm_rotation_cache`) and
   stored as a constant tensor. At runtime, `bind(role, filler)`
   is a single matmul against a precomputed matrix — the
   compile-time resolution eliminates the QR construction from
   the runtime graph entirely.
2. **Fixed-depth loop unroll.** Tail-recursive loops compile to a
   fixed-T iteration over the RNN cell body. The compiler fixes T
   at compile time (configurable, default 50), and the soft-halt
   gating ensures convergence typically occurs in far fewer steps.
   With `torch.compile` (opt-in via `SUTRA_TORCH_COMPILE=1`), the
   tracer folds the unrolled iteration into a single fused kernel.

Both are instances of the same principle: the compiler resolves
structure at compile time so the runtime is a straight-line
tensor-op graph. Role rotations become constant matrices;
recursion becomes a fixed-depth cell. This is how beta reduction
to tensor normal form works in practice.

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

### 6.2 Codebook integration depth

The embedded codebook store covers the compile-time embed →
runtime decode path today. Extended features (hashmap routing,
persistent codebook across runs via `SUTRA_DB_PATH`) are
deferred until there is a concrete requirement beyond the
current demonstration corpus.

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
- Kleene, S. C. (1952). *Introduction to Metamathematics*. North-
  Holland. The strong three-valued logic system used as the
  ground for Sutra's polynomial fuzzy connectives (§1.2-1).
- Mikolov, T., Chen, K., Corrado, G., & Dean, J. (2013). Efficient
  estimation of word representations in vector space. *ICLR
  Workshop*.
- Badreddine, S., Garcez, A. d., Serafini, L., & Spranger, M.
  (2022). Logic Tensor Networks. *Artificial Intelligence* 303.
- Hájek, P. (1998). *Metamathematics of Fuzzy Logic*. Trends in
  Logic vol. 4. Kluwer Academic. The standard reference for
  t-norm-based fuzzy logics (Gödel, Łukasiewicz, product) cited
  in §1.2-1 to place Sutra's polynomial connectives.
- Heddes, M., Nunes, I., Vergés, P., Kleyko, D., Abraham, D.,
  Givargis, T., Nicolau, A., & Veidenbaum, A. (2023). Torchhd: An
  open source python library to support research on
  hyperdimensional computing and vector symbolic architectures.
  *Journal of Machine Learning Research* 24(255):1–10.
- Li, Z., Huang, J., & Naik, M. (2023). Scallop: A Language for
  Neurosymbolic Programming. *Proceedings of the ACM on Programming
  Languages* 7(PLDI):1463–1487. arXiv:2304.04812.
- Manhaeve, R., Dumancic, S., Kimmig, A., Demeester, T., & De
  Raedt, L. (2018). DeepProbLog: Neural Probabilistic Logic
  Programming. *NeurIPS*.
- Serafini, L. & Garcez, A. d. (2016). Logic Tensor Networks: Deep
  Learning and Logical Reasoning from Data and Knowledge. *NeSy
  Workshop*.
- van Krieken, E., Acar, E., & van Harmelen, F. (2022).
  Analyzing Differentiable Fuzzy Logic Operators. *Artificial
  Intelligence* 302:103602. The differentiable-fuzzy-logic survey
  cited in §1.2-1; analyzes t-norm-derived AND/OR/IMPLIES
  operators in the neural-symbolic context and is the closest
  prior literature to Sutra's polynomial approach.
- Vergés, P., Heddes, M., Nunes, I., Givargis, T., & Nicolau, A.
  (2023). HDCC: A Hyperdimensional Computing compiler for
  classification on embedded systems and high-performance
  computing. arXiv:2304.12398.
- Yang, Z., Ishay, A., & Lee, J. (2020). NeurASP: Embracing Neural
  Networks into Answer Set Programming. *IJCAI*.
- Plate, T. A. (1995). Holographic reduced representations. *IEEE
  Transactions on Neural Networks* 6(3):623–641.
- Siegelmann, H. T. & Sontag, E. D. (1992). On the computational
  power of neural nets. *COLT '92*. Establishes that recurrent
  neural networks with rational weights are Turing-complete; the
  result Sutra inherits via tail-recursive loops over a
  fixed-width state vector.
- Smolensky, P. (1990). Tensor product variable binding and the
  representation of symbolic structures in connectionist systems.
  *Artificial Intelligence* 46(1–2):159–216.
- Sun, Z., Deng, Z. H., Nie, J. Y., & Tang, J. (2019). RotatE:
  Knowledge graph embedding by relational rotation in complex
  space. *ICLR*.
- Wang, Z., Zhang, J., Feng, J., & Chen, Z. (2014). Knowledge
  graph embedding by translating on hyperplanes. *AAAI*.
