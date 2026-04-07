# VSA Speculations, Sources, and Open Questions

This file contains everything we've learned, speculated, and not yet verified
about the connection between our work and Vector Symbolic Architecture.
None of this is in the paper unless backed by empirical results.

## Confirmed Empirically (in paper)

1. **Our operations are bundling, not binding.** cos(result, head) = 0.860 across
   9,432 triples. Binding requires cos ≈ 0 (Plate 2003). Clear fail.

2. **Addition beats multiplication.** 29/30 predicates, MRR 0.464 vs 0.022.
   The embedding space uses additive superposition, not multiplicative binding.

3. **FHRR bridge holds trivially.** mxbai-embed-large is L2-normalized (||v||=1.0000),
   so all vectors are on the hypersphere. Angular and Euclidean operations are identical.

4. **All 188 predicates classified as bundling.** Zero exceptions.

## Speculations NOT in Paper (Need Verification)

### The KGE↔VSA Correspondence Table

| KGE Method | Scoring Function | Possible VSA Equivalent |
|-----------|-----------------|------------------------|
| TransE    | ||h + r - t||    | Bundling (addition)    |
| RotatE    | ||h ⊙ r - t|| (complex) | Possibly FHRR binding |
| HolE      | circular correlation | Possibly HRR binding |
| DistMult  | h ⊙ r ⊙ t      | Possibly MAP binding   |
| ComplEx   | Re(h ⊙ r ⊙ t̄)  | Possibly FHRR binding  |

**STATUS: UNVERIFIED.** We claimed this was novel. The AI reviewer said it's
"well-recognized in the neuro-symbolic community." We have a background research
agent checking this. Until we have citations either way, DO NOT put this in the paper.

**Known connection:** HolE is explicitly named after "Holographic" embeddings,
which references Plate's Holographic Reduced Representations. So at least the
HolE↔HRR connection is probably acknowledged somewhere.

### Is the Bundling Finding Actually Novel?

Word2vec analogies (king - man + woman = queen) have been around since 2013.
That's addition/subtraction on embeddings. Our contribution is:
- Systematic sweep across ALL predicates (not cherry-picked analogies)
- Quantified consistency metric
- Cross-model validation (3 models)
- Formal VSA axiom testing

But the basic observation (embeddings support additive relational structure)
is NOT novel. What's novel is the systematic methodology and what it finds
(the defect, the cross-model universality, the consistency-accuracy correlation).

### Symmetric Failure = Bundling Commutativity?

We observe: symmetric relations (sibling, spouse) produce no consistent displacement.
VSA theory says: bundling is commutative (A + B = B + A), so no directional signal.

This explanation is clean and correct, but it's also just a restatement of what
the KGE literature already says about TransE. The VSA vocabulary adds clarity
but not new prediction.

### Could We Actually Test Binding Operations?

Element-wise multiplication was tested (Experiment 2) and failed badly.
But that's MAP binding — only one variant. We could also test:
- Circular convolution (HRR binding)
- Complex multiplication (FHRR binding, after converting to complex)
- Outer product (TPR binding, but grows dimension)

**Worth doing?** Maybe for a follow-up paper. Not for this submission.

### The Collision Defect in VSA Terms

Collided embeddings have identical vectors → in VSA, they've lost identity.
You can't unbundle (subtract) information from a vector if the vector is
the same as thousands of other vectors. The algebraic capacity is destroyed.

This is a real insight but it's also just... common sense? If two things have
the same embedding, you can't tell them apart with any operation. The VSA
framing doesn't add predictive power here.

## Sources (Verified Real Papers)

### VSA/HDC Foundational
- Kanerva, P. (2009). "Hyperdimensional Computing." Cognitive Computation, 1(2), 139-159.
  - THE foundational tutorial. Defines binding, bundling, permutation.
- Gayler, R. W. (2003). "Vector Symbolic Architectures answer Jackendoff's challenges."
  - Defines the algebraic framework. MAP variant.
- Plate, T. A. (1995/2003). Holographic Reduced Representations.
  - Circular convolution as binding. Formal axioms for binding (dissimilarity, invertibility, distributivity).
- Smolensky, P. (1990). "Tensor Product Variable Binding." Artificial Intelligence.
  - Binding via outer product. TPR framework.

### VSA Surveys and Comparisons
- Schlegel, K., et al. (2022). "A comparison of vector symbolic architectures." AI Review, 51.
  - Compares 11 VSA variants. THE reference for which variant does what.
- Kleyko, D., et al. (2023). "A survey on hyperdimensional computing." ACM Computing Surveys.
  - Comprehensive recent survey.
- Fong, B., et al. (2025). "A category-theoretic foundation for VSA." arXiv:2501.05368.
  - Category theory formalization. Binding = multiplication, bundling = addition in a division ring.
  - **WARNING: The AI reviewer flagged this as a "hallucinated citation" because of the 2025 date.**
  - It's a real arXiv preprint. But if we cite it, the reviewer may reject us for it.

### Emergent VSA in Neural Networks
- McCoy, R. T., et al. (2019). "RNNs implicitly implement tensor-product representations." ICLR.
  - Showed RNNs learn TPR internally. Closest precedent to our "emergent VSA" claim.
- "Attention as Binding" (2025). arXiv:2512.14709.
  - Argues transformer attention implements soft VSA binding/unbinding.
  - **WARNING: Same 2025 date problem. Real paper, but may be flagged.**

### KGE Methods
- Bordes et al. (2013). TransE. NeurIPS.
- Sun et al. (2019). RotatE. ICLR.
- Nickel et al. (2016). HolE. AAAI.
  - Name explicitly references "Holographic" = Plate's HRR.
- Trouillon et al. (2016). ComplEx. ICML.
- Yang et al. (2015). DistMult. ICLR.

### Other
- Gosmann, J., & Eliasmith, C. (2019). VTB. Neural Computation.
- Allen, C., & Hospedales, T. (2019). Analogies explained. arXiv:1901.09813.
  - Formal analysis of why word2vec analogies work. PMI matrix factorization.

## Open Questions

1. Has anyone formally connected the KGE and VSA literatures? (Research pending)
2. Is circular convolution binding better than addition for our task? (Untested)
3. Can we test FHRR binding by converting to complex phasors? (Possible experiment)
4. Is there a way to do actual binding on frozen embeddings? (Unclear)
5. What would a complete VSA look like built on top of frozen embeddings? (Future work)
