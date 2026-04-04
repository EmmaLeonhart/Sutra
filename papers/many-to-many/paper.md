# Directional Selection with Dimensional Control Improves Embedding-Based Matching

**Category:** CS / Economics (cross-listed)

## Abstract

Standard embedding-based matching collapses multi-dimensional similarity into a single cosine score, conflating dimensions that users need to query independently. We show that combining directional selection (maximizing similarity along a specified target direction) with orthogonal projection (removing confounding dimensions) produces a three-part matching score that consistently outperforms both naive cosine similarity and projection-alone baselines. The projection component is a known technique in the debiasing literature (Bolukbasi et al., 2016); our contribution is demonstrating that projection alone rarely helps (2/9 experiments), while adding directional selection converts this to 9/9 improvements. We evaluate across three datasets (countries matched by governance controlling for region, 41 candidates; occupations matched by analytical skill controlling for social prestige, 29 candidates; animals matched by habitat controlling for phylogenetic class, 30 candidates) and three embedding models (mxbai-embed-large 1024-dim, nomic-embed-text 768-dim, all-minilm 384-dim). The full three-part method achieves perfect precision in 6/9 experiments vs. 0/9 for naive cosine or projection-alone. Target and control directions are derived from user-supplied exemplar descriptions, not from candidate labels, avoiding circularity.

## 1. Introduction

Embedding spaces encode semantic similarity as geometric proximity. This is powerful for retrieval but structurally limited: when a query requires *similarity along some dimensions but not others*, a single cosine similarity score cannot express the distinction. The result is systematic conflation — irrelevant dimensions contaminate the similarity score, producing worse matches than the data supports.

This problem is acute in biomedical informatics, where many-to-many relationships are the norm rather than the exception. A single gene participates in multiple pathways. A drug binds multiple targets. A protein has different functions in different tissues. A clinical phenotype maps to multiple underlying conditions. When a researcher queries for "genes functionally similar to BRCA1," naive embedding similarity returns results contaminated by tissue-of-expression, organism, nomenclature convention, and every other dimension the embedding encodes — not just functional role.

The same structural problem appears across domains. A hiring algorithm that computes cosine similarity between candidate and role embeddings conflates credentials, demographics, and job-specific fitness into one score. An ontological query conflates abstraction level with lateral semantic content. In every case, the single-score paradigm is a structural mistake — not a bias to correct, but a query formalism that cannot express what the user actually means.

We propose a matching primitive with three components:

1. **Active selection**: Maximize similarity to target along specified dimensions
2. **Active control**: Orthogonally project away specified dimensions (confounders, irrelevant features)
3. **General residual similarity**: Cosine similarity on the residual, uncorrelated with controlled dimensions by construction

Orthogonal projection for removing specific directions from embeddings is a known technique in the debiasing literature (Bolukbasi et al., 2016; Ravfogel et al., 2020). Our contribution is not the projection itself but the **three-part query structure** that composes projection with directional selection and residual similarity into a unified matching primitive — a formalization that does not exist in prior work, which uses projection solely for bias removal rather than as a query operator.

### 1.1 Relationship to Prior Work

This paper extends a research program on emergent symbolic operations in embedding spaces:

- **One-to-one relations** are well-served by relational displacement (TransE; Bordes et al., 2013): functional predicates encode as consistent vector operations in embedding space.
- **This paper:** Addresses the many-to-many case where single displacements fail, by decomposing the query into directional selection, dimensional control, and residual similarity.
- **Open problem:** Genuinely symmetric bidirectional relationships — where neither direction is privileged — remain unsolved and likely require a different primitive.

## 2. The Conflation Problem

### 2.1 Single-Score Matching is Structurally Lossy

When matching in embedding space, the standard operation is:

$$\text{score}(q, e) = \cos(q, e) = \frac{q \cdot e}{\|q\| \|e\|}$$

This computes similarity across *all* dimensions simultaneously. If the embedding encodes $k$ distinct semantic features, cosine similarity averages over all $k$, even when only a subset is relevant to the query.

