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

S2 has three tiers of operations, ordered by cost and abstraction level:

1. **Primitive operations** — scalars, tuples, integer iteration. The scaffolding that isn't vector computation at all.
2. **Algebraic / VSA operations** — bind, bundle, unbind, similarity, projection. The core vector algebra. O(1), pure math, no infrastructure needed.
3. **Non-algebraic / vector-graph operations** — snap-to-nearest, cone traversal, graph hop. All ANN-based, all involve traversal of an HNSW index or similar vector database. Most expensive tier.

### 3.1 Primitive Operations (Scaffolding)

These are not vector operations. They are the conventional computational scaffolding that supports the vector computation. They exist because not everything in a program is a semantic vector operation — sometimes you just need to count to 10 or group two things together.

#### Scalars
```
alpha = 0.7
count = 10
threshold = 0.85
```
Scalars exist in S2 but are **not considered vectors**. They are plain numbers used for:
- Weighting vectors (scalar multiplication: `alpha * v`)
- Thresholds for `is_true` defuzzification
- Loop counters for bounded iteration
- Similarity scores (the output of a similarity query is a scalar)

Scalars are the bridge between the fuzzy vector world and the crisp control world. They are how you extract actionable decisions from continuous computation.

#### Tuples
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

#### Bounded Iteration
```
repeat 10:
    state = bind(transform, state)
    state = snap(state)
```
Integer-based iteration: do something a fixed number of times. The iteration count is a scalar (an integer), not a vector. This sidesteps the unsolved problem of convergence-based termination — you simply specify how many times to loop.

This is the most pragmatic iteration primitive. It composes well with snap-to-nearest (clean up noise every N iterations) and is straightforward to reason about. More sophisticated iteration (convergence-based, state-encoded) may be added later but bounded repetition covers the most common case.

### 3.2 Algebraic / VSA Operations (Core)

These are the native operations of the vector space. Each is **O(1)** — constant time, operating elementwise on fixed-dimensional vectors. No infrastructure required — pure math on vectors.

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
Cosine similarity or dot product. The fundamental "how close are these?" operation. This is how you read results, compare states, and defuzzify. Returns a **scalar**.

**Important:** Cosine similarity discards magnitude, which carries information about binding strength and bundling count. Euclidean distance preserves both direction and magnitude. The right metric depends on what you're measuring.

#### Scalar Multiplication
```
result = alpha * v
```
Scales a vector, adjusting its magnitude (confidence/weight) without changing its direction (meaning). The scalar `alpha` is a primitive; the result is a vector.

#### Projection
```
result = project(v, subspace)
```
Projects a vector onto a subspace, extracting the component of meaning along certain dimensions. This is how you ask "what does this vector say about X?"

### 3.3 Non-Algebraic / Vector-Graph Operations (Expensive)

These operations require approximate nearest neighbor (ANN) search infrastructure — typically an HNSW index or similar vector database. They involve traversal across an indexed vector space. All are significantly more expensive than algebraic operations and should be used deliberately.

The unifying characteristic: **all non-algebraic operations are ANN-based.** They all involve some form of nearest-neighbor search or graph traversal over an indexed collection of vectors. This is what makes them expensive — they hit an external index rather than computing purely on the vectors in hand.

They serve two purposes:
1. **Error correction** — snap-to-nearest cleans up noise from algebraic chains
2. **Navigation** — cone traversal and graph hop provide branching and relational topology that pure algebra cannot express

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

### 3.4 Summary: Three Tiers

| | Primitive | Algebraic (VSA) | Non-Algebraic (Vector-Graph) |
|---|---|---|---|
| **Operations** | scalars, tuples, bounded iteration | bundle, bind, unbind, similarity, scale, project | snap, cone, hop |
| **Operates on** | Numbers, groups of values | Vectors | Vectors + ANN index |
| **Cost** | O(1) | O(1) | O(log n) |
| **Infrastructure** | None | None (pure math) | HNSW index, codebook, graph DB |
| **Error behavior** | Exact | Noise accumulates | Noise gets corrected |
| **Encouraged?** | Use as needed | Yes — the core | Use deliberately — most expensive |
| **Analogy** | Registers, counters | Arithmetic on a CPU | Memory access / cache lookup |

The design philosophy: primitives handle scaffolding (counting, grouping, thresholds), algebraic operations handle the actual semantic computation, non-algebraic operations handle error correction and navigation. Keep as much work as possible in the algebraic tier. Drop to primitives for control. Rise to non-algebraic only when you need to hit the index.

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

## 9. Lambda Calculus Encoding

S2's computational universality claim rests on the ability to encode lambda calculus in VSA. This section documents how that encoding works, where it strains, and what it means for S2.

### 9.1 The Mapping

| Lambda Calculus | VSA Encoding |
|---|---|
| Variable `x` | Atomic hypervector (random, high-dimensional) |
| Abstraction `λx.body` | `bind(VAR_role, x) + bind(BODY_role, encode(body))` |
| Application `(f a)` | `bind(FUNC_role, encode(f)) + bind(ARG_role, encode(a))` |
| Variable reference `x` | The atomic vector `x` itself |

Lambda terms are encoded as **trees in superposition**. Each node bundles its role-tagged children:

```
encode(App(f, a)) = bind(FUNC_role, encode(f)) + bind(ARG_role, encode(a))
encode(Lam(x, b)) = bind(VAR_role, encode(x)) + bind(BODY_role, encode(b))
encode(Var(x))    = x    # atomic vector, no further structure
```

