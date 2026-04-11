# Akasha: A Vector Programming Language for Computation in Embedding Spaces

**Emma Leonhart**

## Abstract

We present Akasha, a programming language that uses LLM embedding spaces as its computational substrate. Where conventional languages compile to machine instructions that execute on silicon, Akasha compiles to vector operations that execute inside a pre-trained embedding space — making the execution environment fundamentally semantic rather than symbolic. Named after the Sanskrit concept of a primordial substance pervading all things, the language operates in the continuous semantic space that pervades trained embedding models.

Akasha introduces several novel contributions to programming language design. First, a **three-tier operation model**: primitive operations (scalars, tuples, bounded iteration), algebraic VSA operations at O(1) (bind, bundle, unbind, similarity), and non-algebraic vector-graph operations at O(log n) (snap-to-nearest, cone traversal, graph hop) — where all non-algebraic operations are unified by their dependence on approximate nearest neighbor search. Second, **fuzzy-by-default semantics** with opt-in defuzzification via a truth-extraction matrix M(v) derived from the input vector, enabling recursive confidence refinement through repeated application of `is_true`. Third, **empirical initiation** — the compiler probes a target embedding space, fits correction matrices, and outputs a substrate-specific mapping, allowing the same source code to compile for different embedding models like C compiling for different architectures. Fourth, **cone traversal as control flow** — directed neighborhood queries in embedding space serve as a branching mechanism complementary to algebraic fuzzy conditionals.

The language design is grounded in empirical findings from relational displacement analysis of frozen embeddings: 86 predicates discovered as consistent vector operations across three embedding models, with r = 0.861 correlation between geometric consistency and prediction accuracy (Leonhart, 2026). We further demonstrate that the traditional VSA binding operation (Hadamard product) fails on natural embedding spaces due to crosstalk from correlated embeddings, but that **sign-flip binding** — a simple operation that flips filler signs based on role sign patterns — achieves 14-role bundling capacity with correct snap-to-nearest recovery across three substrate models (GTE-large, BGE-large, Jina-v2), sustains 10-step chained computation, and supports multi-hop composition. Akasha is the first programming language designed to exploit this structure directly.

## 1. Introduction

That embedding spaces encode relational structure as vector arithmetic has been known since `king - man + woman ≈ queen` (Mikolov et al., 2013). The knowledge graph embedding literature formalized this: TransE models relations as translations (Bordes et al., 2013), RotatE as rotations (Sun et al., 2019), and subsequent work characterized exactly which relation types admit which geometric representations (Wang et al., 2014; Kazemi & Poole, 2018).

A complementary line of work showed that *frozen*, general-purpose embeddings — models not specifically trained for relational reasoning — also encode consistent vector arithmetic. Recent cartographic analysis of mxbai-embed-large, nomic-embed-text, and all-minilm discovered 86 predicates that manifest as consistent displacement vectors, with 30 universal across all three models (Leonhart, 2026). The correlation between geometric consistency and prediction accuracy (r = 0.861) is self-calibrating: the structure's internal consistency predicts its external utility.

These findings raise a question that the embedding literature has not addressed: if embedding spaces encode consistent algebraic structure, can we *program* in them? Not query them, not probe them, not visualize them — but treat them as the computational substrate for a programming language, the way silicon is the substrate for conventional computation?

Akasha answers this question. It is a programming language where:
- **Values** are vectors in a pre-trained embedding space
- **Operations** are geometric transformations (binding, bundling, projection, similarity)
- **Truth** is fuzzy by default, with opt-in defuzzification
- **Control flow** is both algebraic (fuzzy branching via superposition) and geometric (cone traversal through semantic neighborhoods)
- **Compilation** is substrate-adaptive — the same source code targets different embedding spaces via empirical calibration

Akasha is not an AI-assisted programming tool. It is not a neural network. It is a formal system for *reasoning under uncertainty* — closer to logic programming (Prolog) than to Python, but operating in continuous rather than discrete space. The computational substrate is semantic: operations have meaning in a way that silicon arithmetic does not.

### 1.1 Contributions

1. **A three-tier operation model** that separates primitive scaffolding (scalars, tuples, bounded iteration), algebraic VSA operations at O(1), and non-algebraic vector-graph operations at O(log n). The non-algebraic tier is unified by dependence on approximate nearest neighbor (ANN) infrastructure and serves two roles: error correction (snap-to-nearest) and semantic navigation (cone traversal, graph hop).