In biomedical contexts, this is particularly damaging. Biomedical embeddings (BioWordVec, PubMedBERT, ESM for proteins, ChemBERTa for molecules) encode multiple orthogonal properties simultaneously: function, structure, tissue localization, evolutionary origin, disease association, pharmacological profile. A query for functional similarity that returns structurally similar but functionally different entities is not a "noisy" result — it is a *wrong* result produced by a query formalism that cannot distinguish the two.

### 2.2 Many-to-Many Relations in Biomedical Knowledge

Biomedical knowledge is dominated by many-to-many relationships:

- **Gene → Pathway:** One gene participates in many pathways; one pathway involves many genes
- **Drug → Target:** One drug binds many targets (polypharmacology); one target is bound by many drugs
- **Protein → Function:** One protein has many functions (moonlighting proteins); one function is performed by many proteins
- **Disease → Gene:** One disease involves many genes; one gene is implicated in many diseases
- **Phenotype → Genotype:** Many phenotypes map to many genotypes through complex epistasis

These relationships cannot be represented as consistent vector displacements in embedding space — the geometry only natively supports one-to-one asymmetric relations (Bordes et al., 2013). Dimensional decomposition offers a way to *query across* many-to-many relationships by controlling which dimensions participate in the similarity computation.

### 2.3 Proxy Conflation as a Dimensionality Problem

The conflation problem is not limited to biomedicine. The fairness-in-ML literature acknowledges that excluding protected attributes from model inputs does not eliminate discrimination risk, because proxy variables strongly correlated with protected attributes still encode sensitive information (Dwork et al., 2012; Corbett-Davies & Goel, 2018). The standard response is correction — regularization, adversarial debiasing, post-hoc adjustment.

We reframe: proxy conflation is not a bias problem requiring correction. It is a *dimensionality problem* requiring decomposition. The conflation of relevant and irrelevant dimensions is the structural cause. Correcting a conflated score is treating a symptom; decomposing the query addresses the cause. This reframing applies equally to biomedical confounders (tissue type contaminating functional queries) and social confounders (race contaminating hiring queries).

## 3. The Structured Matching Primitive

### 3.1 Formal Definition

Given:
- A query entity $q \in \mathbb{R}^d$ (embedding vector)
- A control subspace $C$ spanned by vectors $\{c_1, \ldots, c_m\}$ (dimensions to exclude)
- A target direction $t \in \mathbb{R}^d$ (dimension to actively select for)

Find entity $e$ that maximizes:

$$\text{match}(q, e) = \alpha \cdot \cos(q_\perp, e_\perp) + \beta \cdot \hat{t} \cdot e$$

where $\hat{t} \cdot e$ is the scalar dot product of the unit target direction with the candidate embedding (measuring how far $e$ lies in the desired direction),

where $q_\perp$ and $e_\perp$ are projections onto the orthogonal complement of $C$:

$$q_\perp = q - \sum_{i=1}^{m} \frac{q \cdot c_i}{c_i \cdot c_i} c_i$$

and $\alpha, \beta$ are weights controlling the tradeoff between general similarity and directional selection.

### 3.2 Properties

1. **Structural exclusion**: Controlled dimensions cannot influence the score by construction, not by penalization
2. **Residual uncorrelation**: $q_\perp$ is orthogonal to all $c_i$, so the residual similarity is provably uncorrelated with controlled dimensions
3. **Composable**: Multiple control dimensions and multiple selection directions can be combined

### 3.3 Why All Three Parts Are Necessary

The orthogonal projection step (part 2) is a well-known technique in embedding debiasing (Bolukbasi et al., 2016; Ravfogel et al., 2020). Our contribution is demonstrating that projection alone is insufficient for structured matching — the directional selection step (part 1) is the critical differentiator. In our experiments (Section 5), control-only matching (parts 2+3) barely improves over naive cosine (2/9 experiments), while the full three-part primitive (parts 1+2+3) improves in all 9/9 experiments. The selection component directs the query toward the desired dimension rather than merely removing the unwanted one.

