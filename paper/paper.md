# Sutra: Compiling a Vector Symbolic Architecture to a Tensor-Op Recurrent Neural Network via Beta Reduction



---

## Abstract

**Sutra** is a typed, purely functional programming language;
a compiled Sutra program *is* a PyTorch neural network. Every
primitive — rotation binding, unbind, bundle, similarity,
soft-halt RNN cells, polynomial Kleene three-valued logic —
compiles to a tensor op, and the compiler beta-reduces the
whole program (control flow included) to a fused tensor-op
graph whose substrate-resident computation is straight-line
dataflow: no in-graph branches inside any operation, no
string-keyed lookup at runtime, and no Python control flow
inside the body of a loop cell — the only remaining host-side
control flow is a thin tick-loop that breaks when a
substrate-computed halt scalar saturates (§3.4). The contribution is the construction that
makes this isomorphism land: a symbolic source language whose
compiled forward pass is a substrate-pure neural network,
autograd-compatible by construction, executable wherever
PyTorch executes. We validate the language across four frozen
embedding substrates spanning two modalities — three text
encoders (nomic-embed-text, all-minilm, mxbai-embed-large) and
one protein language model (ESM-2) — and observe the same
rotation-vs-Hadamard separation across modalities: rotation
binding decodes at 100% accuracy through bundle width k=8 on
every substrate, where Hadamard binding has already collapsed
(e.g. 2.5% on mxbai-embed-large, 28.7% on ESM-2), with
single-cycle bind/unbind exactly reversible (round-trip
≈ 1.5×10⁻¹⁵). The program-network identity is end-to-end
testable through PyTorch autograd: a symbolic if-then program of
fuzzy rules over twenty classes (animal, vehicle, food, color,
clothing, weather, emotion, tool, instrument, profession,
body-part, plant, furniture, building, country, sport, drink,
metal, shape, fabric; 992 words total, K=20 rule tree nineteen
ANDs deep) trains from chance accuracy (4%) to 95% in 300
epochs, with nonzero gradient at every prototype and no
modification to the symbolic source — gradient descent moves
the embeddings the rules evaluate against, not the rule graph
itself.

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
these consolidated operations. The naming: **Sutra** is the
Sanskrit *sūtra* — thread, rule, aphorism — the term for
Pāṇini's foundational Sanskrit grammar.

### 1.1 Contributions

The four core technical contributions of this paper are:

1. **Polynomial fuzzy logic via Lagrange interpolation of
   Kleene's three-valued truth tables.** The truth axis encodes
   T = +1, U = 0, F = −1. On the discrete {−1, 0, +1} grid, the
   Kleene connectives are AND = min, OR = max, NOT = −·. The
   min/max forms (the standard Gödel t-norm/t-conorm choice;
   Hájek 1998) are non-differentiable at the diagonal `a = b`,
   which breaks gradient flow when connectives compose with the
   tensor-op graph (van Krieken, Acar & van Harmelen 2022 survey
   the issue across t-norm-derived neural-symbolic operators).
   Sutra resolves this by Lagrange-interpolating each connective
   as a polynomial that is exact on the 3×3 Kleene grid and C^∞
   elsewhere:

   - `AND(a, b) = (a + b + ab − a² − b² + a²b²) / 2`
   - `OR(a, b)  = (a + b − ab + a² + b² − a²b²) / 2`
   - `NOT(a)    = −a`
   - `XOR(a, b) = −ab`,  `XNOR(a, b) = ab`

   {AND, OR, NOT} is functionally complete for the Kleene
   fragment; XOR/XNOR collapse to a single multiplicative term
   because their interpolant is zero whenever either input is U
   and bilinear in the {−1, +1} corners. Every Kleene-valid
   connective is therefore a polynomial tensor-op-graph fragment
   — gradient-compatible, branchless, and exact on the
   discrete-logic regime. A symbolic if-then rule built from
   these gates is one fused subgraph that PyTorch autograd
   backprops through end-to-end (§3.6).

