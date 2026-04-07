# Source Conversation: Many-to-Many Matching in Embedding Spaces

**Source:** https://claude.ai/share/f07a549b-7dc4-4269-8449-11f02dc87a6f

**Date:** March 28, 2026

---

## Thread Summary

The conversation develops the idea that embedding spaces can only natively represent intransitive one-to-one asymmetric relations, and that many-to-many relations require a different approach. It moves through several key stages:

1. **Problem identification**: Embedding geometry is fundamentally a metric space over points — many-to-many structure requires set membership primitives that aren't metric
2. **Rejection of hyperbolic embeddings**: Accuracy demands enforce rigid arborescent ontology; small errors catastrophically misrepresent; this is a navigation problem not a geometry problem
3. **Ontological height as continuous scalar**: Train a dimension representing abstraction level using Wikidata P279 chain depth, with BFO types at top and concrete instances at bottom — no categorical commitment
4. **Small-world traversal**: HNSW-analog where layers correspond to ontological height, not random subsampling
5. **Pivot to structured matching primitive**: The core insight is similarity-modulo-one-dimension — find things similar across arbitrary dimensions but differing along a specific semantic dimension
6. **Labor economics application**: Two-axis hiring system (general quality + role fitness) where controlling for protected characteristics is structural, not correctional
7. **Formalization**: Orthogonal projection (not hypervectors as initially discussed) for dimensional control, combined with directed small-world navigation
8. **Literature gap confirmed**: Nobody combines controlled dimensional exclusion + directional selection + small-world navigation as a unified matching primitive

---

## Full Conversation

### User:
[Context: Discussion about being a "non-math person" who does matrix algebra in code]

Yeah. hmm so I am thinking. Semantic relations can only be represented in the embedding space if they are intransitive one to one asymmetric relations. But other mathematical models might be able to grasp many-to-many ones better

### Claude:
That's a sharp observation. The embedding space constraint is real — the geometry of dense vectors handles graded similarity well but struggles with the full relational structure of many-to-many mappings because every entity gets one point (or one region), and distance/direction has to do all the semantic work.

Directions that handle this better:
- **Hypergraph / tensor models** — relations as hyperedges, tensor decomposition (CP, Tucker) for n-ary relations
- **Type-theoretic / categorial approaches** — entities as types with ports, functorial semantics, DisCoCat
- **RDF-star / property graphs** — reification lets relations be arguments to other relations

The interesting question for the isosymbolic framework: do the FOL operations encode many-to-many relations through composition of asymmetric ones, or is that genuinely outside what the geometry can represent?

### User:
I do not seem to be able to represent many-to-many ones. Property graphs are like a level that I think is still expensive. idk about type theoretic and hypergraph ones

### Claude:
Three tiers of representational cost:
1. **Embedding space** — handles asymmetric one-to-one well, many-to-many is structurally excluded
2. **Graph / RDF** — handles many-to-many natively but at traversal cost
3. **Type-theoretic / hypergraph** — full expressive power but leaving the "cheap inference" regime

The question: are many-to-many relations actually primitive or are they composed? Is "ingredient of" many-to-many, or is it a conjunction of many asymmetric one-to-one "ingredient-of-instance" relations?

### User:
Like there is a "flat directional ontology" here and I think it exists in natural language and definitely in embedding spaces. And I think we need something between this and a knowledge graph. Hyperbolic embeddings are not the answer. But there's a fuckton of many to many relations in mathematics right now right?

### Claude:
Mathematics is saturated with many-to-many relations — functors, correspondences, multivalued functions, sheaves, spans and cospans.

The "something between" might be: **sparse relational structure on top of dense embeddings**. Not a full graph, but a lightweight incidence structure — which entities co-participate in which relations, without fully reifying relations as nodes. Closer to factor graphs.

### User:
Accuracy is so high stakes in hyperbolic embeddings that it pretty much enforces a rigid arborescent ontology on the data and just a tiny bit of error or ambiguity completely kills the category system

