# VSA Mathematical Grounding

## VSA Is Algebra, HDC Is Engineering

A critical distinction that Akasha's documentation must maintain:

- **Vector Symbolic Architecture (VSA)** is the algebra — the formal mathematical framework defining operations (bind, bundle, similarity) and their properties over high-dimensional vector spaces. It is as rigorous as Boolean algebra or linear algebra.
- **Hyperdimensional Computing (HDC)** is the engineering application — specific choices about dimensionality (10,000? 100,000?), vector type (binary? bipolar? continuous?), specific tasks (classification? retrieval? reasoning?), hardware implementation.

The relationship is: **Boolean algebra is to digital circuits as VSA is to HDC.** Boolean algebra defines AND, OR, NOT and their properties. Digital circuit design uses those operations to build useful things. VSA defines bind, bundle, similarity and their properties. HDC uses those operations to build useful things.

Akasha operates at the VSA level. Its semantics are defined in terms of algebraic operations. The specific dimensionality, embedding model, and hardware are implementation details handled by empirical initiation.

## Concentration of Measure

The mathematical foundation that makes VSA work is **concentration of measure** in high-dimensional spaces. This is not empirical hand-waving — it is a proven mathematical phenomenon:

- In high-dimensional space (d > 1000), randomly sampled vectors are **almost certainly nearly orthogonal**. The probability that two random unit vectors have cosine similarity > ε decreases exponentially with dimensionality.
- This means thousands of random vectors can coexist in the same space without significant interference. Each one is approximately orthogonal to all the others.
- Bundling (addition) of k vectors produces a result that is approximately `1/√k` similar to each component. This is predictable and quantifiable.
- Binding (elementwise multiplication) of two vectors produces a result that is approximately orthogonal to both inputs. This is the "encryption" property.

These properties are **theorems**, not empirical observations. They follow from the geometry of high-dimensional spheres and the law of large numbers.

## The Eight Axioms

Akasha's computational substrate must satisfy the eight axioms of a real vector space. LLM embedding spaces do, because they are subsets of R^n:

1. **Commutativity of addition:** u + v = v + u
2. **Associativity of addition:** (u + v) + w = u + (v + w)
3. **Additive identity (zero vector):** There exists 0 such that v + 0 = v
4. **Additive inverse:** For every v, there exists -v such that v + (-v) = 0
5. **Multiplicative identity:** 1 * v = v
6. **Associativity of scalar multiplication:** a(bv) = (ab)v
7. **Distributivity over vector addition:** a(u + v) = au + av
8. **Distributivity over scalar addition:** (a + b)v = av + bv

Because Akasha operates in a real vector space, it inherits the **entire toolkit of linear algebra** for free: subspaces, bases, dimension, linear maps, eigendecomposition, projections, orthogonal complements. These are all valid Akasha operations because the substrate satisfies the axioms.

The abstraction is powerful: Akasha programs work regardless of what the vectors "actually are" — Wikidata entities, English words, protein sequences, user behavior embeddings. If the space satisfies the axioms and passes empirical initiation, Akasha can compute in it.

## Embeddings Are Domain-Agnostic

Akasha's vectors should not be conceived as "word embeddings" or "text embeddings." Embeddings are a general technique for mapping **any discrete categorical input** into dense continuous vector space:

- Words and subwords (NLP)
- User IDs and product IDs (recommender systems)
- Graph nodes (knowledge graphs, social networks)
- Amino acid sequences (protein structure prediction)
- Board states (game playing)
- Sensor readings discretized into categories (IoT)

The embedding matrix is **learned jointly** with the rest of the network — gradients flow back through the model into the embedding weights, shaping how meanings get encoded. This is why embedding spaces have algebraic structure: the training process optimizes for relationships between entities, and those relationships manifest as geometric regularities.

Akasha can in principle operate in any of these embedding spaces. The substrate is not "language" — it's "learned dense representations of structured domains." This broadens Akasha's applicability far beyond NLP.
