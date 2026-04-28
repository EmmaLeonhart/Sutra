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

Standard compilers do beta reduction *during inlining*, but as an
incidental optimization. Most languages preserve sequential control
flow as their compilation target. Sutra's target is a **value** — a
linear map — not an instruction sequence. The output of compilation
is structurally different from the input.

The closest existing analog is supercompilation (some Haskell
compilers), but supercompilation still produces program-shaped
output, not closed-form values.

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
- **Kolmogorov-Arnold representation theorem (KART) and Liu &
  Tegmark 2024 (KANs).** KART says any continuous multivariate
  function decomposes into univariates summed. KART is the
  completeness certificate for "any continuous function is reachable
  via a tensor op." KANs put learnable splines on edges. Sutra's
  compile-time math approximation strategy (Chebyshev / lookup /
  CORDIC tiers) is the same idea applied at compile time rather than
  at training time.

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
