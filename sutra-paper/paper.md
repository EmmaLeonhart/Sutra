# Sign-Flip Binding and Vector Symbolic Operations on Frozen LLM Embedding Spaces

**Emma Leonhart**


## Abstract

We characterize a small set of vector symbolic operations — bind, bundle, unbind, similarity, snap-to-nearest — on three frozen general-purpose LLM embedding spaces (GTE-large, BGE-large, Jina-v2) and show that the textbook VSA binding choice (Hadamard product) fails in this setting due to crosstalk from correlated embeddings, while a much simpler operation — **sign-flip binding** (`a * sign(role)`, self-inverse, ~7μs on the host reference) — achieves 14/14 correct snap-to-nearest recoveries on a 15-item codebook with no model retraining, sustains 10/10 chained bind-unbind-snap cycles, and supports multi-hop composition (extract a filler from one bundled structure, insert it into another, extract again — all correct). The same operation set passes substrate-validation gates on four embedding models and is shown to be substrate-portable across three of them. This is an empirical paper about which VSA operations actually work on natural embedding spaces and at what capacity; it does not propose a new programming language. It establishes the operation set on top of which one could be built — the language itself is in active development and is reported separately.

The work is grounded in prior relational-displacement analysis of frozen embeddings: 86 predicates discovered as consistent vector operations across three embedding models, with r = 0.861 correlation between geometric consistency and prediction accuracy (Leonhart, *Latent space cartography applied to Wikidata*).

## 1. Introduction

That embedding spaces encode relational structure as vector arithmetic has been known since `king - man + woman ≈ queen` (Mikolov et al., 2013). The knowledge graph embedding literature formalized this: TransE models relations as translations (Bordes et al., 2013), RotatE as rotations (Sun et al., 2019), and subsequent work characterized exactly which relation types admit which geometric representations (Wang et al., 2014; Kazemi & Poole, 2018).

A complementary line of work showed that *frozen*, general-purpose embeddings — models not specifically trained for relational reasoning — also encode consistent vector arithmetic. Recent cartographic analysis of three general-purpose embedding models discovered 86 predicates that manifest as consistent displacement vectors, with 30 universal across all three models (Leonhart, *Latent space cartography applied to Wikidata*). The correlation between geometric consistency and prediction accuracy (r = 0.861) is self-calibrating: the structure's internal consistency predicts its external utility.

If general-purpose embedding spaces encode consistent algebraic structure, the next empirical question is which Vector Symbolic Architecture (VSA) operations actually compose over that structure — and at what capacity. The textbook VSA binding choice (Hadamard product) was developed for spaces designed for VSA (random hypervectors with controlled correlation statistics). Frozen LLM embeddings are not such spaces: they are anisotropic, correlated, and shaped by the unrelated objective of next-token or contrastive prediction. Whether the standard VSA operation set transfers to them is an empirical question that has not been addressed.

This paper reports that test. We hold the operation interface fixed (bundle, bind, unbind, snap-to-nearest, similarity) and vary the binding implementation across six candidates on bundled role-filler structures, then run the surviving operation through chained-computation and multi-hop-composition stress tests on three independent embedding models. The scope of the paper is exactly this: which VSA operations work, on which substrates, at what capacity. We do not propose a programming language here, and the language work in active development is reported separately.

### 1.1 Contributions

1. **An empirical characterization of which VSA operations work on natural embedding spaces.** We test six binding operations (Hadamard, sign-flip, permutation, circular convolution, FFT correlation, rotation) on bundled role-filler structures of 1–7 pairs. Hadamard — the textbook VSA choice — fails (2/7 correct snap recoveries at 7 roles); five alternatives succeed.

2. **Sign-flip binding as a substrate-portable choice.** `a * sign(role)` is self-inverse, ~7μs on the host reference, achieves 14/14 snap recoveries at the 14-role limit of our test set, sustains 10/10 chained bind-unbind-snap cycles, and supports multi-hop composition. The result is identical on three independent embedding models (GTE-large, BGE-large, Jina-v2).

3. **Substrate-validation gates including pathology detection.** A documented attention-sink defect in mxbai-embed-large (diacritic characters cause cosine > 0.95 between unrelated strings) passes algebraic gates but fails as a deployment substrate. We report this as a worked example of why algebraic validation alone is insufficient.