To read back a component, unbind with the role vector:

```
unbind(FUNC_role, encode(App(f, a))) ≈ encode(f)    # approximate!
unbind(ARG_role, encode(App(f, a)))  ≈ encode(a)
```

The role vectors (`VAR_role`, `BODY_role`, `FUNC_role`, `ARG_role`) are fixed random vectors chosen at initialization. They act like field names in a struct — binding a role to a filler is like setting a field, unbinding is like reading one.

### 9.2 The Substitution Problem

Beta reduction — the core computation step of lambda calculus — requires substitution: replace every occurrence of variable `x` in `body` with argument `a`. This is the hard part.

In symbolic lambda calculus, substitution is a tree walk: find every leaf labeled `x`, replace it with `a`. In VSA, the problem is fundamentally different: occurrences of `x` are not localized in the superposed vector. The variable `x` is bound into the structure at encoding time and cannot be found by scanning — it's entangled with the roles and other fillers.

**This is equivalent to the binding problem in cognitive science.** How do you update one slot of a distributed representation without corrupting the others? Strategies explored:

1. **Cleanup memory approach:** Decode the entire tree back to symbolic form, perform substitution symbolically, re-encode. This works but defeats the purpose — you're leaving vector space to do the hard part.

2. **Depth-aware mapping:** Encode binding depth as part of the role vector (e.g., `bind(VAR_role, bind(DEPTH_2, x))`). Substitution becomes: unbind at the target depth, rebind with the new value. Noise compounds with depth.

3. **Fixed-point / resonance:** Define substitution as a constraint satisfaction problem — the reduced form is an attractor in vector space. Iterate the operation until the representation stabilizes. Elegant but convergence is not guaranteed.

4. **Sequential tree rebuilding:** Walk the tree layer by layer, rebuilding each level with the substitution applied. Requires snap-to-nearest between layers to prevent noise accumulation.

### 9.3 De Bruijn Indices

Named variables create scoping headaches in VSA (alpha-equivalence requires renaming, which requires finding and replacing — back to the substitution problem). **De Bruijn indices** replace variable names with positional numbers:

```
λx. λy. x    becomes    λ. λ. 2
λx. λy. y    becomes    λ. λ. 1
```

This maps naturally to VSA: instead of binding a variable name to a role, you bind a **depth counter**. The index is a permutation or shift operation on a fixed "pointer" vector. Substitution becomes: shift all indices, replace index 1 with the argument.

This eliminates the naming/scoping problem entirely but substitution still requires the shift+replace operations, which accumulate noise.

### 9.4 Smolensky's Tensor Product Representations

Smolensky (1990) provides the theoretical foundation. A variable binding `role:filler` is a **tensor product** `role ⊗ filler`. A structure with multiple bindings is a sum of tensor products:

```
structure = (role_1 ⊗ filler_1) + (role_2 ⊗ filler_2) + ...
```

Unbinding is contraction with the role vector. In the exact (infinite-dimensional) case, this recovers the filler perfectly. In the approximate (finite-dimensional) case — which is what VSA and S2 actually use — it recovers the filler plus noise proportional to the other terms.

The key insight: **the unbinding problem is formally equivalent to the substitution step in beta reduction.** If you can cleanly unbind, you can cleanly substitute. Both are limited by the same noise floor. This connects the practical engineering question (how noisy is unbinding?) to the theoretical question (can VSA compute arbitrary functions?).

### 9.5 Tomkins-Flanagan & Kelly: Running Lisp in Vectors

The existence proof. Tomkins-Flanagan and Kelly built a **working Lisp 1.5 interpreter** using Holographic Reduced Representations (an HRR-based VSA). It implements:

- Variable binding via role-filler pairs
- Substitution (beta reduction) via unbind-rebind cycles
- Alpha renaming to avoid variable capture
- Recursive evaluation of nested expressions

This is not a theoretical argument — it actually runs. Lambda terms go in, reduced results come out. The catch: it relies heavily on **cleanup memory** (snap-to-nearest) after every reduction step to prevent noise accumulation from destroying the computation. Without cleanup, the interpreter degrades after a few reduction steps.

**What this means for S2:** Lambda calculus semantics are implementable in vector space. The price is mandatory periodic cleanup (snap-to-nearest). Pure algebraic computation without cleanup is limited to short chains. This is why snap-to-nearest is a core non-algebraic operation in S2, not an optimization — it's load-bearing for any computation deeper than a few steps.

### 9.6 Implications for S2

VSA gives you a **memory format** for lambda terms. Lambda calculus gives you the **rewrite rules**. The challenge is making the rewrite rules work inside the memory without unpacking back to symbolic form.

S2's position: accept that deep computation requires periodic cleanup (snap-to-nearest), design the language so that cleanup points are explicit and predictable (like memory barriers in concurrent programming), and optimize the algebraic chains between cleanup points for maximum depth before noise becomes problematic.

## 10. Turing Completeness

### 10.1 The Cartesian Closed Category Argument

Flanagan et al. (2024), "Hey Pentti, We Did It!", constructs a VSA encoding of Lisp 1.5 and argues Turing completeness via **Cartesian closed categories (CCCs)**.