2. **A truth-extraction matrix mechanism** for defuzzification. Given vector v, a matrix M(v) derived from v maps it to a truth vector: M(v) · v = t. This enables equality evaluation via truth-vector comparison and recursive confidence refinement via iterated application.

3. **Empirical initiation** as a compilation strategy. The Akasha compiler probes a target embedding space, tests algebraic operation fidelity, fits correction matrices, and outputs a substrate-specific mapping file. The same Akasha source code compiles differently for different embedding models, analogous to C compiling for x86 versus ARM.

4. **Cone traversal as a control flow mechanism.** Directed neighborhood queries in embedding space — defined by origin, direction, and angular spread — provide non-algebraic branching that complements the algebraic fuzzy conditional `(condition * branch_true) + (¬condition * branch_false)`.

5. **An honest assessment of Turing completeness.** VSA algebra alone is not Turing-complete due to fixed dimensionality and approximate retrieval. Akasha's position: VSA algebra + ANN-backed non-algebraic operations + external graph memory = Turing complete. The algebra handles local computation; the graph provides unbounded external memory. This is analogous to a CPU (fixed registers) with RAM (unbounded, addressable).

## 2. Related Work

### 2.1 Vector Symbolic Architectures

Vector Symbolic Architecture (VSA) is a family of algebraic frameworks for computing with high-dimensional vectors (Kanerva, 2009; Plate, 1995; Gayler, 2003). The core operations — binding (elementwise multiplication), bundling (addition), and similarity (dot product) — define an algebra over hypervectors that can represent and manipulate structured symbolic information.

Tomkins-Flanagan and Kelly demonstrated that VSA can implement a Turing-complete Lisp 1.5 interpreter using Holographic Reduced Representations, with cleanup memory providing the error correction necessary for sustained computation. Flanagan et al. (2024) formalized this via Cartesian closed categories, arguing that VSA with cleanup memory satisfies the Curry-Howard-Lambek correspondence.

Smolensky (1990) provided the theoretical foundation with tensor product representations, showing that role-filler binding via tensor products is formally equivalent to the substitution step in beta reduction — connecting the practical engineering of VSA to the theoretical question of computational universality.

Akasha differs from prior VSA work in three ways: (1) it treats VSA as a programming language substrate rather than a computational model, (2) it operates inside *frozen, naturally-learned* embedding spaces rather than spaces designed for VSA, and (3) it formalizes the non-algebraic operations (snap, cone, hop) as first-class language constructs rather than implementation details.

### 2.2 Hyperdimensional Computing

Hyperdimensional Computing (HDC) applies VSA to engineering tasks: classification (Imani et al., 2019), language recognition (Joshi et al., 2016), and robotics (Neubert et al., 2019). HDCC provides a compiler for HDC classification tasks, and libraries like Torchhd and vsapy offer Python interfaces. However, these are classification tools and research libraries — not general-purpose programming languages. The distinction between VSA (the algebra) and HDC (the engineering) parallels Boolean algebra versus digital circuits. Akasha operates at the VSA level.

### 2.3 Probabilistic Programming Languages

Languages like Stan (Carpenter et al., 2017), Pyro (Bingham et al., 2019), and Church (Goodman et al., 2008) integrate probabilistic reasoning into programming. However, they compile to conventional computation — the substrate is silicon, and the probabilistic semantics are layered on top. Akasha's distinction is that the substrate itself is semantic: operations execute in a space where *similarity is geometric distance* and *meaning is position*.

### 2.4 Neurosymbolic Integration

Logic Tensor Networks (Serafini & Garcez, 2016), Neural Theorem Provers (Rocktäschel & Riedel, 2017), and DeepProbLog (Manhaeve et al., 2018) integrate logical reasoning with neural computation. These are constructive approaches that build systems combining symbolic logic and neural networks. Akasha is different: it does not combine two paradigms but rather programs directly in the geometric structure that neural networks produce. The embedding space is not an intermediary — it is the execution environment.

### 2.5 Relational Displacement Analysis

TransE (Bordes et al., 2013) demonstrated that knowledge graph relations can be modeled as translations in learned embedding spaces. Recent work extended this to frozen general-purpose embeddings (Leonhart, 2026), discovering 86 consistent relational displacements across three models and a correlation (r = 0.861) between consistency and prediction accuracy. These results provide the empirical foundation for Akasha: the algebraic structure needed for computation already exists in pre-trained embedding spaces.