4. **An operation cost analysis** showing that snap-to-nearest is not the bottleneck on these substrates — even at a 10K-item codebook, snap is 8× cheaper than producing one embedding. The substrate-side cost of VSA-style computation on frozen embeddings is dominated by the LLM forward pass that produces the vectors in the first place, not by the algebra over them.

## 2. Related Work

### 2.1 Vector Symbolic Architectures

Vector Symbolic Architecture (VSA) is a family of algebraic frameworks for computing with high-dimensional vectors (Kanerva, 2009; Plate, 1995; Gayler, 2003). The core operations — binding (elementwise multiplication), bundling (addition), and similarity (dot product) — define an algebra over hypervectors that can represent and manipulate structured symbolic information. The standard VSA development assumes hypervectors drawn from a controlled random distribution; the present work asks what happens when the vectors are instead drawn from a frozen LLM embedding space, which is anisotropic and correlated.

Smolensky (1990) provided the theoretical foundation with tensor product representations, showing that role-filler binding via tensor products is formally equivalent to the substitution step in beta reduction. The relevance of this work to the present paper is that role-filler binding is the operation our six-way comparison varies; the substrate change (LLM embeddings rather than random hypervectors) is what we measure.

### 2.2 Hyperdimensional Computing

Hyperdimensional Computing (HDC) applies VSA to engineering tasks: classification (Imani et al., 2019), language recognition (Joshi et al., 2016), and robotics (Neubert et al., 2019). Libraries like Torchhd and vsapy provide HDC implementations on hand-designed hypervector spaces. The present paper differs in substrate, not in algebra: we test the same operation set on naturally-learned embedding spaces, which require a different binding choice.

### 2.3 Relational Displacement Analysis

TransE (Bordes et al., 2013) demonstrated that knowledge graph relations can be modeled as translations in learned embedding spaces. Recent work extended this to frozen general-purpose embeddings (Leonhart, *Latent space cartography applied to Wikidata*), discovering 86 consistent relational displacements across three models and a correlation (r = 0.861) between consistency and prediction accuracy. That work establishes the algebraic structure exists in these spaces; the present paper asks which compositional operations successfully exploit it.

## 3. Empirical Results

### 3.1 Algebraic Structure in Frozen Embeddings

The foundational empirical result (Leonhart, *Latent space cartography applied to Wikidata*): relational displacement analysis of three general-purpose embedding models — nomic-embed-text (768-dim), all-minilm (384-dim), and mxbai-embed-large (1024-dim) — using Wikidata triples discovers 86 predicates that manifest as consistent vector displacements, with 30 universal across all three models. The mxbai model is included in this baseline as a known-pathological case (see §3.5); the algebraic structure reported here was independently reproduced on the other two models.

The correlation between geometric consistency and prediction accuracy (r = 0.861, 95% CI [0.773, 0.926]) means the algebraic structure is self-calibrating: internally consistent operations are externally useful. This establishes that the algebraic structure needed for VSA-style composition exists in pre-trained, general-purpose embedding spaces without any VSA-specific training — the precondition for the remainder of the paper.

### 3.2 Binding Operation Selection

The traditional VSA binding operation (Hadamard / elementwise product) **fails on natural embedding spaces** when multiple role-filler pairs are bundled.

We tested six binding operations on GTE-large (1024-dim) by constructing bundled structures with 1–7 role-filler pairs, then attempting to recover a target filler via unbinding and snap-to-nearest against a 20-item codebook. Results:

| Method | Cos at 2 roles | Cos at 7 roles | Snap correct (7) | Cost (μs) |
|--------|---------------|---------------|-------------------|-----------|
| Hadamard | 0.11 | 0.09 | 2/7 | 1.5 |
| **Sign-flip** | **0.74** | **0.40** | **7/7** | **6.6** |
| Permutation | 0.71 | 0.37 | 7/7 | 30.9 |
| Circular conv | 0.29 | 0.13 | 7/7 | 79.3 |
| FFT correlation | 0.62 | 0.34 | 7/7 | 67.3 |
| **Rotation** | **0.89** | **0.80** | **7/7** | **321.3** |

