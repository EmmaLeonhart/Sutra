# Relational Displacement in Three General-Purpose Text Embedding Models: Tokenizer-Induced Collisions and the Limits of Vector Arithmetic

**Emma Leonhart**

## Abstract

It is well established that embedding spaces encode relational structure as vector arithmetic — from word2vec analogies (Mikolov et al., 2013) through TransE translations (Bordes et al., 2013) to modern knowledge graph embeddings. What remains underexplored is where this encoding *breaks down* and what the failure modes reveal about the topology of embedding spaces. We apply standard relational displacement analysis to three general-purpose text embedding models (mxbai-embed-large 1024-dim, nomic-embed-text 768-dim, all-minilm 384-dim) using Wikidata triples from two domains: Engishiki (a Japanese historical text with dense romanized non-Latin terminology) and a broad sample of country-level entities via P31 (instance of). Across all three models, 30 relations manifest as consistent displacements universally, with up to 109 per model. The self-diagnostic correlation between geometric consistency and prediction accuracy (r = 0.861, 95% CI [0.773, 0.926]) reproduces across models and domains. The Engishiki-seeded dataset is retained deliberately: its dense romanized Japanese, Arabic, Irish, and indigenous-language terminology exposes a large-scale **embedding collision** — 147,687 cross-entity embedding pairs at cosine similarity ≥ 0.95, traceable to WordPiece diacritic stripping. We analyze the geometry of this collapse, showing that colliding embeddings occupy the **densest** regions of the embedding space — 71% fall in the dense-collision quartile — crowding into already-saturated neighborhoods rather than drifting into empty space. We observe that these collisions, functional displacements, and sparse regions partition the embedding space into empirically distinguishable zones with different properties for relational reasoning. A string overlap null model confirms that the discovered operations are not trivially explained by label text similarity: vector arithmetic achieves 49× higher MRR than the string baseline across all 39 tested predicates. All code and data are publicly available.

## 1. Introduction

That embedding spaces encode relational structure as vector arithmetic is well established. The word2vec analogy `king - man + woman ≈ queen` (Mikolov et al., 2013) demonstrated this for distributional word embeddings. TransE (Bordes et al., 2013) formalized the insight for knowledge graphs, training embeddings such that `h + r ≈ t` for each triple (head, relation, tail). Subsequent work introduced rotations (RotatE; Sun et al., 2019), complex-valued embeddings (ComplEx; Trouillon et al., 2016), geometric constraints for hierarchical relations (box embeddings; Vilnis et al., 2018), and extensive theoretical analysis of which relation types admit which geometric representations (e.g., Wang et al., 2014; Kazemi & Poole, 2018).

It is also well known that these methods work best on functional (many-to-one) and bijective (one-to-one) relations, and struggle with symmetric, transitive, or many-to-many relations. TransE explicitly cannot model symmetric relations (Bordes et al., 2013); RotatE was designed partly to address this gap. The characterization of which relation types encode as consistent displacements — non-transitive, bijective relations succeed; symmetric and semantically overloaded relations fail — is a consequence of the mathematics, not a new empirical finding.

**What we contribute is not the relational displacement itself, but its application as a diagnostic for embedding space topology.** We apply standard relational displacement analysis to general-purpose text embedding models — models trained for semantic similarity, not for knowledge graph completion — and use the *pattern of success and failure* to characterize the structure of the embedding space. Specifically:

1. We use a deliberately domain-specific seed (Engishiki, a Japanese historical text) alongside a broader country-level sample to expose how different regions of the same embedding space behave under identical relational tests.

2. We show that the Engishiki-seeded data, rich in romanized Japanese, Arabic, Irish, and indigenous-language terminology, reveals a large-scale **embedding collision** — 147,687 cross-entity embedding pairs at cosine ≥ 0.95, driven by WordPiece diacritic stripping.

3. We analyze the geometry of the collapse zone, showing that colliding embeddings are not merely close to each other but are **sparse and distant** from the well-structured regions where relational displacement succeeds — establishing hard topological limits on vector arithmetic methods.

### 1.1 Key Findings

1. **Relational displacement reproduces in untrained models.** Of 159 predicates tested (≥10 triples each), 86 produce consistent displacement vectors in mxbai-embed-large, with 30 universal across all three models tested. This confirms that general-purpose models inherit the same relational structure that trained KGE models exploit.

2. **The self-diagnostic correlation holds.** The correlation between geometric consistency and prediction accuracy (r = 0.861, 95% CI [0.773, 0.926]) means the displacement consistency metric predicts which relations will function as vector arithmetic — reproducing the known functional/relational split without ground-truth labels.

3. **Embedding collapse is large-scale and dense-collision.** 147,687 cross-entity pairs collapse to cosine ≥ 0.95. Geometric analysis shows colliding embeddings are 2.4× denser (mean k-NN distance 0.106 vs 0.258) and 71% fall in the dense-collision (densest) quartile. The collapse zone is not distant and sparse — it is crowded and central.

