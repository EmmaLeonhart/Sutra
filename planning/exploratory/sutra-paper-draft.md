# Sutra paper draft — embedding-as-ISA

**Date opened:** 2026-04-28.
**Status:** Outline. Different framing from the earlier
compile-time-beta-reduction-vs-runtime-VSA-LC angle (that draft was
removed during the 2026-04-27 chats cleanup; the framing it relied
on came directly from triaged chats). This draft is built around the
**embedding-space-as-instruction-set-architecture** framing, which is
a sharper rhetorical anchor and survives independently of the
Flanagan / "Hey Pentti" line of work that the prior draft was reacting
to.

This is a parking lot for the contributions list and motivation. If
it becomes real work, it moves to STATUS.md and gets a target venue.

## Working title

"Embedding-space as ISA: a programming language whose compilation
target is a frozen LLM's geometric substrate"

## The framing

Compilers target an **instruction set architecture**. C targets x86.
Rust targets LLVM IR which targets x86. The ISA is the contract
between the compiler and the hardware: a stable, documented set of
operations the compiler is allowed to assume.

Sutra targets an **embedding space**. Specifically, a frozen LLM's
geometric substrate: a fixed set of high-dimensional points
representing concepts, with a fixed set of substrate-supported
operations (similarity, projection, rotation, bind / bundle). The
compilation target isn't an instruction sequence — it's a value, a
position in the embedding space, reachable by a composition of
substrate-native operations.

This is the move nobody else made. Word2vec arithmetic (`king − man +
woman ≈ queen`) has been known since 2013. Over a decade of people
treating it as a curiosity. The leap Sutra makes: **treat the
embedding space as a compilation target the way you treat x86 as
a compilation target** — a stable interface to a substrate, an ISA
in the strict sense.

The two-way relationship that follows is the same one C had with
CPUs:

- **C assumed flat memory; CPUs were optimized for that assumption.**
- **Sutra assumes geometrically structured semantic space; embedding
  spaces can be optimized for that assumption.**

CPU architecture was a physical engineering problem with hard
constraints. Embedding spaces are *learned statistical structures*
with much more degrees of freedom — they can be shaped much more
deliberately toward what Sutra needs than silicon can be shaped
toward what C needed. The co-evolution is faster and more
intentional.

## The four computational novelties

These compose around the embedding-as-ISA framing. Each is
implemented in Sutra today; the paper's job is to articulate why each
is novel and how they add up to something coherent.

### 1. Beta reduction to tensor normal form as compiler architecture

Compilation is **typed beta reduction plus algebraic simplification**
with a tensor expression as the normal form. Programs collapse to
single matrices (or short tensor-op chains) when the simplifier can
prove the necessary identities. This is the organizing principle, not
an optimization pass.

The crisper framing: **the program is a value, not an instruction
sequence.** A function is a matrix; a program is a function;
compilation is reduction until you have the matrix. The program
doesn't *run* — it *evaluates*. This is much closer to how a
mathematician thinks than how a systems programmer thinks. Standard
compilers preserve sequential control flow as their compilation
target and do beta reduction incidentally during inlining; Sutra
inverts that — beta reduction is the compiler's organizing principle
and the output is structurally different from the input.

**Related work the paper has to distinguish from:**

- **Supercompilation** (some Haskell compilers, partial-evaluation
  research). Symbolically runs a program with unknown inputs,
  collecting residual computation into a single expression. Closest
  in spirit, but the output is still program-shaped, not a
  closed-form value.
- **Polyhedral compilation** (XLA, Halide, MLIR Affine). Analyzes
  loop nests as geometric objects and fuses / reorders them. Output
  is still code — fused tensor kernels — not a closed-form function.
  Related geometric framing, different target.
- **Automatic differentiation** (JAX, PyTorch tracing). Builds a
  computation graph and reduces through it. Sutra's collapse-to-matrix
  is structurally similar, but Sutra reduces at *compile time*, not
  at trace time, and the target is a matrix rather than a gradient.
- **None of the above treat collapse-to-a-single-value as the
  compiler's organizing principle.** That is the gap Sutra fills.

The Kolmogorov-Arnold representation theorem (KART) is the
completeness certificate for this novelty: KART says any continuous
bounded multivariate function decomposes into a finite composition of
univariates, so any continuous function the user could have written
*has* a reduced form that fits Sutra's target. The simplifier's job
is to find it; KART guarantees it exists.

**Worked example.** The expression `Cat == "cat"` traces through the
pipeline as:

1. **Desugaring** (syntactic): `Cat == "cat"` →
   `Function.equals(Cat, Function.embed("cat"))`. Pure notation
   removal, no computation.
2. **Beta reduction** (semantic): function applications collapse
   into compositions in the hyperdimensional algebra. The result is
   an expression in linear maps, not function calls.