Hadamard binding fails because natural embeddings are correlated and anisotropic — they share significant structure, so crosstalk from non-orthogonal role vectors overwhelms the target signal. All five alternatives achieve 7/7 correct snap recoveries at 7 bundled roles.

**Sign-flip binding** (`a * sign(role)`) strips magnitude correlation, leaving a pseudo-random binary mask that is self-inverse and nearly orthogonal across roles. At 6.6μs (4.4× Hadamard), it is cheap enough to use pervasively. **Rotation binding** (`R(role) @ a`) is the high-accuracy alternative at 321μs, maintaining 0.80 cosine similarity to the target even at 7 bundled roles.

Extended testing of sign-flip binding revealed substantially higher capacity than the initial 7-role test suggested. With a 15-item codebook on GTE-large, sign-flip achieves **14/14 correct snap recoveries** — cosine degrades gracefully from 0.74 at 2 roles to 0.30 at 14 roles, but snap consistently identifies the correct target. This capacity is substrate-portable: BGE-large-en-v1.5 (1024-dim) and Jina-v2-base-en (768-dim) both achieve identical 14/14 results.

**Chained computation** — the test for sustained reasoning — was run by repeatedly building 3-role bundled structures, unbinding the target, snapping, and using the result in the next structure. With sign-flip binding: **10/10 steps correct**, with raw cosine stable at 0.58–0.65 throughout the chain. Snap recovers the exact target at every step.

**Multi-hop composition** was run by extracting a filler from structure A (agent=cat, action=sit), inserting it into a different role in structure B (agent=dog, patient=extracted_cat), then extracting from B. All three extractions (agent from A, patient from B, agent from B) returned the correct filler, demonstrating that information can be moved between bundled structures via unbind-snap-rebind cycles without loss.

### 3.3 Cross-Substrate Validation

We ran substrate-validation gates on four non-normalized embedding models. Initial tests used Hadamard binding; sign-flip capacity was tested subsequently on three models:

| Model | Dims | Mag Mean | Hadamard Capacity | Sign-Flip Capacity | Approved |
|-------|------|----------|-------------------|-------------------|----------|
| GTE-large | 1024 | 19.08 | ~4 | **14** | Yes |
| BGE-large-en-v1.5 | 1024 | 17.29 | ~4 | **14** | Yes |
| Jina-v2-base-en | 768 | 26.43 | ~3 | **14** | Yes |
| mxbai-embed-large | 1024 | 17.38 | ~5 | (not tested)* | No* |

*mxbai passes algebraic tests but has a documented diacritic attention-sink pathology (Leonhart, *Latent space cartography applied to Wikidata*) — see §3.5. We treat it as a known-broken baseline and do not deploy operations against it.

The shift from Hadamard to sign-flip binding increases effective capacity by 3–5× across all tested substrates, from ~3–5 roles to 14 roles — the limit of our test set. All four models produce non-normalized vectors (magnitudes 17–26, not 1.0) when accessed via raw transformers without post-processing normalization layers. Non-normalized output matters for VSA-style operation: magnitude carries information about binding strength and bundling count, and Euclidean distance, not cosine similarity, becomes the natural metric.

### 3.4 Operation Cost Analysis

Benchmarked on GTE-large (1024-dim, CPU):

| Kind | Operation | Cost (μs) | Relative |
|------|-----------|-----------|----------|
| vector | Bind (sign-flip) | 6.6 | 1× |
| vector | Bundle (addition) | 1.7 | 0.3× |
| vector | Unbind (sign-flip) | 7.9 | 1.2× |
| vector | Similarity (dot) | 1.6 | 0.2× |
| vector | Euclidean distance | 4.6 | 0.7× |
| codebook | Snap (20 items) | 31.8 | 4.8× |
| codebook | Snap (1K items) | 3,540 | 536× |
| codebook | Snap (10K items) | 31,000 | 4,697× |
| — | Embed one text (LLM) | ~250,000 | ~38,000× |

The headline finding: **snap-to-nearest is not the bottleneck**. Even with a 10K-item codebook, snap (31ms) is 8× cheaper than embedding a single text (250ms). The dominant cost in any system that produces and then composes embeddings is the LLM forward pass that produces the vectors in the first place. Once vectors are in the space, the fixed-dimensional vector operations are microsecond-scale and codebook-scale snap is millisecond-scale — both negligible compared to the embedding step. Practically, this means VSA-style composition over frozen embeddings is essentially free relative to the cost of generating those embeddings.