A CCC requires:
1. **Terminal object** — a distinguished "unit" element
2. **Products** — you can pair any two objects (bundling)
3. **Exponentials (function objects)** — you can represent functions as objects (lambda abstraction encoded as bound structures)
4. **Evaluation morphism** — you can apply a function object to an argument (beta reduction via unbind-rebind)

The **Curry-Howard-Lambek correspondence** equates:
- CCCs ↔ typed lambda calculi ↔ intuitionistic logic
- If your system is a CCC, it is Turing-complete (modulo the usual caveats about recursion/fixed points)

Flanagan et al. argue that VSA with cleanup memory forms a CCC: bundling gives products, binding gives exponentials, unbinding gives evaluation. The Lisp interpreter is the constructive proof.

### 10.2 What Was Actually Proven (and What Wasn't)

**What holds:**
- The Lisp interpreter works. Lambda terms are encoded, reduced, and read back correctly.
- The CCC structure is real — the algebraic operations satisfy the categorical axioms.
- The construction is elegant and the framing is mathematically sophisticated.

**What's strained:**
- **Cleanup memory does the heavy lifting.** The boundary between "the VSA computing" and "the cleanup lookup table computing" is not formalized. If you count the cleanup codebook as part of the VSA, you're arguably just doing symbolic computation with a vector-space cache. If you don't count it, the VSA alone can't sustain computation past a few steps.
- **Fixed dimensionality vs. unbounded computation.** A Turing machine's tape is unbounded. A VSA vector has fixed dimensionality. Encoding potentially infinite information into a fixed-dimensional space requires either: (a) secretly growing dimensionality (which makes it not a fixed VSA), or (b) accepting hard capacity limits on computation depth/breadth. The CCC argument sidesteps this by not addressing it.
- **Approximate retrieval vs. exact state transitions.** Turing completeness requires that each computation step produces an exact next state. VSA unbinding produces an approximate result. Over unbounded computation, approximation errors compound to certainty of corruption. Cleanup memory patches this, but cleanup is itself a non-algebraic operation that depends on the codebook being complete — and a complete codebook for arbitrary computation is itself unbounded.

**The honest assessment:** VSA is Turing-complete in the same sense that floating-point arithmetic is "real number arithmetic" — it works for all practical purposes within its precision limits, with periodic rounding (cleanup) to stay on track. The theoretical gap between "works for all practical chains we've tested" and "provably computes any Turing-computable function" is real but may not matter for S2's purposes.

### 10.3 The Two Fundamental Obstacles

1. **Fixed dimensionality.** A 10,000-dimensional vector can superpose a limited number of items before signal-to-noise degrades below usefulness. This limit is quantifiable (it scales roughly as √d for bundling, where d is dimensionality) but it is hard. You cannot represent an unbounded tape in a fixed-dimensional space.

2. **Approximate retrieval.** Unbinding returns the nearest vector, not the exact one. Each operation introduces noise proportional to the other items in the superposition. Over a long chain, errors compound geometrically. Cleanup (snap-to-nearest) resets the error but requires a codebook that contains the correct answer — which presupposes you know what the correct answer is.

### 10.4 The Non-Algebraic Patch

This is where S2's non-algebraic operations (snap, cone, hop) become load-bearing for the Turing completeness argument:

- **Snap-to-nearest** provides error correction, allowing computation chains to extend beyond the algebraic noise limit
- **Cone traversal** provides conditional branching that isn't limited by superposition capacity
- **Graph hop** provides unbounded memory via an external graph structure — the vector state navigates the graph, which can grow without bound

The graph structure isn't fixed ahead of time — the vector state influences which edges get traversed. New nodes and edges can be created during computation. This is the mechanism that patches fixed-dimensionality: the vectors do local computation, the graph provides unbounded external memory. It's analogous to a CPU (fixed registers) with RAM (unbounded, addressable memory).

**S2's Turing completeness claim is: VSA algebra + ANN-backed non-algebraic operations + external graph = Turing complete.** The algebra alone is not. This is an honest and architecturally clean position.

## 11. JEPA Hybrid Architecture

### 11.1 The HDC-JEPA Connection

Hyperdimensional Computing (HDC) and Joint Embedding Predictive Architecture (JEPA) both operate in high-dimensional representational spaces where **similarity is the core currency of computation**. Both avoid pixel/token-level reconstruction in favor of abstract representations.

The differences are complementary:
- **HDC** has explicit algebraic structure (bind, bundle, release) but learns nothing — the operations are fixed by design
- **JEPA** learns rich representations but has no explicit compositional structure — the algebra is implicit in the weights

S2 proposes a hybrid: HDC's algebraic structure as an **explicit compositional prior** on JEPA's learned embeddings. The algebra isn't imposed externally — it's a formalization of structure the model has already learned implicitly. The FOL discovery work in this repo validates this: embedding spaces do encode consistent vector arithmetic for semantic relationships, without being told to.

### 11.2 Two-Phase Training

The proposed training architecture for an S2-native model:

**Phase 1 — Algebraic consistency training.** Train the model so its embedding space respects VSA axioms: binding produces vectors dissimilar to inputs, unbinding approximately recovers fillers, bundling creates superpositions that are similar to all components. This doesn't replace the model's learned representations — it regularizes them so algebraic operations work reliably.

**Phase 2 — Predictive coding on structured space.** Once the embedding space has algebraic structure, train JEPA-style prediction on top. The predictor learns relationships between **structured representations**, not between unstructured blobs. This should produce more compositionally generalizable predictions.

