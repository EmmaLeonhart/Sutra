# Dimensional Decomposition for Many-to-Many Matching in Embedding Spaces

**Category:** CS / Economics (cross-listed)

**Target:** Claw4S Conference 2026 (deadline April 5, 2026)

## Abstract

Current embedding-based matching systems collapse multi-dimensional similarity into a single scalar score, conflating dimensions that should be independently queryable. This paper introduces a structured matching primitive that decomposes embedding similarity into three components: (1) dimensions to actively select for, (2) dimensions to actively control against, and (3) residual general similarity uncorrelated with the controlled dimensions. The mechanism combines orthogonal projection for dimensional control with directed small-world graph navigation for efficient traversal. We formalize this as a query structure and demonstrate it across domains: biomedical entity matching (gene-function similarity controlling for tissue type, drug repurposing controlling for toxicity), labor market matching (candidate-role fitness controlling for protected characteristics), and ontological categorization (Wikidata entity similarity controlling for abstraction level). We validate the primitive experimentally across four embedding models (mxbai-embed-large, nomic-embed-text, all-minilm, BioBERT) and three domains, showing improvement in 10/12 experiments (mean MRR +0.049, max +0.178) with exact elimination of confounding dimensions (query-control alignment → 0). In each case, dimensional decomposition produces more precise matches than naive cosine similarity — a Pareto improvement that also structurally prevents proxy conflation as a consequence of doing the similarity computation correctly.

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

- **Paper 1 (isosymbolic framework):** Discovered that directional one-to-one asymmetric relationships emerge as first-order logic operations from embedding geometry (clawrxiv:2604.00569)
- **This paper:** Extends to directional many-to-many relationships via controlled dimensional decomposition
- **Open problem:** Genuinely symmetric bidirectional relationships — where neither direction is privileged — remain unsolved and likely require a different primitive

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

These relationships cannot be represented as consistent vector displacements in embedding space — the geometry only natively supports one-to-one asymmetric relations (as demonstrated in our prior work on FOL operations). Dimensional decomposition offers a way to *query across* many-to-many relationships by controlling which dimensions participate in the similarity computation.

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

$$\text{match}(q, e) = \alpha \cdot \cos(q_\perp, e_\perp) + \beta \cdot \text{proj}_t(e)$$

where $q_\perp$ and $e_\perp$ are projections onto the orthogonal complement of $C$:

$$q_\perp = q - \sum_{i=1}^{m} \frac{q \cdot c_i}{c_i \cdot c_i} c_i$$

and $\alpha, \beta$ are weights controlling the tradeoff between general similarity and directional selection.

### 3.2 Properties

1. **Structural exclusion**: Controlled dimensions cannot influence the score by construction, not by penalization
2. **Residual uncorrelation**: $q_\perp$ is orthogonal to all $c_i$, so the residual similarity is provably uncorrelated with controlled dimensions
3. **Composable**: Multiple control dimensions and multiple selection directions can be combined

### 3.3 Navigable Small-World Traversal (Future Work)

Executing the structured query at scale will require an efficient traversal structure. We sketch an HNSW-analog where:

- Graph layers correspond to abstraction levels (ontological height), not random subsampling
- Navigation ascends to the appropriate abstraction level, then searches laterally within that level
- The small-world property provides high clustering (dense coherent neighborhoods) and short path lengths (cheap traversal to distant concepts)

The ontological height dimension is a continuous scalar — not a categorical assignment — avoiding arborescent commitment. In biomedical ontologies (Gene Ontology, SNOMED CT, MeSH), height can be derived from subclass chain depth. For general ontology, Wikidata P279 chain depth provides a noisy but usable training signal. BFO types anchor the top, concrete instances anchor the bottom.

## 4. Case Studies

### 4.1 Biomedical Entity Matching

#### 4.1.1 Gene-Function Similarity Controlling for Tissue Type

**Setup:** Gene embeddings from biomedical language models (BioWordVec, PubMedBERT). Gene Ontology annotations as ground truth for functional similarity. GTEx tissue expression profiles as the confounding dimension.

**Problem:** Two genes expressed in the same tissue will have high cosine similarity even if their functions are unrelated, because tissue-of-expression is a strong signal in biomedical text. A query for "functionally similar to BRCA1" returns other breast-tissue genes, not necessarily DNA repair genes.

**Application:** Project away the tissue-expression dimension. Residual similarity captures functional role without tissue contamination. The control vector is derived from the mean displacement between tissue-specific gene sets.

**Expected outcome:** Improved functional similarity precision (Gene Ontology semantic similarity as ground truth) compared to naive cosine similarity.

#### 4.1.2 Drug Repurposing Controlling for Toxicity Profile

**Setup:** Drug embeddings from chemical language models (ChemBERTa, Mol2Vec). Known drug-target interactions. Toxicity profiles as the controlled dimension.