3. **Evaluation**: `embed("cat")` is computed once at compile time
   against the project's embedding space, producing a concrete
   vector. The embedding space is itself a compile-time constant
   (declared in `atman.toml`), so this is just baseline compilation
   work — not a runtime concern.
4. **Algebraic simplification**: `equals • cat_embedding` is
   recognized as a fixed vector and named `is_cat_function`.
5. **Result**: a runtime string-equality comparison has been
   compiled to a single dot product against a precomputed vector.
   No string handling, no function dispatch — geometric proximity
   query.

**The input is the only runtime variable.** The function body
`fn is_cat(word: Word) -> Bool { word == "cat" }` compiles to
`dot(word_vector, is_cat_function) > threshold`. Everything else
collapsed at compile time because the embedding space was known.
This is the embedding-as-ISA story made concrete: the compilation
target isn't an instruction sequence, it's a precomputed vector in a
fixed substrate.

The algebraic-simplification step is where Sutra is smarter than a
generic lambda-calculus reducer: it knows the domain is
hyperdimensional, so it knows `equals • cat_embedding` has a closed
form worth precomputing.

### 2. Differentiable fuzzy logic as a polynomial substrate

Three-valued logic over `{-1, 0, +1}` implemented via Lagrange
polynomial form on the truth axis. Every logical operation is a
polynomial in truth-axis values and is therefore differentiable
end-to-end.

What's novel is not "fuzzy logic" — that's been around since Zadeh.
What's novel is the *combination*: exact on the three-valued grid
(agrees with classical truth tables at the corners), smooth in
between, closed under polynomial algebra, and end-to-end
differentiable. Most fuzzy-logic systems use min/max
(non-differentiable at corners) or sigmoid relaxations (lossy and
substrate-dependent). The Lagrange polynomial form gets all four
properties at once, and that combination is what makes the rest of
the compiler work.

### 3. Eigenrotation as a loop primitive

`loop(cond)` compiles to `state ← R · state` on the substrate with
prototype-match termination. There is no program counter at runtime;
the "iteration count" is the angular position on the helix
`R^i · v_0` traced through the substrate's state space. Termination
is a similarity match against a compiled prototype, which itself runs
on the substrate.

Iteration is the canonical non-linear-algebraic operation. Most
ML-adjacent languages handle loops by stepping out of tensor land
into a Python `for`. Sutra keeps iteration *inside* the tensor
algebra by reframing it as matrix exponentiation with
substrate-resident termination. There is no instant during a loop's
execution where the runtime is doing something other than tensor ops.

### 4. Synthetic-dimension rotation for arrays and hashmaps

Arrays and hashmaps as **single bundled vectors** built from
rotation-bound key-value pairs. Reads are a single `unbind`. Storage
and retrieval are pure algebra — no branches, no pointers, no index
decode. The data structure lives in a synthetic-dimension slice of
the extended state vector and is differentiable and compile-time
factorable.

Conventional data structures are *control-flow* problems. Indexing is
a branch. Hashing is a sequence of operations. Sutra makes them
rotations in synthetic dimensions. The "data structure" doesn't
exist at runtime — the compile-time factorization absorbs the access
pattern into the surrounding tensor expression. Lookups in dense
vector space become matrix-row selections, which are already what
you're doing — there's no representation switch.

This is a profound departure from how data structures are
conventionally understood, not an optimization of the conventional
approach.

## How the four compose

Every Sutra construct compiles to tensor operations because *every*
construct is one of:

- A polynomial on the truth axis (logic, conditionals — novelty 2).
- An eigenrotation on the substrate (loops, arrays, hashmaps —
  novelties 3, 4).
- Pure linear algebra (bind, bundle, similarity, projection).

The compiler is then beta reduction over a uniformly-typed tensor
algebra (novelty 1). The four mechanisms are the universal cover for
"things the compiler can route to the substrate."

The empirical claim of the paper: **these four mechanisms together
make the embedding-space-as-ISA story work.** Without all four, you'd
end up with a hybrid where some operations run on the substrate and
some don't — which is what every existing VSA library does. With all
four, the substrate is the only thing running, and the compiler is
the bridge between the source language and the geometric machine.

## Origins — first principles, not literature

A note for the methods / motivation section.

The Sutra design wasn't derived by surveying the VSA literature and
finding gaps. It was derived from one observation:
`king − man + woman ≈ queen`. The reaction wasn't "interesting
property of this embedding space" — that was everyone else's
reaction. The reaction was **"this is a general computation model;
everything is this; let me build a language where this is the
primitive."**