### 3.5 Substrate Validation: The mxbai Pathology

During the cartographic analysis that grounds this paper, a previously unreported defect in mxbai-embed-large was characterized: diacritic characters cause catastrophic embedding collapse via attention sink (a high-magnitude key vector dominates the attention mechanism, overwriting all other token representations). Completely unrelated strings containing diacritics produce cosine similarity > 0.95.

This is a worked example of why substrate validation must include both algebraic tests and pathology probes. mxbai passes all algebraic validation gates above — the diacritic bug is an attention-mechanism pathology, not an algebraic one. A substrate can be algebraically sound and still have silent corruption modes. We treat mxbai as a known-broken baseline included only for comparison; the deployment-worthy substrates in this paper are GTE-large, BGE-large, and Jina-v2.

## 4. Discussion

The headline result is narrow and strong: sign-flip binding is a working binding operation on frozen LLM embedding spaces at 14-role capacity across three independent models, at a cost (6.6μs) that makes it usable as a primitive in any system that has the embeddings on hand. The textbook VSA binding (Hadamard product) does not work in this setting. This is a small empirical correction to an assumption the VSA literature inherited from working with hand-designed hypervector spaces.

The paper establishes a small, reproducible, substrate-portable operation set for VSA-style computation on frozen LLM embeddings, with the specific binding choice (sign-flip) that makes it work, validated on three real embedding models with operation costs measured. This is the empirical foundation for systems that compose computation over naturally-learned embedding spaces, including the Sutra programming language (Leonhart, *Sutra: A Control-Flow-Free Programming Language for Hyperdimensional Computing*), whose numpy backend compiles to exactly this operation set.

## 5. Conclusion

Six binding operations were tested on bundled role-filler structures over three frozen LLM embedding spaces. Hadamard product, the textbook VSA binding choice, fails (2/7 correct at 7 roles). Sign-flip binding, the cheapest of the working alternatives, achieves 14/14 correct snap recoveries on a 15-item codebook, sustains 10/10 chained computation steps, and supports multi-hop composition between bundled structures. The result is identical on GTE-large, BGE-large, and Jina-v2, and substrate-validation surfaces a documented attention-sink defect in mxbai-embed-large that algebraic gates alone do not catch. Snap-to-nearest, often suspected as the cost bottleneck for VSA-style systems, is shown to be 8× cheaper than producing a single embedding even on a 10K-item codebook. Together these results characterize a small, substrate-portable operation set for VSA-style composition on naturally-learned embedding spaces.

## References

Bordes, A., et al. (2013). Translating embeddings for modeling multi-relational data. NeurIPS.

Gayler, R. W. (2003). Vector symbolic architectures answer Jackendoff's challenges for cognitive neuroscience. ICCS.

Imani, M., et al. (2019). A framework for HD computing. ReConFig.

Joshi, A., et al. (2016). Language recognition using random indexing. arXiv.

Kanerva, P. (2009). Hyperdimensional computing: An introduction to computing in distributed representation. Cognitive Computation.

Kazemi, S. M., & Poole, D. (2018). Simple embedding for link prediction in knowledge graphs. NeurIPS.

Leonhart, E. Latent space cartography applied to Wikidata: Relational displacement analysis reveals a silent tokenizer defect in mxbai-embed-large.

Leonhart, E. Sutra: A Control-Flow-Free Programming Language for Hyperdimensional Computing.

Mikolov, T., et al. (2013). Efficient estimation of word representations in vector space. ICLR Workshop.

Neubert, P., et al. (2019). An introduction to hyperdimensional computing for robotics. KI.

Plate, T. A. (1995). Holographic reduced representations. IEEE Transactions on Neural Networks.

Smolensky, P. (1990). Tensor product variable binding and the representation of symbolic structures in connectionist systems. Artificial Intelligence.

Sun, Z., et al. (2019). RotatE: Knowledge graph embedding by relational rotation in complex space. ICLR.

Wang, Z., et al. (2014). Knowledge graph embedding by translating on hyperplanes. AAAI.