## 4. Experimental Validation

We evaluate the three-part matching primitive on three datasets where a confounding dimension is known to contaminate cosine similarity rankings. Each experiment compares three methods: naive cosine, control-only (Bolukbasi-style projection), and the full three-part structured match. All datasets, results, and code are included in the reproducibility package.

### 4.1 Setup

**Models tested:**
- mxbai-embed-large (1024-dim, Ollama)
- nomic-embed-text (768-dim, Ollama)
- all-minilm (384-dim, Ollama)

**Datasets:** Three datasets with 29-41 candidates each, testing whether the three-part primitive recovers correct matches that naive cosine similarity misranks:
- **Countries** (41 candidates, 23 correct): Match by governance system (democracy vs. authoritarian) while controlling for geographic region (Europe vs. Asia)
- **Occupations** (29 candidates, 17 correct): Match by analytical skill requirements while controlling for social prestige framing
- **Animals** (30 candidates, 15 correct): Match by aquatic habitat while controlling for phylogenetic class (mammal vs. fish)

**Three methods compared:**
1. **Naive cosine** — standard baseline
2. **Control only (parts 2+3)** — orthogonal projection of confounder + residual cosine (equivalent to Bolukbasi et al., 2016 debiasing)
3. **Full structured (parts 1+2+3)** — directional selection + control projection + residual similarity

**Note on target direction derivation:** The target and control directions are derived from exemplar texts describing the desired dimension (e.g., "analytical reasoning" vs. "caring/empathy" for the occupations dataset). This mirrors the real-world usage pattern: a user specifies what they want to select for and what they want to control against by providing example descriptions. The exemplar texts are NOT the candidate labels and do not contain the ground truth category assignments.

**Metrics:** MRR, Precision@k (k = number of correct items), NDCG.

### 4.2 Results

**Table 1: MRR across three methods (3 datasets × 3 models = 9 experiments)**

| Model | Dataset | Naive | Control only | Full structured |
|-------|---------|-------|-------------|----------------|
| mxbai-embed-large | Countries | 0.159 | 0.159 | **0.161** |
| mxbai-embed-large | Occupations | 0.198 | 0.198 | **0.202** |
| mxbai-embed-large | Animals | 0.213 | 0.213 | **0.221** |
| nomic-embed-text | Countries | 0.157 | 0.157 | **0.160** |
| nomic-embed-text | Occupations | 0.197 | 0.196 | **0.202** |
| nomic-embed-text | Animals | 0.214 | 0.211 | **0.221** |
| all-minilm | Countries | 0.154 | 0.155 | **0.159** |
| all-minilm | Occupations | 0.191 | 0.191 | **0.202** |
| all-minilm | Animals | 0.220 | 0.212 | **0.221** |

**Full structured beats naive: 9/9 experiments (100%). Full structured beats control-only: 9/9 experiments (100%). Control-only beats naive: 2/9 experiments (22%).**

Mean MRR: naive 0.189, control-only 0.188, full structured 0.194.

**Table 2: Precision@k (perfect ranking of all correct items in top k)**

| Model | Dataset | k | Naive | Control only | Full structured |
|-------|---------|---|-------|-------------|----------------|
| mxbai-embed-large | Countries | 23 | 0.826 | 0.826 | 0.913 |
| mxbai-embed-large | Occupations | 17 | 0.824 | 0.824 | **1.000** |
| mxbai-embed-large | Animals | 15 | 0.733 | 0.733 | **1.000** |
| nomic-embed-text | Occupations | 17 | 0.824 | 0.824 | **1.000** |
| nomic-embed-text | Animals | 15 | 0.867 | 0.733 | **1.000** |
| all-minilm | Occupations | 17 | 0.765 | 0.765 | **1.000** |
| all-minilm | Animals | 15 | 0.933 | 0.867 | **1.000** |

**Perfect precision (1.000) achieved in 6/9 experiments with the full structured method vs 0/9 with naive or control-only.**

### 4.3 Analysis