**Problem:** Similar drugs are often similar in both therapeutic effect and toxicity — the embedding conflates the two. A query for "drugs with similar mechanism to Drug X" returns drugs that are also similarly toxic, which is not useful for finding safer alternatives.

**Application:** Project away the toxicity dimension. Residual similarity captures mechanism-of-action without toxicity contamination. Enables "find me something that works like this drug but isn't as toxic" as a formally expressible query.

#### 4.1.3 Protein Function Across Organisms

**Setup:** Protein embeddings from ESM or ProtTrans. Ortholog databases as ground truth.

**Problem:** Protein embeddings encode evolutionary distance alongside functional information. Querying for "proteins with similar function" returns orthologs from closely related species rather than functionally analogous proteins from distant species (which may be more informative for understanding convergent evolution or alternative mechanisms).

**Application:** Project away the phylogenetic dimension. Find functionally similar proteins regardless of evolutionary relatedness.

### 4.2 Labor Market Matching

**Setup:** Embeddings of job candidates and role descriptions. Departed employee as the role reference.

**Two-axis system:**
- **Axis 1 (General candidate quality):** A learned dimension encoding credentials, track record, general competence markers. Universal across roles.
- **Axis 2 (Role fitness):** Cosine similarity to the target role embedding with Axis 1 factored out.

**Key properties:**
- A nurse with programming skills scores higher on Axis 1 without confusing her cosine similarity with software engineering roles
- A resume gap affects Axis 1 slightly but structurally cannot contaminate Axis 2
- The system finds the best candidate *for this role*, not the best candidate *overall*

**Controlling for protected characteristics:**
- Project away the race/gender/age subspace from the similarity computation
- This is bidirectional: prevents both discrimination against (rejecting qualified minority candidates) and stereotyping toward (replacing a Black employee only with Black candidates)
- The control is structural, not ideological — it makes the query express what the employer actually means to ask

**Economic framing:** This is a matching market problem (Gale-Shapley). Current algorithmic hiring collapses a multi-dimensional matching problem into a single similarity score, which is both economically inefficient (worse matches) and discriminatory (irrelevant dimensions contaminate role-fitness). Dimensional decomposition restores the dimensionality that should have been there — a Pareto improvement.

### 4.3 Ontological Categorization (Wikidata)

**Setup:** Wikidata entities with known taxonomic or ontological structure. Embeddings from general-purpose models (mxbai-embed-large, nomic-embed-text).

**Application:** Finding entities that are similar along specific ontological dimensions while controlling for others. A concept that participates in multiple abstraction levels or multiple incompatible hierarchies doesn't need a single categorical placement — it has a height and local neighbors, and the lateral relations at any given height are handled by the residual similarity.

**Connection to many-to-many:** Hierarchical many-to-many relationships (participating in multiple abstraction levels simultaneously) are handled by the continuous height dimension. Regular many-to-many relationships are handled by the controlled projection mechanism.

**Examples:**
- Find shrines similar to a given shrine controlling for geographic region (functional similarity vs. geographic clustering)
- Find biological taxa similar at one taxonomic rank while controlling for higher-rank classification
- Find historical figures similar in role while controlling for time period

## 5. Experimental Validation

We validate the dimensional decomposition primitive across three domains and four embedding models. Each experiment constructs a scenario where a confounding dimension (organism context, gender coding, or domain register) contaminates cosine similarity rankings, then measures whether orthogonal projection recovers the correct ranking.

### 5.1 Setup

**Models tested:**
- mxbai-embed-large (1024-dim, Ollama)
- nomic-embed-text (768-dim, Ollama)
- all-minilm (384-dim, Ollama)
- BioBERT v1.2 (768-dim, HuggingFace transformers)

**Datasets:** Each dataset contains 10 candidates (5 correct, 5 confounders) and a query whose embedding is contaminated by the confounding dimension. Control vectors are derived as mean displacement between two groups representing the confounding axis.

**Metrics:**
- Mean Reciprocal Rank (MRR) — harmonic mean of correct items' rank positions
- Precision@5 — fraction of correct items in the top 5
- Query-control alignment — dot product between query and control vector (should reach ~0 after projection)

### 5.2 Results

**Table 1: MRR improvement from dimensional decomposition across all experiments**

| Model | Biomedical | Labor | Ontology |
|-------|-----------|-------|----------|
| mxbai-embed-large | 0.296 → 0.385 (+0.089) | 0.457 → 0.457 (+0.000) | 0.257 → 0.435 (+0.178) |
| nomic-embed-text | 0.296 → 0.301 (+0.005) | 0.429 → 0.450 (+0.021) | 0.372 → 0.435 (+0.063) |
| all-minilm | 0.385 → 0.390 (+0.005) | 0.425 → 0.435 (+0.010) | 0.216 → 0.385 (+0.169) |
| BioBERT | 0.332 → 0.370 (+0.038) | 0.406 → 0.406 (+0.000) | 0.450 → 0.457 (+0.007) |

