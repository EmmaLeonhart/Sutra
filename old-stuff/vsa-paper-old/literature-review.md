# Literature Review: Discovering First-Order Logic in Arbitrary Embedding Spaces

## Search Methodology

An agent conducting a literature review for this paper should search for prior work in the following areas, in order of priority:

### 1. Model-Agnostic Neuro-Symbolic Approaches
Search for work that treats pre-trained embedding spaces as existing infrastructure to build symbolic reasoning on top of, rather than constructing symbolic reasoning systems from first principles. The key distinction is: does the work assume a given embedding space and discover structure in it, or does it build a new system?

**Search terms:** "model-agnostic neuro-symbolic", "embedding space symbolic reasoning", "post-hoc symbolic operations embeddings", "logical operations pre-trained embeddings"

### 2. Vector Symbolic Architectures (VSAs)
Search for the VSA literature, particularly any work that applies VSA techniques to LLM embedding spaces rather than purpose-built hypervector spaces. The VSA field is large but mostly lives in cognitive science and neuromorphic hardware contexts.

**Search terms:** "vector symbolic architecture", "hyperdimensional computing", "VSA language model", "holographic reduced representations", "Kanerva hypervector"

### 3. Stratified Manifold Structure in Embedding Spaces
Search for work describing embedding spaces as having regions of different dimensionality, density, or semantic granularity. This would independently validate the oversymbolic/undersymbolic/isosymbolic zone taxonomy proposed in this work.

**Search terms:** "stratified manifold embedding space", "embedding space topology", "semantic density embedding", "intrinsic dimensionality embedding regions"

### 4. Discovering Logical Operations in Pre-Trained Embeddings
Search for work that empirically discovers transformation matrices or vector operations that correspond to logical relations, particularly from knowledge graph embeddings or sentence embeddings.

**Search terms:** "discovering vector operations embeddings", "transformation matrix embedding space", "learned relational operators embeddings", "analogy arithmetic embeddings beyond word2vec"

### 5. Mechanistic Interpretability
Search for work that probes or reverse-engineers the internal representations of neural networks, particularly approaches that extract structured/symbolic information from continuous representations.

**Search terms:** "mechanistic interpretability embeddings", "probing classifiers", "structural probes", "linear probes logical structure"

---

## What We Found (from Strategic Discussion)

Based on an agent-assisted literature search conducted during strategic planning (see `planning/strategic-discussion.md`):

### Vector Symbolic Architectures (VSAs)
- VSAs are an entire field doing algebraic operations on hypervectors (binding, bundling, permutation).
- The field is primarily rooted in cognitive science and neuromorphic hardware, NOT in treating LLM embedding spaces as a substrate.
- The "Hyperdimensional Probe" paper uses VSAs to decode LLM representations, making it the most adjacent work found. It is somewhat related but takes a different approach: it uses VSA as a decoding tool rather than discovering the embedding space's own algebraic structure.

### Stratified Manifold Work
- Independent research describes embedding spaces as containing "stratified sub-manifolds of different dimensions."
- This is significant because it provides independent empirical validation for the oversymbolic/undersymbolic/isosymbolic zone taxonomy proposed in this paper.
- The actual paper and citation still need to be identified and verified.

### Core Novelty Assessment
The systematic empirical methodology -- generating controlled permutations of sentences, computing transformation vectors, averaging them to obtain canonical transformation matrices, then using those matrices for invertible logical operations -- does not appear to have a direct prior in the literature. Most related work either:
- Builds VSA systems from scratch (not discovering structure in existing spaces)
- Probes existing spaces interpretively (not extracting reusable transformation operators)
- Works within knowledge graph embedding frameworks (TransE, RotatE, etc.) that construct purpose-built spaces rather than analyzing general-purpose embedding models

The glitch token / undersymbolic zone connection also appears novel, though it remains theoretical and is not a core claim of this paper.

---

## References to Verify

### Currently in Paper -- Well-Known but Not Formally Verified by Author

These are all well-known, real papers in the field. They have not been formally checked against the author's `sources/verified.md` file, which only contains Vaswani et al. (2017) and Seshia et al. (2022).