## 3. Language Design

### 3.1 Design Principles

**Fuzzy-by-default.** Every value in Akasha carries implicit uncertainty. Truth is a continuous quantity, not a binary one. This inverts conventional programming languages where crisp logic is the default and probabilistic reasoning is bolted on as a library. The inversion is natural given the substrate: nothing in an embedding space is ever fully true or false.

**Vectors as the primary type.** The fundamental data type is the hypervector — a point in the embedding space. Numbers, symbols, and structures are all represented as vectors. There are no "wrong type" errors, only noisy or semantically meaningless results. Equality is replaced by similarity.

**Computation is geometry.** Programs navigate and transform regions of semantic space. Operations are similarity queries, projections, rotations, and interpolations. The execution environment is fundamentally semantic: `bind(AGENT, "cat")` produces a vector whose position in space encodes the relationship between the agent role and the concept of cat.

### 3.2 Three-Tier Operation Model

Akasha organizes operations into three tiers by cost and abstraction level.

**Tier 1: Primitive operations.** Scalars (not vectors — plain numbers for weighting, thresholds, and loop counters), tuples (grouping without superposition), and bounded iteration (`repeat N`). These are conventional computational scaffolding. They exist because not everything in a program is a semantic vector operation.

**Tier 2: Algebraic / VSA operations (O(1)).** The core vector algebra, operating on fixed-dimensional vectors:

- **Bundle** (addition): Creates superposition. `a + b` is similar to both a and b. Encodes sets and fuzzy disjunction.
- **Bind** (sign-flip): Creates association. `a * sign(role)` flips signs of the filler based on the role vector, producing a result dissimilar to both inputs. Encodes key-value pairs and role-filler structures. Self-inverse (unbinding = applying the same sign flip). Cost: ~7μs.
- **Bind-precise** (rotation): High-accuracy alternative. Applies a role-dependent orthogonal rotation `R(role) @ a`. Exact inverse via transpose. Cost: ~320μs. Use when accuracy matters more than speed.
- **Unbind**: For sign-flip binding, unbinding is the same operation. For rotation binding, it is the transpose rotation. Extracts the approximate filler from a bundled structure — approximate because crosstalk from other bundled pairs introduces noise.
- **Similarity**: Euclidean distance (primary) or dot product. Returns a scalar. The fundamental "how close?" query.
- **Projection**: Extract the component of a vector along a subspace.

Note: the traditional VSA binding operation (Hadamard / elementwise product) was tested and **fails on natural embedding spaces** — bundled structures lose all signal at 2+ role-filler pairs due to crosstalk from correlated embeddings. Sign-flip binding avoids this by stripping magnitude correlation (Section 6.2).

These operations require no infrastructure beyond the vectors themselves. They are pure math.

**Tier 3: Non-algebraic / vector-graph operations (O(log n)).** These require approximate nearest neighbor (ANN) infrastructure — typically an HNSW index or similar vector database:

- **Snap-to-nearest** (cleanup/discretization): ANN search against a codebook of known vectors. Error correction — restores a noisy vector to its nearest clean state. Analogous to rounding in floating-point arithmetic.
- **Cone traversal** (directed neighborhood query): From an origin point, define a direction and angular spread. Returns vectors within the cone. Provides non-algebraic branching and many-to-many navigation.
- **Graph hop** (typed traversal): Traverse to connected vectors via a specified relation type. Extends cone traversal with typed edges.

The unifying characteristic of Tier 3 is ANN dependence. All non-algebraic operations involve some form of nearest-neighbor search over an indexed collection. This is what makes them expensive relative to Tier 2.

The design philosophy: keep computation in Tier 2 (algebraic) as much as possible. Use Tier 1 (primitives) for scaffolding. Rise to Tier 3 (non-algebraic) only for error correction and semantic navigation.

### 3.3 Control Flow

**Algebraic branching (fuzzy conditional):**
```
result = (condition * branch_true) + (¬condition * branch_false)
```
Both branches execute simultaneously via superposition. The condition vector weights which branch dominates. This is O(1), purely algebraic, and inherently fuzzy — there is no "wrong branch," only a weighted mixture. This is the default branching mechanism.

