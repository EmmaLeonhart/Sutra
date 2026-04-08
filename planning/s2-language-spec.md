# S2 Language Specification (Draft)

## 1. Overview

S2 is a vector programming language that uses LLM embedding spaces as its computational substrate. Named after System 2 thinking (Kahneman) — the language literally implements slow, deliberate, effortful reasoning by computing in continuous semantic space.

S2 is not a scripting language bolted onto an AI. It is a formal system for reasoning under uncertainty, closer to Prolog than Python, but operating in continuous rather than discrete space. Code compiles to vector operations that execute inside an embedding space the way conventional code compiles to machine instructions that execute on silicon.

## 2. Design Principles

### Fuzzy-by-Default
Uncertainty is the ground truth; precision is the special case. Every value carries implicit confidence. This inverts conventional languages where you have crisp logic and bolt on probabilistic stuff as a library.

### Vectors Are the Only Type
One type: the hypervector. There are no integers, strings, or booleans as primitives. Numbers, symbols, and structures are all represented as vectors in semantic space. Addition is bundling. Multiplication is binding. There are no "wrong type" errors — only noisy or meaningless results. Equality is replaced by similarity.

### Computation Is Geometry
Operations are similarity, projection, interpolation, rotation, scaling. Programs navigate and transform regions of semantic space. The execution environment is fundamentally semantic rather than symbolic — operations have meaning in a way that silicon arithmetic doesn't.

### Commutative
Every object is a vector that can be decomposed with certain operations. The algebraic operations are commutative.

### Long-Range Dependencies
The semantics are too rich and context-dependent for any single file to capture. IDE/MCP tooling is load-bearing, not optional. This is a feature — the tooling becomes part of the language runtime.

## 3. Operations

S2 has two classes of operations: **algebraic** (cheap, native to the vector space, encouraged) and **non-algebraic** (expensive, requiring ANN infrastructure, discouraged but necessary).

### 3.1 Algebraic Operations (Core)

These are the native operations of the vector space. Each is **O(1)** — constant time, operating elementwise on fixed-dimensional vectors.

#### Bundle (Addition)
```
result = a + b
```
Elementwise vector addition. Creates **superposition** — the result is similar to all inputs. This is fuzzy disjunction (OR). Encodes sets, mixtures, "any of these."

Properties: commutative, associative. Signal-to-noise degrades as more items are superposed (a fundamental capacity limit, not a bug).

#### Bind (Multiplication)
```
result = a * b
```
Elementwise multiplication (Hadamard product). The result is **dissimilar to both inputs** — a kind of encryption. Encodes key-value pairs, role-filler structures, relationships.

Properties: commutative, associative, has an approximate inverse (unbind). This is how you attach a role to a filler: `bind(SUBJECT_role, "cat")` creates a structured representation.

#### Unbind (Approximate Inverse of Bind)
```
filler = unbind(role, bound_structure)
```
Given a role vector, extract the approximate filler from a bound structure. This is noisy — the result is close to the original filler but not exact. Noise accumulates with binding depth.

#### Similarity Query
```
score = similarity(a, b)
```
Cosine similarity or dot product. The fundamental "how close are these?" operation. This is how you read results, compare states, and defuzzify.

**Important:** Cosine similarity discards magnitude, which carries information about binding strength and bundling count. Euclidean distance preserves both direction and magnitude. The right metric depends on what you're measuring.

#### Scalar Multiplication
```
result = alpha * v
```
Scales a vector, adjusting its magnitude (confidence/weight) without changing its direction (meaning).

#### Projection
```
result = project(v, subspace)
```
Projects a vector onto a subspace, extracting the component of meaning along certain dimensions. This is how you ask "what does this vector say about X?"

### 3.2 Non-Algebraic Operations (Expensive)

These operations require approximate nearest neighbor (ANN) search infrastructure. They are the bridge between pure algebra and practical computation. All are more expensive than algebraic operations and should be used deliberately.

#### Snap-to-Nearest (Cleanup / Discretization)
```
clean = snap(noisy_vector)
```
ANN search against a codebook of known vectors. Finds the nearest clean vector to a noisy result. This is **error correction** — after a chain of binds and unbinds accumulates noise, snap restores the vector to a known-good state.

This is the operation that makes VSA computation practically viable over long chains. Without it, noise from approximate unbinding compounds until results are meaningless. It is analogous to rounding in floating-point arithmetic, or quantization in signal processing.

**Cost:** O(log n) with good ANN indexing, where n is codebook size. The codebook itself is a design choice — what vectors are "known good" is part of the program's semantics.

#### Cone Traversal (Directed Neighborhood Query)
```
neighbors = cone(origin, direction, angle)
```
From a point in embedding space, define a direction vector and angular spread — a directed cone. Returns all vectors that fall within that cone. This is a **directed neighborhood query**, not flat similarity search.

This is the primary mechanism for **non-algebraic branching and control flow**. Different vector states point the cone in different directions, naturally navigating to different regions of the space. The condition is implicit in the geometry rather than explicit as an if/else.