2. **Beta reduction to tensor normal form.** The compiler
   inlines stdlib operator definitions, beta-reduces through
   bound names, then runs an algebraic-simplification pass over
   the residual. What's left is a fused tensor-op graph (matmul
   / element-wise / nonlinear) with no named bindings or
   function calls. Three concrete moves go beyond standard
   inlining + constant folding: conditionals lower to soft-mux
   polynomials (`(1+cond)/2·a + (1−cond)/2·b`) so the compiled
   artifact has no `if` opcodes; Haar-orthogonal binding
   rotations `R_role` are materialized at compile time so
   runtime `bind` is one matmul against a constant matrix;
   canonical synthetic axes are assigned compile-time so every
   primitive-type read/write is a known index, not a hashtable
   lookup. §4.3 traces this lowering stage-by-stage on a
   concrete program; Figure 1 shows the compilation pipeline.

3. **Tail recursion as the loop primitive.** Loops are
   tail-recursive function declarations (`do_while`,
   `while_loop`, `iterative_loop`, `foreach_loop`) whose body's
   `return NAME(args)` becomes the recurrent step. Each loop
   compiles to a soft-halt RNN cell with substrate-pure halt
   detection (heaviside → cumulative monotone halt → soft-mux
   state freeze). The body of every loop tick is one
   straight-line tensor pipeline with no in-graph branches; a
   thin Python `while True: … break` driver wraps the body and
   terminates when the halt scalar saturates (§3.4). The state
   vector is fixed-width across iterations — **O(1) state, O(N)
   compute, O(N) gradient tape during training**, where N is
   iterations actually executed.

4. **Synthetic-dimension rotation binding as an angular hash map.**
   The compiler reserves a synthetic block of canonical
   dimensions and uses Haar-orthogonal rotations seeded from the
   role's content hash to bind keys to slots. To the authors'
   knowledge this is the first use of a high-dimensional
   rotation pattern as the substrate for a functional hash-map
   primitive.

These four primitives integrate into a single working compiler
that lowers `.su` source to a self-contained PyTorch module on
CPU or CUDA.

A fifth result is engineering, not theoretical: **end-to-end
string I/O through the substrate via a compile-time codebook +
`nearest_string` decode** (§3.5). The frozen-LLM embedding gives
a deterministic string-to-vector map that the compiler bakes
into a `.sdb` codebook at build time; the inverse decode runs at
the program output boundary. Existing HDC libraries (TorchHD and
similar) require the user to maintain a string-to-vector
dictionary and codebook tensor by hand. To the authors'
knowledge Sutra is the only HDC implementation that ships this
as a built-in compiler concern.

### 1.2 The substrate is the architecture target

A Sutra program is compiled for an *embedding-space architecture*,
the way a C program is compiled for x86 and a CUDA kernel for an
NVIDIA SM. The embedding model fixes dimensionality, the geometry
of the semantic block, and the meaning of every basis-vector
lookup; swap the model and the same source recompiles to a
different `.sdb` codebook against a different geometry. The
substrate need not be an LLM — it can be any network producing a
dense vector representation, including the hidden state of a
trained model. §3.2's ESM-2 protein-LM row demonstrates this
substrate-agnostically.

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
substrates we tested, and is what Sutra uses today; §3.2
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
  form (§1.1-2): a single straight-line tensor-op graph with no
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

A second axis where Sutra differs from existing HDC software is
**string I/O**. TorchHD and similar libraries expose the algebra
over user-supplied hypervectors; the user maintains a
`dict[str, hypervector]` and an explicit codebook tensor by hand.
Sutra's compile-time codebook (§3.5) closes that loop: every
embedded string in `.su` source is embedded once at compile time
via the configured frozen LLM, stored in the project's `.sdb`
codebook, and decoded at the program output via `nearest_string`.
The frozen-LLM embedding is load-bearing — random hypervectors
yield a working VSA algebra with no I/O story.

A worked side-by-side of the same 3-field role-filler-record
task in Sutra and TorchHD is in Appendix C; the structural
differences (Sutra contains no Python, automatic string-to-vector
mapping, implicit codebook construction, single fused tensor-op
graph) are differences in artifact shape, not library speed.

### 2.2 Comparison to other neuro-symbolic languages