The maturation step was the switch from addition to matrix
multiplication. Vector addition gives you linear transformations
only. Matrix multiplication gives you the full expressiveness needed
for a general computation model. The matrix-multiplication insight
was derived independently (from thinking about parallax and
perspective on a walk home), not pulled from the literature — though
it turned out the literature had also reached it. The 30-dimensional
synthetic-rotation generalization, and the hashmap-as-rotation
construction, were independent leaps that the VSA literature had not
made.

This origin story is relevant to the paper because it explains
*why* the design works: it was derived from the requirements of
"compile programs into embedding space," not from incremental
extension of representation-focused VSA work. Different starting
question, different destination.

### Descriptive of the substrate, not prescriptive

The Sutra algebra is **not handcrafted symbolic structure imposed
on continuous representations.** It is a formal extraction of
structure the embedding model already learned. The model learned
addition-as-bundling and matrix-as-relation implicitly during
training; Sutra makes those operations explicit and operable. The
algebra is **descriptive of the substrate**, not prescriptive over
it.

This is the answer to the most predictable reviewer objection:
*"Isn't this just neurosymbolic AI, which has been failing for
decades?"* The classical neurosymbolic program imposes discrete
symbolic structure onto continuous representations and pays the
representation-mismatch tax forever. Sutra inverts the polarity —
the symbolic operations are read out from the geometry that
emerged from training, not bolted on. Same way `king − man + woman
≈ queen` was discovered, not designed: the structure is *already
there*, and Sutra's contribution is making it programmable.

This framing doubles as an empirical commitment. If the algebra
were prescriptive, demos would work only on substrates trained
specifically to support it. Demos working on stock frozen
embedding models (nomic, mxbai, minilm — see the cross-substrate
sweep in `planning/findings/2026-04-24-capital-country-across-
substrates.md`) is evidence that the structure was already there.
The compiler reads it; it doesn't invent it.

## Prior art the paper has to reckon with

- **Flanagan et al. 2024 — "Hey Pentti, We Did It!: A Fully Vector-
  Symbolic Lisp"** (ICCM 2024; arXiv:2510.17889; arXiv:2511.08767).
  Constructs a runtime VSA Lisp interpreter — beta reduction inside
  the hypervector substrate. Same target, opposite direction: they
  push the lambda calculus *into* the substrate; Sutra collapses it
  *before* the substrate runs.
- **Category-theory companion paper** (arXiv:2501.05368, January
  2025). Generalizes from vectors to co-presheaves. Provides the
  categorical framing the embedding-as-ISA argument can borrow from.
- **Kleyko et al. IEEE survey of VSAs.** Universality via Turing-
  machine simulation. The "computing in superposition" framing is
  the closest prior art for "the substrate as a real machine."
- **Smolensky 1990 — Tensor Product Representations.** Foundational
  treatment of variable binding. §3.7.2 (LISP binary-tree operations
  as linear maps) is directly relevant to the "compilation as linear
  map" thesis.
- **Lambek & Scott 1986 —  *Introduction to Higher-Order Categorical
  Logic*.** Foundational for Curry-Howard-Lambek. The paper's claim
  is that Sutra's compile-time beta reduction makes the CCC structure
  *static* — morphisms composed before runtime, evaluation map
  collapses to a constant.
- **TransE / RotatE / ComplEx.** Knowledge-graph embedding prior art.
  Treat relations as geometric operations (translation / rotation /
  complex multiply). Use embedding spaces for link prediction. Did
  not treat the embedding space as a compilation target.
- **HDCC** (Pale et al., arXiv) — the closest existing
  compile-to-VSA work. An open-source compiler that translates
  high-level descriptions of HDC (Hyperdimensional Computing)
  classification methods into optimized C code. Has an input
  language, IR, and flexible backend — designed like a modern
  compiler. **Why it doesn't count as embedding-as-ISA**: HDCC is
  scoped specifically to ML classification tasks. It compiles HDC
  classifier descriptions to C; it is not a general-purpose
  language whose semantics live in the embedding space. The
  closest precedent for "compile to VSA," but a different problem
  shape — Sutra's claim is general-purpose computation in the
  semantic substrate, not a DSL for one task family.
