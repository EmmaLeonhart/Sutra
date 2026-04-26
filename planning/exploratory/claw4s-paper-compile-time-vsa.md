# Claw4S paper draft — Sutra as compile-time VSA

**Date opened:** 2026-04-25.
**Status:** Draft outline. Paper flagged by user for the
2026-04-30 Claw4S submission window. Not exploratory in the
"maybe someday" sense — it has a target deadline. Lives in
`planning/exploratory/` only because a polished paper repo doesn't
exist yet; promote to its own directory once it goes from outline
to prose.

## Working title

"Compile-time beta reduction in a VSA-substrate language: how Sutra
sidesteps runtime hypervector lambda calculus"

(Working — placeholder until the contribution-list shape settles.)

## Abstract sketch

The recent VSA-as-Turing-complete line of work (Flanagan et al.
2024 onward) constructs *runtime* VSA Lisp interpreters: beta
reduction happens inside the hypervector substrate, paying for it
with approximate unbinding and an external cleanup memory. We
present **Sutra**, a programming language whose VSA substrate is
the *compilation target* rather than the *interpreter*. Beta
reduction and algebraic simplification run at compile time;
runtime is reduced to a tensor evaluation with no remaining
lambda structure. We identify four computational novelties that
ride on this inversion — differentiable fuzzy logic on the truth
axis, beta reduction to tensor normal form as compiler architecture,
eigenrotation as the loop primitive, and synthetic-dimension
rotation as the storage primitive — and show that together they
collapse the runtime VSA-LC problem entirely.

## Thesis

The recent line of VSA-as-Turing-complete work (Flanagan et al.
2024 "Hey Pentti, We Did It!"; arXiv:2510.17889; arXiv:2511.08767;
the category-theory companion arXiv:2501.05368) builds a
**runtime VSA Lisp interpreter** — beta reduction happens *inside*
the hypervector substrate, accepting the costs of approximate
unbinding and an external cleanup memory.

**Sutra inverts this.** Beta reduction happens at **compile time**,
during algebraic simplification. The runtime is left with a single
matrix multiply (or a short chain of cached tensor ops) that
contains no remaining lambda structure. The "how do you do
substitution inside a hypervector" problem doesn't apply because
substitution has already been eliminated before any vector is
touched.

The contribution: **you don't need a runtime VSA lambda calculus
if your compiler reduces the program to its tensor normal form
ahead of execution.** The substrate's job is reduced from
"interpret an encoded program" to "evaluate one composed linear
map," which sidesteps the cleanup-memory and approximation-cascade
issues that constrain the Flanagan line of work.

## The four computational novelties

These are claimed as *computational* novelties — distinct
mechanisms not just framings. Each is implemented in Sutra today;
the paper's job is to articulate why each is novel and how the
four compose.

### 1. Differentiable fuzzy logic for superposition

Three-valued logic over `{-1, 0, +1}` implemented via **Lagrange
polynomial form** on the truth axis. Every logical operation
(`!`, `&&`, `||`, comparison, equality) is a polynomial in the
truth-axis values and is therefore differentiable end-to-end.

```
!a       = -a
a && b   = (a + b + ab − a² − b² + a²b²) / 2
a || b   = (a + b − ab + a² + b² − a²b²) / 2
```

(Pulled from `docs/primitive-classes.md` § "Functional completeness
and factorable logic"; the equivalence with K3 / Kleene three-valued
logic on `{-1, 0, +1}` is the design contract.)

Why this is a computational novelty: most fuzzy-logic systems
either use min/max (non-differentiable at the corners) or sigmoid
relaxations (differentiable but lossy and substrate-dependent).
The Lagrange polynomial form is **exact on the three-valued
grid** (i.e. it agrees with classical truth tables at the corners)
**and** smooth in between. That combination — exact at the
discrete points + globally smooth + closed under polynomial
algebra — is what makes the rest of the compiler work.

### 2. Beta reduction to tensor normal form as compiler architecture

Compilation as **typed beta reduction plus algebraic
simplification** with a tensor expression as the normal form.
Programs collapse to single matrices (or short tensor-op chains)
when the simplifier can prove the necessary identities. This is
the organizing principle, not an optimization pass.