The closest neuro-symbolic-language peers — **Scallop** (Li et
al. 2023, Datalog with provenance-semiring differentiability),
**DeepProbLog** (Manhaeve et al. 2018, ProbLog with neural
predicates), **Logic Tensor Networks** (Badreddine et al. 2022,
first-order logic compiled to t-norm losses), and **NeurASP**
(Yang et al. 2020, Answer Set Programming with neural predicates)
— all share a two-stage perception-then-reasoning shape: a
neural model extracts discrete symbols from raw input, and a
symbolic program reasons over those symbols. Sutra's shape is
different at this architectural level: the substrate is a
continuous embedding space throughout, primitives operate on
vectors end-to-end, and the whole program — including what would
be the logic program in Scallop — compiles to a single fused
tensor-op graph through beta reduction. There is no discrete
symbolic stratum to extract into or reason over; differentiability
is inherited from the tensor-op graph itself, not from a
provenance annotation on a relational query. The two are good at
different problem structures: Scallop and its peers when the
problem is naturally relational and perception cleanly factors
out; Sutra when computation is best expressed as algebra on
vectors over a substrate the program reads strings into and
decodes strings out of.

The closest HDC peer with compiler infrastructure is **HDCC**
(Vergés et al. 2023), a description-file DSL targeting
self-contained C for embedded classification — random/level
hypervectors only, no general control flow, scoped to
classification. **TorchHD** and OpenHD / HDTorch are libraries
without a language-level loop primitive. To the authors'
knowledge, no published HDC system combines (a) one fused
tensor-op graph as compile target, (b) HDC primitives as the
operations, (c) a frozen externally-trained vector embedding
space as the substrate, and (d) tail-recursive loops compiled to
soft-halt RNN cells with constant state-vector width in
recursion depth. The combination is what distinguishes Sutra,
not any one of those properties in isolation.

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

The central design move: hold the operation interface fixed and
pick a binding implementation that works on dense
externally-trained substrates. Standard VSA's Hadamard product
fails here — elementwise multiplication of correlated real-valued
vectors produces destructive crosstalk on bundled retrieval (§3.2
measures this directly). Rotation binding works: each role gets a
Haar-random orthogonal `R_role` seeded by `hash(role)`, and
`bind(role, filler) = R_role @ filler` is invertible (unbind is
the transpose) and well-conditioned. The compiler caches
`R_role` per-role at module init so runtime bind is a single
matmul against a precomputed matrix.

### 3.1 Notation

We work in ℝᵈ with d the substrate's embedding dimension (768
for nomic-embed-text). Every value has the layout
`[semantic | synthetic]`. The seven primitive operations:
`bind(r,f) = Rᵣ·f` where `Rᵣ = QR(hash(r))[Q]` is Haar-orthogonal,
`unbind(r,v) = Rᵣᵀ·v`, `bundle(x,y) = (x+y)/(‖x+y‖+ε)`,
`similarity(x,y) = (x·y)/(‖x‖·‖y‖+ε)`, `normalize(v) = v/(‖v‖+ε)`,
the Lagrange Kleene gates as in §1.1-1, and the soft-halt cell
of §3.4. Full signature/definition table and the soft-halt cell
update equations are in Appendix H.

### 3.2 Capacity of rotation versus Hadamard binding across substrates

We measure decode accuracy as a function of bundle width k on
real embeddings across four substrates spanning two modalities:
three frozen LLM text encoders (nomic-embed-text, all-minilm,
mxbai-embed-large) and one frozen protein language model (ESM-2
small, `facebook/esm2_t6_8M_UR50D`). LLM substrates embed an
84-word noun vocabulary; the ESM-2 substrate embeds an
84-sequence amino-acid vocabulary (full protocol in Appendix E).
For each bundle width and binding scheme we run 10 trials,
sampling k random (role, filler) pairs without replacement,
forming the bundle, and decoding by unbind + argmax-cosine
against the full codebook. *Rotation binding* uses a role-seeded
Haar-orthogonal `R_role`; *Hadamard binding* is the textbook
elementwise product (MAP-VSA).