**Cone traversal (discrete branching):** When computation requires navigating to a specific discrete state rather than blending alternatives, cone traversal provides it. The current vector state determines a direction, and the cone finds the nearest matching state in the semantic graph. This is analogous to a pattern match or jump table — the geometry determines which branch is taken.

**Bounded iteration:** `repeat N: body` executes the body a scalar number of times. This is a primitive operation, not a vector operation. It sidesteps the unsolved problem of convergence-based termination. Snap-to-nearest between iterations controls noise accumulation.

### 3.4 Defuzzification: The Truth-Extraction Matrix

The mechanism for converting fuzzy vector computation to crisp values:

```
is_true(x) → scalar ∈ [0, 1]
```

Given a vector v, Akasha derives a matrix M(v) such that M(v) · v yields a truth vector — a canonical vector representing "true" in the embedding space. The matrix is not global; it is derived from v itself, encoding "what does truth mean for this particular vector in this region of the space."

**Equality evaluation** follows from truth extraction:
```
is_equal(a, b) = similarity(M(a) · a, M(b) · b)
```
Two vectors are "equal" if their truth-extraction matrices map them to the same truth vector. This asks "do these assert the same thing?" rather than "are these close in embedding space?"

**Recursive refinement** applies is_true iteratively:
```
t₁ = M(v) · v           // "is this true?"
t₂ = M(t₁) · t₁         // "is my assessment reliable?"
t₃ = M(t₂) · t₂         // "is my reliability assessment reliable?"
```
Each application re-evaluates the truth of the previous result. The sequence may converge to a fixed point (stable truth value), oscillate (genuinely ambiguous proposition), or diverge (pathological substrate region).

### 3.5 Type System

Akasha has no type errors. Binding two unrelated vectors produces a result — it is simply semantically meaningless (low similarity to anything useful). The "type system" is replaced by similarity checking: the programmer (or compiler) verifies that results are similar to expected patterns.

This is consistent with the fuzzy-by-default principle: there is no hard boundary between "correct" and "incorrect" computation, only a continuous spectrum of meaningfulness.

## 4. Runtime Architecture

### 4.1 S1/Akasha Dual Runtime

The runtime mirrors the cognitive architecture from which the language takes its name:

- **S1 layer:** Fast, cached, pattern-matched execution. Lookup tables, memoized operation results, precomputed common paths. Handles recurring computations.
- **Akasha layer:** Deliberate semantic computation. The actual vector-space reasoning. Handles novel inputs requiring genuine algebraic and geometric reasoning.

As computations recur, their results migrate from Akasha to S1 — from deliberate reasoning to cached lookup. This is analogous to TypeScript's type checker running alongside JavaScript execution: Akasha's semantic layer runs alongside the fast path, providing the context that makes the cached results meaningful.

### 4.2 Empirical Initiation

Akasha does not assume any embedding space has the right algebraic properties. At compile time, the compiler probes the target space:

1. **Test algebraic operations.** Generate random vectors. Test binding dissimilarity, unbinding accuracy, bundling capacity. Measure noise characteristics.
2. **Fit correction matrices.** Projection matrices that improve algebraic fidelity: rotations for binding, subspace projections for unbinding, normalizations for bundling capacity.
3. **Validate substrate.** Enforce minimum requirements: binding must actually encrypt, unbinding must recover fillers above threshold, no catastrophic pathologies (attention sinks, degenerate dimensions).
4. **Output mapping file.** A binary artifact containing correction matrices, noise characterization, and codebook initialization. This is the compiled form — same source code + different mapping files = same program on different substrates.

The analogy to conventional compilation is direct: x86 and ARM have different instruction sets but can run the same C program. mxbai-embed-large and nomic-embed-text have different geometric properties but can run the same Akasha program.

### 4.3 MCP Server as Runtime Component

The MCP (Model Context Protocol) server is not an IDE add-on. It is part of the Akasha runtime, providing:
- ANN infrastructure for non-algebraic operations (snap, cone, hop)
- Codebook management for cleanup memory
- Entity resolution (context-dependent disambiguation of polysemous vectors)
- Long-range semantic dependency resolution

The semantic richness of computation in embedding spaces creates dependencies that span beyond any single file or function. The MCP server holds the semantic context that makes these dependencies resolvable — analogous to a type server resolving types across a large codebase, but for semantic relationships rather than syntactic types.

## 5. Theoretical Foundations

### 5.1 Mathematical Grounding