Implementation: `sdk/sutra-compiler/sutra_compiler/simplify.py`
(900-line hand-rolled rewriter, 16 rules) plus the in-flight
egglog migration tracked under STATUS.md's "Egglog integration"
entry. The matrix-chain-fusion proof-of-concept
(`experiments/egglog_matrix_chain_fusion.py`) extracts fully-fused
`(Mn @ ... @ M1).apply(v)` from nested-apply chains via cost-model
extraction.

Why this is a computational novelty: standard compilers do beta
reduction *during inlining* but it's incidental. Most languages
preserve sequential control-flow structure as their compilation
target. Sutra's target is a **value** — a linear map — not an
instruction sequence. The output of compilation is structurally
different from the input. Closest existing analog is
supercompilation (some Haskell compilers), but supercompilation
still produces program-shaped output, not closed-form values.

### 3. Eigenrotation as a loop primitive eliminating control flow

`loop(cond)` compiles to `state ← R · state` on the substrate
with prototype-match termination. There is no program counter at
runtime; the "iteration count" is the angular position on the
helix `R^i · v_0` traced through the substrate's state space.
Termination is a Jaccard match against a compiled prototype,
which itself runs on the substrate (in the fly-brain backend, on
spiking Kenyon-cell sparse codes).

Spec: `planning/sutra-spec/control-flow.md` § "loop(cond)" and
`docs/loops.md`. Empirical validation: 30/30 across k ∈
{1,2,3,5,8,12} × 5 seeds on real FlyWire wiring
(`planning/findings/2026-04-13-jaccard-target-k-sweep-30-of-30.md`).

Why this is a computational novelty: iteration is the canonical
non-linear-algebraic operation. Most ML-adjacent languages handle
loops by stepping out of tensor land into a Python `for`. Sutra
keeps iteration *inside* the tensor algebra by reframing it as
matrix exponentiation with substrate-resident termination. There
is no instant during a loop's execution where the runtime is doing
something other than tensor ops.

### 4. Synthetic-dimension rotation for arrays and hashmaps

Arrays and hashmaps as **single bundled vectors** built from
rotation-bound key-value pairs; reads are a single `unbind`.
Storage and retrieval are pure algebra — no branches, no pointers,
no index decode. The data structure lives in a synthetic-dimension
slice of the extended state vector and is differentiable and
compile-time factorable.

Implementation: `docs/memory.md` (the rotation-binding +
superposition mechanism), `examples/rotation_hashmap.su`
(library-pattern demo, 5/5 exact lookup),
`planning/findings/2026-04-23-rotation-hashmap-capacity-extended-state.md`
(capacity curve at d=868: 100% to k=24, 90% threshold at k=48).

Why this is a computational novelty: standard data structures are
control-flow problems (indexing is a branch, hashing is a sequence
of operations). Sutra makes them rotations in synthetic
dimensions. The "data structure" doesn't exist at runtime — the
compile-time factorization absorbs the access pattern into the
surrounding tensor expression. Lookups in dense vector space
become matrix-row selections, which are already what you're
doing — there's no representation switch.

## The framing that unifies all four

Every Sutra construct compiles to tensor operations because
*every* construct is one of:

- A polynomial on the truth axis (logic, conditionals — novelty 1)
- An eigenrotation on the substrate (loops, arrays, hashmaps —
  novelties 3, 4)
- Pure linear algebra (bind, bundle, similarity, projection)

The compiler is then beta reduction over a uniformly-typed tensor
algebra (novelty 2). The Flanagan-line approach handles the same
set of programs but interprets them on the substrate at runtime;
Sutra reduces them past the substrate boundary at compile time.

The empirical claim of the paper is: **these four mechanisms
together eliminate the runtime VSA-LC problem entirely.** No
runtime substitution, no cleanup memory, no approximation cascade
on iterated beta reductions. The substrate sees only the reduced
form.

## Why this is a Claw4S-shaped paper

- It's a **methodology contribution** — not a new substrate, not a
  new VSA flavor, but a different relationship between a VSA and
  the language it hosts.
- It plugs into the same target audience as the Flanagan / "Hey
  Pentti" line — they'll recognize the contrast.
