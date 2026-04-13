# Operations

Every Sutra operation executes on the substrate — the connectome, mushroom body, HNSW index, codebook, or whatever vector-graph backend a given deployment uses. There is no sorting of operations into "runs on the host" vs "runs on the substrate" classes. An operation either executes on the substrate or it is a gap to close. A current implementation that runs on numpy is a limitation of that implementation, not a spec-sanctioned execution mode.

Scalars, tuples, and bounded iteration still exist as scaffolding around the vector computation. They are numbers and groupings; they are not the semantic work Sutra exists to do. The semantic work — bundle, bind, unbind, similarity, scalar multiplication, projection, rotation, snap, cone, hop — runs on the substrate.

## Scaffolding

### Scalars
```
alpha = 0.7
count = 10
threshold = 0.85
```
Scalars are plain numbers. They weight vectors, set thresholds for `is_true` defuzzification, drive bounded iteration, and carry the output of similarity queries back into control flow.

### Tuples
```
pair = (vector_a, vector_b)
triple = (role, filler, confidence)
```
Tuples group values without superposing them. A tuple keeps its elements separate and individually accessible — distinct from bundling, which merges vectors into a single superposed state where individual components become approximate.

Currently no linked lists. If you need a sequence, use a tuple or encode it via binding with positional roles.

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
Integer-based iteration: repeat a body a fixed number of times. `loop (N)` unrolls to N copies of the body; `loop (N as i)` adds an index variable. The iteration count is a scalar.

For convergence-based iteration (unbounded), use `loop (condition)` — see [Control Flow](03-control-flow.md).

## Vector operations

Each operation below is defined by what it computes. Each executes on the substrate. When an implementation currently runs an operation on numpy (because the substrate mapping is not yet wired up), that is a limitation of the implementation — describe it that way in the result, do not describe it as a class property of the operation.

### Bundle
```
result = a + b
```
Elementwise vector sum. Creates **superposition** — the result is similar to all inputs. Fuzzy disjunction (OR). Encodes sets, mixtures, "any of these." Commutative and associative. Signal-to-noise degrades as more items are bundled; this is a capacity limit of the substrate, not a bug.

### Bind

Binding encodes key-value pairs and role-filler structures. The result is dissimilar to both inputs — a form of encryption by the role.

**Hadamard binding fails on natural embedding spaces.** Empirical testing on GTE-large (1024d) showed bundled structures with Hadamard binding lose signal at 2+ role-filler pairs because the crosstalk from correlated (non-orthogonal) natural embeddings overwhelms the target.

Sutra uses **sign-flip binding** as its default and **rotation binding** as its high-accuracy alternative.

#### Sign-flip binding (default)
```
result = bind(a, role)    # a * sign(role)
```
Flip the signs of the filler's dimensions based on the sign of the role vector. The mask `sign(role)` is:
- **Self-inverse:** unbinding is the same operation (`unbind = bind`).
- **Nearly orthogonal** across different roles.
- **Effective:** maintains correct snap recovery through 7+ bundled role-filler pairs on natural embeddings.

Empirical results on GTE-large: cosine to target = 0.74 at 2 roles, 0.52 at 5 roles, 0.40 at 7 roles. All 7/7 snap-to-nearest recoveries correct.

#### Rotation binding (high-accuracy)
```
result = bind_precise(a, role)    # R(role) @ a
```
Apply a role-dependent orthogonal rotation. The rotation is deterministically derived from the role vector via composed Givens rotations.
- **Exact inverse:** unbinding via transpose (`R^T @ bound`).
- **Best accuracy:** 0.89 cosine at 2 roles, 0.80 at 7 roles.
- **Use when accuracy matters.**

#### Other viable alternatives
All tested on GTE-large, all achieve 7/7 correct snap at 7 bundled roles: permutation (shuffle dimensions by role), circular convolution (Plate HRR), FFT correlation.

#### Why Hadamard fails on natural embeddings
Hadamard works in traditional VSA because the vectors are random and nearly orthogonal by construction. Natural embedding spaces are correlated and anisotropic. Bundling multiple Hadamard-bound pairs lets crosstalk from non-orthogonal roles dominate the target. Sign-flip strips the magnitude information that causes correlation, leaving only a binary mask.

### Unbind
```
filler = unbind(role, bound_structure)
```
Given a role, extract the approximate filler from a bundled bound structure. Sign-flip binding is self-inverse; rotation binding inverts via transpose. Results are approximate when multiple role-filler pairs are bundled — the noise is crosstalk with the other pairs.

### Similarity
```
score = similarity(a, b)
```
Cosine similarity or dot product. How close are two vectors. This is how results are read, states compared, and defuzzification driven. Returns a scalar.

Cosine discards magnitude, which carries information about binding strength and bundling count. Euclidean distance preserves both direction and magnitude. Pick the metric to match what is being measured.

### Scalar multiplication
```
result = alpha * v
```
Scale a vector, adjusting magnitude (confidence/weight) without changing direction (meaning). `alpha` is a scalar; the result is a vector.

### Projection
```
result = project(v, subspace)
```
Project a vector onto a subspace, extracting the component along given dimensions. "What does this vector say about X?"

### Rotation
```
result = R @ v
```
Apply an orthogonal operator R to a vector. R may be a Givens composition, a polar-decomposition factor of a connectome weight matrix, or a block-diagonal composition across motifs. Rotation is the iteration step in eigenrotation loops — see [Control Flow](03-control-flow.md).

Rotation executes on the substrate. On the fly-brain backend this means Q enters the network as synaptic weights and the iterated state is read from membrane voltage or spike rate. A version of rotation that multiplies Q into v with numpy is a limitation of the current implementation, not a spec-sanctioned execution path — when a result relies on that numpy step, say so in the result.

### Snap (cleanup / discretization)
```
clean = snap(noisy_vector)
```
Nearest-neighbor lookup against a codebook of known vectors. Cleans up noise from accumulated bind/unbind/rotation chains. Analogous to rounding in floating-point arithmetic or quantization in signal processing — it is what makes long VSA chains practically viable.

The codebook is part of the program's semantics — what vectors count as "known good" is a design choice.

### Cone traversal (directed neighborhood)
```
neighbors = cone(origin, direction, angle)
```
From a point in the space, define a direction and an angular spread. Return all vectors within the cone. Directed neighborhood query — not flat similarity.

This is the primary mechanism for branching and control flow that is not expressible by algebra alone. Different vector states point the cone in different directions, naturally navigating to different regions. The condition is implicit in the geometry.

### Graph hop
```
destination = hop(origin, relation)
```
Given a vector and a relation type, traverse to connected vectors in the semantic graph. Extends cone traversal with typed edges — not just "nearby in this direction" but "connected by this specific relationship." The graph structure need not be fixed ahead of time; the vector state influences which edges are traversed, which is what gives Sutra the potential for unbounded computation.

## Substrate requirement

Every operation above — bundle, bind, unbind, similarity, scalar multiplication, projection, rotation, snap, cone, hop — executes on the substrate. A backend that cannot execute an operation on its substrate must either implement it or refuse to compile programs that use it. A silent fallback to host numpy is a bug, not a design choice. When a current result depends on such a fallback, that fallback is stated in the result as a limitation to close, not as a legitimate execution mode.