4. **Three-regime structure sets hard limits.** The embedding space partitions into dense-collision (saturated, where collisions concentrate), functional (vector arithmetic works), and sparse (sparse) regimes. No relational displacement method — learned or discovered — can extract consistent structure from the embedding collision zone. This is a property of the space, not the method.

5. **Engishiki highlights the dense-collision regime.** The domain-specific seed is not a limitation but a feature: it floods the embedding space with exactly the kind of input (romanized non-Latin scripts) that triggers dense-collision crowding, making the phenomenon measurable at scale.

## 2. Related Work

### 2.1 Knowledge Graph Embedding

TransE (Bordes et al., 2013) established that relations can be modeled as translations (`h + r ≈ t`) in learned embedding spaces. Subsequent work analyzed which relation types each model can represent: TransE handles antisymmetric and compositional relations but cannot model symmetric ones; RotatE (Sun et al., 2019) handles symmetry via rotation; ComplEx (Trouillon et al., 2016) handles symmetry and antisymmetry via complex-valued embeddings. Wang et al. (2014) and Kazemi & Poole (2018) provided systematic analyses of the relation type expressiveness of different KGE architectures. Our work does not introduce a new embedding method but applies the known displacement test to general-purpose (non-KGE) models as a diagnostic for embedding space topology.

### 2.2 Word Embedding Analogies

Mikolov et al. (2013) showed that `king - man + woman ≈ queen` holds in word2vec. Subsequent work (Linzen, 2016; Rogers et al., 2017; Schluter, 2018) showed these analogies are less robust than initially claimed, often reflecting frequency biases and dataset artifacts. Ethayarajh et al. (2019) formalized the conditions under which analogy recovery succeeds, showing it requires the relation to be approximately linear and low-rank in the embedding space. Our work is consistent with these findings: the relations we recover are exactly those that satisfy the linearity condition (functional, bijective), and those that fail are those the theory predicts will fail (symmetric, many-to-many).

### 2.3 Neurosymbolic Integration

Logic Tensor Networks (Serafini & Garcez, 2016), Neural Theorem Provers (Rocktäschel & Riedel, 2017), and DeepProbLog (Manhaeve et al., 2018) integrate logical reasoning into neural architectures. These constructive approaches build systems that reason logically. Our work is analytical rather than constructive, but we make no claim that the analytical approach is novel in itself — probing pre-trained representations for structure is standard practice.

### 2.4 Probing and Representation Analysis

Probing classifiers (Conneau et al., 2018; Hewitt & Manning, 2019) test what linguistic properties are encoded in learned representations. Our displacement consistency metric is analogous to a probe, but operates at the relational level and uses vector arithmetic rather than learned classifiers. The key methodological difference is that we use the *failure pattern* of the probe — which relations *don't* encode — as the primary finding, rather than the successes.

### 2.5 Embedding Space Topology and Failure Modes

The glitch token phenomenon (Li et al., 2024) documents poorly trained embeddings for low-frequency tokens in LLMs. Our collision finding extends this to sentence-embedding models, showing that entire *classes* of input (romanized non-Latin scripts, diacritical text) collapse into degenerate regions. Recent work on embedding space topology has identified stratified sub-manifolds within learned representations, independently supporting the multi-regime structure we observe.

### 2.6 Tokenizer-Induced Information Loss

WordPiece (Schuster & Nakajima, 2012) and BPE (Sennrich et al., 2016) tokenizers are known to struggle with out-of-vocabulary and non-Latin text. Rust et al. (2021) showed that tokenizer quality strongly predicts downstream multilingual model performance. Our collision analysis provides a geometric characterization of this failure: tokenizer-induced information loss creates measurable topological defects in the embedding space — sparse, distant regions where distinct inputs become indistinguishable.

## 3. Method

### 3.1 Problem Formulation

**Given:**
- An embedding function $f: \text{Text} \to \mathbb{R}^d$ (any text embedding model)
- A knowledge base $\mathcal{K} = \{(s, p, o)\}$ of subject-predicate-object triples

**Find:** The subset of predicates $P^* \subseteq P$ whose triples manifest as consistent displacement vectors in the embedding space.

**Definition (Relational Displacement).** For a triple $(s, p, o) \in \mathcal{K}$, the *relational displacement* is the vector $\mathbf{g}_{s,p,o} = f(o) - f(s)$, connecting the subject's embedding to the object's embedding. This is the standard TransE formulation applied without training.

**Definition (Displacement Consistency).** For a predicate $p$ with triples $\{(s_1, p, o_1), \ldots, (s_n, p, o_n)\}$, the *mean displacement* is $\mathbf{d}_p = \frac{1}{n}\sum_{i=1}^{n} \mathbf{g}_{s_i, p, o_i}$. The *consistency* of $p$ is the mean cosine alignment of individual displacements with the mean:

$$\text{consistency}(p) = \frac{1}{n}\sum_{i=1}^{n} \cos(\mathbf{g}_{s_i,p,o_i}, \mathbf{d}_p)$$

A predicate with consistency > 0.5 encodes as a **consistent relational displacement**: its triples are approximated by a single vector operation. This threshold is not novel — it corresponds to the standard criterion for meaningful directional agreement in high-dimensional spaces.