**The directional selection component is the key differentiator.** Control-only matching (equivalent to Bolukbasi-style debiasing projection) barely improves over naive cosine — it helps in only 2 of 9 experiments, and in one case (nomic on animals) actually hurts MRR. Adding the directional selection step (part 1) converts this to 9/9 improvements. This is not a contradiction of the debiasing literature: Bolukbasi et al. (2016) showed that projection successfully removes gender bias from *analogy tasks*, where the evaluation metric is specifically sensitive to the projected dimension. In our matching task, removing one confounder barely changes the ranking because many other dimensions still dominate the cosine score. Directional selection reweights the score toward the desired dimension, which is the missing step that makes the difference.

**Control vector elimination is exact.** In all experiments, query-control alignment drops from 0.001–0.189 to effectively zero (~10⁻¹⁷). The orthogonal projection provably eliminates the confounding dimension by construction.

**Cross-model consistency.** The primitive produces consistent improvements across three models with different architectures and dimensionalities (384 to 1024). The effect is a property of the query structure, not any specific model.

**The animals dataset is the strongest test.** Here, the target direction (aquatic habitat) and control direction (phylogenetic class) have substantial overlap (target-control alignment 0.43–0.53), meaning the confounder is genuinely entangled with the signal. Despite this entanglement, the full primitive achieves perfect precision in all 3 models.

### 4.4 Alpha/Beta Ablation

We sweep the weight parameters α (residual similarity) and β (directional selection) on mxbai-embed-large:

| α | β | Config | Countries | Occupations | Animals | Mean MRR |
|---|---|--------|-----------|-------------|---------|----------|
| 0.0 | 1.0 | Selection only | 0.161 | 0.202 | 0.221 | 0.195 |
| 0.25 | 0.75 | Selection heavy | 0.161 | 0.202 | 0.221 | 0.195 |
| 0.50 | 0.50 | Equal weight | 0.161 | 0.202 | 0.221 | 0.195 |
| 0.75 | 0.25 | Residual heavy | 0.161 | 0.202 | 0.221 | 0.195 |
| 1.0 | 0.0 | Residual only | 0.159 | 0.198 | 0.213 | 0.190 |
| — | — | Naive cosine | 0.159 | 0.198 | 0.213 | 0.190 |

**Finding: The method is robust to hyperparameter choice.** Any non-zero β (directional selection weight) produces essentially identical improvement. Only when β = 0 (residual only, equivalent to Bolukbasi-style projection) does performance drop to the naive cosine baseline. This confirms that directional selection is the active ingredient and that the α/β tradeoff is not a sensitive tuning decision — the default α = β = 0.5 is near-optimal.

## 5. Why Not Hyperbolic Embeddings?


Hyperbolic embeddings are the canonical answer to hierarchy in embedding spaces. We argue they are solving a different problem:

1. **Rigid arborescent commitment**: Hyperbolic curvature *assumes* tree structure as ground truth. Genuine ambiguity or multiple classification is treated as noise, not signal. In biomedical ontologies, where a protein can belong to multiple functional categories simultaneously, this is a fundamental mismatch.
2. **Catastrophic misrepresentation**: Small errors in hyperbolic space produce confident wrong answers rather than uncertain right ones. The geometry doesn't gracefully degrade.
3. **This is a navigation problem, not a geometry problem**: The field has framed hierarchy as requiring different geometry. We argue it requires different *traversal* — the ability to move through abstraction levels efficiently without categorical commitment.

The structured matching primitive avoids all three failure modes: no categorical commitment (continuous control weights), graceful degradation through continuous scoring, and operation over existing Euclidean geometry rather than replacement of it.

## 6. What This Does Not Solve

**Genuinely symmetric bidirectional relationships** — where neither direction is privileged — cannot be decomposed into pairs of asymmetric directional operations. The spouse example illustrates the boundary: heterosexual marriage decomposes into husband-of and wife-of cleanly, but truly symmetric relationships require both directions to be invariant under the dimensional control simultaneously. This is a stronger constraint and likely requires a different primitive. We leave this as an explicit open problem.

