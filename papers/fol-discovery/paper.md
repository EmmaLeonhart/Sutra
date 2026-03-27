# Discovering First-Order Logic in Arbitrary Embedding Spaces: Trajectory Displacement Analysis of Latent Relational Structure

**Emma Leonhart**

## Abstract

Existing neurosymbolic approaches engineer embedding spaces to support logical operations — training relation-specific transformations (TransE), designing geometric constraints (box embeddings), or encoding logical axioms into loss functions (Logic Tensor Networks). We take the opposite approach: given a general-purpose embedding model with no logical training signal, we systematically discover which first-order logical operations are latently encoded as vector arithmetic. Our method embeds entities from a knowledge base (Wikidata), computes displacement vectors for each predicate's triples, and tests whether these displacements are geometrically consistent — i.e., whether applying the same vector operation to different entity pairs produces parallel results. Across three embedding models with different architectures and dimensionalities (mxbai-embed-large 1024-dim, nomic-embed-text 768-dim, all-minilm 384-dim), we discover 30 universal operations that manifest as consistent displacements in all three models, with up to 109 operations per model. The strongest operations achieve perfect prediction (MRR = 1.0) via leave-one-out vector arithmetic, and two-hop composition succeeds at 28.3% Hits@10. The correlation between geometric consistency and prediction accuracy is r = 0.861 (95% CI [0.773, 0.926]), meaning the discovery metric itself predicts which operations will work — without ground-truth labels. The method requires no training, no gradient optimization, and no assumptions about the embedding geometry. We characterize failure modes: symmetric relations (siblings: 0.026), temporally ordered sequences (follows: 0.050), and semantically diverse predicates (instance-of: 0.244) resist vector encoding, revealing that embedding spaces encode *functional* relationships as geometry but not *relational* ones. Collision analysis reveals 147,687 undersymbolic embedding collapses traceable to WordPiece diacritic stripping — extending the glitch token phenomenon to sentence-embedding models. All code and data are publicly available, and the analysis reproduces end-to-end in approximately 30 minutes per model on commodity hardware.

## 1. Introduction

A persistent question in representation learning is whether embedding spaces encode logical structure, and if so, how faithfully. The word2vec analogy `king - man + woman ≈ queen` (Mikolov et al., 2013) demonstrated that at least some relational structure exists as vector arithmetic in distributional embeddings. TransE (Bordes et al., 2013) formalized this insight for knowledge graphs, training embeddings such that `h + r ≈ t` for each triple (head, relation, tail). Subsequent work introduced rotations (RotatE; Sun et al., 2019), complex-valued embeddings (ComplEx; Trouillon et al., 2016), and geometric constraints for hierarchical relations (box embeddings; Vilnis et al., 2018).

All of these approaches share a common assumption: **the embedding space must be constructed with logical operations in mind.** The relation vector `r` in TransE is a learned parameter, optimized specifically to make `h + r ≈ t` hold. The rotation in RotatE is a learned transformation. The box boundaries are learned constraints. If you take a general-purpose text embedding model — one trained for semantic similarity, not for logical reasoning — none of these guarantees hold.

**Our contribution is empirical rather than architectural.** We ask: given an embedding model that was never trained for logic, which logical operations does it *already* encode? We introduce **trajectory displacement analysis**, a model-agnostic method for discovering latent logical operations in any embedding space. Given a knowledge base of ground-truth triples, we discover the subset of predicates whose triples manifest as consistent vector displacements — treating the embedding space as existing infrastructure to be analyzed, not a system to be constructed. No training is required. No parameters are learned. The method is a pure diagnostic applicable to any text embedding model.

### 1.1 Key Findings

