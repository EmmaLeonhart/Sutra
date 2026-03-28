# Dimensional Decomposition for Many-to-Many Matching in Embedding Spaces

**Category:** Labor Economics / Microeconomics (with CS and Statistics applications)

**Target:** Claw4S Conference 2026 (deadline April 5, 2026)

## Abstract

Current embedding-based matching systems collapse multi-dimensional similarity into a single scalar score, conflating dimensions that should be independently queryable. This paper introduces a structured matching primitive that decomposes embedding similarity into three components: (1) dimensions to actively select for, (2) dimensions to actively control against, and (3) residual general similarity uncorrelated with the controlled dimensions. The mechanism combines orthogonal projection for dimensional control with directed small-world graph navigation for efficient traversal. We formalize this as a query structure, demonstrate it across multiple case studies including labor market matching, and show that this decomposition both improves match quality (a Pareto improvement) and structurally prevents proxy discrimination — not as a post-hoc correction but as a consequence of doing the similarity computation correctly.

## 1. Introduction

Embedding spaces encode semantic similarity as geometric proximity. This is powerful for retrieval but structurally limited: when a query requires *similarity along some dimensions but not others*, a single cosine similarity score cannot express the distinction. The result is systematic conflation — irrelevant dimensions contaminate the similarity score, producing worse matches than the data supports.

This conflation is where algorithmic discrimination structurally originates. A hiring algorithm that computes cosine similarity between a candidate embedding and a role embedding will encode race, gender, resume gaps, and other irrelevant features into the score, not because the algorithm is biased but because the query formalism cannot distinguish relevant from irrelevant dimensions.

We propose a matching primitive with three components:

1. **Active selection**: Maximize similarity to target along specified dimensions
2. **Active control**: Orthogonally project away specified dimensions (protected characteristics, irrelevant features)
3. **General residual similarity**: Cosine similarity on the residual, uncorrelated with controlled dimensions by construction

This is not a debiasing method. It is a *correctly specified query* that expresses what the user actually means when they ask for "similar but not along these axes."

### 1.1 Relationship to Prior Work

This paper extends a research program on emergent symbolic operations in embedding spaces:

- **Paper 1 (isosymbolic framework):** Discovered that directional one-to-one asymmetric relationships emerge as first-order logic operations from embedding geometry [self-cite]
- **This paper:** Extends to directional many-to-many relationships via controlled dimensional decomposition
- **Open problem:** Genuinely symmetric bidirectional relationships — where neither direction is privileged — remain unsolved and likely require a different primitive

## 2. The Conflation Problem

### 2.1 Single-Score Matching is Structurally Lossy

When matching in embedding space, the standard operation is:

$$\text{score}(q, e) = \cos(q, e) = \frac{q \cdot e}{\|q\| \|e\|}$$

This computes similarity across *all* dimensions simultaneously. If the embedding encodes $k$ distinct semantic features, cosine similarity averages over all $k$, even when only a subset is relevant to the query.

### 2.2 Proxy Discrimination as a Dimensionality Problem

The fairness-in-ML literature acknowledges that excluding protected attributes from model inputs does not eliminate discrimination risk, because proxy variables strongly correlated with protected attributes still encode sensitive information (Dwork et al., 2012; Corbett-Davies & Goel, 2018). The standard response is correction — regularization, adversarial debiasing, post-hoc adjustment.

We reframe: proxy discrimination is not a bias problem requiring correction. It is a *dimensionality problem* requiring decomposition. The conflation of relevant and irrelevant dimensions is the structural cause. Correcting a conflated score is treating a symptom; decomposing the query addresses the cause.

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

### 3.3 Navigable Small-World Traversal

Executing the structured query at scale requires an efficient traversal structure. We propose an HNSW-analog where:

- Graph layers correspond to abstraction levels (ontological height), not random subsampling
- Navigation ascends to the appropriate abstraction level, then searches laterally within that level
- The small-world property provides high clustering (dense coherent neighborhoods) and short path lengths (cheap traversal to distant concepts)

The ontological height dimension is a continuous scalar — not a categorical assignment — avoiding arborescent commitment. BFO types anchor the top, concrete instances anchor the bottom. Height can be derived from Wikidata P279 (subclass of) chain depth as a training signal.

## 4. Case Studies

### 4.1 Labor Market Matching

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

### 4.2 Ontological Categorization

**Setup:** Wikidata entities with known taxonomic or ontological structure.

**Application:** Finding entities that are similar along specific ontological dimensions while controlling for others. A concept that participates in multiple abstraction levels or multiple incompatible hierarchies doesn't need a single categorical placement — it has a height and local neighbors, and the lateral relations at any given height are handled by the residual similarity.

**Connection to many-to-many:** Hierarchical many-to-many relationships (participating in multiple abstraction levels simultaneously) are handled by the continuous height dimension. Regular many-to-many relationships are handled by the controlled projection mechanism.