The key: Phase 1 gives you a space you can compute in. Phase 2 gives you a model that reasons about the structure of that space. S2 programs operate in the space; the JEPA predictor is what makes novel inference possible.

### 11.3 Mixed-Regime Latent Spaces

Not all dimensions of an embedding need to behave the same way. A more expressive architecture uses **mixed-regime** dimensions:

- **Binary/ternary dimensions** for structural/symbolic facts: Is this a noun or a verb? Is this entity a member of this class? These are inherently discrete and benefit from hard values. A binding operation might have a binary role slot but a continuous filler.
- **Continuous dimensions** for graded/sensory facts: How similar are these? How confident am I? What's the degree of this property? These are inherently fuzzy and should stay continuous.

The binding operation itself could be mixed-regime: the role is binary (which slot?), the filler is continuous (what value?). This captures the intuition that structure is crisp but content is graded.

### 11.4 Staged Commitment

Binary dimensions don't start binary. During training, they begin as **soft continuous values** and gradually anneal toward hard 0/1 values. Structure "crystallizes" over time as the model becomes more confident about categorical distinctions.

This mirrors human cognitive development — early representations are diffuse and become more structured with experience. It also provides a natural training curriculum: the model first learns continuous similarity structure, then gradually commits to discrete categorical structure on top of it.

**Relevance to `is_true`:** The staged commitment process is the training-time analog of S2's runtime `is_true` defuzzification. During training, dimensions gradually defuzzify from continuous to binary. During inference, `is_true` explicitly defuzzifies a continuous truth value to a discrete judgment. Same operation, different timescales.

### 11.5 Product Manifold Embeddings

Going further than mixed-regime dimensions: different **geometric types** for different kinds of semantic structure:

- **Hyperbolic dimensions** for hierarchical/taxonomic relationships. Hyperbolic space naturally represents trees — distance from the origin corresponds to depth, and the exponentially growing circumference at each radius provides room for branching. "Dog is-a animal" is a hierarchical relation that lives naturally in hyperbolic space.
- **Euclidean dimensions** for lateral/analogical relationships. "King is-to queen as man is-to woman" is a parallelogram relation that lives naturally in flat Euclidean space.
- **Spherical dimensions** for cyclical/periodic relationships. Time of day, seasons, cardinal directions — these wrap around and live naturally on spheres.

A **product manifold** embedding combines these: some dimensions are hyperbolic, some Euclidean, some spherical. The geometry itself becomes the knowledge representation. An entity's position in the hyperbolic subspace encodes where it sits in a taxonomy; its position in the Euclidean subspace encodes its analogical relationships.

**Relevance to S2:** This suggests that S2's "vector" type could have geometric subtypes. A projection onto the hyperbolic subspace asks "where does this sit in the hierarchy?" A projection onto the Euclidean subspace asks "what is this analogous to?" Different operations would be natural in different subspaces. This is speculative but architecturally interesting — it means the type of a vector isn't just its dimensionality but its geometry.

## 12. The Inquisitiveness/Perceptiveness Parameter

### 12.1 The Concept

A novel attention mechanism variant discovered during S2 design conversations. Standard scaled dot-product attention is:

```
Attention(Q, K, V) = softmax(QK^T / √d) V
```

The inquisitiveness/perceptiveness variant adds a second term:

```
Attention(Q, K, V, α) = softmax(QK^T / √d + α · S(Q, K)) V
```

Where:
- `S(Q, K)` is a **surprisingness function** — how unexpected each key is relative to the query context
- `α ∈ [-1, 1]` is the **perceptiveness parameter** — controls sensitivity to surprising/outlier keys

### 12.2 What α Does

- **α > 0 (inquisitive):** Amplifies attention to surprising, unexpected keys. The model actively seeks out outliers and novel information. Useful for exploration, creative reasoning, anomaly detection.
- **α = 0 (neutral):** Standard attention. No surprisingness bias.
- **α < 0 (conservative):** Suppresses attention to surprising keys. The model ignores outliers and sticks to expected, familiar patterns. Useful for stable, predictable execution.

### 12.3 Orthogonality to Temperature

This is **not** the same as temperature scaling. Temperature scales the entire attention distribution uniformly — high temperature makes everything more uniform, low temperature makes everything more peaked. Perceptiveness **selectively** amplifies or suppresses the tail of unexpected keys without affecting the core distribution.

This creates a **2D behavioral space** (temperature × perceptiveness) with four distinct regimes:

| | Low Temperature | High Temperature |
|---|---|---|
| **High α (inquisitive)** | Sharply focused on the most surprising key | Diffuse attention but biased toward novelty |
| **Low α (conservative)** | Sharply focused on the most expected key | Diffuse attention biased toward familiarity |

Each extreme has characteristic failure modes:
- High temp + high α: distracted, chasing every novelty
- High temp + low α: blandly averaging everything familiar
- Low temp + high α: fixated on a single outlier (potentially hallucinating)
- Low temp + low α: stuck in a rut, ignoring all new information

### 12.4 Geometric Surprisingness

The surprisingness function can be computed cheaply and geometrically:

```
S(K)_i = ||K_i - mean(K_1, ..., K_{i-1})||
```

The distance of each key from the running mean of all previous keys. This is:
- **Cheap:** One subtraction and one norm per key, computed causally
- **No extra parameters:** Uses only the existing key vectors
- **Geometrically meaningful:** Surprisingness is literally "how far is this from what I've seen before?" in embedding space
- **Causal:** Only looks at preceding keys (compatible with autoregressive models)

