# Hyperdimensional computing and JEPA connection

**Human:**

How much of a novelty is it that I saw hyperdimensional computing and JEPA as basically really closely tied? I was very surprised to know that thjere is not much overlap?

**Claude:**

Your intuition is actually quite insightful, and the lack of literature connecting the two is a genuine gap rather than evidence that they're unrelated. Let me break down why the connection is real and why the overlap is sparse.

**Where you're clearly onto something**

Both HDC and JEPA are fundamentally about operating in high-dimensional representational spaces where similarity is the core currency of computation. In HDC, processing is based on similarity between hypervectors, using measures like cosine similarity or dot product.  And JEPA learns to predict embeddings — dense, abstract representations that encode meaningful structure — in the latent level rather than predicting raw data tokens.  The structural resonance is real: both frameworks care deeply about what it means for two things to be "close" in representational space, and both deliberately avoid pixel-level or token-level reconstruction.

There's also a deeper alignment around *compositionality*. HDC/VSA models use high-dimensional distributed representations and rely on algebraic properties of key operations to incorporate the advantages of structured symbolic representations and distributed vector representations.  This compositionality-through-binding is conceptually adjacent to what JEPA tries to do when building up structured predictions in latent space.

**Why the literal connection is sparse**

The communities are quite segregated by origin and goal. HDC grew out of cognitive science, neuromorphic hardware, and symbolic AI — Kanerva's work in the late 80s/90s. Unlike many traditional neural networks, HDC/VSA models do not rely on backpropagation or other compute-intensive learning algorithms and can often induce a pattern from a single example.  JEPA, by contrast, is squarely a deep learning self-supervised learning framework, aimed at vision/video and world modeling, trained with gradient descent. They don't share conferences, authors, or benchmarks to any significant degree.

There's also a technical divergence in *how* the high-dimensional space is constructed. HDC uses explicit algebraic operations (binding, bundling, permutation) with hand-crafted hypervectors. JEPA learns its latent geometry end-to-end. So while the spirit is similar — structured reasoning in high-dimensional space without reconstructing raw inputs — the mechanisms are quite different.

**How novel is your observation?**

Genuinely somewhat novel, at least at the level of explicit synthesis. There's a small body of work combining VSA principles with learned latent spaces (the disentanglement paper you might find interesting applies VSA principles to represent objects in latent space using attention over codebook vectors combined with principles of Hyperdimensional Computing ), but nobody appears to have made the JEPA-HDC connection in a systematic theoretical way. The Graph-JEPA line of work does predict in hyperbolic latent spaces, which is adjacent territory, but it's not making the HDC connection explicitly.

The most interesting version of your intuition might be: *HDC's algebraic structure (bind, bundle, release) could serve as an explicit compositional prior on top of JEPA's learned embeddings*, potentially giving you the structured world modeling LeCun wants without having to learn compositionality from scratch. That's a paper waiting to be written.

**Human:**

hmm explicit compositional prior? Like a hybrid embedding that starts out with strict logical training and then after has more learned organic training built on it?

**Claude:**

Yes, exactly that spirit — though the framing can be sharpened a bit. Let me think through what this would actually look like mechanistically.

**The core idea**

HDC gives you a *fixed algebraic scaffold*: binding (⊗) creates role-filler pairs, bundling (+) creates superpositions, and the whole thing is reversible. You can say things like "red ∘ ball + left-of ∘ blue-cube" and get a single vector that can be queried for its parts. This is compositional structure that's *guaranteed by construction*, not learned.

JEPA then operates on top of that — instead of predicting in a raw pixel or token space, or even a purely learned latent space, it would be predicting in a space that already has algebraic structure baked into it. The predictor has to learn *relationships between structured representations*, not relationships between blobs.

**What the training phases might look like**