### 3.2 Data Pipeline

1. **Entity Import.** Two seed strategies: (a) Breadth-first search from Engishiki (Q1342448), seeding 500 entities then importing all their triples and linked entities. The BFS expansion produces **34,335 unique entities** (not 500), of which 1,781 contain diacritical marks. With aliases, the total embedding count reaches 41,725. (b) Broad P31 (instance of) sampling across country-level entities to provide a domain-general baseline. Both seeds contribute to the relational displacement analysis (Section 4.1); the collision analysis (Section 5.4) focuses on the Engishiki seed because its 1,781 diacritic-bearing labels trigger tokenizer collisions at scale.

2. **Embedding.** Each entity's English label is embedded using mxbai-embed-large (1024-dim) via Ollama. Aliases receive separate embeddings. Total: 41,725 embeddings from the Engishiki seed. Labels are short text strings (typically 1-5 words), consistent with how these models are used in practice for entity linking and retrieval.

3. **Relational Displacement Computation.** For each entity-entity triple, compute the displacement vector between subject and object label embeddings. Total: 16,893 entity-entity triples across 1,472 unique predicates. This is the standard `h + r ≈ t` test from TransE, applied without training.

### 3.3 Discovery Procedure

For each predicate $p$ with $\geq 10$ entity-entity triples:

1. Compute all relational displacements $\{\mathbf{g}_i\}$
2. Compute mean displacement $\mathbf{d}_p$
3. Compute consistency: mean alignment of each $\mathbf{g}_i$ with $\mathbf{d}_p$
4. Compute pairwise consistency: mean cosine similarity between all pairs of displacements
5. Compute magnitude coefficient of variation: stability of displacement magnitudes

**Note on unit-norm embeddings.** mxbai-embed-large returns L2-normalized embeddings (||v|| = 1.0000). Consequently, displacement magnitudes are a deterministic function of cosine similarity: ||f(o) - f(s)|| = sqrt(2(1 - cos(f(o), f(s)))). The MagCV metric therefore carries no information independent of cosine distance for this model. We retain it for cross-model comparability, as other models (e.g., BioBERT) do not necessarily normalize.

### 3.4 Prediction Evaluation

For each discovered operation ($\text{consistency} > 0.5$), we evaluate prediction accuracy using **leave-one-out**:

For each triple $(s, p, o)$:
1. Compute $\mathbf{d}_{p}^{(-i)}$ = mean displacement excluding this triple
2. Predict: $\hat{\mathbf{o}} = f(s) + \mathbf{d}_{p}^{(-i)}$
3. Rank all entities by cosine similarity to $\hat{\mathbf{o}}$
4. Record the rank of the true object $o$

We report Mean Reciprocal Rank (MRR) and Hits@k for k ∈ {1, 5, 10, 50}.

### 3.5 Composition Test

To test whether operations can be chained, we find all two-hop paths $s \xrightarrow{p_1} m \xrightarrow{p_2} o$ where both $p_1$ and $p_2$ are discovered operations. We predict:

$$\hat{\mathbf{o}} = f(s) + \mathbf{d}_{p_1} + \mathbf{d}_{p_2}$$

and evaluate whether the true $o$ appears in the top-k nearest neighbors. We test 5,000 compositions.

## 4. Results

### 4.1 Operation Discovery

Of 159 predicates with ≥10 triples, 86 (54.1%) produce consistent displacement vectors:

| Category | Count | Alignment Range |
|----------|-------|-----------------|
| Strong operations | 32 | > 0.7 |
| Moderate operations | 54 | 0.5 – 0.7 |
| Weak/no operation | 73 | < 0.5 |

**Table 1.** Distribution of discovered operations by consistency.

The top 15 discovered operations:

| Predicate | Label | N | Alignment | Pairwise | MagCV | Cos Dist |
|-----------|-------|---|-----------|----------|-------|----------|
| P8324 | funder | 25 | 0.930 | 0.859 | 0.079 | 0.447 |
| P2633 | geography of topic | 18 | 0.910 | 0.819 | 0.097 | 0.200 |
| P9241 | demographics of topic | 21 | 0.899 | 0.799 | 0.080 | 0.215 |
| P2596 | culture | 16 | 0.896 | 0.790 | 0.063 | 0.202 |
| P5125 | Wikimedia outline | 20 | 0.887 | 0.777 | 0.089 | 0.196 |
| P7867 | category for maps | 29 | 0.878 | 0.763 | 0.099 | 0.205 |
| P8744 | economy of topic | 30 | 0.870 | 0.749 | 0.094 | 0.182 |
| P1740 | cat. for films shot here | 18 | 0.862 | 0.728 | 0.121 | 0.266 |
| P1791 | cat. for people buried here | 13 | 0.857 | 0.714 | 0.121 | 0.302 |
| P1465 | cat. for people who died here | 29 | 0.857 | 0.725 | 0.124 | 0.249 |
| P163 | flag | 31 | 0.855 | 0.723 | 0.123 | 0.208 |
| P2746 | production statistics | 11 | 0.850 | 0.696 | 0.048 | 0.411 |
| P1923 | participating team | 32 | 0.831 | 0.681 | 0.042 | 0.387 |
| P1464 | cat. for people born here | 32 | 0.814 | 0.653 | 0.145 | 0.265 |
| P237 | coat of arms | 21 | 0.798 | 0.620 | 0.138 | 0.268 |