Cross-substrate decode accuracy at representative widths (full
k ∈ {2, 4, 8, 16, 24, 32, 48} sweeps in Appendix E):

| substrate (dim)         | rotation k=8 | rotation k=48 | Hadamard k=8 | Hadamard k=48 |
|-------------------------|---:|---:|---:|---:|
| nomic-embed-text (768)  | 100.0% | 93.3% | 87.5% | 48.3% |
| all-minilm (384)        | 100.0% | 42.3% |  7.5% |  1.7% |
| mxbai-embed-large (1024)| 100.0% | 72.1% |  2.5% |  1.0% |
| ESM-2 (320)             | 100.0% | 44.2% | 28.7% |  4.2% |

ESM-2 (Lin et al., Science 2023) is a frozen protein language
model trained on UniRef sequences with no natural-language
exposure; the same rotation-vs-Hadamard separation appears in
this entirely different modality. Reversibility round-trip:
mean ‖unbind(R, bind(R, x)) − x‖ = 1.5 × 10⁻¹⁵ across all four
substrates (floating-point round-off — `Q` is orthogonal so
`QᵀQ = I`). Sutra's rotation primitive is sensitive to dense
high-dimensionality, not to whether the substrate was trained
on words. Reproduction:
`experiments/rotation_binding_capacity_{llm,bioinformatics}.py`.

#### 3.2.1 Noise accumulation across chained bind/unbind cycles

The §3.2 protocol measures one bind+bundle+unbind cycle. Nested
records — a recovered filler becoming the role of a sub-record —
add bundle noise per level. We measured this directly: chain
lengths L ∈ {1, 2, 4, 8, ...}, 20 trials, bundle width 4. Raw
accuracy holds at 100% through L=2 on every substrate and falls
to chance (1/84) by L=8. The demonstrated regime is therefore
single-cycle records, which matches the shape of the
`role_filler_record`, `knowledge_graph`, and predicate-lookup
demos. Pure rotation chains without per-step distractor bundling
remain exact (round-trip 1.5×10⁻¹⁵ per cycle), so the noise
mechanism here does not apply to the soft-halt loop cell of §3.4.
Reproduction script: `experiments/crosstalk_chain.py`; full
per-substrate L-sweep tables in Appendix A.

### 3.3 The extended-state-vector layout

Every value carries a fixed `[semantic | synthetic]` layout:
the d-dimensional semantic block holds the substrate embedding
for vector-shaped values, and a small synthetic block reserves
canonical axes for primitive types (real, imag, truth, char) and
a loop-completion flag, with the remaining axes paired into 2D
Givens planes for variable slots. Default at d = 768
(nomic-embed-text): a 100-dim synthetic block accommodates the
five canonical axes plus 47 disjoint slots. Rotation binding is
block-diagonal across the split (`Q_role` is Haar-random in the
semantic block, identity on the synthetic block), so the
synthetic axes pass through bind/unbind unchanged — a fuzzy-truth
scalar can coexist with a semantic vector inside the same value
without bind smearing them. Full per-axis purpose table and slot
allocator details in Appendix D.

### 3.4 First-class loops as RNN cells

Runtime data-dependent loops compile to **self-halting RNN
cells**. Each tick: snapshot pre-step state, evaluate the halt
condition on the substrate (truth-axis read → heaviside step →
cumulative saturating sum), run the cell body, then a soft-mux
blends pre-step and new-step state weighted by the halt
accumulator. A Python `while True:` driver breaks the moment
`halt_cum` saturates.

```
            state_in
               |
        +------+------+
        |             |
        v             v
    pre_state    cell body (pure tensor ops)
                      |
                      v
                 new_state, halt_signal
                      |
              halt_cum  ← saturating sum
                      |
                      v
              soft-mux freeze:
              state_out = (1 - halt_cum) · new_state
                        +     halt_cum  · pre_state
```

Once `halt_cum` saturates, the soft-mux output is `pre_state` —
the loop has frozen. The Python driver checks `halt_cum` once per
tick and breaks; this is the only host-side branch in the loop
machinery. Inside the cell body, every operation is a substrate
tensor op. There is no compile-time iteration cap — programs
terminate when their halt condition fires, exactly the way any
other programming language's `while` loop does. The halt-cum read
is a boundary operation of the same shape as the codebook decode
(§3.5).