- **Torchhd / vsapy / OpenHD** and the broader VSA library family.
  Embedded-in-Python (or C++) libraries that expose
  bind/bundle/permute as function calls. The user writes Python
  that calls `bind(...)` / `bundle(...)`; the library does the
  tensor work. **Why none of them count as a language**: the host
  language is Python (or C++); VSA is library calls inside it.
  There is no compiler whose job is to translate ordinary-looking
  source code into VSA operations as its execution model. The
  semantic gap between "library you call from Python" and
  "language whose compilation target is the embedding space" is
  the gap Sutra fills. (The Hey-Pentti VSA Lisp interpreter cited
  above is the one effort that *does* push past the library
  framing — and it does so by interpreting the lambda calculus
  *inside* the substrate at runtime, the opposite direction from
  Sutra's compile-time collapse.)
- **Kolmogorov-Arnold representation theorem (KART) and Liu &
  Tegmark 2024 (KANs).** KART (Hilbert's 13th problem; Arnold &
  Kolmogorov) says any continuous bounded multivariate function
  decomposes into a finite composition of univariates summed. This
  is the **completeness certificate for novelty 1** — any continuous
  function the user could have written has a reduced form Sutra's
  simplifier could in principle find. KANs (2024) put learnable
  splines on edges and use this constructively for training. Sutra's
  compile-time math approximation strategy is the same idea applied
  at compile time rather than at training time, with a concrete tier
  hierarchy:

  1. **Exact** — function has a closed linear form → direct matrix op.
  2. **Chebyshev / polynomial approximation** — function is smooth on
     a bounded domain → polynomial dot product, degree chosen at
     compile time to hit the requested precision.
  3. **Lookup + interpolation** — function is weird or expensive →
     tensor table, interpolation as sparse matmul. Cheap in Sutra
     specifically because there is no representation switch — the
     table is just another tensor and indexing is just a multiply.
  4. **CORDIC-style decomposition** — for functions that decompose
     into shifts/adds (trig, exp). Expressible as a matrix chain.

  The tier is selected by the compiler based on the argument's domain
  type and project-wide TOML settings split across two axes:

  - `[math]` controls **approximation precision** (Chebyshev
    polynomial degree, lookup-table resolution). E.g.
    `approximation_precision = 1e-6, approximation_method = "chebyshev"`.
  - `[backend]` controls **storage dtype** (`float16` /
    `float32` / `bfloat16`) and target device (`cuda` / `cpu` /
    `metal` / `tpu`). The dtype is the GPU/TPU axis ML
    practitioners actually trade against — float16 is dramatically
    faster on CUDA tensor cores; bfloat16 preserves exponent range
    at lower mantissa precision.

  Both axes have to be coherent (a 1e-12 math precision target on
  float16 storage is incoherent — the compiler should warn). The
  user writes `sqrt(x)` and gets a tensor op at the right precision
  on the right device, not a libm call. PyTorch typically scatters
  this with `torch.float16` casts and `autocast()` context managers
  through user code; Julia and F# both defer to IEEE 754 + libm with
  no user knob. No mainstream language exposes both axes as
  compile-time architectural decisions. This is a real differentiator
  for numerical work, not just AI work. The honest caveat: KART's
  inner univariates can be pathologically non-smooth in the worst
  case; the practical ceiling on what Sutra can reduce is set by how
  well the simplifier represents those univariates, not by KART
  itself.

## Honest limits

- **Type checking isn't there.** The runtime is Python-duck-typed.
  Type annotations are spec commitments and parser metadata, not
  enforced constraints. The "compile-time enforcement of
  ontological constraints" claim is currently aspirational at the
  type-checker level, even though the codegen does enforce some of
  it.
- **Learned-matrix binding is deferred.** Rotation binding is what
  ships today. The richer "fit a matrix to corpus pairs at compile
  time" form is on the roadmap but not implemented. Sections of the
  paper that promise the richer form must say "deferred" rather
  than overclaiming.
- **Embedding space is fixed per program.** Multi-substrate type
  systems (a `nomic` value vs. a `clip` value) are partial today.
  The paper should not claim multi-substrate first-class status.
- **Cleanup-as-cheating critique.** A reviewer could argue: "Sutra
  doesn't need cleanup memory at runtime because the cleanup is
  done at compile time by the simplifier — but that's just moving
  the cleanup, not eliminating it." The honest answer is yes,
  compile-time simplification *is* the cleanup, but it's a static
  one-time cost paid before any data touches the substrate. The
  paper should engage this directly rather than dodge it.

## What would need to land

- [ ] Decision on scope. Five-contribution paper vs. focused single-
  contribution paper (probably contribution 1, framed as
  "compile-time beta reduction to tensor normal form on a frozen
  LLM substrate," with the others as supporting evidence).
- [ ] **One end-to-end `.su` program** that visibly compiles to a
  single matrix. The rotation-hashmap demo is close; the
  fuzzy-branching demo is closer to the differentiable-logic story.
- [ ] **Honest comparison section** to Flanagan / "Hey Pentti" —
  including the cleanup-memory honesty.
- [ ] **Differentiability story** — Lagrange polynomial form for
  the logic. Needs a paper-shaped paragraph plus the gradient-flow
  argument.
- [ ] **Embedding-as-ISA argument** — the framing pillar. Needs
  the C/CPU co-evolution analogy paid out properly.

## What this is not

A commitment that the paper gets written or submitted. A parking lot
for the framing and contributions list. If it becomes real work, it
moves into STATUS.md with a target venue and a deadline.
