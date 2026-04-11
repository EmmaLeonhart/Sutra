# JEPA Hybrid Architecture

## The HDC-JEPA Connection

Hyperdimensional Computing (HDC) and Joint Embedding Predictive Architecture (JEPA) both operate in high-dimensional representational spaces where **similarity is the core currency of computation**. Both avoid pixel/token-level reconstruction in favor of abstract representations.

The differences are complementary:
- **HDC** has explicit algebraic structure (bind, bundle, release) but learns nothing — the operations are fixed by design
- **JEPA** learns rich representations but has no explicit compositional structure — the algebra is implicit in the weights

Akasha proposes a hybrid: HDC's algebraic structure as an **explicit compositional prior** on JEPA's learned embeddings. The algebra isn't imposed externally — it's a formalization of structure the model has already learned implicitly. The FOL discovery work in this repo validates this: embedding spaces do encode consistent vector arithmetic for semantic relationships, without being told to.

## Two-Phase Training

The proposed training architecture for an Akasha-native model:

**Phase 1 — Algebraic consistency training.** Train the model so its embedding space respects VSA axioms: binding produces vectors dissimilar to inputs, unbinding approximately recovers fillers, bundling creates superpositions that are similar to all components. This doesn't replace the model's learned representations — it regularizes them so algebraic operations work reliably.

**Phase 2 — Predictive coding on structured space.** Once the embedding space has algebraic structure, train JEPA-style prediction on top. The predictor learns relationships between **structured representations**, not between unstructured blobs. This should produce more compositionally generalizable predictions.

The key: Phase 1 gives you a space you can compute in. Phase 2 gives you a model that reasons about the structure of that space. Akasha programs operate in the space; the JEPA predictor is what makes novel inference possible.

## Mixed-Regime Latent Spaces

Not all dimensions of an embedding need to behave the same way. A more expressive architecture uses **mixed-regime** dimensions:

- **Binary/ternary dimensions** for structural/symbolic facts: Is this a noun or a verb? Is this entity a member of this class? These are inherently discrete and benefit from hard values. A binding operation might have a binary role slot but a continuous filler.
- **Continuous dimensions** for graded/sensory facts: How similar are these? How confident am I? What's the degree of this property? These are inherently fuzzy and should stay continuous.

The binding operation itself could be mixed-regime: the role is binary (which slot?), the filler is continuous (what value?). This captures the intuition that structure is crisp but content is graded.

## Staged Commitment

Binary dimensions don't start binary. During training, they begin as **soft continuous values** and gradually anneal toward hard 0/1 values. Structure "crystallizes" over time as the model becomes more confident about categorical distinctions.

This mirrors human cognitive development — early representations are diffuse and become more structured with experience. It also provides a natural training curriculum: the model first learns continuous similarity structure, then gradually commits to discrete categorical structure on top of it.

**Relevance to `is_true`:** The staged commitment process is the training-time analog of Akasha's runtime `is_true` defuzzification. During training, dimensions gradually defuzzify from continuous to binary. During inference, `is_true` explicitly defuzzifies a continuous truth value to a discrete judgment. Same operation, different timescales.

## Product Manifold Embeddings

Going further than mixed-regime dimensions: different **geometric types** for different kinds of semantic structure:

- **Hyperbolic dimensions** for hierarchical/taxonomic relationships. Hyperbolic space naturally represents trees — distance from the origin corresponds to depth, and the exponentially growing circumference at each radius provides room for branching. "Dog is-a animal" is a hierarchical relation that lives naturally in hyperbolic space.
- **Euclidean dimensions** for lateral/analogical relationships. "King is-to queen as man is-to woman" is a parallelogram relation that lives naturally in flat Euclidean space.
- **Spherical dimensions** for cyclical/periodic relationships. Time of day, seasons, cardinal directions — these wrap around and live naturally on spheres.

A **product manifold** embedding combines these: some dimensions are hyperbolic, some Euclidean, some spherical. The geometry itself becomes the knowledge representation. An entity's position in the hyperbolic subspace encodes where it sits in a taxonomy; its position in the Euclidean subspace encodes its analogical relationships.

**Relevance to Akasha:** This suggests that Akasha's "vector" type could have geometric subtypes. A projection onto the hyperbolic subspace asks "where does this sit in the hierarchy?" A projection onto the Euclidean subspace asks "what is this analogous to?" Different operations would be natural in different subspaces. This is speculative but architecturally interesting — it means the type of a vector isn't just its dimensionality but its geometry.