**Loop body vs loop driver.** Tensor normal form applies to the
body of each tick, not to the loop itself: standard PyTorch
tracing handles a Python while-loop wrapping pure tensor ops, and
autograd records each iteration as it executes — the mechanism
§3.6 relies on for end-to-end backprop through the cell.

**Constant memory in recursion depth.** The state vector is
fixed-width and shared across iterations, so a tail-recursive
loop consumes O(1) memory in the state vector regardless of trip
count: no per-step stack frame, no growing context. Compute is
O(N) and the autograd tape during training is O(N) in iterations
actually executed (standard PyTorch behavior, freed after
backward). To the authors' knowledge no other HDC system or
compiler exposes user-program-level recursion: HDCC is scoped to
classification pipelines, TorchHD requires the user to write
Python loops over hypervectors. The recurrent shape that emerges
is the same one Siegelmann & Sontag (1992) showed can compute any
Turing-machine-computable function with rational weights.

### 3.5 Embedded codebook store

Every embedded string in a Sutra program is embedded once at
compile time and stored in a `.sdb` codebook that ships
alongside the compiled module. The runtime decode
`_VSA.nearest_string(query)` returns the nearest-string label
for any query vector; the lookup runs at the program's *output
boundary*, returning a host string the same way any compiled
program returns a host value. Calling a well-engineered ANN
library at this boundary is shape-equivalent to calling PyTorch
for a matmul — neither is the kind of host-side control flow
substrate purity forbids. Implementation details (RDF triple
layout, HNSW graph parameters, `.sdb` file format, complexity
analysis) are in Appendix B.

### 3.6 End-to-end differentiable training through Sutra operations

Because every Sutra primitive compiles to a differentiable tensor
operation, the compiled graph supports standard PyTorch
`loss.backward()` without modification. We verify this by
training learnable parameters through a fuzzy-logic classifier
built entirely from Sutra operations.

**Setup.** 992 words across twenty semantic categories
(50 each, deduplicated; full list in Appendix F) are embedded
via nomic-embed-text (768-d, frozen). Twenty learnable prototype
vectors are initialized randomly. The classifier computes cosine
similarity between input and each prototype and applies a
Lagrange-interpolated fuzzy if-then rule:

    rule_i = AND(sim(x, proto_i), AND_{j ≠ i} NOT(sim(x, proto_j)))

with the AND-of-NOTs left-folded across K−1 other classes (so
the K=20 rule nests nineteen ANDs deep). Full-batch cross-entropy
over the twenty rule scores drives Adam updates (lr=0.005) on
the prototype embeddings.

**Results.** Random init: 4% accuracy (chance = 5%). Training
reaches 95% by epoch 50 and holds through epoch 299, loss
converging to 1.154. Gradient norms at all twenty prototypes are
nonzero throughout (range 0.94–4.20), so backprop reaches every
learnable parameter through `similarity` → `fuzzy_not` →
nineteen nested `fuzzy_and` → cross-entropy.

| Phase  | Accuracy | Loss  |
|--------|---------:|------:|
| Before |     4%   |  3.01 |
| After  |    95%   |  1.15 |

As a tensor-op graph (drawn explicitly for K=3 in Appendix I,
the K=20 case has the same shape but with the AND-of-NOTs
left-folded over nineteen terms): the input embedding fans out
to K cosine-similarity nodes against the K learnable prototypes,
each `sim_i` enters one branch of an AND-tree (the i-th rule
takes `sim_i` directly and `NOT(sim_j)` for j ≠ i), the K rule
scores are stacked, scaled by temperature, softmaxed, and
cross-entropied against the label. Every node is a PyTorch
tensor op; every edge carries a vector or scalar. There are no
Python branches, no host-side dispatch, no string-keyed lookup
— backprop reaches every learnable parameter through the same
compiled graph that runs at inference.