### Claude:
That's a deep problem not a tuning problem. Hyperbolic space requires the tree to be real. When data has genuine ambiguity, the geometry doesn't gracefully degrade — it catastrophically misrepresents. Confident wrong answers instead of uncertain right ones.

It's the Deleuzian criticism of arborescent thought made into a mathematical constraint.

### User:
hmm I think there might actually be something here. Training a specific dimension of "ontological height", and something analogous to HNSW could kind of ascend or descend through this with a network with small-worldedness?

### Claude:
HNSW works because it builds a hierarchy of graphs with decreasing connectivity — upper layers are long-range coarse navigation, lower layers are dense local search. The hierarchy is **emergent from the data not imposed on it**.

If you train an explicit "ontological height" dimension — not derived from curvature but learned as a feature — then something HNSW-like could navigate it without the arborescent commitment. Ascend to find the right abstraction level, descend to find specific instances, but lateral relations at any given height are still metric and can be rhizomatic.

The small-world property means local ontological neighborhoods are dense and coherent, but you can reach distant concepts cheaply by ascending and re-descending.

### User:
I figure wikidata ontological height might work for it. I know it is crazy and inconsistent, but we are basically only doing it for the height, not for even the coordinates of the things.

### Claude:
Elegant dodge of Wikidata's consistency problems. You're not trusting it to tell you *what* things are — just roughly *how abstract* they are. The noise is probably fine because you're averaging over a massive inconsistent ontology and what survives averaging is genuine signal about abstraction level.

Wikidata's P279 (subclass of) chain depth is the most direct signal. The inconsistency might actually help — multiply classified concepts get a height score that reflects real ontological uncertainty.

### User:
Yeah again the big thing that might cause people to freak out: I am not actually asserting category membership as a thing. This is a continuous scalar dimension. BFO types would probably be at the top, instances of concrete things will be at the bottom.

### Claude:
That's the move that makes it work. A continuous scalar sidesteps the arborescent commitment entirely. You're not saying "this is an abstract object," you're saying "this has an abstraction score of 0.87."

BFO types at the top is a good anchor — continuant, occurrent, entity — maximally commitment-light by design.

### User:
Yeah I think this makes sense. This does not solve all problems. It does not solve regular many-to-many relations but it does solve hierarchical ones if it works

### Claude:
Scope it correctly and it's a real contribution. Hierarchical many-to-many is a genuine problem. The clean version of the claim: this extends the isosymbolic zone upward into abstraction space by adding a navigable height dimension, without making categorical commitments the data doesn't support.

### User:
It's a new paper I'll do. Harder because it involves more fundamental training and more compute but I'll try it

### Claude:
The compute concern might be more tractable than it feels. The Wikidata height signal derivation is cheap. The expensive part is training with an explicit height dimension, but you might fine-tune on top of an existing embedding model. Probe for height as a linear feature first — if it's already latent, the paper becomes about surfacing and calibrating it rather than introducing it from scratch.

Phylogeny was suggested as ideal test domain: clean ground truth height from taxonomic ranks, decent Wikidata coverage, real and unambiguous hierarchy.

### User:
[Extended voice note about ontological height, the difficulty of training, interest in phylogeny as test domain, and VSA/hypervectors]

### Claude:
For the height-specific question, relevant prior work:
- **Vendrov et al.** on order embeddings
- **Nickel & Kiela** on Poincare embeddings (motivation section useful for framing)
- Cone embeddings as alternative to hyperbolic

The probe for emergent height in frozen embeddings framing doesn't appear to have been done cleanly for ontological abstraction level specifically.

### User:
[Extended voice note about navigation, categorization as primary use case, and the core insight: finding things similar across arbitrary dimensions but differing along a specific semantic dimension]

### Claude:
That formulation inverts the usual embedding use case. Normally you search for overall similarity. Here you're searching for **similarity-modulo-one-dimension**, which requires factoring out everything else and isolating the axis of difference.

### User:
[Extended voice note about hiring application — replacing an employee who quit, two-axis system]