### 12.5 Relevance to S2

The perceptiveness parameter is a concrete example of the kind of **tunable fuzzy control knob** that S2 should support as a first-class construct. In S2 terms:

- It's a parameterized transformation over attention distributions
- The parameter controls a continuous behavioral spectrum (not a binary switch)
- The underlying computation is geometric (distance from running mean)
- It's composable — you could have different α values for different layers, attention heads, or even different parts of a single computation

This is also a proof-of-concept that novel computation can be designed by **thinking geometrically about what attention means** rather than just optimizing benchmarks. S2's design philosophy encourages this kind of geometric reasoning about operations.

**Proposed as inference-time only** — no retraining needed. You can adjust α at runtime to change the model's reasoning strategy, which maps to S2's philosophy that runtime behavior should be tunable without recompilation.

## 13. Entity Resolution and Active Retrieval

### 13.1 The Fidelity Mismatch Problem

Current RAG (Retrieval-Augmented Generation) pipelines have a fundamental architectural flaw: frontier LLMs have rich contextual embeddings that resolve polysemy (river bank vs. financial bank), but the retrieval step uses a separate, weaker embedding model. The retrieval model doesn't have the context that the generation model has. This is a **fidelity mismatch** — the dumb retriever fetches documents for the smart generator, but the retriever doesn't understand the query the way the generator does.

Example: The LLM, mid-reasoning about financial regulations, has internally resolved "bank" to mean "financial institution." But the retrieval embedding model, seeing "bank" in isolation, returns documents about river banks, blood banks, and actual banks with roughly equal relevance. The LLM then has to re-disambiguate from the retrieved context, wasting capacity and risking confusion.

### 13.2 The Canonicalization Endpoint

Proposed solution: LLMs should expose a **canonicalization endpoint**. Given a span of text in context, return a stable identifier or coordinate for the resolved entity — not just a raw embedding.

```
canonicalize("bank", context="The Federal Reserve regulates banks...")
→ Q22687 (Wikidata: "bank" as financial institution)
   or: a stable vector in a canonical entity space
```

This would be more useful than raw internal embeddings because:
- It's **auditable** — you can check what the model thinks "bank" means
- It's **stable** — the same entity in different phrasings maps to the same ID
- It's **interoperable** — different models can agree on entity identity via shared identifiers

### 13.3 Active Retrieval During Inference

The deeper proposal: retrieval shouldn't be a separate preprocessing step. The model's **evolving internal state during inference** should drive retrieval in real time.

Instead of: `embed query → retrieve docs → feed to LLM → generate`

It should be: `LLM starts reasoning → internal state drives retrieval → retrieved context updates internal state → reasoning continues with new context → more retrieval if needed → ...`

The disambiguation happens **before retrieval, inside the same process**. The model's mid-reasoning representation of "bank" (already resolved to financial institution by context) is what queries the index. The retrieval system sees the resolved representation, not the ambiguous surface form.

This is architecturally hard because nearest-neighbor search over a large corpus isn't differentiable in a way that's easy to integrate into a forward pass. Existing work (REALM, RAG-token model, memory-augmented transformers) tackles this but it's genuinely difficult to make efficient. The two-stage pipeline exists partly because it's the tractable approximation.

### 13.4 How This Maps to S2

Entity resolution is a **core S2 operation**, not a library function. In embedding space, the same surface form maps to different vectors depending on context. S2 must handle this natively.

The MCP server architecture is S2's version of active retrieval during inference:
- The MCP server holds **semantic context** that the S2 runtime uses to resolve ambiguous references
- Resolution happens in real time during computation, not as a preprocessing step
- The server maintains a **running model of what entities are in scope** and what they resolve to in the current context
- This is why the MCP server is part of the runtime, not an add-on — without it, entity resolution would require leaving vector space to do symbolic lookup

The canonicalization endpoint concept maps to a potential S2 built-in:

```
resolved = canonicalize(ambiguous_vector, context_vector)
```

This would be a non-algebraic operation (it requires ANN lookup against an entity codebook, informed by context) but a very commonly needed one — more common than cone traversal or graph hop.

## 14. Embedding Model Pathologies

### 14.1 The mxbai-embed-large Diacritic Bug