At K=20 the rule for class i is an AND of `sim(x, proto_i)`
with a left-folded chain of nineteen `NOT(sim)` terms — a tensor
pipeline that could naively saturate or vanish gradients
somewhere along the chain. Empirically it doesn't: every
prototype receives a nonzero gradient, accuracy reaches 95% on a
vocabulary 70× larger than the K=3 setting (15 → 992 words), and
the symbolic program text is unchanged across training. The
remaining 5% gap is honest semantic overlap (e.g. *salmon* fits
food and color); gradient norms remain bounded above zero
throughout, so this is the optimizer plateauing under those
overlaps, not gradient pathology. Standard `torch.autograd`
suffices — no Sutra-specific autograd machinery — because the
compiler emits only operations PyTorch already knows how to
differentiate. Reproduction:
`experiments/differentiable_training.py` + raw JSON.

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

Stages 1–4 run at compile time; stage 5 is the runtime forward
pass. The compile-time/runtime boundary is exactly where
neural-network training versus inference draws the line — by
the time stage 5 begins, every role rotation, codebook entry,
and stdlib reduction has been resolved to a constant tensor or
a primitive op, the same way a feed-forward network's weights
are constants by inference time. Appendix J shows the pipeline
as a vertical flow with the residual at each stage.

### 4.1 Substrate-purity invariants

Three invariants the compiler enforces: (1) every primitive runs
on the substrate (numpy is allowed only at compile time for
codebook construction and rotation pre-warm, never on the runtime
hot path); (2) no scalar extraction inside an operation —
operations may not unpack a Python float from a substrate vector,
do scalar arithmetic, and pack the result back; (3) no Python
control flow inside an operation — loop halt uses substrate
primitives (`heaviside`, `saturate_unit`) instead of Python
ternaries.

### 4.2 Compile-time resolution to tensor normal form

The central compile-time mechanism that lets the compiler
achieve tensor normal form is **precomputed rotation matrices**:
every role rotation is constructed at compile time
(`prewarm_rotation_cache`) and stored as a constant tensor. At
runtime, `bind(role, filler)` is a single matmul against a
precomputed matrix — the compile-time resolution eliminates the
QR construction from the runtime graph entirely. Role rotations
are constants from the runtime's perspective, the same way
neural-network weights are constants at inference time. With
`torch.compile` (opt-in via `SUTRA_TORCH_COMPILE=1`), the
tracer further folds the per-tick loop body into a single fused
kernel.

### 4.3 A worked lowering

A two-field bundled record `encode2(r_a, f_a, r_b, f_b) :=
bundle(bind(r_a, f_a), bind(r_b, f_b))` lowers in five stages
(parse → stdlib beta-substitution → compile-time `RotationFor`
resolution → peephole fusion to `_VSA.bundle_of_binds` → leaf
tensor ops `einsum + linalg.norm + divide`) over rotations
materialized at compile time. Appendix G traces each stage with
the residual after every reduction. The bottom of the chain
contains no `bind`/`bundle`/`normalize` symbol and no Python
control flow; surface lambda calculus and runtime tensor
arithmetic are two notations for the same computation.

---

## 5. Demonstration corpus

The smoke test (`examples/_smoke_test.py`) runs 10 demonstration
programs end-to-end (`hello-world`, fuzzy branching, role-filler
record, classifier, analogy, knowledge graph, predicate lookup,
fuzzy dispatch, nearest-phrase retrieval, sequence reduction)
across 27 `.su` files in `examples/`. Loop coverage lives in
`examples/do_while_adder.su` and the 23-case
`test_loop_function_decl.py` suite. Each program exercises a
different language feature; the §3.6 differentiable-training
experiment uses the same primitive set those programs are built
from.

---

## 6. Limitations and Future Work

### 6.1 Codebook integration depth

The embedded codebook store covers the compile-time embed →
runtime decode path today. Extended features (hashmap routing,
persistent codebook across runs via `SUTRA_DB_PATH`) are
deferred until there is a concrete requirement beyond the
current demonstration corpus.

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
  ground for Sutra's polynomial fuzzy connectives (§1.1-1).
- Mikolov, T., Chen, K., Corrado, G., & Dean, J. (2013). Efficient
  estimation of word representations in vector space. *ICLR
  Workshop*.