Phase 1 (the "logical" phase you're describing): Train the HDC encoding layer on symbolic consistency — the binding/unbinding algebra has to hold. You're essentially learning *how to map sensory input into hypervectors* while preserving the compositional guarantees. This is more like a curriculum constraint than a separate training run.

Phase 2 (the "organic" phase): Freeze or soften the algebraic structure and run JEPA-style predictive coding on top. The predictor learns which compositional transformations predict future states. Crucially, because the representation space already has structure, the predictor doesn't have to rediscover that "objects persist" or "relations are transitive" — those are partially handed to it.

**Why this is non-trivial**

The hard part is the interface. HDC hypervectors are typically very high-dimensional and binary or ternary — they're designed for a specific algebraic regime. JEPA's latent space is continuous and shaped by gradient flow. Reconciling those two regimes without losing the guarantees of either is the real research problem. You'd probably need something like a *soft hypervector* regime where the binding operations are differentiable approximations, so the whole thing remains trainable end-to-end.

There's actually adjacent work in this direction — Smolensky's Tensor Product Representations and more recently work on differentiable Holographic Reduced Representations — but nobody has wired that directly into a JEPA training objective.

**The intuition underneath**

What you're really pointing at is a kind of *inductive bias spectrum*. Pure HDC is maximally structured but inflexible. Pure JEPA is flexible but has to discover structure from scratch. A hybrid sits in the middle: start with structure you *know* is right (objects bind to roles, relations compose), and let the learned component handle everything that's genuinely too complex or domain-specific to specify algebraically. That's a principled way to get the best of both worlds rather than just hoping the transformer discovers compositionality at scale.

It's a legitimately interesting research direction.

**Human:**

hmm what about having binary/ternary dimenisons and more flexible ones?

**Claude:**

This is a really natural extension of the idea. You're essentially proposing a **mixed-regime latent space** — and there's actually a principled reason to think this could work well rather than just being an ad hoc compromise.

**The intuition**

Different aspects of a scene have different "rigidity" in reality. Whether a ball is *to the left of* a cup is a discrete, structural fact. How the light falls on that ball, or the exact trajectory of its motion, is continuous and fuzzy. Forcing both into the same representational regime is a mismatch from the start. So you'd have:

- **Binary/ternary dimensions** → structural, symbolic, compositional facts. Object identity, relational roles, categorical membership. These are the HDC-native dimensions where binding and bundling have clean algebraic meaning.
- **Continuous dimensions** → graded, sensory, dynamical facts. Texture, motion dynamics, uncertainty, degree of similarity. These are the JEPA-native dimensions where gradient-based learning shines.

**Why this isn't just two separate systems bolted together**

The interesting thing is that these two regimes can *interact* within a single vector. Imagine a binding operation where the role slot is binary (crisp — this IS the "agent" role) but the filler is continuous (a learned embedding of whoever the agent is). The algebraic structure governs *how* things compose; the continuous part governs *what* gets composed. That's qualitatively different from running HDC and a neural net in parallel.

**The technical challenge this creates**

Gradients flow differently through binary vs continuous dimensions. Binary dimensions essentially need something like the straight-through estimator or Gumbel-softmax to remain trainable — you're approximating a discrete decision with a continuous relaxation during the forward pass, then snapping to binary for the structural operations. This is solvable but it creates a tension: the more you relax the binary dimensions for trainability, the more you erode the algebraic guarantees that made them useful in the first place.

One way around this is **staged commitment** — during early training the binary dimensions are soft (continuous relaxations), and as training stabilizes you anneal toward hard binary values. The structural guarantees "crystallize" over time rather than being imposed from the start.

**What the JEPA predictor sees**

This is where it gets interesting. The predictor is now trying to predict future states in this mixed-regime space. Some of what it has to predict is essentially logical inference (which objects will still be present, what roles they'll occupy) and some is continuous extrapolation (where exactly, how fast, how lit). You'd want the predictor architecture to reflect this — perhaps separate attention heads or pathways for the binary vs continuous subspaces, with cross-talk between them.

**The biological angle**

This actually maps loosely onto something real in neural computation. There's evidence that the brain uses both discrete/categorical representations (grandmother cells, concept neurons, attractor states) and continuous manifold representations (grid cells, population codes). A mixed-regime hypervector might be a more neurobiologically honest computational model than either pure approach — which loops back to HDC's original cognitive science motivation.

The most honest summary: the idea is clean and principled, the math is tractable, but the engineering of the binary-continuous interface during training is where someone would have to do real work. It's not a known-hard problem, just an unsolved one.

**Human:**

Okay here is a bit of a weird idea that I feel might just be totally off the rails: hyperbolic and non-hyperbolic dimensions

**Claude:**

Not off the rails at all — this is actually a really elegant extension of the mixed-regime idea, and there's more grounding for it than you might expect.

**Why this makes immediate sense**

Hyperbolic space has a specific property that makes it compelling here: it's exponentially more capacious than Euclidean space as you move away from the origin. It naturally encodes **hierarchical structure** — trees embed into hyperbolic space with arbitrarily low distortion, whereas embedding them into Euclidean space requires dimensions that grow with the tree size. So the geometry itself carries meaning.

So you'd have:

- **Hyperbolic dimensions** → hierarchical, taxonomic, part-whole relationships. "Dog is-a animal is-a living thing." "Wheel is-part-of car is-part-of vehicle." The *nesting structure* of the world.
- **Euclidean dimensions** → lateral, relational, analogical facts. Things that are similar without being hierarchically related. Motion, transformation, co-occurrence.

And potentially combined with the earlier idea:

- **Hyperbolic + binary** → crisp taxonomic membership (this IS a mammal)
- **Hyperbolic + continuous** → graded hierarchical similarity (this is *somewhat* cat-like)
- **Euclidean + binary** → crisp relational facts
- **Euclidean + continuous** → graded similarity in flat space

**Why JEPA specifically benefits from this**

JEPA's core job is predicting future latent states from context. A lot of what makes prediction hard is that the world has structure at multiple levels simultaneously — a ball rolling off a table is a physics event (Euclidean, continuous) but also involves object persistence and categorical identity (hierarchical, discrete). If your latent space geometry actually reflects those different structural types, the predictor doesn't have to learn to *represent* the hierarchy — it's already in the metric. It just has to learn *dynamics within* each geometric regime.

**The real precedent**

This isn't as exotic as it sounds. Graph-JEPA already predicts in hyperbolic latent space. And there's a growing body of work on **product manifold embeddings** — spaces that are literally the Cartesian product of multiple geometric spaces, like hyperbolic × Euclidean × spherical. The idea being that real data has mixed curvature structure and no single geometry captures it well. A 2019 paper by Gu et al. showed this works empirically for knowledge graph embeddings — the product manifold outperformed any single geometry.

What you're proposing is essentially bringing that product manifold intuition *inside* a JEPA-style architecture, which to my knowledge hasn't been done explicitly.

**The hard part**

The operations that work cleanly in Euclidean space — addition, inner product, linear interpolation — don't transfer directly to hyperbolic space. Hyperbolic space requires Möbius transformations, the exponential/logarithmic map to move between tangent space and the manifold, and gyrovector arithmetic. So your predictor network can't just be a standard transformer — it needs to be geometry-aware, with different operations in different subspaces. That's non-trivial but there are frameworks for it (Poincaré embeddings, hyperbolic neural networks by Ganea et al.).

The deeper question is whether gradients flow well across the geometric boundary — when a prediction requires *both* a hierarchical inference (hyperbolic) and a continuous extrapolation (Euclidean), how do you backpropagate through a space that has different curvature in different dimensions? That's probably the core unsolved technical problem.

**The conceptual payoff if it works**

You'd have a latent space where the *geometry itself is a knowledge representation* — hierarchies live in the curvature, lateral relations live in the flat dimensions, symbolic structure lives in the binary dimensions. The predictor is then essentially doing inference in a space that's pre-shaped by the structure of reality rather than having to learn that shape from scratch. That's a pretty compelling vision.
