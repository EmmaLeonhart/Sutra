# Operations

Sutra has three tiers of operations, ordered by cost and abstraction level:

1. **Primitive operations** — scalars, tuples, integer iteration. The scaffolding that isn't vector computation at all.
2. **Algebraic / VSA operations** — bind, bundle, unbind, similarity, projection. The core vector algebra. O(1), pure math, no infrastructure needed.
3. **Non-algebraic / vector-graph operations** — snap-to-nearest, cone traversal, graph hop. All ANN-based, all involve traversal of an HNSW index or similar vector database. Most expensive tier.

## Primitive Operations (Scaffolding)

These are not vector operations. They are the conventional computational scaffolding that supports the vector computation. They exist because not everything in a program is a semantic vector operation — sometimes you just need to count to 10 or group two things together.

### Scalars
```
alpha = 0.7
count = 10
threshold = 0.85
```
Scalars exist in Sutra but are **not considered vectors**. They are plain numbers used for:
- Weighting vectors (scalar multiplication: `alpha * v`)
- Thresholds for `is_true` defuzzification
- Loop counters for bounded iteration
- Similarity scores (the output of a similarity query is a scalar)

Scalars are the bridge between the fuzzy vector world and the crisp control world. They are how you extract actionable decisions from continuous computation.

### Tuples
```
pair = (vector_a, vector_b)
triple = (role, filler, confidence)
```
Tuples group values together without superposing them. This is **not** bundling — bundling merges vectors into a single superposition where individual components become approximate. A tuple keeps its elements separate and individually accessible.

Tuples are used for:
- Passing multiple values to/from operations without merging them
- Holding structured results (e.g., a snap operation might return `(nearest_vector, distance)`)
- Organizing program state where you need exact access, not approximate unbinding

**Currently no linked lists.** Tuples are the primary compound data structure. Linked lists may be added later but are not part of the current design. If you need a sequence, use a tuple or encode it via binding with positional roles.

### Bounded Iteration
```sutra
loop (10) {
    state = bind(transform, state);
    state = snap(state);
}

loop (10 as i) {
    state = bind(steps[i], state);
    state = snap(state);
}
```
Integer-based iteration: do something a fixed number of times. The iteration count is a scalar (an integer), not a vector. `loop (N)` unrolls to N copies of the body at compile time — no rotation matrix, no circuit iteration, just straight-line code. `loop (N as i)` adds an index variable.

This is the default and preferred loop form. It composes well with snap-to-nearest (clean up noise every N iterations) and is straightforward to reason about. For convergence-based iteration (unbounded), use `loop (condition)` — see [Control Flow](03-control-flow.md) for the eigenrotation semantics.

## Algebraic / VSA Operations (Core)

These are the native operations of the vector space. Each is **O(1)** — constant time, operating elementwise on fixed-dimensional vectors. No infrastructure required — pure math on vectors.

### Bundle (Addition)
```
result = a + b
```
Elementwise vector addition. Creates **superposition** — the result is similar to all inputs. This is fuzzy disjunction (OR). Encodes sets, mixtures, "any of these."

Properties: commutative, associative. Signal-to-noise degrades as more items are superposed (a fundamental capacity limit, not a bug).

### Bind

Binding encodes key-value pairs and role-filler structures. The result is **dissimilar to both inputs** — a kind of encryption.

**CRITICAL FINDING:** The traditional VSA binding operation (Hadamard / elementwise product) **fails on natural embedding spaces**. Empirical testing on GTE-large (1024d) shows that bundled structures with Hadamard binding lose all signal at 2+ role-filler pairs — the crosstalk from correlated (non-orthogonal) natural embeddings overwhelms the target.

Sutra uses **sign-flip binding** as its default and **rotation binding** as its high-accuracy alternative:

#### Sign-Flip Binding (Default)
```
result = bind(a, role)    # a * sign(role)
```
Flip the signs of the filler's dimensions based on the sign of the role vector. The sign pattern `sign(role)` creates a pseudo-random binary mask (+1/-1) that is:
- **Self-inverse:** unbinding is the same operation (`unbind = bind`)
- **Nearly orthogonal** across different role vectors
- **Cheap:** 6.6μs per operation (only 4.4x slower than Hadamard)
- **Effective:** Maintains correct snap recovery through 7+ bundled role-filler pairs on natural embeddings

Empirical results on GTE-large: cosine to target = 0.74 at 2 roles, 0.52 at 5 roles, 0.40 at 7 roles. All 7/7 snap-to-nearest recoveries correct.

#### Rotation Binding (High-Accuracy)
```
result = bind_precise(a, role)    # R(role) @ a
```
Apply a role-dependent orthogonal rotation matrix. The rotation is deterministically derived from the role vector via composed Givens rotations.
- **Exact inverse:** unbinding via transpose (`R^T @ bound`)
- **Best accuracy:** 0.89 cosine at 2 roles, 0.80 at 7 roles
- **Expensive:** 321μs per operation (213x Hadamard)
- **Use when accuracy matters more than speed**

#### Other Viable Alternatives
All tested on GTE-large, all achieve 7/7 correct snap at 7 bundled roles:
- **Permutation** (30.9μs, 21x): Shuffle dimensions based on role. Good middle ground.
- **Circular convolution** (79.3μs, 53x): Classic Plate HRR binding. Works but slower than sign-flip for comparable accuracy.
- **FFT correlation** (67.3μs, 45x): Frequency-domain multiply. Similar to circular convolution.