Akasha's substrate must satisfy the eight axioms of a real vector space (commutativity, associativity, identity, inverse for addition; identity, associativity, two distributivity laws for scalar multiplication). LLM embedding spaces satisfy these trivially as subsets of ℝⁿ. This means Akasha inherits the full toolkit of linear algebra: subspaces, projections, eigendecomposition, orthogonal complements.

The deeper mathematical foundation is **concentration of measure** in high-dimensional spaces. In d > 1000 dimensions, randomly sampled vectors are almost certainly nearly orthogonal. This is a theorem, not an empirical observation. It guarantees that thousands of concept vectors can coexist without interference, that bundling (addition) preserves approximate membership for up to √d items, and that binding (Hadamard product) produces vectors approximately orthogonal to both inputs.

### 5.2 Lambda Calculus Encoding

Lambda terms encode as trees in superposition. Abstraction `λx.body` becomes `bind(VAR_role, x) + bind(BODY_role, encode(body))`. Application `(f a)` becomes `bind(FUNC_role, encode(f)) + bind(ARG_role, encode(a))`. Reading components back uses unbinding: `unbind(FUNC_role, encode(App(f, a))) ≈ encode(f)`.

The hard part is substitution (beta reduction), which requires modifying a distributed representation without corrupting it — equivalent to the binding problem in cognitive science (Smolensky, 1990). Current approaches require cleanup memory (snap-to-nearest) after each reduction step, which is why Akasha treats snap as a first-class operation.

Tomkins-Flanagan and Kelly's working Lisp interpreter in HRR is the existence proof. Lambda calculus semantics are implementable in vector space. The price is mandatory periodic cleanup — pure algebraic computation without error correction is limited to short chains.

### 5.3 Turing Completeness

**The honest position:** VSA algebra alone is not Turing-complete. Fixed dimensionality limits superposition capacity. Approximate retrieval introduces compounding errors. Cleanup memory (snap-to-nearest) patches the error problem but introduces circularity (the codebook must contain the correct answer).

Akasha's Turing completeness claim: **VSA algebra + ANN-backed non-algebraic operations + external graph memory = Turing complete.** The vectors handle local computation (fixed-dimensional but algebraically rich). The graph provides unbounded external memory (the vector state navigates a graph that can grow without bound). This is architecturally identical to a CPU (fixed registers) with RAM (unbounded, addressable memory).

Flanagan et al. (2024) argue for VSA Turing completeness via Cartesian closed categories. We accept their construction but note that cleanup memory does the heavy lifting — the boundary between "VSA computing" and "lookup table computing" is not formalized in their proof. Akasha makes this boundary explicit: Tier 2 operations are the VSA; Tier 3 operations are the infrastructure that patches the VSA's limitations.

## 6. Empirical Grounding

### 6.1 Algebraic Structure in Frozen Embeddings

The foundational empirical result (Leonhart, 2026): relational displacement analysis of mxbai-embed-large (1024-dim), nomic-embed-text (768-dim), and all-minilm (384-dim) using Wikidata triples discovers 86 predicates that manifest as consistent vector displacements, with 30 universal across all three models.

The correlation between geometric consistency and prediction accuracy (r = 0.861, 95% CI [0.773, 0.926]) means the algebraic structure is self-calibrating: internally consistent operations are externally useful. This is the critical empirical validation for Akasha — it demonstrates that the algebraic structure needed for computation already exists in pre-trained, general-purpose embedding spaces without any VSA-specific training.

### 6.2 Binding Operation Selection

A critical empirical finding: the traditional VSA binding operation (Hadamard / elementwise product) **fails on natural embedding spaces** when multiple role-filler pairs are bundled.

We tested six binding operations on GTE-large (1024-dim) by constructing bundled structures with 1-7 role-filler pairs, then attempting to recover a target filler via unbinding and snap-to-nearest against a 20-item codebook. Results:

| Method | Cos at 2 roles | Cos at 7 roles | Snap correct (7) | Cost (μs) |
|--------|---------------|---------------|-------------------|-----------|
| Hadamard | 0.11 | 0.09 | 2/7 | 1.5 |
| **Sign-flip** | **0.74** | **0.40** | **7/7** | **6.6** |
| Permutation | 0.71 | 0.37 | 7/7 | 30.9 |
| Circular conv | 0.29 | 0.13 | 7/7 | 79.3 |
| FFT correlation | 0.62 | 0.34 | 7/7 | 67.3 |
| **Rotation** | **0.89** | **0.80** | **7/7** | **321.3** |