**Why it matters:** Pure VSA algebra handles local computation well but cannot express many-to-many relationships or conditional navigation through a semantic graph. Cone traversal patches this — it provides the relational topology that algebra alone lacks.

**Cost:** O(log n) with spatial indexing. More expensive than algebraic ops but far cheaper than exhaustive search.

#### Graph Hop
```
destination = hop(origin, relation)
```
Given a starting vector and a relation type, traverse to connected vectors in the semantic graph. This extends cone traversal with typed edges — not just "what's nearby in this direction" but "what's connected by this specific relationship."

**Cost:** Depends on graph indexing. The graph structure isn't fixed ahead of time — the vector state influences which edges get traversed, which is what gives S2 the potential for unbounded computation.

### 3.3 Summary: Algebraic vs. Non-Algebraic

| | Algebraic | Non-Algebraic |
|---|---|---|
| **Operations** | bundle, bind, unbind, similarity, scale, project | snap, cone, hop |
| **Cost** | O(1) | O(log n) |
| **Infrastructure** | None (pure math) | ANN index, codebook, graph |
| **Error behavior** | Noise accumulates | Noise gets corrected |
| **Encouraged?** | Yes — these are the core | Use deliberately — expensive but necessary |
| **Analogy** | Arithmetic on a CPU | Memory access / cache lookup |

The design philosophy: do as much as possible algebraically, use non-algebraic operations only when you need error correction, branching, or relational navigation. This is analogous to keeping computation in registers and only hitting memory when you must.

## 4. Control Flow

### 4.1 Algebraic Conditionals (Fuzzy Branching)
```
result = (condition * branch_true) + (NOT_condition * branch_false)
```
Both branches execute simultaneously via superposition. The condition vector weights which branch dominates the result. Confidence propagates through computation as geometry. This is **O(1)** and purely algebraic.

This is the default and preferred way to branch. It is inherently fuzzy — both branches contribute to the result proportional to the condition's truth value. There is no "wrong branch" — there is a weighted mixture.

### 4.2 Cone Traversal (Non-Algebraic Branching)
When you need discrete navigation — "go here OR there, not a mixture" — cone traversal provides it. The current vector state determines a direction, and the cone finds the appropriate next state in the semantic graph. This is more like a jump table or pattern match than an if/else.

**When to use which:**
- Fuzzy conditional: when both branches are meaningful and you want a weighted blend
- Cone traversal: when you need to navigate to a discrete next state in a graph, resolve a many-to-many relationship, or branch based on relational topology rather than vector similarity

### 4.3 Iteration
The hardest unsolved primitive. Current candidates:
- **Fixed unrolling:** Compile-time expansion of loops to a fixed depth
- **Convergence:** Recurrent application of an operation until similarity between successive states drops below a threshold (the result "stabilizes")
- **State encoding:** Encode loop state as a hypervector, bind the iteration counter, update per step

Iteration interacts with the noise problem — each iteration potentially accumulates error, so snap-to-nearest may be needed between iterations.

## 5. Defuzzification: `is_true`

```
is_true(x)           → scalar in [0, 1]
is_true(is_true(x))  → refined confidence
```

The mechanism for extracting crisp answers from fuzzy computation. `is_true` takes a vector and returns a truth value (similarity to a reference "true" vector, or magnitude, or some learned function).

Recursive application (`is_true(is_true(x))`) allows dialing in confidence at arbitrary granularity. Open design question: does this converge toward 1.0 (certainty attractor), oscillate, or have more complex fixed-point behavior? The answer likely depends on the operator definition and may itself be a tunable parameter.

This is a first-class language concern, not a library afterthought. "How true is this?" is always a valid question in S2.

## 6. Runtime Architecture

### 6.1 S1/S2 Dual Runtime
Mirrors the cognitive architecture:

- **S1 layer:** Fast, cached, pattern-matched execution. Lookup tables, precomputed results, memoized operations. Handles the well-trodden paths.
- **S2 layer:** Deliberate semantic computation. The actual vector-space reasoning. Handles novel inputs and complex chains.

Like TypeScript's type checker running alongside JavaScript execution, S2's semantic layer runs alongside cached fast-path execution. The S1 cache is populated by S2 computation — as patterns recur, they graduate from expensive deliberate reasoning to cheap cached lookup.

### 6.2 MCP Server as Runtime Component
The MCP server is not an IDE add-on. It is part of the runtime:
- Resolves long-range semantic dependencies that no single file can capture
- Holds the semantic context that makes fuzzy vector operations meaningful
- Provides the ANN infrastructure for non-algebraic operations (snap, cone, hop)
- Manages the codebook / cleanup memory
- Handles entity resolution (same surface form → different vectors depending on context)

### 6.3 Empirical Initiation
S2 does not impose algebraic structure on an embedding space. It **discovers** what structure already exists and calibrates to it.

At compile time, the compiler probes a target embedding model's space:
1. Tests whether binding/unbinding work reliably (they do in most naturally-learned spaces)
2. Fits projection matrices that make the space behave like a well-formed VSA
3. Outputs a mapping file (matrices + lookup tables)