- The empirical core can be small: three demos compiling to single
  matrix multiplications, plus the rotation-hashmap capacity numbers
  we already have, plus the differentiable-logic polynomial form.
  No new experiments strictly required if scope is held tight.
- The honest limit is captured by the "what about non-fuzzy /
  non-eigenrotation control flow" question — answer is: you can't
  write it (`if/else` is rejected at codegen, `select` is the only
  branching primitive). That's a feature, not a gap.

## Prior art the paper has to reckon with

Mostly already cataloged in `planning/prior-art-vsa-turing-completeness.md`.
Additional pieces specific to this framing:

- **De Bruijn indices** as a "natural VSA bridge" — the Flanagan
  line uses them to dodge the named-variable-scoping problem inside
  the runtime hypervector. Sutra's compile-time reduction makes
  De Bruijn vs. named irrelevant — the compiler resolves names
  before the VSA layer runs at all. Worth one paragraph in the
  comparison.
- **Gayler & Levy** on VSA cognitive architectures — touched on
  functional application; same target-audience argument as Plate /
  Smolensky / Flanagan.
- **The Curry–Howard–Lambek angle** — the Flanagan line cites it.
  Sutra's claim is that compile-time beta reduction makes the
  CCC structure *static* — the morphisms are composed before
  runtime, the evaluation map collapses to a constant. This is a
  cleaner story than "the VSA realizes a fuzzy CCC" because
  there's no fuzziness left at the boundary the substrate sees.

## What would need to land before 2026-04-30

- [ ] **Decision on scope.** Five-contribution paper vs. focused
  one-contribution paper (probably contribution #1, framed as
  "compile-time beta reduction to tensor normal form" with the
  others as supporting evidence).
- [ ] **Egglog matrix-chain-fusion result** as a concrete demo of
  the simplifier doing the beta reduction it claims. Already in
  `experiments/egglog_matrix_chain_fusion.py` per STATUS.md
  (DONE 2026-04-24); needs writeup.
- [ ] **One end-to-end .su program** that visibly compiles to a
  single matrix. The rotation-hashmap demo is close; might need a
  cleaner pedagogical example.
- [ ] **Honest comparison section** to Flanagan / "Hey Pentti" —
  including the cleanup-memory honesty (their line accepts it as
  part of the algebra; Sutra doesn't need it because reduction
  happened before runtime).
- [ ] **Differentiability story** — Lagrange polynomial form
  documented in `docs/primitive-classes.md`. Needs a paper-shaped
  paragraph plus the gradient-flow argument.

## Open questions before this becomes a real paper

1. **Is "Sutra programs compile to a single matrix" empirically
   true on the demos we have?** Rotation-hashmap, fuzzy-branching,
   role-filler-record — does each actually reduce to a single
   matrix multiply, or just to a short chain of tensor ops? The
   simplifier doesn't quite get there yet for all cases; the
   egglog pass is the bet that closes that gap.
2. **What's the substitution-equivalence proof?** "Compile-time
   beta reduction is equivalent to the VSA-runtime version
   (Flanagan)" needs a formal statement. The compiler does
   substitution syntactically; the VSA does it via approximate
   unbinding. Are these equivalent under what assumptions?
3. **The cleanup-memory-as-cheating argument.** A reviewer could
   say: "Sutra doesn't need cleanup memory at runtime because
   the cleanup is done at compile time by the simplifier — but
   that's just moving the cleanup, not eliminating it." How does
   the paper handle that? The honest answer is probably yes,
   compile-time simplification is the cleanup, but it's a static
   one-time cost paid before any data touches the substrate.
4. **Does this generalize to ML training?** Sutra doesn't currently
   train anything; the differentiability claim is end-to-end but
   not exercised. Whether the paper claims trainability or
   explicitly defers it is a scope question.

## What this is not

This is **a paper-idea note**, not a commitment that the paper
gets written or submitted. The 2026-04-30 window is tight; if
the egglog matrix-chain-fusion writeup doesn't land in time, the
paper either drops to a workshop submission, slips to the next
window, or doesn't go. Treat this doc as a parking lot for the
framing and contributions list. If it becomes real work, it moves
into STATUS.md.