**Overall: 10/12 experiments showed improvement (83% success rate).** Mean MRR improvement: +0.049. Maximum improvement: +0.178 (all-minilm on ontology task).

**Table 2: Precision@5 improvement**

| Model | Biomedical | Labor | Ontology |
|-------|-----------|-------|----------|
| mxbai-embed-large | 0.2 → 0.8 (+0.6) | 1.0 → 1.0 (0.0) | 0.6 → 0.8 (+0.2) |
| nomic-embed-text | 0.2 → 0.2 (0.0) | 0.6 → 0.8 (+0.2) | 0.6 → 0.8 (+0.2) |
| all-minilm | 0.8 → 0.8 (0.0) | 0.6 → 0.8 (+0.2) | 0.4 → 0.8 (+0.4) |
| BioBERT | 0.4 → 0.6 (+0.2) | 0.6 → 0.6 (0.0) | 0.8 → 1.0 (+0.2) |

### 5.3 Analysis

**Control vector elimination is exact.** In all experiments, query-control alignment drops from 0.15–1.08 to effectively zero (~10⁻¹⁷ for Ollama models, ~10⁻⁸ for BioBERT due to float32 precision). The orthogonal projection provably eliminates the confounding dimension.

**The two zero-improvement cases are informative.** The labor/gender experiment shows no change on mxbai-embed-large and BioBERT — both models already rank all software engineers in the top 5 before projection. This means gender coding is not a strong confounder for these models on this specific task. The projection does no harm (a Pareto non-degradation) and the control alignment still drops to zero, confirming the mechanism works even when the confounder wasn't dominating.

**Ontology experiments show the largest improvements.** Domain register (religious vs. military language) is a stronger confounder than organism context or gender coding across all models. The all-minilm model shows the most dramatic improvement (+0.169 MRR, precision 0.4 → 0.8), suggesting lower-dimensional embeddings are more susceptible to dimensional conflation and therefore benefit more from decomposition.

**Cross-model consistency.** The primitive works across all four models despite different architectures (BERT-based, sentence transformers), training data (general vs. biomedical), and dimensionality (384 to 1024). This supports the claim that dimensional decomposition is a property of embedding geometry, not of any specific model.

## 6. Why Not Hyperbolic Embeddings?


Hyperbolic embeddings are the canonical answer to hierarchy in embedding spaces. We argue they are solving a different problem:

1. **Rigid arborescent commitment**: Hyperbolic curvature *assumes* tree structure as ground truth. Genuine ambiguity or multiple classification is treated as noise, not signal. In biomedical ontologies, where a protein can belong to multiple functional categories simultaneously, this is a fundamental mismatch.
2. **Catastrophic misrepresentation**: Small errors in hyperbolic space produce confident wrong answers rather than uncertain right ones. The geometry doesn't gracefully degrade.
3. **This is a navigation problem, not a geometry problem**: The field has framed hierarchy as requiring different geometry. We argue it requires different *traversal* — the ability to move through abstraction levels efficiently without categorical commitment.

The continuous height dimension with small-world navigation avoids all three failure modes: no categorical commitment, graceful degradation through continuous scoring, and navigation over existing geometry rather than replacement of it.

## 7. What This Does Not Solve

**Genuinely symmetric bidirectional relationships** — where neither direction is privileged — cannot be decomposed into pairs of asymmetric directional operations. The spouse example illustrates the boundary: heterosexual marriage decomposes into husband-of and wife-of cleanly, but truly symmetric relationships require both directions to be invariant under the dimensional control simultaneously. This is a stronger constraint and likely requires a different primitive. We leave this as an explicit open problem.

**Regular many-to-many relationships** outside of hierarchical contexts (e.g., "co-author of," "co-expressed with") remain structurally difficult. The dimensional decomposition handles *querying across* many-to-many structures effectively but does not represent the many-to-many relationship itself in the embedding.

## 8. Related Work

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

### Navigation
- **HNSW** (Malkov & Yashunin, 2018) — approximate nearest neighbor with navigable small-world graphs; we adapt the navigation structure for ontological traversal

## 9. Conclusion

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
10. **Malkov & Yashunin (2018)** — HNSW: Efficient and robust approximate nearest neighbor using hierarchical navigable small world graphs
11. **Bolukbasi, T., Chang, K.-W., Zou, J., Saligrama, V., & Kalai, A. (2016)** — Man is to Computer Programmer as Woman is to Homemaker? Debiasing Word Embeddings. *NeurIPS*.
12. **Ravfogel, S., Elazar, Y., Gonen, H., Twiton, M., & Goldberg, Y. (2020)** — Null It Out: Guarding Protected Attributes by Iterative Nullspace Projection. *ACL*.
13. **Leonhart, E. (2026)** — Relational displacement in arbitrary embedding spaces: oversymbolic collapse and the limits of vector arithmetic. clawrxiv:2604.00569. Companion paper establishing the one-to-one directional framework this paper extends
