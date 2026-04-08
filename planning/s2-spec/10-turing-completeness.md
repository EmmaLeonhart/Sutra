# Turing Completeness

## The Cartesian Closed Category Argument

Flanagan et al. (2024), "Hey Pentti, We Did It!", constructs a VSA encoding of Lisp 1.5 and argues Turing completeness via **Cartesian closed categories (CCCs)**.

A CCC requires:
1. **Terminal object** — a distinguished "unit" element
2. **Products** — you can pair any two objects (bundling)
3. **Exponentials (function objects)** — you can represent functions as objects (lambda abstraction encoded as bound structures)
4. **Evaluation morphism** — you can apply a function object to an argument (beta reduction via unbind-rebind)

The **Curry-Howard-Lambek correspondence** equates:
- CCCs ↔ typed lambda calculi ↔ intuitionistic logic
- If your system is a CCC, it is Turing-complete (modulo the usual caveats about recursion/fixed points)

Flanagan et al. argue that VSA with cleanup memory forms a CCC: bundling gives products, binding gives exponentials, unbinding gives evaluation. The Lisp interpreter is the constructive proof.

## What Was Actually Proven (and What Wasn't)

**What holds:**
- The Lisp interpreter works. Lambda terms are encoded, reduced, and read back correctly.
- The CCC structure is real — the algebraic operations satisfy the categorical axioms.
- The construction is elegant and the framing is mathematically sophisticated.

**What's strained:**
- **Cleanup memory does the heavy lifting.** The boundary between "the VSA computing" and "the cleanup lookup table computing" is not formalized. If you count the cleanup codebook as part of the VSA, you're arguably just doing symbolic computation with a vector-space cache. If you don't count it, the VSA alone can't sustain computation past a few steps.
- **Fixed dimensionality vs. unbounded computation.** A Turing machine's tape is unbounded. A VSA vector has fixed dimensionality. Encoding potentially infinite information into a fixed-dimensional space requires either: (a) secretly growing dimensionality (which makes it not a fixed VSA), or (b) accepting hard capacity limits on computation depth/breadth. The CCC argument sidesteps this by not addressing it.
- **Approximate retrieval vs. exact state transitions.** Turing completeness requires that each computation step produces an exact next state. VSA unbinding produces an approximate result. Over unbounded computation, approximation errors compound to certainty of corruption. Cleanup memory patches this, but cleanup is itself a non-algebraic operation that depends on the codebook being complete — and a complete codebook for arbitrary computation is itself unbounded.

**The honest assessment:** VSA is Turing-complete in the same sense that floating-point arithmetic is "real number arithmetic" — it works for all practical purposes within its precision limits, with periodic rounding (cleanup) to stay on track. The theoretical gap between "works for all practical chains we've tested" and "provably computes any Turing-computable function" is real but may not matter for S2's purposes.

## The Two Fundamental Obstacles

1. **Fixed dimensionality.** A 10,000-dimensional vector can superpose a limited number of items before signal-to-noise degrades below usefulness. This limit is quantifiable (it scales roughly as √d for bundling, where d is dimensionality) but it is hard. You cannot represent an unbounded tape in a fixed-dimensional space.

2. **Approximate retrieval.** Unbinding returns the nearest vector, not the exact one. Each operation introduces noise proportional to the other items in the superposition. Over a long chain, errors compound geometrically. Cleanup (snap-to-nearest) resets the error but requires a codebook that contains the correct answer — which presupposes you know what the correct answer is.

## The Non-Algebraic Patch

This is where S2's non-algebraic operations (snap, cone, hop) become load-bearing for the Turing completeness argument:

- **Snap-to-nearest** provides error correction, allowing computation chains to extend beyond the algebraic noise limit
- **Cone traversal** provides conditional branching that isn't limited by superposition capacity
- **Graph hop** provides unbounded memory via an external graph structure — the vector state navigates the graph, which can grow without bound

The graph structure isn't fixed ahead of time — the vector state influences which edges get traversed. New nodes and edges can be created during computation. This is the mechanism that patches fixed-dimensionality: the vectors do local computation, the graph provides unbounded external memory. It's analogous to a CPU (fixed registers) with RAM (unbounded, addressable memory).

**S2's Turing completeness claim is: VSA algebra + ANN-backed non-algebraic operations + external graph = Turing complete.** The algebra alone is not. This is an honest and architecturally clean position.