**Table 2.** Top 15 relations by displacement consistency (alignment with mean displacement). N = number of triples. Pairwise = mean cosine similarity between all pairs of displacements. MagCV = coefficient of variation of displacement magnitudes. Cos Dist = mean cosine distance between subject and object.

### 4.2 Prediction Accuracy

Leave-one-out evaluation of all 86 discovered operations:

| Predicate | Label | N | Align | MRR | H@1 | H@10 | H@50 |
|-----------|-------|---|-------|-----|-----|------|------|
| P9241 | demographics of topic | 21 | 0.899 | 1.000 | 1.000 | 1.000 | 1.000 |
| P2596 | culture | 16 | 0.896 | 1.000 | 1.000 | 1.000 | 1.000 |
| P7867 | category for maps | 29 | 0.878 | 1.000 | 1.000 | 1.000 | 1.000 |
| P8744 | economy of topic | 30 | 0.870 | 1.000 | 1.000 | 1.000 | 1.000 |
| P5125 | Wikimedia outline | 20 | 0.887 | 0.975 | 0.950 | 1.000 | 1.000 |
| P2633 | geography of topic | 18 | 0.910 | 0.972 | 0.944 | 1.000 | 1.000 |
| P1465 | cat. for people who died here | 29 | 0.857 | 0.966 | 0.966 | 0.966 | 0.966 |
| P163 | flag | 31 | 0.855 | 0.937 | 0.903 | 0.968 | 1.000 |
| P8324 | funder | 25 | 0.930 | 0.929 | 0.920 | 0.960 | 0.960 |
| P1464 | cat. for people born here | 32 | 0.814 | 0.922 | 0.906 | 0.938 | 0.938 |
| P237 | coat of arms | 21 | 0.798 | 0.858 | 0.762 | 0.952 | 1.000 |
| P21 | sex or gender | 91 | 0.674 | 0.422 | 0.121 | 0.945 | 0.989 |
| P27 | country of citizenship | 37 | 0.690 | 0.401 | 0.162 | 0.892 | 0.973 |

**Table 3.** Prediction results for selected operations (full table in supplementary). MRR = Mean Reciprocal Rank. H@k = Hits at rank k. The four predicates achieving MRR = 1.000 are functional predicates with highly consistent Wikidata naming conventions (e.g., every country has exactly one "Demographics of [Country]" article). Perfect MRR is expected when: (a) the predicate is strictly functional (one object per subject), (b) the displacement is consistent (alignment > 0.87), and (c) the object label is semantically close to a predictable transformation of the subject. Crucially, the string overlap null model (Section 4.4) confirms this is not a string manipulation artifact: these same predicates achieve string MRR of only 0.008–0.046 vs. vector MRR of 1.000. The embedding captures the semantic operation; the label convention merely makes the target unambiguous among 41,725 candidates.

**Aggregate statistics across all 86 operations:**