During development of the FOL discovery system in this repo, a major defect was discovered in mxbai-embed-large (the 1024-dimensional embedding model used as S2's initial substrate). Diacritic characters — specifically macron vowels (ō, ū, etc.) used in Japanese romanization — cause **catastrophic embedding collapse**.

### 14.2 The Mechanism: Attention Sink

The bug is not a simple out-of-vocabulary collapse. The pathological token has a **high-magnitude key vector** that dominates the attention mechanism:

1. The diacritic character tokenizes to a token with an unusually high-magnitude key vector
2. During the attention computation, this high-magnitude key attracts disproportionate attention from all query vectors
3. The attention distribution collapses — nearly all attention weight goes to the pathological token
4. All other tokens' representations get overwritten by the pathological token's value vector
5. The final embedding (which pools over all token positions) is dominated by the single pathological token

The result: completely unrelated strings containing diacritic characters produce nearly identical embeddings (cosine similarity > 0.95). The model produces **confident-looking but completely corrupted** embeddings — there is no error signal, no NaN, no obvious failure. The embeddings look normal until you check that "Shintō shrine architecture" and "Tōkyō ramen restaurant" have cosine similarity 0.98.

### 14.3 Blast Radius

Any text containing diacritic characters is affected:
- **Japanese romanization** (rōmaji): shrine names, place names, historical terms
- **Polynesian languages**: Hawaiian, Māori, Samoan — macron vowels are standard orthography
- **Academic/linguistic text**: IPA transcriptions, transliterations, medieval manuscript studies
- **Music**: tempo markings, non-English musical terms

This is not a niche issue. Entire languages and academic fields are silently broken.

### 14.4 Model-Specific

The bug is **mxbai-specific**. The same texts embedded with OpenAI's text-embedding-3-small, nomic-embed-text, or BGE-large produce correct, discriminating embeddings. The pathological attention sink behavior points to either:
- A training data issue (diacritic characters underrepresented or corrupted in training)
- A tokenizer issue (pathological tokenization of diacritic characters)
- An architectural issue (no attention sink mitigation in the model design)

The exact cause is unknown but the defect is reliably reproducible.

### 14.5 Implications for S2

This is a **foundational risk** for S2. If the computational substrate has silent corruption modes, all computation built on it is unreliable in ways that are invisible without explicit checking.

S2 must include:

1. **Substrate validation at empirical initiation time.** When S2 probes a target embedding space, it should test for known pathologies (attention sinks, degenerate dimensions, collapse modes). A model that fails validation should be rejected as a substrate.

2. **Runtime integrity checking.** Vectors produced by computation should be periodically checked for degeneracy — unexpectedly high magnitude, unexpectedly high similarity to unrelated vectors, collapse to a low-dimensional subspace. These are symptoms of substrate pathology propagating into computation.

3. **Substrate abstraction.** S2 programs should be substrate-agnostic — the same program runs on any embedding model that passes validation. If mxbai has a defect, swap to nomic or BGE without changing the program. This is already part of the design (empirical initiation produces different mappings for different models) but the pathology risk makes it load-bearing rather than just convenient.

4. **Defensive codebook design.** The snap-to-nearest codebook should be tested for collision sensitivity — if two unrelated codebook entries are unusually close in the substrate space (possibly due to a diacritic-style collapse), flag it.

## 15. Empirical Initiation (Expanded)

### 15.1 The Core Idea

S2 does not assume any embedding space has the right algebraic properties. It **probes and calibrates** at compile time. This is called empirical initiation — the compiler characterizes the target space before generating code for it.

The analogy: C compiles differently for x86 and ARM because the instruction sets are different. S2 compiles differently for mxbai-embed-large and nomic-embed-text because the geometric properties are different. The "instruction set" is the geometry of the target space.

### 15.2 The Probing Process

**Step 1 — Test algebraic operations.**
- Generate random vectors in the target space
- Test binding: does `a * b` produce a vector dissimilar to both `a` and `b`?
- Test unbinding: does `unbind(a, a * b) ≈ b`? How much noise?
- Test bundling: does `a + b` produce a vector similar to both `a` and `b`?
- Test capacity: how many items can be bundled before signal-to-noise drops below a usable threshold?
- Measure noise characteristics: Gaussian? Uniform? Correlated with input?

**Step 2 — Fit correction matrices.**
Naturally learned embedding spaces are not perfect VSA spaces. The algebraic operations work (this is the core finding from the FOL discovery work) but they work approximately. Empirical initiation fits **projection matrices** that improve algebraic fidelity:
- A matrix that rotates the space so binding produces maximally dissimilar outputs
- A matrix that projects onto the subspace where unbinding is most accurate
- A normalization that makes bundling capacity predictable

These matrices are specific to the target embedding model. They are the "compiled" form of S2's adaptation to a specific substrate.

**Step 3 — Build the mapping file.**
Output: a binary artifact containing:
- The correction matrices from Step 2
- Noise characterization (expected error per operation, capacity limits)
- Known pathologies detected during probing (degenerate dimensions, attention sinks)
- Codebook initialization (if applicable)

This mapping file is the S2 equivalent of a compiled binary. The same S2 source code + different mapping files = same program running on different embedding substrates.

### 15.3 What "Same Source, Different Targets" Means

A concrete example:

```s2
result = bind(AGENT_role, "cat") + bind(ACTION_role, "sit") + bind(LOCATION_role, "mat")
agent = unbind(AGENT_role, result)
# agent ≈ embedding("cat")
```

On mxbai-embed-large (1024-dim):
- Vectors are 1024-dimensional float64
- Binding noise is ~0.15 cosine distance per operation
- Bundling capacity is ~12 items before SNR < 3
- Correction matrix rotates by ~7° to improve unbinding accuracy
- Known diacritic pathology: flag inputs containing macron characters

On nomic-embed-text (768-dim):
- Vectors are 768-dimensional float64
- Binding noise is ~0.12 cosine distance per operation
- Bundling capacity is ~9 items (lower dimensionality = less capacity)
- Correction matrix is different (different geometry)
- No known pathologies

The S2 source code is identical. The mapping file handles the differences. The programmer writes semantic operations; the compiler generates substrate-specific code.

### 15.4 Validation Gates

Empirical initiation should include **validation gates** — minimum requirements a substrate must meet:

- Binding dissimilarity: `similarity(a, a*b) < threshold` (the binding actually encrypts)
- Unbinding accuracy: `similarity(b, unbind(a, a*b)) > threshold` (you can recover fillers)
- Bundling capacity: at least N items before SNR drops below usability
- No catastrophic pathologies detected (attention sinks, degenerate dimensions)

A substrate that fails validation is rejected. The compiler refuses to generate code for it. This is S2's equivalent of a platform compatibility check.

## 16. VSA Mathematical Grounding

### 16.1 VSA Is Algebra, HDC Is Engineering

A critical distinction that S2's documentation must maintain:

- **Vector Symbolic Architecture (VSA)** is the algebra — the formal mathematical framework defining operations (bind, bundle, similarity) and their properties over high-dimensional vector spaces. It is as rigorous as Boolean algebra or linear algebra.
- **Hyperdimensional Computing (HDC)** is the engineering application — specific choices about dimensionality (10,000? 100,000?), vector type (binary? bipolar? continuous?), specific tasks (classification? retrieval? reasoning?), hardware implementation.

The relationship is: **Boolean algebra is to digital circuits as VSA is to HDC.** Boolean algebra defines AND, OR, NOT and their properties. Digital circuit design uses those operations to build useful things. VSA defines bind, bundle, similarity and their properties. HDC uses those operations to build useful things.

S2 operates at the VSA level. Its semantics are defined in terms of algebraic operations. The specific dimensionality, embedding model, and hardware are implementation details handled by empirical initiation.

### 16.2 Concentration of Measure

The mathematical foundation that makes VSA work is **concentration of measure** in high-dimensional spaces. This is not empirical hand-waving — it is a proven mathematical phenomenon:

- In high-dimensional space (d > 1000), randomly sampled vectors are **almost certainly nearly orthogonal**. The probability that two random unit vectors have cosine similarity > ε decreases exponentially with dimensionality.
- This means thousands of random vectors can coexist in the same space without significant interference. Each one is approximately orthogonal to all the others.
- Bundling (addition) of k vectors produces a result that is approximately `1/√k` similar to each component. This is predictable and quantifiable.
- Binding (elementwise multiplication) of two vectors produces a result that is approximately orthogonal to both inputs. This is the "encryption" property.

These properties are **theorems**, not empirical observations. They follow from the geometry of high-dimensional spheres and the law of large numbers.

### 16.3 The Eight Axioms

S2's computational substrate must satisfy the eight axioms of a real vector space. LLM embedding spaces do, because they are subsets of ℝⁿ:

1. **Commutativity of addition:** u + v = v + u
2. **Associativity of addition:** (u + v) + w = u + (v + w)
3. **Additive identity (zero vector):** There exists 0 such that v + 0 = v
4. **Additive inverse:** For every v, there exists -v such that v + (-v) = 0
5. **Multiplicative identity:** 1 · v = v
6. **Associativity of scalar multiplication:** α(βv) = (αβ)v
7. **Distributivity over vector addition:** α(u + v) = αu + αv
8. **Distributivity over scalar addition:** (α + β)v = αv + βv

Because S2 operates in a real vector space, it inherits the **entire toolkit of linear algebra** for free: subspaces, bases, dimension, linear maps, eigendecomposition, projections, orthogonal complements. These are all valid S2 operations because the substrate satisfies the axioms.

The abstraction is powerful: S2 programs work regardless of what the vectors "actually are" — Wikidata entities, English words, protein sequences, user behavior embeddings. If the space satisfies the axioms and passes empirical initiation, S2 can compute in it.

### 16.4 Embeddings Are Domain-Agnostic

S2's vectors should not be conceived as "word embeddings" or "text embeddings." Embeddings are a general technique for mapping **any discrete categorical input** into dense continuous vector space:

- Words and subwords (NLP)
- User IDs and product IDs (recommender systems)
- Graph nodes (knowledge graphs, social networks)
- Amino acid sequences (protein structure prediction)
- Board states (game playing)
- Sensor readings discretized into categories (IoT)

The embedding matrix is **learned jointly** with the rest of the network — gradients flow back through the model into the embedding weights, shaping how meanings get encoded. This is why embedding spaces have algebraic structure: the training process optimizes for relationships between entities, and those relationships manifest as geometric regularities.

S2 can in principle operate in any of these embedding spaces. The substrate is not "language" — it's "learned dense representations of structured domains." This broadens S2's applicability far beyond NLP.

## 17. Concrete Compute Savings and Benchmarks

### 17.1 Adjacent Domain Benchmarks

No direct benchmarks exist for "VSA as programming language substrate" because S2 is novel. But adjacent domains provide reference points for the magnitude of speedups from vectorized symbolic computation:

**Vector Chains of Recurrences (VCR):**
- 2x to 10x speedup over scalar Chains of Recurrences and Intel SVML (Short Vector Math Library)
- These are vectorized symbolic computation over polynomial recurrence relations — not VSA per se, but the same principle of doing symbolic work in vector form

**Diospyros compiler (Cornell):**
- 3.1x average speedup over hand-optimized DSP library implementations
- Automatically synthesizes vectorized linear algebra kernels
- Demonstrates that compiler-automated vectorization can beat human-optimized code

**Hash consing in JuliaSymbolics:**
- Up to 3.2x computation speedup
- 2x memory reduction
- 5x faster code generation
- This is symbolic computation optimization via structural sharing — relevant because S2's VSA encoding of lambda terms is conceptually similar (shared structure via binding)

**VSA-based ARC-AGI solver:**
- Outperforms GPT-4 on a subset of ARC benchmarks
- At a tiny fraction of computational cost (hypervector operations on CPU vs. billions of parameters on GPU)
- But: comparisons are fuzzy, the ARC subset is cherry-picked, and the VSA solver handles a narrow class of pattern-matching tasks

### 17.2 The Missing Benchmark

There is a surprising gap in the literature: **systematic FLOPS-saved benchmarks for "symbolic simplification before numerical evaluation"** are essentially absent. Everyone knows that simplifying `x * 0` to `0` before evaluating saves a multiply, but nobody has systematically measured how much compute is saved by symbolic preprocessing across a representative workload.

This matters for S2 because one of S2's potential use cases is exactly this: perform algebraic simplification in vector space before executing expensive numerical computation. If the savings are 2x-10x (as VCR and Diospyros suggest), S2 has a clear practical value proposition beyond its theoretical interest.

### 17.3 What S2 Needs to Prove

For S2 to have a credible compute savings story, it needs benchmarks showing:
1. A task that takes X compute with conventional computation
2. The same task takes Y compute with S2's VSA operations
3. X/Y > 1, ideally by a significant factor
4. The comparison is fair (same task, same accuracy, same hardware)

The most promising candidate tasks:
- Semantic search with algebraic pre-filtering (narrow the search space via binding/unbinding before doing expensive ANN)
- Compositional reasoning chains (multi-hop inference via vector arithmetic instead of multiple LLM calls)
- Structured prediction with known algebraic regularities (exploit the FOL-like structure discovered in embedding spaces)

## 18. Known Defects and Risks

### 18.1 Noise Accumulation
Without periodic snap-to-nearest, computation degrades over long chains. The tension between algebraic purity (stay in continuous space) and practical reliability (discretize periodically) is a core design challenge. Every snap-to-nearest is an admission that the algebra alone isn't enough — but without them, the algebra produces garbage after a few steps.

### 18.2 Iteration
No clean solution yet. Fixed unrolling limits expressiveness. Convergence-based termination is elegant but hard to guarantee. State encoding with counter binding is the most VSA-native approach but accumulates noise per iteration. This is the biggest open problem.

### 18.3 Substrate Pathologies
Documented in detail in section 14. The computational substrate can have silent failure modes that propagate into all computation built on it. Empirical initiation with validation gates is the mitigation.

### 18.4 Cleanup Memory Circularity
Snap-to-nearest requires a codebook of "correct" vectors. But for arbitrary computation, the set of correct intermediate results is not known in advance. The codebook must either be (a) precomputed for a specific problem domain (limiting generality), (b) grown during computation (requiring a policy for when to add entries), or (c) universal (impractically large). This is the circularity at the heart of the Turing completeness argument.

### 18.5 Permutation May Be Unnecessary
VSA traditionally includes permutation (cyclic shift) as a third operation alongside binding and bundling, used to encode sequential order. In S2, sequential/positional relationships are more naturally encoded via relation types (binding with a POSITION_role) rather than permutation. Permutation is also not differentiable (it's a discrete operation) which makes it awkward in continuous embedding spaces. Current assessment: probably drop permutation from S2, use relation-typed binding instead. This is an open question pending more design work.

## 19. Open Questions

- **Syntax:** Semantics are solidifying but no concrete syntax yet. The syntax needs to make algebraic vs. non-algebraic operations visually distinct so programmers can see where the expensive ops are.
- **Iteration:** Which approach (unrolling, convergence, state encoding) works best? Likely task-dependent — may need all three as options.
- **`is_true` fixed-point behavior:** Converge, oscillate, or tunable? Needs formal analysis and empirical testing.
- **Mixed-regime dimensions:** How to express geometric heterogeneity (hyperbolic, Euclidean, spherical) in source code? This may require a richer type system than "everything is a vector."
- **Permutation:** Probably not needed for S2. Confirm and drop.
- **Cosine vs Euclidean:** When does magnitude matter? Should similarity metric be configurable per operation?
- **Codebook design:** What vectors are "known good"? How is the codebook populated, maintained, and grown during computation?
- **α parameter integration:** How does the inquisitiveness/perceptiveness parameter generalize beyond attention? Could similar tunable behavioral parameters exist for other operations?
- **Canonicalization semantics:** What does `canonicalize(v, context)` return exactly? A codebook vector? A Wikidata QID? A point in a canonical entity space? All three?
- **Training pipeline:** How to train a model that produces S2-friendly embedding spaces (Phase 1 + Phase 2 from section 11)?
- **Benchmark suite:** What tasks should S2 be benchmarked on to demonstrate practical value?

## 20. Abstraction Level

S2 sits between assembly and a high-level language — "C-tier" for vector spaces. The programmer is always aware they're in hypervector space but doesn't manage codebooks manually. You think in terms of binding roles to fillers, superposing alternatives, and querying similarity — not in terms of individual float operations or ANN index parameters.

The compiler handles:
- Empirical initiation (probing the target embedding space, fitting matrices)
- Codebook management (building, maintaining, growing the snap-to-nearest codebook)
- ANN infrastructure (indexing for snap, cone, and hop operations)
- Substrate validation (detecting pathologies, enforcing validation gates)
- Noise budgeting (inserting snap-to-nearest operations where noise would exceed thresholds)

The programmer writes in terms of semantic operations. The compiler makes them run on a specific substrate.
