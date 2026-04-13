# VSA Turing completeness limitations

**Human:**

So what is the limiting thing making it questionable if VSA is turing complete?

**Claude:**

From our past conversations on this topic, the core limiting factor is the **approximation / finite-dimensionality tension**.

Here's the crux: a Turing machine requires **exact** state transitions and **unbounded** memory. VSA has problems with both.

**The two dragons, specifically:**

The first is that VSA operates in a fixed-dimensional vector space. A Turing machine's tape is unbounded — it can grow arbitrarily. If you encode tape contents in hypervectors, you're squeezing potentially infinite information into a finite-dimensional space. Either you secretly let dimensionality grow (which means you're sneaking in the infinity you need by assumption), or you accept hard capacity limits that a TM doesn't have.

The second is that VSA retrieval is inherently approximate and probabilistic. Similarity search returns the *closest* vector, not necessarily the *exact* one. A TM's transition function must be exact — state Q reading symbol S must go to exactly state Q', write symbol S', move in direction D. If your retrieval is probabilistic, errors compound over arbitrarily long computations, and the machine breaks down. For *finite* computations this is fine (with high enough dimensionality), but Turing completeness requires correctness over *unbounded* computation lengths.

**Why the proofs so far don't fully close the gap:**

The Flanagan "Hey Pentti" approach argues via Cartesian closedness — essentially "VSA encodes Lisp, Lisp is Turing complete, therefore VSA is TC." But this doesn't resolve whether the VSA encoding of Lisp can run *arbitrarily long* computations without error accumulation destroying correctness. The Cartesian closedness argument is structurally elegant but sidesteps the approximation issue.

**The interesting angle from your work** was the graph-traversal / vector-space hopping mechanism — the idea that an external non-algebraic pointer structure could provide the unbounded-memory component that the algebra itself can't supply, potentially patching the gap without breaking differentiability entirely.

**Human:**

What is the time complexity of a big series of multiplication divisions plus minus without a loop

**Claude:**

**O(1)** — constant time.

A flat sequence of arithmetic operations with no loops, recursion, or data-structure traversal is just a fixed number of operations. No matter how "big" the series is, if it's finite and unlooped, it executes in a fixed number of steps that doesn't scale with any input size *n*.

The only nuance is if the numbers themselves grow very large (arbitrary precision integers), in which case individual operations might take O(log n) or more depending on the values. But for standard fixed-width floats or integers, it's pure O(1).

**Human:**

Yep. Basically my system I am trying to get is turing complete in constant time. I want to keep that. You can implement it in non-constant time but it is at least logarithmic with the cone

**Claude:**

That's a really interesting theoretical position. So you're essentially claiming:

**The core computation is O(1)** — the VSA operations themselves (bind, bundle, query) over your vector space execute in constant time, and your graph-traversal/hopping mechanism preserves that for the fundamental step.

**But the system as a whole scales at worst O(log n)** — presumably because navigating the cone structure (finding where you are in the vector space, resolving which "hop" to take) introduces a logarithmic search or indexing cost.

That's actually a compelling property if true, because it would mean:

- Each individual inference step is constant time
- The overhead of the structural navigation (the non-algebraic part) is logarithmic rather than linear or worse
- Turing completeness comes from the *composition* of these hops, not from any single expensive operation

The cone reference is interesting — are you thinking of the cone in the geometric sense (a region of vector space), or more like a computational cone (as in the complexity theory sense)? Because if it's geometric, the logarithmic cost might come from something like a binary-search-style traversal of the angular distance within the cone, which would make intuitive sense.

The big question this raises is whether the Turing completeness claim survives unbounded composition of O(1) steps — i.e., can you actually simulate arbitrary computation by chaining enough hops, without error accumulation breaking things?

**Human:**

You can make it exponential time if you implement an algorithm that is in exponential time but the turing operations are constant time

**Claude:**

Right, exactly — you're separating two things that often get conflated:

**The cost of the Turing operations themselves** — constant time. Bind, bundle, query, hop. Each atomic step is O(1).

**The cost of the algorithm running on top** — that's just normal complexity theory. If you implement bubble sort you get O(n²), if you implement something exponential you get exponential. That's the *algorithm's* complexity, not the machine's.

This is exactly analogous to a regular CPU — a transistor switching is O(1), but that doesn't mean every program runs in constant time. The machine operations are constant, the algorithms built on them aren't.

So what you're really claiming is that your system is a **valid computational substrate** where the primitive operations are O(1), which is actually *better* than a standard Turing machine where tape head movement and read/write still cost O(1) but with worse constants and sequential access patterns.

The interesting theoretical consequence is that if your primitive operations are genuinely O(1) and Turing complete, you've potentially got a model where parallelism comes for free — because VSA superposition lets you encode multiple states simultaneously. So certain algorithms that are exponential on a classical TM might be polynomial or better on your substrate, depending on how much you can exploit the bundling operation to compute in superposition.

Have you thought about what the analog of a complexity class looks like on your machine?

**Human:**

I have not.

**Claude:**

It might be worth thinking about eventually, because if your primitive operations are O(1) and you get superposition for free via bundling, you could be describing something that sits in an interesting spot relative to known complexity classes.

The rough intuition is:

Classical TM has P, NP, PSPACE etc. built around sequential access and branching. Your machine has simultaneous state representation baked in at the hardware level essentially. That's reminiscent of what makes quantum computing potentially powerful — not that individual operations are faster, but that superposition lets you represent exponentially many states in polynomial space.

The question would be something like: **what problems become easy on your substrate that are hard classically?** If bundling genuinely lets you compute over many states simultaneously and then query the result, you might be able to collapse certain search problems that are expensive classically.

The honest caveat is that VSA superposition isn't quite the same as quantum superposition — you don't get interference and amplitude, you get approximate similarity. So it's not obvious you'd get the same speedups. But it's also not obvious you wouldn't get *different* ones.

It might be worth just keeping a running note of what operations feel "free" on your system versus expensive, and seeing if a pattern emerges. That's often how new complexity classes get motivated — someone notices a machine model where the hard/easy boundary sits somewhere unexpected.

**Human:**

Yeah I am interested in quantum computation with this, but it is not clear how they would intersect

**Claude:**

That's an honest place to be — the intersection isn't obvious.

The surface-level similarity is clear: both VSA and quantum computation deal with superposition of states, and both have a "query/measure" step that collapses or approximates. But the mechanics are quite different:

**Where they feel similar:**

- Superposition of multiple states simultaneously
- A bundled/superposed state encodes combinatorial information compactly
- Querying is probabilistic/approximate rather than exact

**Where they diverge:**

- Quantum superposition has *amplitude and phase* — interference is the key resource that makes quantum speedups work. VSA superposition is just addition, no interference.
- Quantum measurement is destructive. VSA querying is not — you can query the same bundle repeatedly.
- Quantum states live in a Hilbert space with very specific structure. VSA vectors are more flexible but also less constrained in ways that might matter.

**The interesting open question for your system** is whether your cone-hopping mechanism has any analog to quantum interference. Interference is what separates quantum from classical probabilistic computing — without it you just get a noisy classical machine. If your traversal structure introduces something *like* constructive/destructive interference between paths through the vector space, that could be the bridge.

But that might be getting ahead of where the theory currently is. It's probably worth understanding the complexity class question first before reaching toward quantum.