| Citation | Status | Notes |
|----------|--------|-------|
| Bordes et al. (2013). Translating Embeddings for Modeling Multi-relational Data. *NeurIPS*. | Real paper, not formally verified | TransE -- foundational KG embedding work |
| Conneau et al. (2018). What you can cram into a single vector. *ACL*. | Real paper, not formally verified | Probing sentence embeddings |
| Hewitt & Manning (2019). A structural probe for finding syntax in word representations. *NAACL*. | Real paper, not formally verified | Structural probes |
| Linzen (2016). Issues in evaluating semantic spaces using word analogies. *RepEval*. | Real paper, not formally verified | Critique of analogy evaluation |
| Manhaeve et al. (2018). DeepProbLog. *NeurIPS*. | Real paper, not formally verified | Neural probabilistic logic programming |
| Mikolov et al. (2013). Distributed representations of words and phrases. *NeurIPS*. | Real paper, not formally verified | Word2Vec -- foundational |
| Rocktaschel & Riedel (2017). End-to-end differentiable proving. *NeurIPS*. | Real paper, not formally verified | Differentiable logic |
| Rogers et al. (2017). The (too many) problems of analogical reasoning. *StarSem*. | Real paper, not formally verified | Analogy evaluation critique |
| Serafini & Garcez (2016). Logic Tensor Networks. *NeSy Workshop*. | Real paper, not formally verified | Neuro-symbolic integration |
| Sun et al. (2019). RotatE. *ICLR*. | Real paper, not formally verified | KG embedding via rotation |
| Trouillon et al. (2016). Complex embeddings for simple link prediction. *ICML*. | Real paper, not formally verified | ComplEx model |
| Vilnis et al. (2018). Probabilistic embedding of knowledge graphs with box lattice measures. *ACL*. | Real paper, not formally verified | Box embeddings |

### Formally Verified by Author (in `redoing-paper/sources/verified.md`)

| Citation | Status |
|----------|--------|
| Vaswani et al. (2017). Attention Is All You Need. *NeurIPS*. | Verified |
| Seshia, Sadigh, & Sastry (2022). Toward Verified Artificial Intelligence. | Verified |

### Problematic

| Citation | Status | Issue |
|----------|--------|-------|
| Leonhart, I. (2026). Beyond Proximity: Mapping the Topology of Isosymbolic Space. Working draft. | PROBLEMATIC | Self-citation to a working draft that does not exist publicly. Should be removed or replaced with a note about ongoing work. Cannot be independently verified or accessed by reviewers. |

---

## What Still Needs Searching

### High Priority
1. **VSA literature specifically** -- Need to identify the most relevant VSA papers to position against. Key names: Kanerva, Plate (Holographic Reduced Representations), Gayler. Need to find any VSA work applied to LLM embedding spaces.

2. **Stratified manifold paper** -- The strategic discussion references work on "stratified sub-manifolds of different dimensions" in embedding spaces. The actual paper needs to be found and cited. This is important because it provides independent validation.

3. **Empirical transformation matrix discovery** -- Any work that systematically discovers reusable transformation matrices from pre-trained embeddings (beyond the word2vec king-queen analogy). TransE/RotatE/ComplEx construct purpose-built spaces; we need to check if anyone has done this with general-purpose sentence embeddings.

### Medium Priority
4. **Hyperdimensional Probe paper** -- Need full citation details. This is the closest adjacent work found so far.

5. **Knowledge graph embedding surveys** -- A recent survey would help position this work relative to the TransE/RotatE/ComplEx family and clarify the distinction between constructing embedding spaces for logic vs. discovering logic in existing spaces.

6. **Probing classifier literature** -- Conneau and Hewitt are cited, but the broader probing literature may contain work closer to our approach than initially expected.

### Lower Priority
7. **Glitch token literature** -- If the oversymbolic/undersymbolic framing is included even as background, any prior work on glitch tokens and embedding space geometry should be found.

8. **Compositional generalization in embeddings** -- Work on whether learned transformations compose (our two-hop composition results) may have relevant priors.