### Claude:
Two-axis system:
- **Axis 1**: General candidate quality (credentials, track record) — universal across roles
- **Axis 2**: Role fitness — cosine similarity to target role with Axis 1 factored out

The nurse with programming skills scores higher on Axis 1 without confusing her Axis 2 similarity with software engineering roles.

### User:
[Discussion of anti-discrimination properties being structural, not ideological]

### Claude:
The proxy discrimination problem cuts both ways. If the departed employee was Black, naive cosine similarity steers toward Black replacements — same conflation failure. The control makes the query express what the employer actually means to ask.

### User:
Yeah. Like like, I would be publishing this as I'd be publishing this in economics... fundamentally, what we're trying to do is we're because fundamentally this is also a way of encoding many to many relationships.

### Claude:
The many-to-many connection ties everything together. Selective dimensional matching is a general primitive. Case study structure:
1. Hiring/labor matching
2. Ontological categorization
3. Gender-controlled similarity
4. One emergent/surprising finding (exploratory)

### User:
[Discussion establishing the two-paper arc: Paper 1 = directional one-to-one, Paper 2 = directional many-to-many, bidirectional remains open]

### Claude:
Clean theoretical arc. The asymmetry — bidirectional relationships remain unsolved — is honest and strengthens the contribution. "Relationships that are genuinely symmetric without a privileged direction cannot be decomposed this way and require a different primitive."

### User:
I am confused about what a hyper vector even is... We're essentially doing a dimension reduction into 3 dimensions... Is this Hyper Vectors?

### Claude:
No — what you're describing is closer to **orthogonal projection / orthogonal decomposition**:
1. Take the embedding vector
2. Project out dimensions correlated with the controlled axis
3. Compute cosine similarity on the residual

$$e_\perp = e - \frac{e \cdot v}{v \cdot v} v$$

This is standard linear algebra and actually cleaner than VSA hypervectors for this use case.

### User:
I feel like you just hallucinated some word that wasn't supposed to be used for this... I think the directed small world navigation thing is still novel. But I want you to actually verify this.

### Claude:
[Web search performed]

Results:
- Orthogonal projection for controlling dimensions exists in compositional concept extraction literature (DebugML)
- **But**: Nobody combines controlled dimensional exclusion + directional selection + small world navigation as a unified matching primitive
- The fairness literature does **correction**
- The compositional concept literature does **subspace discovery**
- The HNSW literature does **approximate nearest neighbor**
- **The three-part query structure does not exist**

### User:
So basically, there's people using orthogonal vectors to control for something but there's not really the structured querying form...

### Claude:
The components exist separately but nobody has assembled them into a coherent query structure:
1. Maximize similarity to target
2. Subject to orthogonality with controlled dimensions
3. Navigating via directed small world traversal

Formally: given query entity q, control subspace C, and target direction d, find entity e that maximizes cosine similarity to q projected onto complement of C, while preferring movement along d. The small world graph is the efficient data structure for executing that query at scale.

**That formulation doesn't exist in the literature.**

---

## Key Sources Cited in Conversation

1. **Vendrov et al. (2016)** — Order embeddings for visual-semantic hierarchy
2. **Nickel & Kiela (2017)** — Poincare embeddings for hierarchical representations
3. **Malkov & Yashunin (2018)** — HNSW approximate nearest neighbor
4. **Dwork et al. (2012)** — Fairness through awareness
5. **Corbett-Davies & Goel (2018)** — Measure of fairness
6. **FairGHDC** (arXiv) — Fairness in graph hyperdimensional computing
7. **Compositional concept extraction** (DebugML) — Orthogonal projection for concept subspaces
8. **PubMed Central** — VSA tree traversal via binding chains
9. **Proxy discrimination papers** (arXiv) — Protected attribute exclusion doesn't prevent proxy discrimination

## Key Novelty Claims

1. **The structured three-part query primitive** (select + control + navigate) as a unified formalism
2. **Framing matching as decomposition rather than correction** for fairness
3. **Directed small-world navigation** over ontological height (continuous, non-categorical)
4. **The conflation diagnosis**: single-score similarity is where discrimination structurally originates
