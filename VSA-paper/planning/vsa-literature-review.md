# VSA / Hyperdimensional Computing Literature Review Plan

## Why This Matters

We need to verify that our operations genuinely map to VSA formalism before
reframing the paper. If the mapping is loose, the reviewer will punish us
the same way it punished "cartography."

## Key Papers to Read

### Foundational
1. **Kanerva (2009)** - "Hyperdimensional Computing: An Introduction to Computing in Distributed Representation with High-Dimensional Random Vectors"
   - The foundational tutorial. Defines binding, unbinding, bundling, permutation.
   - Need to check: does our displacement = binding? Does composition = sequential binding?

2. **Gayler (2003)** - "Vector Symbolic Architectures Answer Jackendoff's Challenges for Cognitive Science"
   - Defines the algebraic framework. Key operations: MAP (binding), superposition (bundling).
   - Need to check: what algebraic properties does our space satisfy?

3. **Plate (1995/2003)** - Holographic Reduced Representations
   - Circular convolution as binding. Our operation is vector addition, not convolution.
   - Need to check: is additive binding a recognized VSA variant? (Yes — it's essentially the "MAP" operation in some formulations)

### Surveys
4. **Kleyko et al. (2021)** - "Vector Symbolic Architectures as a Computing Framework for Emerging Hardware and Applications"
   - Comprehensive survey. Covers all VSA variants and their properties.
   - Need to check: which VSA family does our space most resemble?

5. **Kleyko et al. (2023)** - "A Survey on Hyperdimensional Computing"
   - More recent survey. May cover connections to neural network representations.
   - Need to check: has anyone studied emergent VSA in trained neural nets?

### Directly Relevant (VSA + neural embeddings)
6. **Smolensky (1990)** - Tensor Product Representations
   - Binding via outer product. Different from our additive displacement.
   - But: established the idea that neural nets might implement symbolic operations.

7. Any papers on **"emergent symbolic computation in neural networks"**
   - This is our actual claim: frozen embeddings spontaneously implement VSA-like operations
   - Need to search for: who else has found this? Is this known?

## What We Need to Establish

### The mapping must answer these questions:

1. **Is displacement a recognized binding operation?**
   - Our operation: `relation = tail - head` (unbinding), `head + relation ≈ tail` (binding)
   - In VSA terms: is vector addition a valid binding? (Some VSA variants use addition)
   - If yes: we're discovering binding in frozen embeddings
   - If no: we need to explain why our operation is VSA-adjacent but not exactly binding

2. **Is composition evidence of sequential binding?**
   - Our operation: `head + r1 + r2 ≈ tail` (two-hop)
   - VSA sequential binding: `bind(bind(x, r1), r2)` — depends on the binding operation
   - If binding = addition, then sequential binding = addition of operations = exactly what we do

3. **What does the consistency score mean in VSA terms?**
   - High consistency = the binding is "clean" (low noise)
   - Low consistency = the binding is "dirty" (high noise)
   - VSA literature has extensive treatment of noise in high-dimensional operations
   - Our consistency score might map to "signal-to-noise ratio" in VSA

4. **What does the [UNK] collapse mean in VSA terms?**
   - Collided embeddings have lost their identity vectors
   - In VSA: you can't unbind if the vectors are identical (no information to recover)
   - This frames the defect as "loss of representational capacity" in the algebra

5. **Has anyone shown emergent VSA in frozen neural embeddings before?**
   - If no: this is our novel contribution and it's significant
   - If yes: we need to cite them and explain what we add

## Search Strategy

- Google Scholar for: "vector symbolic architecture" + "text embeddings"
- Google Scholar for: "hyperdimensional computing" + "language models"
- Google Scholar for: "emergent symbolic computation" + "neural networks"
- Check citations of Kleyko et al. surveys for recent applied work
- Check arXiv cs.CL and cs.AI for 2024-2025 papers connecting VSA and LLMs

## Output

After this review, update `reframe-notes.md` with:
- Confirmed or rejected VSA mapping
- Specific terminology to use (which VSA variant we most resemble)
- Papers to cite
- Revised framing for the paper