Hadamard binding fails because natural embeddings are correlated and anisotropic — they share significant structure, so crosstalk from non-orthogonal role vectors overwhelms the target signal. All five alternatives achieve 7/7 correct snap recoveries at 7 bundled roles.

**Sign-flip binding** (`a * sign(role)`) is Akasha's default: it strips magnitude correlation, leaving a pseudo-random binary mask that is self-inverse and nearly orthogonal across roles. At 6.6μs (4.4x Hadamard), it is cheap enough for the algebraic tier. **Rotation binding** (`R(role) @ a`) is the high-accuracy alternative at 321μs, maintaining 0.80 cosine similarity to the target even at 7 bundled roles.

Extended testing of sign-flip binding revealed substantially higher capacity than the initial 7-role test suggested. With a 15-item codebook on GTE-large, sign-flip achieves **14/14 correct snap recoveries** — cosine degrades gracefully from 0.74 at 2 roles to 0.30 at 14 roles, but snap consistently identifies the correct target. This capacity is substrate-agnostic: BGE-large-en-v1.5 (1024-dim) and Jina-v2-base-en (768-dim) both achieve identical 14/14 results.

**Chained computation** — the critical test for sustained reasoning — was tested by repeatedly building 3-role bundled structures, unbinding the target, snapping, and using the result in the next structure. With sign-flip binding: **10/10 steps correct**, with raw cosine stable at 0.58-0.65 throughout the chain. Snap recovers the exact target at every step.

**Multi-hop composition** was tested by extracting a filler from structure A (agent=cat, action=sit), inserting it into a different role in structure B (agent=dog, patient=extracted_cat), then extracting from B. All three extractions (agent from A, patient from B, agent from B) returned the correct filler. This demonstrates that Akasha can perform the fundamental operation required for multi-step inference: move information between structures via unbind-snap-rebind cycles.

### 6.3 Cross-Substrate Validation

We ran Akasha's empirical initiation validation gates on four non-normalized embedding models. Initial tests used Hadamard binding; sign-flip capacity was tested subsequently on three models:

| Model | Dims | Mag Mean | Hadamard Capacity | Sign-Flip Capacity | Approved |
|-------|------|----------|-------------------|-------------------|----------|
| GTE-large | 1024 | 19.08 | ~4 | **14** | Yes |
| BGE-large-en-v1.5 | 1024 | 17.29 | ~4 | **14** | Yes |
| Jina-v2-base-en | 768 | 26.43 | ~3 | **14** | Yes |
| mxbai-embed-large | 1024 | 17.38 | ~5 | (not tested)* | Yes* |

*mxbai passes algebraic tests but has a documented diacritic attention-sink pathology (Leonhart, 2026). This demonstrates that validation gates must include both algebraic tests and pathology detection.

The shift from Hadamard to sign-flip binding increases effective capacity by 3-5x across all tested substrates, from ~3-5 roles to 14 roles — the limit of our test set. All four models produce non-normalized vectors (magnitudes 17-26, not 1.0) when accessed via raw transformers without post-processing normalization layers. Akasha requires non-normalized output because magnitude carries information about binding strength and bundling count — Euclidean distance, not cosine similarity, is the primary metric.

### 6.4 Operation Cost Analysis

Benchmarked on GTE-large (1024-dim, CPU):

| Tier | Operation | Cost (μs) | Relative |
|------|-----------|-----------|----------|
| 2 | Bind (sign-flip) | 6.6 | 1x |
| 2 | Bundle (addition) | 1.7 | 0.3x |
| 2 | Unbind (sign-flip) | 7.9 | 1.2x |
| 2 | Similarity (dot) | 1.6 | 0.2x |
| 2 | Euclidean distance | 4.6 | 0.7x |
| 3 | Snap (20 items) | 31.8 | 4.8x |
| 3 | Snap (1K items) | 3,540 | 536x |
| 3 | Snap (10K items) | 31,000 | 4,697x |
| — | Embed one text (LLM) | ~250,000 | ~38,000x |

The critical finding: **snap-to-nearest is not the bottleneck**. Even with a 10K-item codebook, snap (31ms) is 8x cheaper than embedding a single text (250ms). The real cost is the LLM forward pass that produces the embeddings in the first place. Once vectors are in the space, algebraic operations are microsecond-scale and snap is millisecond-scale — both negligible compared to the embedding step.