#### Why Hadamard Fails on Natural Embeddings
The Hadamard product `a * b` works in traditional VSA because the vectors are random and nearly orthogonal by construction. In natural embedding spaces, vectors are **correlated and anisotropic** — they share significant structure. When you bundle multiple Hadamard-bound pairs, the crosstalk terms (from the non-orthogonal roles) dominate the target term. Sign-flip avoids this because `sign(role)` strips the magnitude information that causes correlation, leaving only a random-looking binary mask.

### Unbind (Inverse of Bind)
```
filler = unbind(role, bound_structure)
```
Given a role vector, extract the approximate filler from a bundled bound structure. For sign-flip binding, unbinding is the same operation applied again (self-inverse). For rotation binding, it's the transpose of the rotation matrix. The result is approximate when multiple role-filler pairs are bundled — noise comes from crosstalk with the other pairs.

### Similarity Query
```
score = similarity(a, b)
```
Cosine similarity or dot product. The fundamental "how close are these?" operation. This is how you read results, compare states, and defuzzify. Returns a **scalar**.

**Important:** Cosine similarity discards magnitude, which carries information about binding strength and bundling count. Euclidean distance preserves both direction and magnitude. The right metric depends on what you're measuring.

### Scalar Multiplication
```
result = alpha * v
```
Scales a vector, adjusting its magnitude (confidence/weight) without changing its direction (meaning). The scalar `alpha` is a primitive; the result is a vector.

### Projection
```
result = project(v, subspace)
```
Projects a vector onto a subspace, extracting the component of meaning along certain dimensions. This is how you ask "what does this vector say about X?"

## Non-Algebraic / Vector-Graph Operations (Expensive)

These operations require approximate nearest neighbor (ANN) search infrastructure — typically an HNSW index or similar vector database. They involve traversal across an indexed vector space. All are significantly more expensive than algebraic operations and should be used deliberately.

The unifying characteristic: **all non-algebraic operations are ANN-based.** They all involve some form of nearest-neighbor search or graph traversal over an indexed collection of vectors. This is what makes them expensive — they hit an external index rather than computing purely on the vectors in hand.

They serve two purposes:
1. **Error correction** — snap-to-nearest cleans up noise from algebraic chains
2. **Navigation** — cone traversal and graph hop provide branching and relational topology that pure algebra cannot express

### Snap-to-Nearest (Cleanup / Discretization)
```
clean = snap(noisy_vector)
```
ANN search against a codebook of known vectors. Finds the nearest clean vector to a noisy result. This is **error correction** — after a chain of binds and unbinds accumulates noise, snap restores the vector to a known-good state.

This is the operation that makes VSA computation practically viable over long chains. Without it, noise from approximate unbinding compounds until results are meaningless. It is analogous to rounding in floating-point arithmetic, or quantization in signal processing.

**Cost:** O(log n) with good ANN indexing, where n is codebook size. The codebook itself is a design choice — what vectors are "known good" is part of the program's semantics.

### Cone Traversal (Directed Neighborhood Query)
```
neighbors = cone(origin, direction, angle)
```
From a point in embedding space, define a direction vector and angular spread — a directed cone. Returns all vectors that fall within that cone. This is a **directed neighborhood query**, not flat similarity search.

This is the primary mechanism for **non-algebraic branching and control flow**. Different vector states point the cone in different directions, naturally navigating to different regions of the space. The condition is implicit in the geometry rather than explicit as an if/else.

**Why it matters:** Pure VSA algebra handles local computation well but cannot express many-to-many relationships or conditional navigation through a semantic graph. Cone traversal patches this — it provides the relational topology that algebra alone lacks.

**Cost:** O(log n) with spatial indexing. More expensive than algebraic ops but far cheaper than exhaustive search.

### Graph Hop
```
destination = hop(origin, relation)
```
Given a starting vector and a relation type, traverse to connected vectors in the semantic graph. This extends cone traversal with typed edges — not just "what's nearby in this direction" but "what's connected by this specific relationship."

**Cost:** Depends on graph indexing. The graph structure isn't fixed ahead of time — the vector state influences which edges get traversed, which is what gives Sutra the potential for unbounded computation.

## Summary: Three Tiers

| | Primitive | Algebraic (VSA) | Non-Algebraic (Vector-Graph) |
|---|---|---|---|
| **Operations** | scalars, tuples, bounded iteration | bundle, bind (sign-flip), unbind, similarity, scale, project | snap, cone, hop |
| **Operates on** | Numbers, groups of values | Vectors | Vectors + ANN index |
| **Cost** | O(1) | O(1) (~1-7μs) | O(log n) (~30-31,000μs) |
| **Infrastructure** | None | None (pure math) | HNSW index, codebook, graph DB |
| **Error behavior** | Exact | Noise accumulates | Noise gets corrected |
| **Encouraged?** | Use as needed | Yes — the core | Use deliberately — most expensive |
| **Analogy** | Registers, counters | Arithmetic on a CPU | Memory access / cache lookup |

The design philosophy: primitives handle scaffolding (counting, grouping, thresholds), algebraic operations handle the actual semantic computation, non-algebraic operations handle error correction and navigation. Keep as much work as possible in the algebraic tier. Drop to primitives for control. Rise to non-algebraic only when you need to hit the index.