The same S2 source code compiles differently for different embedding models, like C compiling for x86 vs ARM. The "instruction set" is the geometry of the target space.

## 7. Type System Considerations

### 7.1 No Wrong Types, Only Noise
There are no type errors in S2. Binding two unrelated vectors produces a result — it's just semantically meaningless (low similarity to anything useful). The type system is replaced by **similarity checking**: "does this result look like what I expected?"

### 7.2 Mixed-Regime Spaces
Not all dimensions need to be the same kind:
- **Binary/ternary dimensions:** Structural roles, categorical membership (crisp)
- **Continuous dimensions:** Similarity, degree, graded properties (fuzzy)
- **Hyperbolic dimensions:** Hierarchical/taxonomic relationships (tree-like)
- **Euclidean dimensions:** Lateral/analogical relationships (flat)

This is speculative but suggests S2's "vector" type could have geometric subtypes reflecting different kinds of semantic structure.

### 7.3 Entity Resolution Is Native
The same symbol in different contexts maps to different vectors. S2 handles this through context-dependent embedding — entity resolution is part of the runtime, not a preprocessing step. The MCP server maintains context for disambiguation.

## 8. Computational Complexity

**Machine-level operations:**
- Algebraic ops (bind, bundle, similarity): O(1) each
- Non-algebraic ops (snap, cone, hop): O(log n) each

**Algorithm complexity** is separate — just as a CPU transistor switching is O(1) but algorithms built on it can be any complexity class, S2 programs can have arbitrary complexity built from O(1) and O(log n) primitives.

**Capacity limits are real and quantifiable:**
- Bundling degrades signal-to-noise as items are superposed (geometric consequence of dimensionality)
- Binding depth accumulates noise through each operation
- Codebook size limits snap-to-nearest resolution
- These limits are a strength — they are predictable, unlike neural net capacity which is opaque

**On VSA and NP problems:** A "perfect embedding" that let you read off NP solutions in polynomial time would itself require exponential resources to construct. The impossibility of such an embedding is provably equivalent to P ≠ NP — same wall, different face.

## 9. Relationship to Prior Work

### VSA / Hyperdimensional Computing
S2 operates at the **algebra level** (VSA), not the engineering level (HDC). S2's formal semantics are defined in terms of algebraic operations over vector spaces. Dimensionality, precision, and hardware are implementation concerns.

Key papers validating the approach:
- Tomkins-Flanagan & Kelly: Turing-complete Lisp interpreter in HRR (VSA variant)
- Smolensky (1990): Tensor product representations for variable binding
- Flanagan et al. 2024: VSA Turing completeness via Cartesian closed categories

### JEPA Connection
S2 can be conceived as an extension to JEPA (Joint Embedding Predictive Architecture) that makes it algebraically structured. The VSA operations formalize what JEPA's learned representations do implicitly. HDC provides explicit compositional structure; JEPA provides learned prediction on top. S2 is the programming interface to this.

### FOL Discovery (This Project)
The embedding-mapping work in this repo proved that embedding spaces encode consistent vector arithmetic (86 predicates as FOL operations, r=0.78 consistency-prediction correlation). This validates S2's core premise: embedding spaces are a viable computational substrate, not just a similarity lookup table.

## 10. Known Defects and Risks

### Embedding Model Pathologies
The mxbai-embed-large diacritic collision bug (documented in `chats/embedding-models-survey.md`) demonstrates that embedding models have silent failure modes. Pathological tokens can hijack attention and corrupt entire embeddings. S2 must include integrity checking — detecting degenerate or corrupted vectors at runtime.

### Noise Accumulation
Without periodic snap-to-nearest, computation degrades over long chains. The tension between algebraic purity (stay in continuous space) and practical reliability (discretize periodically) is a core design challenge.

### Iteration
No clean solution yet. Fixed unrolling limits expressiveness. Convergence-based termination is elegant but hard to guarantee. This is the biggest open problem.

## 11. Open Questions

- **Syntax:** Semantics are solidifying but no concrete syntax yet
- **Iteration:** Which approach (unrolling, convergence, state encoding) works best?
- **`is_true` fixed-point behavior:** Converge, oscillate, or tunable?
- **Mixed-regime dimensions:** How to express geometric heterogeneity in source code?
- **Permutation:** Probably not needed for S2 (it encodes sequence order, but S2 uses relation types instead). Confirm and drop.
- **Cosine vs Euclidean:** When does magnitude matter? Should similarity metric be configurable per operation?
- **Codebook design:** What vectors are "known good"? How is the codebook populated and maintained?

## 12. Abstraction Level

S2 sits between assembly and a high-level language — "C-tier" for vector spaces. The programmer is always aware they're in hypervector space but doesn't manage codebooks manually. You think in terms of binding roles to fillers, superposing alternatives, and querying similarity — not in terms of individual float operations or ANN index parameters.

The compiler handles empirical initiation (probing the target embedding space), codebook management, and ANN infrastructure. The programmer writes in terms of semantic operations.