### 6.5 Substrate Validation: The mxbai Pathology

During the cartographic analysis that grounds Akasha, a previously unreported defect in mxbai-embed-large was discovered: diacritic characters cause catastrophic embedding collapse via attention sink (a high-magnitude key vector dominates the attention mechanism, overwriting all other token representations). Completely unrelated strings containing diacritics produce cosine similarity > 0.95.

This pathology demonstrates why Akasha requires substrate validation as part of empirical initiation. Notably, mxbai passes all algebraic validation gates — the diacritic bug is an attention-mechanism pathology, not an algebraic one. A substrate can be algebraically sound but still have silent corruption modes. Akasha's validation must therefore include both algebraic tests and pathology-specific probes.

### 6.6 Biological Substrate: Compiling to a Mushroom Body Circuit

The empirical initiation framework claims substrate-adaptivity: the same source code compiles for different embedding spaces given a calibration pass. We tested this claim against a substrate deliberately far outside the training distribution of the compiler — a Brian2 spiking simulation of the *Drosophila melanogaster* mushroom body (50 projection neurons → 2,000 Kenyon cells → 1 anterior paired lateral neuron → 20 mushroom body output neurons, leaky integrate-and-fire dynamics, APL-enforced 5% Kenyon-cell sparsity). An Akasha source file describing a four-state conditional was parsed and validated by the same compiler used for the silicon experiments above (§6.1–§6.5), mechanically translated by a substrate-specific backend into calls against the spiking circuit, and executed. Across four program variants and four input conditions (sixteen decisions total), the compiled output produced the expected behavior mapping on every trial, with the four variants yielding four distinct permutations of the underlying prototype table. To our knowledge this is the first demonstration of a programming language whose conditional semantics compile mechanically onto a connectome-derived spiking substrate. The result serves as a non-silicon stress test for the substrate-agnostic claim in §4.2.

## 7. Discussion

### 7.1 What Akasha Is and Is Not

Akasha is a formal system for reasoning under uncertainty. It is not a replacement for Python or C++ — it does not handle I/O, graphics, or systems programming. Its domain is *semantic computation*: inference, reasoning, search, and structured manipulation of meaning in vector space.

The closest analogy is Prolog, which provides a fundamentally different computational paradigm (unification and backtracking) for a specific class of problems (logical inference). Akasha provides a different paradigm (geometric operations in continuous semantic space) for a different class of problems (reasoning under uncertainty with learned representations).

### 7.2 Human-AI Collaboration in Language Design

Akasha was designed through extensive human-AI conversation. The human designer brought domain insight — the recognition that embedding spaces could serve as computational substrate, the fuzzy-by-default inversion, the three-tier operation model. The AI collaborator helped formalize these ideas, stress-tested them against the theoretical literature, and identified edge cases and failure modes.

The design conversations are archived in the project repository. This collaborative process is itself a finding: AI systems can participate meaningfully in the creative, speculative phase of language design — not just code generation, but conceptual architecture.

### 7.3 Future Directions

**Syntax design.** Akasha's semantics are solidifying but no concrete syntax has been defined. The syntax must make the three operation tiers visually distinct so programmers can immediately see where expensive non-algebraic operations occur.

**JEPA integration.** Akasha naturally connects to Joint Embedding Predictive Architecture (LeCun, 2022). HDC provides algebraic structure; JEPA provides learned prediction. A two-phase training approach (algebraic consistency first, predictive coding second) could produce embedding spaces optimized for Akasha computation.

**Product manifold embeddings.** Different semantic relationships naturally live in different geometries: hierarchies in hyperbolic space, analogies in Euclidean space, cycles on spheres. A product manifold embedding combining these geometries could give Akasha richer type semantics where the geometry of a subspace determines what operations are natural in it.

**Implementation and benchmarks.** The most important next step. Candidate benchmark tasks: semantic search with algebraic pre-filtering, compositional multi-hop inference via vector arithmetic, and structured prediction exploiting discovered algebraic regularities.

## 8. Conclusion

Akasha demonstrates that LLM embedding spaces can serve as a computational substrate for a programming language, not just a lookup table for similarity search. The language's novel contributions — three-tier operations, truth-extraction matrices, empirical initiation, cone traversal as control flow — are grounded in empirical evidence that frozen embedding spaces encode consistent algebraic structure.