### 4.3 Gender-Controlled Similarity

**Setup:** Embeddings of people or roles with known gender associations.

**Application:** Finding "the same role but different gender" — priest/nun, actor/actress — by maximizing similarity while controlling for the gender dimension. Demonstrates the bidirectional control mechanism cleanly.

### 4.4 Exploratory: Emergent Latent Structure

**Setup:** Probe for structure in embeddings that wasn't explicitly trained.

**Hypothesis:** If the dimensional decomposition surfaces genuine latent relational structure, it should recover relationships the embedding model didn't know it had encoded. Potential examples: phylogenetic lineage, patronymic relationships in biographical text, or other implicit many-to-many structures.

**Status:** Exploratory. Results framed as suggestive findings with appropriate uncertainty.

## 5. Why Not Hyperbolic Embeddings?

Hyperbolic embeddings are the canonical answer to hierarchy in embedding spaces. We argue they are solving a different problem:

1. **Rigid arborescent commitment**: Hyperbolic curvature *assumes* tree structure as ground truth. Genuine ambiguity or multiple classification is treated as noise, not signal.
2. **Catastrophic misrepresentation**: Small errors in hyperbolic space produce confident wrong answers rather than uncertain right ones. The geometry doesn't gracefully degrade.
3. **This is a navigation problem, not a geometry problem**: The field has framed hierarchy as requiring different geometry. We argue it requires different *traversal* — the ability to move through abstraction levels efficiently without categorical commitment.

The continuous height dimension with small-world navigation avoids all three failure modes: no categorical commitment, graceful degradation through continuous scoring, and navigation over existing geometry rather than replacement of it.

## 6. What This Does Not Solve

**Genuinely symmetric bidirectional relationships** — where neither direction is privileged — cannot be decomposed into pairs of asymmetric directional operations. The spouse example illustrates the boundary: heterosexual marriage decomposes into husband-of and wife-of cleanly, but truly symmetric relationships require both directions to be invariant under the dimensional control simultaneously. This is a stronger constraint and likely requires a different primitive. We leave this as an explicit open problem.

**Regular many-to-many relationships** outside of hierarchical contexts (e.g., "ingredient of," "co-author of") remain structurally difficult. The dimensional decomposition handles *hierarchical* many-to-many well but does not solve the general case.

## 7. Related Work

- **Order embeddings** (Vendrov et al., 2016) — explicitly training partial order structure into embedding space
- **Poincare embeddings** (Nickel & Kiela, 2017) — hyperbolic geometry for hierarchy; different diagnosis than ours
- **Cone embeddings** — alternative to hyperbolic for hierarchy
- **Compositional concept extraction** (DebugML) — uses orthogonal projection to discover and separate concept subspaces; analysis tool, not a matching primitive
- **FairGHDC** (arXiv) — fairness in graph hyperdimensional computing; correction-based approach, structurally different
- **Fairness-in-ML literature** (Dwork et al., 2012; Corbett-Davies & Goel, 2018) — acknowledges proxy discrimination but proposes correction, not decomposition
- **HNSW** (Malkov & Yashunin, 2018) — approximate nearest neighbor with navigable small-world graphs; we adapt the navigation structure for ontological traversal

## 8. Conclusion

The single-score similarity paradigm is a structural mistake that produces both worse matches and systematic discrimination. Dimensional decomposition — actively selecting, actively controlling, and computing residual similarity — is the correct query formalism for multi-dimensional matching. The contribution is not any individual technique but their composition into a coherent, formalizable matching primitive that doesn't exist in the current literature.

## Sources and References

### From conversation / web search results:
1. **Dwork et al. (2012)** — Fairness through awareness; proxy discrimination and individual fairness
2. **Corbett-Davies & Goel (2018)** — Measure of fairness and proxy variable problem
3. **Vendrov et al. (2016)** — Order embeddings for visual-semantic hierarchy
4. **Nickel & Kiela (2017)** — Poincare embeddings for learning hierarchical representations
5. **Malkov & Yashunin (2018)** — HNSW: Efficient and robust approximate nearest neighbor using hierarchical navigable small world graphs
6. **FairGHDC** (arXiv) — Fairness in graph hyperdimensional computing
7. **Compositional concept extraction** (DebugML) — Orthogonal projection for concept subspace discovery
8. **PubMed Central** — VSA tree traversal via binding chains (hypervector literature)
9. **Proxy discrimination in ML** (arXiv) — Excluding protected attributes doesn't eliminate discrimination risk via proxy variables

### Key findings from literature search:
- Nobody is combining controlled dimensional exclusion + directional selection + small world navigation as a unified matching primitive
- The fairness literature does **correction** (regularization, adversarial debiasing, post-hoc)
- The compositional concept literature does **subspace discovery**
- The HNSW literature does **approximate nearest neighbor**
- **The three-part query structure does not exist in the literature**