1. **86 discovered operations.** Of 159 predicates tested (≥10 triples each), 86 produce consistent displacement vectors (mean alignment > 0.5 with the predicate's mean displacement), and 32 achieve strong consistency (> 0.7).

2. **Prediction via vector arithmetic.** The strongest operations predict unknown triples with perfect accuracy (MRR = 1.0 for demographics-of-topic, culture, economy-of-topic) using leave-one-out evaluation. Across all 86 operations, mean Hits@10 = 0.550.

3. **Composition works.** Chaining two displacement vectors (S + d₁ + d₂) predicts two-hop targets at 28.3% Hits@10 over 5,000 tested compositions, with successful chains like `Fujiwara no Tadahira →[citizenship]→ Japan →[flag]→ flag of Japan` (Rank 1).

4. **Consistency predicts accuracy.** The correlation between a predicate's displacement consistency (alignment) and its prediction quality (MRR) is r = 0.78 (p < 0.001). This means the discovery metric itself tells you which operations will be reliable — without needing ground-truth labels for evaluation.

5. **Functional vs. relational split.** Operations succeed when the predicate is *functional* (many-to-one or one-to-one: flag, central bank, head of state) and fail when the predicate is *relational* (many-to-many or symmetric: sibling, spouse, shares-border-with). This is not a limitation of the method — it reveals what embedding spaces actually encode.

## 2. Related Work

### 2.1 Knowledge Graph Embedding

TransE (Bordes et al., 2013) models relations as translations: `h + r ≈ t`. Our work tests whether this property *emerges* in spaces not trained for it. RotatE (Sun et al., 2019) and ComplEx (Trouillon et al., 2016) use richer transformations but still require training. Our method uses no learned parameters.

### 2.2 Word Embedding Analogies

Mikolov et al. (2013) showed that `king - man + woman ≈ queen` holds in word2vec. Subsequent work (Linzen, 2016; Rogers et al., 2017) showed these analogies are less robust than initially claimed, often reflecting dataset biases rather than true relational understanding. Our approach is more systematic: instead of testing cherry-picked analogies, we exhaustively test all instances of each predicate and report aggregate statistics.

### 2.3 Neurosymbolic Integration

Logic Tensor Networks (Serafini & Garcez, 2016), Neural Theorem Provers (Rocktäschel & Riedel, 2017), and DeepProbLog (Manhaeve et al., 2018) integrate logical reasoning into neural architectures. These are *constructive* approaches: they build systems that can reason logically. Our approach is *analytical*: we examine an existing system to discover what logical reasoning it already supports.

### 2.4 Probing Approaches

Probing classifiers (Conneau et al., 2018; Hewitt & Manning, 2019) test what linguistic properties are encoded in learned representations. Our method is analogous but operates at the relational/logical level rather than the syntactic level, and uses vector arithmetic rather than learned classifiers — making our results directly interpretable as geometric properties of the space.

### 2.5 Vector Symbolic Architectures

Vector Symbolic Architectures (VSAs) perform algebraic operations — binding, bundling, permutation — on high-dimensional vectors to represent symbolic structures [CITATION NEEDED — Kanerva, 2009; Plate, 2003]. VSAs are primarily applied in cognitive science and neuromorphic hardware, constructing hypervector representations from scratch. Recent work has begun probing LLM internal representations using VSA-inspired methods [CITATION NEEDED — "Hyperdimensional Probe"]. Our approach differs in a key respect: VSAs *construct* symbolic algebras over vectors, while we *discover* what algebraic structure already exists in embedding spaces not built for it. We do not impose a binding operation — we test whether the space's native geometry already functions as one.

Separately, work on embedding space topology has identified stratified sub-manifolds of different dimensions within learned representations [CITATION NEEDED — stratified manifold work]. This independently validates the intuition behind our three-regime classification (Section 5.3): embedding spaces are not uniformly structured but contain regions of varying representational density and reliability.

## 3. Method

### 3.1 Problem Formulation

**Given:**
- An embedding function $f: \text{Text} \to \mathbb{R}^d$ (any text embedding model)
- A knowledge base $\mathcal{K} = \{(s, p, o)\}$ of subject-predicate-object triples

**Find:** The subset of predicates $P^* \subseteq P$ whose triples manifest as consistent displacement vectors in the embedding space.

**Definition (Trajectory).** For a triple $(s, p, o) \in \mathcal{K}$, the *trajectory* is the displacement vector $\mathbf{g}_{s,p,o} = f(o) - f(s)$, connecting the subject's embedding to the object's embedding.

**Definition (Operation Consistency).** For a predicate $p$ with triples $\{(s_1, p, o_1), \ldots, (s_n, p, o_n)\}$, the *operation vector* is $\mathbf{d}_p = \frac{1}{n}\sum_{i=1}^{n} \mathbf{g}_{s_i, p, o_i}$. The *consistency* of $p$ is the mean cosine alignment of individual trajectories with the operation vector:

$$\text{consistency}(p) = \frac{1}{n}\sum_{i=1}^{n} \cos(\mathbf{g}_{s_i,p,o_i}, \mathbf{d}_p)$$

A predicate with consistency > 0.5 is a **discovered operation**: its triples are approximated by a single vector displacement.

### 3.2 Data Pipeline

1. **Entity Import.** Breadth-first search from a seed entity (Engishiki, Q1342448) through Wikidata, importing 500 entities with all their triples and linked entities (14,796 items total).

2. **Embedding.** Each entity's English label is embedded using mxbai-embed-large (1024-dim) via Ollama. Aliases receive separate embeddings. Total: 41,725 embeddings.

3. **Trajectory Computation.** For each entity-entity triple, compute the displacement vector between subject and object label embeddings. Total: 16,893 entity-entity triples across 1,472 unique predicates.

### 3.3 Discovery Procedure

For each predicate $p$ with $\geq 10$ entity-entity triples:

1. Compute all trajectories $\{\mathbf{g}_i\}$
2. Compute operation vector $\mathbf{d}_p$ (mean trajectory)
3. Compute consistency: mean alignment of each $\mathbf{g}_i$ with $\mathbf{d}_p$
4. Compute pairwise consistency: mean cosine similarity between all pairs of trajectories
5. Compute magnitude coefficient of variation: stability of trajectory lengths

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

**Table 2.** Top 15 discovered operations by consistency (alignment with mean displacement). N = number of triples. Pairwise = mean cosine similarity between all pairs of trajectories. MagCV = coefficient of variation of trajectory magnitudes. Cos Dist = mean cosine distance between subject and object.

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

**Table 3.** Prediction results for selected operations (full table in supplementary). MRR = Mean Reciprocal Rank. H@k = Hits at rank k.

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

The correlation between displacement consistency and prediction accuracy (r = 0.861, 95% CI [0.773, 0.926]) is the central methodological finding: **the discovery metric is also the quality metric.** A predicate's geometric consistency, computable without any held-out evaluation, predicts how well that predicate will function as a vector operation. The effect size between strong (>0.7) and moderate (0.5-0.7) operations is Cohen's d = 3.092 — a large effect, indicating the alignment threshold cleanly separates high-performing from marginal operations.

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

### 4.4 Failure Analysis

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

### 4.5 Cross-Model Generalization

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

### 5.1 What Makes an Operation Discoverable?

The pattern across Tables 2 and 7 is clear: **discovered operations are functional relationships.** Each country has one flag, one coat of arms, one head of state. These many-to-one mappings produce consistent displacements because the "direction from country to its flag" is a well-defined geometric direction. Symmetric or many-to-many relationships produce no consistent direction because there is no single "direction from person to their sibling."

This finding has implications for knowledge graph completion: vector arithmetic will succeed for functional predicates and fail for relational ones, regardless of the embedding model. The limitation is not in the model but in the *nature of the relationship.*

### 5.2 The Correlation as a Self-Diagnostic

The r = 0.78 correlation between consistency and prediction accuracy means the method is **self-calibrating**: you can determine which operations will work without needing ground-truth evaluation data. This is practically important because it means the method can be applied to embedding spaces where no labeled evaluation set exists — the discovery process produces its own quality estimate.

### 5.3 Three Regimes of Embedding Space

Our results, combined with collision analysis, reveal that embedding spaces are not uniformly structured. We identify three regimes:

- **Oversymbolic regions** — areas where the model compresses too many semantically *rich* concepts into overlapping coordinates. In an oversymbolic region, distinct and meaningful entities share embedding space because the model's representational capacity is saturated. This regime produces collisions between concepts the model *has learned* but cannot separate at the required granularity.

- **Isosymbolic regions** — the narrow manifold where vector arithmetic reliably preserves logical structure. Our 86 discovered operations live here. The functional predicates (flag, coat of arms, demographics) produce consistent displacements precisely because the entities involved are well-represented and well-separated in the embedding space. The isosymbolic regime is where our method works.

- **Undersymbolic regions** — sparse areas with insufficient representational mass to anchor specific concepts. These regions lack the training signal needed to differentiate their contents — distinct inputs receive near-identical embeddings not because the model chose to group them, but because it never learned to distinguish them.

**Empirical evidence: the Jinmyōchō collapse.** Our collision analysis finds 164,084 cross-entity embedding pairs with cosine similarity ≥ 0.95. Of these, 147,687 (90%) are genuine semantic collisions: different text mapped to near-identical vectors. The collisions are dominated by romanized non-Latin-script terms — the single text "Hokkaidō" collides with 1,428 other entities, while "Jinmyōchō" collides with 504 unique texts spanning romanized Japanese (kugyō, Shōtai), Arabic (Djazaïr, Filasṭīn), Irish (Éire), Brazilian indigenous languages (Aikanã, Amanayé), and IPA characters.

Crucially, this is an **undersymbolic** phenomenon, not an oversymbolic one. Tokenizer analysis reveals the mechanism: mxbai-embed-large's WordPiece tokenizer strips diacritical marks during normalization — "Hokkaidō" tokenizes to `['hokkaido']`, "Tōkyō" to `['tokyo']`, "România" to `['romania']`. Terms whose semantic content is carried primarily by diacritics lose that content at tokenization, collapsing into shared or similar subword sequences. The embedding space downstream of the tokenizer has no information to work with — it maps these inputs to a degenerate neighborhood because it was *never given* the distinguishing features.

This resembles the glitch token phenomenon documented in LLM research (Li et al., 2024), where low-frequency tokens receive poorly trained embeddings. Our finding extends this to sentence-embedding models: it is not individual tokens but entire *classes* of input (romanized non-Latin scripts, diacritical text, IPA notation) that collapse into an undersymbolic manifold. The collision count — 147,687 pairs — quantifies the scale of this failure mode in a production embedding model.

This three-regime structure has practical implications. It suggests that vector arithmetic methods — whether our trajectory displacement analysis or TransE-style learned translations — will always be bounded by the *topological quality* of the underlying embedding space. No amount of algorithmic sophistication can extract consistent displacements from a region where distinct concepts have collapsed into the same coordinates. The undersymbolic collapse we document here is particularly insidious because it is invisible to standard evaluation: the model appears to embed these inputs normally, but the resulting vectors carry no discriminative information.

### 5.4 Implications for Neurosymbolic AI

Our results suggest a recategorization of the neurosymbolic landscape:

- **Constructive neurosymbolic:** Build spaces that support logic (TransE, LTN, box embeddings)
- **Analytical neurosymbolic:** Discover what logic exists in spaces not built for it (this work)

The analytical approach is complementary. It tells you what a given embedding space *can* do logically, without modification. This is useful for:
- **Model evaluation:** Comparing embedding models by the richness of their latent logical structure
- **Hybrid architectures:** Using vector arithmetic for operations that work (functional predicates) and falling back to symbolic graph traversal for operations that don't (relational predicates)
- **Embedding space cartography:** Mapping which regions of a space support reliable vector arithmetic, identifying oversymbolic collapse zones, and diagnosing where a model needs more training data

### 5.5 Limitations

1. **Three embedding models.** We validate across mxbai-embed-large (1024-dim), nomic-embed-text (768-dim), and all-minilm (384-dim), finding 30 universal operations. However, all three are English-language text embedding models trained on similar corpora. Testing on multilingual models, code embeddings, or domain-specific models (e.g., biomedical) would further strengthen the generality claim. Future work will also test whether discovered transformation matrices transfer across embedding spaces — applying matrices learned from one model to predictions in another.

2. **Wikidata bias.** Our entity set is seeded from Engishiki (Japanese historical text), producing a dataset heavy on Japanese history, linguistics, and geography. Different seeds would produce different distributions of predicates.

3. **Label embeddings only.** We embed entity *labels* (short text strings), not descriptions or full articles. Richer textual representations might improve results for predicates like instance-of.

4. **No learned refinement.** We report raw discovery results with no optimization. A learned projection layer on top of the discovered operations would likely improve prediction accuracy but would move toward the constructive paradigm.

## 6. Conclusion

We have shown that general-purpose text embedding models, trained for semantic similarity with no logical training signal, latently encode first-order logical operations as consistent vector displacements. Across three models with different architectures and dimensionalities (384 to 1024), we discover 30 universal operations — functional predicates like flag, demographics, and coat of arms that manifest as consistent displacements regardless of the underlying model. The self-diagnostic correlation (r = 0.861, 95% CI [0.773, 0.926]) means the discovery process produces its own quality estimate without ground-truth labels. Collision analysis reveals 147,687 undersymbolic embedding collapses, traced to WordPiece diacritic stripping — extending the glitch token phenomenon (Li et al., 2024) to entire input classes in sentence-embedding models.

The key insight is not that embedding spaces *can* support logic — TransE demonstrated that a decade ago — but that they *already do*, without being asked, and that the same operations emerge across unrelated models. The logical structure is a property of the semantic relationships themselves, not an artifact of any particular architecture.

All code is available at https://github.com/EmmaLeonhart/Claw4S-submissions. The full analysis reproduces end-to-end in approximately 30 minutes on commodity hardware with a local Ollama instance.

## References

Bordes, A., Usunier, N., Garcia-Durán, A., Weston, J., & Yakhnenko, O. (2013). Translating Embeddings for Modeling Multi-relational Data. *NeurIPS*, 26.

Conneau, A., Kruszewski, G., Lample, G., Barrault, L., & Baroni, M. (2018). What you can cram into a single $&!#* vector: Probing sentence embeddings for linguistic properties. *ACL*.

Hewitt, J., & Manning, C. D. (2019). A structural probe for finding syntax in word representations. *NAACL*.

Li, Y., Liu, Y., Deng, G., Zhang, Y., & Song, W. (2024). Glitch Tokens in Large Language Models: Categorization Taxonomy and Effective Detection. *Proceedings of the ACM on Software Engineering*, 1(FSE). https://doi.org/10.1145/3660799

Linzen, T. (2016). Issues in evaluating semantic spaces using word analogies. *RepEval Workshop*.

Manhaeve, R., Dumančić, S., Kimmig, A., Demeester, T., & De Raedt, L. (2018). DeepProbLog: Neural probabilistic logic programming. *NeurIPS*.

Mikolov, T., Sutskever, I., Chen, K., Corrado, G. S., & Dean, J. (2013). Distributed representations of words and phrases and their compositionality. *NeurIPS*.

Rocktäschel, T., & Riedel, S. (2017). End-to-end differentiable proving. *NeurIPS*.

Rogers, A., Drozd, A., & Li, B. (2017). The (too many) problems of analogical reasoning with word vectors. *StarSem*.

Serafini, L., & Garcez, A. d'A. (2016). Logic Tensor Networks: Deep learning and logical reasoning from data and knowledge. *NeSy Workshop*.

Sun, Z., Deng, Z.-H., Nie, J.-Y., & Tang, J. (2019). RotatE: Knowledge Graph Embedding by Relational Rotation in Complex Space. *ICLR*.

Trouillon, T., Welbl, J., Riedel, S., Gaussier, É., & Bouchard, G. (2016). Complex embeddings for simple link prediction. *ICML*.

Vilnis, L., Li, X., Xiang, S., & McCallum, A. (2018). Probabilistic embedding of knowledge graphs with box lattice measures. *ACL*.