- Badreddine, S., Garcez, A. d., Serafini, L., & Spranger, M.
  (2022). Logic Tensor Networks. *Artificial Intelligence* 303.
- Hájek, P. (1998). *Metamathematics of Fuzzy Logic*. Trends in
  Logic vol. 4. Kluwer Academic. The standard reference for
  t-norm-based fuzzy logics (Gödel, Łukasiewicz, product) cited
  in §1.1-1 to place Sutra's polynomial connectives.
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
  cited in §1.1-1; analyzes t-norm-derived AND/OR/IMPLIES
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

---

## Appendix

### Appendix J — Compilation pipeline diagram

The five-stage compilation pipeline of §4, drawn as a vertical
flow with the residual at each stage:

```
   source code  (.su)
        │
        │   (1) lex + parse
        ▼
   AST   (Call / Var / Function / ClassDecl nodes)
        │
        │   (2) inline stdlib + egglog simplify
        │       (bind, bundle, similarity → primitive tensor ops)
        ▼
   simplified AST   (residual: leaf tensor-op composition)
        │
        │   (3) codegen
        │       (emit Python module + inline _VSA class source)
        ▼
   Python module text   (self-contained, no Sutra-runtime import)
        │
        │   (4) compile-time substrate population
        │       embed_batch · prewarm_rotation_cache · populate_sutradb
        ▼
   warm runtime   (module loaded, .sdb codebook, cached R_role tensors)
   ──── compile time ────────────────────────────────────────────────
   ────── runtime ───────────────────────────────────────────────────
        │
        │   (5) forward pass on input tensors
        ▼
   output vector → nearest_string lookup → label
```

### Appendix I — The K=3 rule pipeline as a tensor-op graph

Body §3.6 describes the rule pipeline in prose. The explicit
graph for K=3 (the K=20 graph used in the experiment has the
same shape with twenty learnable prototypes and the AND-of-NOTs
left-folded across nineteen `NOT(sim)` terms):

```
                         input  x ∈ ℝᵈ
                              │
            ┌─────────────────┼─────────────────┐
            │                 │                 │
            │   p₁ (learnable)│   p₂ (learnable)│   p₃ (learnable)
            │                 │                 │
            ▼                 ▼                 ▼
       cos(x, p₁)         cos(x, p₂)        cos(x, p₃)
            │                 │                 │
         sim₁ (∈ℝ)         sim₂ (∈ℝ)        sim₃ (∈ℝ)
            │                 │                 │
            │                 ▼                 ▼
            │             NOT (= −·)        NOT (= −·)
            │                 │                 │
            │              −sim₂             −sim₃
            │                 │                 │
            │                 └──── AND ────────┘
            │                          │
            │                     neg_others
            │                          │
            └────── AND  ──────────────┘     ← Lagrange polynomial:
                          │                    AND(a,b) = (a+b+ab
                          ▼                         −a²−b²+a²b²)/2
                       rule₁ (∈ℝ)
                          ⋮
        (rule₁, rule₂, rule₃)  ─────►  × temperature  ─────►  softmax
                                                                  │
                                                                  ▼
                                                       cross-entropy(label)
                                                                  │
                                                                  ▼
                                                                 loss
```

### Appendix H — Notation: extended layout and primitive operations

We work in a fixed-dimensional real vector space ℝᵈ where d is
the substrate's embedding dimension (768 for nomic-embed-text,
384 for all-minilm, 1024 for mxbai-embed-large, 320 for ESM-2).
Every Sutra value carries the extended layout `[semantic |
synthetic]` — a `d`-dimensional semantic block holding the
substrate embedding, concatenated with a small fixed-width
synthetic block reserving canonical axes for primitive types
(real, imag, truth, char, loop-done) and slot machinery (§3.3).
Where notation does not distinguish, "vector" means "the full
extended-layout tensor."

The seven primitive operations are:

| Op             | Signature                              | Definition                                                 |
|----------------|----------------------------------------|------------------------------------------------------------|
| `bind`         | (vector, vector) → vector              | `Rᵣ · f` where `Rᵣ = QR(seed = hash(r))[Q]`               |
| `unbind`       | (vector, vector) → vector              | `Rᵣᵀ · v`                                                  |
| `bundle`       | (vector, vector) → vector              | `(x + y) / (‖x + y‖ + ε)`                                  |
| `similarity`   | (vector, vector) → scalar              | `(x · y) / (‖x‖ · ‖y‖ + ε)`                                |
| `normalize`    | vector → vector                        | `v / (‖v‖ + ε)`                                            |
| Lagrange gates | (scalar, scalar) → scalar              | exact polynomials on the {−1, 0, +1}² Kleene grid (§1.1-1) |
| soft-halt cell | (state, halt_prev) → (state', halt_cum)| rotation step + halt accumulator (§3.4)                    |

The Lagrange gates compactly:

```
AND(a, b)  =  (a + b + ab − a² − b² + a²b²) / 2
OR(a, b)   =  (a + b − ab + a² + b² − a²b²) / 2
NOT(a)     =  −a
XOR(a, b)  =  −ab
XNOR(a, b) =  ab
```

The soft-halt cell update is, in compact form,

```
   sₜ₊₁  =  R · sₜ                               (rotation step)
   hₜ    =  Heaviside( cond(sₜ) )                (per-tick halt signal)
   Hₜ    =  saturate_unit( Σₖ≤ₜ hₖ )             (cumulative monotone halt)
   ŝₜ₊₁  =  Hₜ · sₜ + (1 − Hₜ) · sₜ₊₁           (soft-mux freeze)
```

Every right-hand side is a tensor expression with no Python
control flow. The compile-time primitives `RotationFor` and
`embed` produce constants `Rᵣ` and basis vectors at compile
time and are not part of the runtime tensor graph.

### Appendix G — Worked lowering of a two-field bundled record

The body §4.3 sketches the lowering of `encode2(r_a, f_a, r_b,
f_b) := bundle(bind(r_a, f_a), bind(r_b, f_b))`. Here we trace
each stage with the explicit residual.

**Stage 1 — AST after parse.** A tree of `Call` nodes over named
identifiers: `Call("bundle", Call("bind", r_a, f_a),
Call("bind", r_b, f_b))`.

**Stage 2 — beta reduction by stdlib inlining.** `bind`,
`bundle`, and `normalize` are stdlib functions:
`bind(r,f) ≡ RotationFor(r) @ f`, `bundle(x,y) ≡ normalize(x+y)`,
`normalize(v) ≡ v / (‖v‖ + ε)`. After substitution the body
becomes `normalize(RotationFor(r_a) @ f_a + RotationFor(r_b) @ f_b)`.
No `bind` or `bundle` symbol remains; the residual is straight-
line algebra over four tensor primitives.

**Stage 3 — compile-time constant resolution.** `RotationFor(r)`
is a compile-time function returning `R = QR(seed = hash(r))[Q]`.
The compiler evaluates it for each role at compile time, freezes
the results as constant tensors `R_a` and `R_b`, and stores them
in the rotation cache. The body becomes `normalize(R_a @ f_a +
R_b @ f_b)` — `R_a` and `R_b` are now load-bearing constants in
the same sense as the weight matrices of a feed-forward network.

**Stage 4 — peephole fusion.** The simplifier recognizes
`normalize(Σᵢ Rᵢ @ fᵢ)` as the bundle-of-binds pattern and
rewrites it to `_VSA.bundle_of_binds([(R_a, f_a), (R_b, f_b)])` —
one kernel launch instead of two matmuls + add + norm.

**Stage 5 — leaf tensor ops at runtime.** `bundle_of_binds`
stacks rotations into a `(k, d, d)` tensor, stacks fillers into
`(k, d)`, runs one batched einsum + sum + L2-normalize:

```
encode2 ≡ v / (‖v‖ + ε)
where  v = einsum("kij,kj->i", stack([R_a, R_b]), stack([f_a, f_b]))
```

The compiled forward pass for `encode2` is exactly those three
torch calls — einsum, linalg.norm, divide — over precomputed
`R_a, R_b` and runtime-supplied `f_a, f_b`.