| Metric | Value | 95% Bootstrap CI |
|--------|-------|-----------------|
| Mean MRR | 0.350 | — |
| Mean Hits@1 | 0.252 | — |
| Mean Hits@10 | 0.550 | — |
| Mean Hits@50 | 0.699 | — |
| Correlation (alignment ↔ MRR) | r = 0.861 | [0.773, 0.926] |
| Correlation (alignment ↔ H@1) | r = 0.848 | [0.721, 0.932] |
| Correlation (alignment ↔ H@10) | r = 0.625 | [0.469, 0.760] |
| Effect size: strong vs moderate MRR (Cohen's d) | 3.092 | (large) |

**Table 4.** Aggregate prediction statistics with bootstrap confidence intervals (10,000 resamples). All correlations survive Bonferroni correction across 3 tests (adjusted alpha = 0.017).

The correlation between displacement consistency and prediction accuracy (r = 0.861, 95% CI [0.773, 0.926]) is the central methodological finding: **the discovery metric is also the quality metric.** A predicate's geometric consistency, computable without any held-out evaluation, predicts how well that predicate will function as a vector operation. Note that this correlation is not tautological despite the apparent circularity: consistency is computed over all triples, while MRR is computed via **leave-one-out** evaluation where each prediction uses a mean displacement that excludes the test triple. A predicate could have high alignment (all displacements point the same direction) but poor prediction (if the mean displacement points to a crowded region where many non-target entities cluster). The correlation is an empirical finding about the geometry of these embedding spaces, not a mathematical necessity. The effect size between strong (>0.7) and moderate (0.5-0.7) operations is Cohen's d = 3.092 — a large effect, indicating the alignment threshold cleanly separates high-performing from marginal operations.

### 4.3 Two-Hop Composition

Over 5,000 tested two-hop compositions (S + d₁ + d₂):

| Metric | Value |
|--------|-------|
| Hits@1 | 0.058 (288/5000) |
| Hits@10 | 0.283 (1414/5000) |
| Hits@50 | 0.479 (2396/5000) |
| Mean Rank | 1029.8 |

**Table 5.** Two-hop composition results.

Selected successful compositions (Rank ≤ 5):

| Chain | Rank |
|-------|------|
| Tadahira →[citizenship]→ Japan →[history of topic]→ history of Japan | 1 |
| Tadahira →[citizenship]→ Japan →[flag]→ flag of Japan | 1 |
| Tadahira →[citizenship]→ Japan →[cat. people buried here]→ Category:Burials in Japan | 2 |
| Tadahira →[citizenship]→ Japan →[cat. people who died here]→ Category:Deaths in Japan | 2 |
| Tadahira →[citizenship]→ Japan →[cat. associated people]→ Category:Japanese people | 3 |
| Tadahira →[citizenship]→ Japan →[head of state]→ Emperor of Japan | 4 |
| Tadahira →[sex or gender]→ male →[main category]→ Category:Male | 5 |

**Table 6.** Successful two-hop compositions. Note: all examples involve Fujiwara no Tadahira because our dataset is seeded from Engishiki (Q1342448), a Japanese historical text. Tadahira is one of the most densely connected entities in this neighborhood, appearing in many two-hop paths. The composition mechanism itself is general — the examples reflect dataset composition, not a limitation of the method.

### 4.4 String Overlap Null Model

A potential concern is that the discovered displacements merely capture string-level patterns — e.g., the displacement for "history of topic" (P2184) might simply encode the string prefix "History of" rather than relational knowledge. We test this with a string overlap null model: for each triple $(s, p, o)$, we rank all entities by longest common substring ratio with the subject label. If string overlap achieves comparable MRR to vector arithmetic, the displacement is trivially explained by surface patterns.

**Result: Vector arithmetic outperforms string overlap in 39/39 tested predicates (100%).** No predicate is trivially string-based.

| Metric | Vector Arithmetic | String Overlap (LCS) | Token Overlap |
|--------|------------------|---------------------|---------------|
| Mean MRR | 0.633 | 0.013 | 0.056 |
| Predicates with MRR > 0.5 | 24 | 0 | 0 |

The gap is not marginal: mean vector MRR is 49× higher than string MRR. Even the strongest string overlap scores (max 0.093 for P163 "flag") are far below the corresponding vector MRR (0.937). The 24 predicates with vector MRR > 0.5 all have string MRR < 0.1, confirming that the embedding captures relational structure that cannot be recovered from label text alone.

This null model directly addresses the concern that relations like "history of topic" or "demographics of topic" are trivial string prefix operations. They are not: the string "demographics of Japan" has negligible substring overlap with "Japan", yet the embedding displacement reliably maps from one to the other. We test three baselines — longest common substring ratio, token (word) overlap (Jaccard), and string containment — to cover both character-level and word-level matching. All three baselines fail: mean MRR of 0.013, 0.056, and below 0.01 respectively, compared to vector MRR of 0.633. The gap holds even for predicates whose naming conventions involve adding a prefix (e.g., "History of [X]"), because the null model must rank the correct object among all 34,335 entities, not just detect the prefix.

### 4.5 Failure Analysis

Predicates that resist vector encoding:

| Predicate | Label | N | Alignment | Pattern |
|-----------|-------|---|-----------|---------|
| P3373 | sibling | 661 | 0.026 | Symmetric |
| P155 | follows | 89 | 0.050 | Sequence (variable direction) |
| P156 | followed by | 86 | 0.053 | Sequence (variable direction) |
| P1889 | different from | 222 | 0.109 | Symmetric/diverse |
| P279 | subclass of | 168 | 0.118 | Hierarchical (variable depth) |
| P26 | spouse | 138 | 0.135 | Symmetric |
| P40 | child | 254 | 0.142 | Variable direction |
| P47 | shares border with | 197 | 0.162 | Symmetric |
| P530 | diplomatic relation | 930 | 0.165 | Symmetric |
| P31 | instance of | 835 | 0.244 | Too semantically diverse |

**Table 7.** Predicates with lowest consistency. Pattern = our characterization of why the displacement is inconsistent.

Three failure modes emerge:

1. **Symmetric predicates** (sibling, spouse, shares-border-with, diplomatic-relation): No consistent displacement direction because `f(A) - f(B)` and `f(B) - f(A)` are equally valid. Alignment ≈ 0.

2. **Sequence predicates** (follows, followed-by): The displacement from "Monday" to "Tuesday" has nothing in common with the displacement from "Chapter 1" to "Chapter 2." The *relationship type* is consistent but the *direction in embedding space* is domain-dependent.

3. **Semantically overloaded predicates** (instance-of, subclass-of, part-of): "Tokyo is an instance of city" and "7 is an instance of prime number" produce wildly different displacement vectors because the predicate covers too many semantic domains.

**Instance-of (P31) at 0.244 is particularly notable.** It is the most important predicate in Wikidata (835 triples in our dataset) and a cornerstone of first-order logic, yet it does not function as a vector operation. This suggests that embedding spaces systematically under-represent relational structure: the space encodes *entities* well but *predicates* poorly.

### 4.6 Cross-Model Generalization

To test whether discovered operations are model-agnostic or artifacts of a single model's training, we ran the full pipeline on two additional embedding models: nomic-embed-text (768-dim) and all-minilm (384-dim). All three models were given identical input: the same Wikidata entities seeded from Engishiki (Q1342448) with --limit 500.

| Model | Dimensions | Embeddings | Discovered | Strong (>0.7) |
|-------|-----------|-----------|------------|---------------|
| mxbai-embed-large | 1024 | 41,725 | 86 | 32 |
| nomic-embed-text | 768 | 69,111 | 101 | 54 |
| all-minilm | 384 | 54,375 | 109 | 41 |

**Table 8.** Operations discovered per model. All three models discover operations despite different architectures and dimensionalities.

**30 operations are universal** — discovered by all three models. These include demographics-of-topic (avg alignment 0.925), culture (0.923), economy-of-topic (0.896), flag (0.883), coat of arms (0.777), and central bank (0.793). The universal operations are exclusively functional predicates, confirming the functional-vs-relational split across architectures.

| Overlap Category | Count |
|-----------------|-------|
| Found by all 3 models | 30 |
| Found by 2 models | 15 |
| Found by 1 model only | 30 |

**Table 9.** Cross-model operation overlap. 30 universal operations constitute the model-agnostic core.

Cross-model consistency correlations (alignment scores on shared predicates): mxbai vs all-minilm r = 0.779, mxbai vs nomic r = 0.554, nomic vs all-minilm r = 0.358. The positive correlations confirm that consistency is not random — predicates that work well in one model tend to work well in others, though the strength varies by model pair.

This result is the core evidence for the model-agnostic claim: **the same logical operations emerge across three unrelated embedding models** with different architectures, different dimensionalities, and different training data. The operations are properties of the semantic relationships themselves, not artifacts of any particular model.

## 5. Discussion

### 5.1 Relation Types and Displacement: Confirming the Known Pattern

The pattern across Tables 2 and 7 confirms what the KGE literature predicts: **consistent displacements emerge for functional (many-to-one) and bijective (one-to-one) relations, and fail for symmetric, transitive, or many-to-many relations.** Each country has one flag, one coat of arms, one head of state — these produce consistent displacements. Symmetric relations (sibling, spouse, shares-border-with) produce no consistent direction because `f(A) - f(B)` and `f(B) - f(A)` are equally valid.

This is not a new finding. It follows directly from the mathematics of translational models (Bordes et al., 2013; Wang et al., 2014). What is notable is that the same pattern holds in general-purpose text embedding models with no relational training signal, confirming that the structure is a property of the semantic relationships themselves, not of the training objective.

### 5.2 The Self-Diagnostic Correlation

The r = 0.861 correlation between consistency and prediction accuracy means the displacement consistency metric is **self-calibrating**: it predicts which relations will function as vector arithmetic without needing ground-truth evaluation data. This is practically useful for applying relational displacement as a diagnostic to new embedding spaces.

### 5.3 Collision Geography: An Empirical Observation

We independently measure two properties of each embedding: (a) its local density (mean k-NN distance) and (b) whether it collides with a semantically distinct entity at cosine ≥ 0.95. We then ask an empirical question: are collisions uniformly distributed across density levels, or concentrated in particular regions? This is not a definitional relationship — dense regions could in principle have few collisions if the model separates semantically distinct entities effectively even in crowded neighborhoods. The following results describe what we observe in these three specific models, not a universal topological law.

### 5.4 The Embedding Collapse: Geometry of Oversymbolic Crowding

**Empirical evidence: the Jinmyōchō collapse.** Our collision analysis finds 147,687 cross-entity embedding pairs with cosine similarity ≥ 0.95 that represent genuine semantic collisions: different text mapped to near-identical vectors. This count reflects *pairwise* collisions: if $k$ entities cluster together, they contribute $\binom{k}{2}$ pairs. A single cluster of 50 entities produces 1,225 pairs. The 147,687 total arises from approximately 16,067 entities (of 41,725) participating in at least one collision, organized into clusters of varying size — not from uniform pairwise comparison of all 41,725 embeddings. The collisions are dominated by romanized non-Latin-script terms — the embedding vector for "Hokkaidō" has cosine similarity ≥ 0.95 with the vectors for 1,428 other entities. This does not mean all 1,428 entities normalize to the same string; rather, the WordPiece tokenizer maps diacritic-bearing text to similar subword sequences, producing embedding vectors that are geometrically near-identical despite representing distinct concepts. "Jinmyōchō" similarly collides with 504 unique texts spanning romanized Japanese (kugyō, Shōtai), Arabic (Djazaïr, Filasṭīn), Irish (Éire), Brazilian indigenous languages (Aikanã, Amanayé), and IPA characters — all of which tokenize to overlapping subword sequences after diacritic stripping.

**The mechanism is tokenizer-induced.** mxbai-embed-large's WordPiece tokenizer strips diacritical marks during normalization — "Hokkaidō" tokenizes to `['hokkaido']`, "Tōkyō" to `['tokyo']`, "România" to `['romania']`. Terms whose semantic content is carried primarily by diacritics lose that content at tokenization, collapsing into shared or similar subword sequences. This is consistent with Rust et al. (2021)'s finding that tokenizer quality predicts multilingual performance, but here we characterize the *geometric* consequence rather than the downstream task impact.

**The collapse zone is dense, not sparse.** Geometric analysis of 16,067 colliding embeddings (vs. 74,760 non-colliding) reveals a finding opposite to what naive intuition might suggest. Colliding embeddings do not occupy empty space far from the well-structured manifold — they crowd into the **densest regions** of the embedding space:

1. **Colliding embeddings are 2.4× denser than non-colliding ones.** Mean k-NN distance for colliding embeddings is 0.106, vs 0.258 for non-colliding (ratio 0.41×). Colliding entities are tightly packed together.

2. **71% of colliding embeddings fall in the dense-collision (densest quartile) regime,** vs the expected 25% if uniformly distributed. Only 3.2% fall in the sparse (sparsest quartile) regime. The collision zone is overwhelmingly dense-collision.

3. **The collapse zone is not geometrically isolated.** The distance from a colliding embedding to its nearest non-colliding neighbor (mean 0.119) is nearly identical to the equivalent non-colliding-to-non-colliding distance (mean 0.121, ratio 0.98×). The centroids of the two populations are close (cosine distance 0.038).

This means tokenizer-induced information loss does not push embeddings into distant, empty regions — it collapses them into **already-crowded neighborhoods** where distinct inputs cannot be differentiated. The colliding embeddings sit *among* the well-structured embeddings, not apart from them. This is an **dense-collision** phenomenon: the model's representational capacity in these regions is saturated, and the tokenizer's diacritic stripping removes the only information that could distinguish these inputs.

This extends the glitch token phenomenon (Li et al., 2024) from individual tokens in LLMs to entire *classes of input* in sentence-embedding models, but with a geometric twist: the failure mode is not sparse under-representation but dense over-crowding. The scale — 147,687 colliding pairs from a single domain seed — suggests that any application of embedding-based reasoning to multilingual or diacritic-rich text will encounter regions where the space is too crowded to discriminate.

**Why the Engishiki seed matters.** The domain-specific seed is not a limitation but a deliberate experimental choice. Engishiki (Q1342448) is a 10th-century Japanese text whose entities include romanized shrine names (Jinmyōchō, Shikinaisha), historical Japanese personal names, and linked entities from Arabic, Irish, and indigenous-language Wikipedia articles. This floods the embedding space with exactly the inputs that trigger embedding collision, making the phenomenon measurable at scale. The country-level P31 sample provides the domain-general baseline against which the collapse is measured.

### 5.5 Hard Limits on Vector Arithmetic

The three-regime structure implies that relational displacement methods — whether learned (TransE, RotatE) or discovered (this work) — are bounded by the *topological quality* of the underlying embedding space. No amount of algorithmic sophistication can extract consistent displacements from a region where distinct concepts have collapsed into the same coordinates. The embedding collision is particularly insidious because it is invisible to standard evaluation: the model appears to embed these inputs normally, and the resulting vectors sit in well-populated regions of the space, but they carry no discriminative information for the colliding inputs.

This has practical implications for any system that chains embedding-based reasoning with knowledge from non-Latin-script domains: RAG systems retrieving over multilingual corpora, knowledge graph completion over Wikidata's non-English entities, and cross-lingual transfer learning.

### 5.6 Limitations

1. **Three embedding models.** We validate across mxbai-embed-large (1024-dim), nomic-embed-text (768-dim), and all-minilm (384-dim), finding 30 universal relations. All three are English-language text embedding models trained on similar corpora. Testing on multilingual models or domain-specific models (e.g., biomedical) would further characterize the generality of the three-regime structure.

2. **Collision geometry analysis covers one seed.** The distance metrics characterizing the embedding collision zone (Section 5.4) are computed from the Engishiki-seeded dataset. Multi-seed analysis would test whether the same crowding pattern holds across domains.

3. **Label embeddings only.** We embed entity *labels* (short text strings), not descriptions or full articles. This deliberately mirrors how these models are used in practice for entity linking and knowledge graph completion (short query strings, not full documents). Richer textual representations might shift some entities out of the sparse zone, but the label-only setting represents a common real-world deployment pattern for these models.

4. **Potential training data overlap.** The embedding models tested were trained on large web crawls that likely include Wikipedia content, and Wikidata entities often have corresponding Wikipedia articles. This raises the possibility that some discovered displacements reflect memorized associations from training data rather than emergent geometric structure. The cross-model consistency (30 universal operations across three independently trained models) provides partial mitigation: memorization patterns would be model-specific, while consistent operations across architectures suggest structural encoding. However, a definitive test would require embedding models trained on corpora that exclude Wikipedia, which we leave for future work.

5. **Single tokenizer family.** All three models use WordPiece or similar subword tokenizers. The collision analysis reflects this specific tokenization strategy. Models using byte-level tokenizers (e.g., CANINE, ByT5) or SentencePiece with different normalization would likely show different collision patterns. Testing against such models would clarify whether the observed collisions are a general embedding phenomenon or specific to the WordPiece diacritic-stripping behavior.

4. **Relational displacement, not full FOL.** We test which binary relations encode as consistent vector arithmetic. Full first-order logic includes quantifiers, variable binding, negation, and complex formula composition, none of which we test. The title of this paper reflects the scope: relational displacement and its failure modes, not a claim about discovering FOL.

## 6. Conclusion

We apply standard relational displacement analysis to three general-purpose text embedding models and confirm the known finding: functional and bijective relations encode as consistent vector displacements, while symmetric and many-to-many relations do not. This holds across models not trained for knowledge graph completion, confirming that the relational structure is a property of the semantic relationships, not the training objective.

The primary contribution is the **embedding collision** finding. A deliberately domain-specific seed (Engishiki) exposes 147,687 cross-entity embedding collapses at cosine ≥ 0.95, traceable to WordPiece diacritic stripping. Geometric analysis reveals that these collapses occupy the **densest** regions of the embedding space — 71% fall in the dense-collision quartile, with 2.4× smaller k-NN distances than non-colliding embeddings. The failure mode is not sparse under-representation but dense over-crowding: tokenizer-induced information loss pushes diacritic-rich inputs into already-saturated neighborhoods where distinct concepts become indistinguishable.

The practical implication is that embedding-based reasoning over multilingual or diacritic-rich text — RAG systems, knowledge graph completion, cross-lingual transfer — will encounter regions where the embedding space provides no discriminative information, and no amount of relational modeling can compensate for what the tokenizer has already destroyed.

All code and data are publicly available. The core FOL discovery analysis (displacement computation and prediction evaluation on pre-computed embeddings) runs in under 30 minutes on commodity hardware. The full pipeline including entity import from Wikidata and embedding computation requires several hours depending on network and GPU speed. The collision analysis adds approximately 10 minutes.

## References

Bordes, A., Usunier, N., Garcia-Durán, A., Weston, J., & Yakhnenko, O. (2013). Translating Embeddings for Modeling Multi-relational Data. *NeurIPS*, 26.

Conneau, A., Kruszewski, G., Lample, G., Barrault, L., & Baroni, M. (2018). What you can cram into a single $&!#* vector: Probing sentence embeddings for linguistic properties. *ACL*.

Ethayarajh, K., Duvenaud, D., & Hirst, G. (2019). Towards understanding linear word analogies. *ACL*.

Hewitt, J., & Manning, C. D. (2019). A structural probe for finding syntax in word representations. *NAACL*.

Kazemi, S. M., & Poole, D. (2018). SimplE embedding for link prediction in knowledge graphs with baseline model comparison. *NeurIPS*.


Li, Y., Liu, Y., Deng, G., Zhang, Y., & Song, W. (2024). Glitch Tokens in Large Language Models: Categorization Taxonomy and Effective Detection. *Proceedings of the ACM on Software Engineering*, 1(FSE). https://doi.org/10.1145/3660799

Linzen, T. (2016). Issues in evaluating semantic spaces using word analogies. *RepEval Workshop*.

Manhaeve, R., Dumančić, S., Kimmig, A., Demeester, T., & De Raedt, L. (2018). DeepProbLog: Neural probabilistic logic programming. *NeurIPS*.

Mikolov, T., Sutskever, I., Chen, K., Corrado, G. S., & Dean, J. (2013). Distributed representations of words and phrases and their compositionality. *NeurIPS*.

Rocktäschel, T., & Riedel, S. (2017). End-to-end differentiable proving. *NeurIPS*.

Rogers, A., Drozd, A., & Li, B. (2017). The (too many) problems of analogical reasoning with word vectors. *StarSem*.

Rust, P., Pfeiffer, J., Vulić, I., Ruder, S., & Gurevych, I. (2021). How good is your tokenizer? On the monolingual performance of multilingual language models. *ACL*.

Schluter, N. (2018). The word analogy testing caveat. *NAACL*.

Schuster, M., & Nakajima, K. (2012). Japanese and Korean voice search. *ICASSP*.

Sennrich, R., Haddow, B., & Birch, A. (2016). Neural machine translation of rare words with subword units. *ACL*.

Serafini, L., & Garcez, A. d'A. (2016). Logic Tensor Networks: Deep learning and logical reasoning from data and knowledge. *NeSy Workshop*.

Sun, Z., Deng, Z.-H., Nie, J.-Y., & Tang, J. (2019). RotatE: Knowledge Graph Embedding by Relational Rotation in Complex Space. *ICLR*.

Trouillon, T., Welbl, J., Riedel, S., Gaussier, É., & Bouchard, G. (2016). Complex embeddings for simple link prediction. *ICML*.

Vilnis, L., Li, X., Xiang, S., & McCallum, A. (2018). Probabilistic embedding of knowledge graphs with box lattice measures. *ACL*.

Wang, Z., Zhang, J., Feng, J., & Chen, Z. (2014). Knowledge graph embedding by translating on hyperplanes. *AAAI*.