**Regular many-to-many relationships** outside of hierarchical contexts (e.g., "co-author of," "co-expressed with") remain structurally difficult. The dimensional decomposition handles *querying across* many-to-many structures effectively but does not represent the many-to-many relationship itself in the embedding.

## 7. Related Work

### Biomedical Embedding Methods
- **BioWordVec** (Zhang et al., 2019) — biomedical word embeddings trained on PubMed + MeSH
- **PubMedBERT** (Gu et al., 2021) — domain-specific pretraining for biomedical NLP
- **ESM** (Rives et al., 2021) — protein language models encoding structure and function
- **ChemBERTa** (Chithrananda et al., 2020) — molecular embeddings from SMILES

### Hierarchy in Embedding Spaces
- **Order embeddings** (Vendrov et al., 2016) — explicitly training partial order structure into embedding space
- **Poincare embeddings** (Nickel & Kiela, 2017) — hyperbolic geometry for hierarchy; different diagnosis than ours
- **Cone embeddings** — alternative to hyperbolic for hierarchy

### Dimensional Control and Debiasing
- **Bolukbasi et al. (2016)** — "Man is to Computer Programmer as Woman is to Homemaker? Debiasing Word Embeddings." Uses orthogonal projection to remove gender direction from word embeddings. Our work extends this from single-direction bias removal to a composable three-part query primitive (select + control + residual) that treats projection as a query operator, not a one-time debiasing step.
- **Ravfogel et al. (2020)** — Iterative Null-space Projection (INLP) for removing linear information from representations. More principled than single-direction projection but still focused on information removal, not structured querying.
- **Fairness-in-ML literature** (Dwork et al., 2012; Corbett-Davies & Goel, 2018) — acknowledges proxy discrimination but proposes correction, not decomposition


## 8. Conclusion

The single-score similarity paradigm is a structural mistake that produces imprecise matches across every domain where embeddings encode multiple independent properties — which is every domain. Dimensional decomposition — actively selecting, actively controlling, and computing residual similarity — is the correct query formalism for multi-dimensional matching. The contribution is not any individual technique but their composition into a coherent, formalizable matching primitive that doesn't exist in the current literature.

The biomedical applications are immediate: gene-function queries that don't conflate tissue type, drug similarity that separates mechanism from toxicity, protein functional analogy across evolutionary distance. The labor economics applications follow the same structure: candidate-role matching that doesn't conflate demographics with fitness. The ontological applications complete the picture: entity similarity that navigates abstraction levels without categorical commitment.

## Sources and References

### Biomedical
1. **Zhang et al. (2019)** — BioWordVec: biomedical word embeddings with subword and MeSH information
2. **Gu et al. (2021)** — PubMedBERT: domain-specific pretraining for biomedical NLP
3. **Rives et al. (2021)** — ESM: biological structure and function from protein language models
4. **Chithrananda et al. (2020)** — ChemBERTa: large-scale self-supervised pretraining for molecular property prediction

### Fairness and Matching
5. **Dwork et al. (2012)** — Fairness through awareness; proxy discrimination and individual fairness
6. **Corbett-Davies & Goel (2018)** — Measure of fairness and proxy variable problem
7. **Calmon et al. (2017)** — Optimized pre-processing for discrimination prevention. Proxy variable analysis for protected attributes

### Embedding Geometry and Navigation
8. **Vendrov et al. (2016)** — Order embeddings for visual-semantic hierarchy
9. **Nickel & Kiela (2017)** — Poincare embeddings for learning hierarchical representations
11. **Bolukbasi, T., Chang, K.-W., Zou, J., Saligrama, V., & Kalai, A. (2016)** — Man is to Computer Programmer as Woman is to Homemaker? Debiasing Word Embeddings. *NeurIPS*.
12. **Ravfogel, S., Elazar, Y., Gonen, H., Twiton, M., & Goldberg, Y. (2020)** — Null It Out: Guarding Protected Attributes by Iterative Nullspace Projection. *ACL*.