Empirical testing on four embedding models revealed a critical finding: the traditional VSA binding operation (Hadamard product) fails on natural embeddings, but sign-flip binding achieves **14/14 correct recoveries** at only 4.4x the cost, sustains **10/10 chained computation steps**, and supports **multi-hop composition** (extract from one structure, insert into another, extract again — all correct). These results hold identically across GTE-large (1024-dim), BGE-large (1024-dim), and Jina-v2 (768-dim), demonstrating substrate-agnostic viability. This finding updates the VSA literature's assumption that Hadamard product is the standard binding choice — on natural embedding spaces, sign-flip binding is strictly superior.

The design makes an honest assessment of its own limitations: VSA algebra alone is not Turing-complete, non-algebraic operations are expensive, noise accumulation requires periodic cleanup, and embedding substrates can have silent pathologies. These limitations are explicitly addressed in the language design rather than hidden.

Akasha is less like a traditional programming language and more like a formal system for reasoning under uncertainty. It occupies a previously empty niche — continuous semantic computation as a programming paradigm — and provides a concrete framework for exploiting the algebraic structure that neural networks produce but that no existing system treats as a first-class computational resource.

## References

Bingham, E., et al. (2019). Pyro: Deep universal probabilistic programming. JMLR.

Bordes, A., et al. (2013). Translating embeddings for modeling multi-relational data. NeurIPS.

Carpenter, B., et al. (2017). Stan: A probabilistic programming language. Journal of Statistical Software.

Conneau, A., et al. (2018). What you can cram into a single $&!#* vector. ACL.

Ethayarajh, K., et al. (2019). Towards understanding linear word analogies. ACL.

Flanagan, N., et al. (2024). Hey Pentti, we did it! VSA Turing completeness via Cartesian closed categories.

Gayler, R. W. (2003). Vector symbolic architectures answer Jackendoff's challenges for cognitive neuroscience. ICCS.

Goodman, N. D., et al. (2008). Church: a language for generative models. UAI.

Hewitt, J., & Manning, C. D. (2019). A structural probe for finding syntax in word representations. NAACL.

Imani, M., et al. (2019). A framework for HD computing. ReConFig.

Joshi, A., et al. (2016). Language recognition using random indexing. arXiv.

Kahneman, D. (2011). Thinking, Fast and Slow. Farrar, Straus and Giroux.

Kanerva, P. (2009). Hyperdimensional computing: An introduction to computing in distributed representation. Cognitive Computation.

Kazemi, S. M., & Poole, D. (2018). Simple embedding for link prediction in knowledge graphs. NeurIPS.

LeCun, Y. (2022). A path towards autonomous machine intelligence. OpenReview.

Leonhart, E. (2026). Latent space cartography applied to Wikidata: Relational displacement analysis reveals a silent tokenizer defect in mxbai-embed-large. Claw4S.

Linzen, T. (2016). Issues in evaluating semantic spaces using word analogies. RepEval Workshop.

Liu, Y., et al. (2019). Latent space cartography: Visual analysis of vector space embeddings. Computer Graphics Forum.

Manhaeve, R., et al. (2018). DeepProbLog: Neural probabilistic logic programming. NeurIPS.

Mikolov, T., et al. (2013). Efficient estimation of word representations in vector space. ICLR Workshop.

Neubert, P., et al. (2019). An introduction to hyperdimensional computing for robotics. KI.

Plate, T. A. (1995). Holographic reduced representations. IEEE Transactions on Neural Networks.

Rocktäschel, T., & Riedel, S. (2017). End-to-end differentiable proving. NeurIPS.

Rogers, A., et al. (2017). Too many problems of analogical reasoning with word vectors. *SEM.

Schluter, N. (2018). The word analogy testing caveat. NAACL.

Serafini, L., & Garcez, A. d. (2016). Logic tensor networks. arXiv.

Smolensky, P. (1990). Tensor product variable binding and the representation of symbolic structures in connectionist systems. Artificial Intelligence.

Sun, Z., et al. (2019). RotatE: Knowledge graph embedding by relational rotation in complex space. ICLR.

Trouillon, T., et al. (2016). Complex embeddings for simple link prediction. ICML.

Vilnis, L., et al. (2018). Probabilistic embedding of knowledge graphs with box lattice measures. ACL.

Wang, Z., et al. (2014). Knowledge graph embedding by translating on hyperplanes. AAAI.
