# S2: A Vector Programming Language for Computation in Embedding Spaces

**Emma Leonhart**

## Abstract

We present S2, a programming language that uses LLM embedding spaces as its computational substrate. Where conventional languages compile to machine instructions that execute on silicon, S2 compiles to vector operations that execute inside a pre-trained embedding space — making the execution environment fundamentally semantic rather than symbolic. Named after System 2 thinking (Kahneman, 2011), the language implements slow, deliberate reasoning as geometric operations in continuous semantic space.

S2 introduces several novel contributions to programming language design. First, a **three-tier operation model**: primitive operations (scalars, tuples, bounded iteration), algebraic VSA operations at O(1) (bind, bundle, unbind, similarity), and non-algebraic vector-graph operations at O(log n) (snap-to-nearest, cone traversal, graph hop) — where all non-algebraic operations are unified by their dependence on approximate nearest neighbor search. Second, **fuzzy-by-default semantics** with opt-in defuzzification via a truth-extraction matrix M(v) derived from the input vector, enabling recursive confidence refinement through repeated application of `is_true`. Third, **empirical initiation** — the compiler probes a target embedding space, fits correction matrices, and outputs a substrate-specific mapping, allowing the same source code to compile for different embedding models like C compiling for different architectures. Fourth, **cone traversal as control flow** — directed neighborhood queries in embedding space serve as a branching mechanism complementary to algebraic fuzzy conditionals.

The language design is grounded in empirical findings from relational displacement analysis of frozen embeddings: 86 predicates discovered as consistent vector operations across three embedding models, with r = 0.861 correlation between geometric consistency and prediction accuracy (Leonhart, 2026). These results demonstrate that embedding spaces encode sufficient algebraic structure to serve as a computational substrate. S2 is the first programming language designed to exploit this structure directly.

## 1. Introduction

That embedding spaces encode relational structure as vector arithmetic has been known since `king - man + woman ≈ queen` (Mikolov et al., 2013). The knowledge graph embedding literature formalized this: TransE models relations as translations (Bordes et al., 2013), RotatE as rotations (Sun et al., 2019), and subsequent work characterized exactly which relation types admit which geometric representations (Wang et al., 2014; Kazemi & Poole, 2018).

A complementary line of work showed that *frozen*, general-purpose embeddings — models not specifically trained for relational reasoning — also encode consistent vector arithmetic. Recent cartographic analysis of mxbai-embed-large, nomic-embed-text, and all-minilm discovered 86 predicates that manifest as consistent displacement vectors, with 30 universal across all three models (Leonhart, 2026). The correlation between geometric consistency and prediction accuracy (r = 0.861) is self-calibrating: the structure's internal consistency predicts its external utility.

These findings raise a question that the embedding literature has not addressed: if embedding spaces encode consistent algebraic structure, can we *program* in them? Not query them, not probe them, not visualize them — but treat them as the computational substrate for a programming language, the way silicon is the substrate for conventional computation?

S2 answers this question. It is a programming language where:
- **Values** are vectors in a pre-trained embedding space
- **Operations** are geometric transformations (binding, bundling, projection, similarity)
- **Truth** is fuzzy by default, with opt-in defuzzification
- **Control flow** is both algebraic (fuzzy branching via superposition) and geometric (cone traversal through semantic neighborhoods)
- **Compilation** is substrate-adaptive — the same source code targets different embedding spaces via empirical calibration

S2 is not an AI-assisted programming tool. It is not a neural network. It is a formal system for *reasoning under uncertainty* — closer to logic programming (Prolog) than to Python, but operating in continuous rather than discrete space. The computational substrate is semantic: operations have meaning in a way that silicon arithmetic does not.

### 1.1 Contributions

1. **A three-tier operation model** that separates primitive scaffolding (scalars, tuples, bounded iteration), algebraic VSA operations at O(1), and non-algebraic vector-graph operations at O(log n). The non-algebraic tier is unified by dependence on approximate nearest neighbor (ANN) infrastructure and serves two roles: error correction (snap-to-nearest) and semantic navigation (cone traversal, graph hop).

2. **A truth-extraction matrix mechanism** for defuzzification. Given vector v, a matrix M(v) derived from v maps it to a truth vector: M(v) · v = t. This enables equality evaluation via truth-vector comparison and recursive confidence refinement via iterated application.

3. **Empirical initiation** as a compilation strategy. The S2 compiler probes a target embedding space, tests algebraic operation fidelity, fits correction matrices, and outputs a substrate-specific mapping file. The same S2 source code compiles differently for different embedding models, analogous to C compiling for x86 versus ARM.

4. **Cone traversal as a control flow mechanism.** Directed neighborhood queries in embedding space — defined by origin, direction, and angular spread — provide non-algebraic branching that complements the algebraic fuzzy conditional `(condition * branch_true) + (¬condition * branch_false)`.

5. **An honest assessment of Turing completeness.** VSA algebra alone is not Turing-complete due to fixed dimensionality and approximate retrieval. S2's position: VSA algebra + ANN-backed non-algebraic operations + external graph memory = Turing complete. The algebra handles local computation; the graph provides unbounded external memory. This is analogous to a CPU (fixed registers) with RAM (unbounded, addressable).

## 2. Related Work

### 2.1 Vector Symbolic Architectures

Vector Symbolic Architecture (VSA) is a family of algebraic frameworks for computing with high-dimensional vectors (Kanerva, 2009; Plate, 1995; Gayler, 2003). The core operations — binding (elementwise multiplication), bundling (addition), and similarity (dot product) — define an algebra over hypervectors that can represent and manipulate structured symbolic information.

Tomkins-Flanagan and Kelly demonstrated that VSA can implement a Turing-complete Lisp 1.5 interpreter using Holographic Reduced Representations, with cleanup memory providing the error correction necessary for sustained computation. Flanagan et al. (2024) formalized this via Cartesian closed categories, arguing that VSA with cleanup memory satisfies the Curry-Howard-Lambek correspondence.

Smolensky (1990) provided the theoretical foundation with tensor product representations, showing that role-filler binding via tensor products is formally equivalent to the substitution step in beta reduction — connecting the practical engineering of VSA to the theoretical question of computational universality.

S2 differs from prior VSA work in three ways: (1) it treats VSA as a programming language substrate rather than a computational model, (2) it operates inside *frozen, naturally-learned* embedding spaces rather than spaces designed for VSA, and (3) it formalizes the non-algebraic operations (snap, cone, hop) as first-class language constructs rather than implementation details.

### 2.2 Hyperdimensional Computing

Hyperdimensional Computing (HDC) applies VSA to engineering tasks: classification (Imani et al., 2019), language recognition (Joshi et al., 2016), and robotics (Neubert et al., 2019). HDCC provides a compiler for HDC classification tasks, and libraries like Torchhd and vsapy offer Python interfaces. However, these are classification tools and research libraries — not general-purpose programming languages. The distinction between VSA (the algebra) and HDC (the engineering) parallels Boolean algebra versus digital circuits. S2 operates at the VSA level.

### 2.3 Probabilistic Programming Languages

Languages like Stan (Carpenter et al., 2017), Pyro (Bingham et al., 2019), and Church (Goodman et al., 2008) integrate probabilistic reasoning into programming. However, they compile to conventional computation — the substrate is silicon, and the probabilistic semantics are layered on top. S2's distinction is that the substrate itself is semantic: operations execute in a space where *similarity is geometric distance* and *meaning is position*.

### 2.4 Neurosymbolic Integration

Logic Tensor Networks (Serafini & Garcez, 2016), Neural Theorem Provers (Rocktäschel & Riedel, 2017), and DeepProbLog (Manhaeve et al., 2018) integrate logical reasoning with neural computation. These are constructive approaches that build systems combining symbolic logic and neural networks. S2 is different: it does not combine two paradigms but rather programs directly in the geometric structure that neural networks produce. The embedding space is not an intermediary — it is the execution environment.

### 2.5 Relational Displacement Analysis

TransE (Bordes et al., 2013) demonstrated that knowledge graph relations can be modeled as translations in learned embedding spaces. Recent work extended this to frozen general-purpose embeddings (Leonhart, 2026), discovering 86 consistent relational displacements across three models and a correlation (r = 0.861) between consistency and prediction accuracy. These results provide the empirical foundation for S2: the algebraic structure needed for computation already exists in pre-trained embedding spaces.

## 3. Language Design

### 3.1 Design Principles

**Fuzzy-by-default.** Every value in S2 carries implicit uncertainty. Truth is a continuous quantity, not a binary one. This inverts conventional programming languages where crisp logic is the default and probabilistic reasoning is bolted on as a library. The inversion is natural given the substrate: nothing in an embedding space is ever fully true or false.

**Vectors as the primary type.** The fundamental data type is the hypervector — a point in the embedding space. Numbers, symbols, and structures are all represented as vectors. There are no "wrong type" errors, only noisy or semantically meaningless results. Equality is replaced by similarity.

**Computation is geometry.** Programs navigate and transform regions of semantic space. Operations are similarity queries, projections, rotations, and interpolations. The execution environment is fundamentally semantic: `bind(AGENT, "cat")` produces a vector whose position in space encodes the relationship between the agent role and the concept of cat.

### 3.2 Three-Tier Operation Model

S2 organizes operations into three tiers by cost and abstraction level.

**Tier 1: Primitive operations.** Scalars (not vectors — plain numbers for weighting, thresholds, and loop counters), tuples (grouping without superposition), and bounded iteration (`repeat N`). These are conventional computational scaffolding. They exist because not everything in a program is a semantic vector operation.

**Tier 2: Algebraic / VSA operations (O(1)).** The core vector algebra, operating elementwise on fixed-dimensional vectors:

- **Bundle** (addition): Creates superposition. `a + b` is similar to both a and b. Encodes sets and fuzzy disjunction.
- **Bind** (Hadamard product): Creates association. `a * b` is dissimilar to both a and b. Encodes key-value pairs and role-filler structures.
- **Unbind** (approximate inverse of bind): Given a role, extracts the approximate filler. Noisy — the fundamental source of error accumulation.
- **Similarity**: Cosine similarity or dot product. Returns a scalar. The fundamental "how close?" query.
- **Projection**: Extract the component of a vector along a subspace.

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

Given a vector v, S2 derives a matrix M(v) such that M(v) · v yields a truth vector — a canonical vector representing "true" in the embedding space. The matrix is not global; it is derived from v itself, encoding "what does truth mean for this particular vector in this region of the space."

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

S2 has no type errors. Binding two unrelated vectors produces a result — it is simply semantically meaningless (low similarity to anything useful). The "type system" is replaced by similarity checking: the programmer (or compiler) verifies that results are similar to expected patterns.

This is consistent with the fuzzy-by-default principle: there is no hard boundary between "correct" and "incorrect" computation, only a continuous spectrum of meaningfulness.

## 4. Runtime Architecture

### 4.1 S1/S2 Dual Runtime

The runtime mirrors the cognitive architecture from which the language takes its name:

- **S1 layer:** Fast, cached, pattern-matched execution. Lookup tables, memoized operation results, precomputed common paths. Handles recurring computations.
- **S2 layer:** Deliberate semantic computation. The actual vector-space reasoning. Handles novel inputs requiring genuine algebraic and geometric reasoning.

As computations recur, their results migrate from S2 to S1 — from deliberate reasoning to cached lookup. This is analogous to TypeScript's type checker running alongside JavaScript execution: S2's semantic layer runs alongside the fast path, providing the context that makes the cached results meaningful.

### 4.2 Empirical Initiation

S2 does not assume any embedding space has the right algebraic properties. At compile time, the compiler probes the target space:

1. **Test algebraic operations.** Generate random vectors. Test binding dissimilarity, unbinding accuracy, bundling capacity. Measure noise characteristics.
2. **Fit correction matrices.** Projection matrices that improve algebraic fidelity: rotations for binding, subspace projections for unbinding, normalizations for bundling capacity.
3. **Validate substrate.** Enforce minimum requirements: binding must actually encrypt, unbinding must recover fillers above threshold, no catastrophic pathologies (attention sinks, degenerate dimensions).
4. **Output mapping file.** A binary artifact containing correction matrices, noise characterization, and codebook initialization. This is the compiled form — same source code + different mapping files = same program on different substrates.

The analogy to conventional compilation is direct: x86 and ARM have different instruction sets but can run the same C program. mxbai-embed-large and nomic-embed-text have different geometric properties but can run the same S2 program.

### 4.3 MCP Server as Runtime Component

The MCP (Model Context Protocol) server is not an IDE add-on. It is part of the S2 runtime, providing:
- ANN infrastructure for non-algebraic operations (snap, cone, hop)
- Codebook management for cleanup memory
- Entity resolution (context-dependent disambiguation of polysemous vectors)
- Long-range semantic dependency resolution

The semantic richness of computation in embedding spaces creates dependencies that span beyond any single file or function. The MCP server holds the semantic context that makes these dependencies resolvable — analogous to a type server resolving types across a large codebase, but for semantic relationships rather than syntactic types.

## 5. Theoretical Foundations

### 5.1 Mathematical Grounding

S2's substrate must satisfy the eight axioms of a real vector space (commutativity, associativity, identity, inverse for addition; identity, associativity, two distributivity laws for scalar multiplication). LLM embedding spaces satisfy these trivially as subsets of ℝⁿ. This means S2 inherits the full toolkit of linear algebra: subspaces, projections, eigendecomposition, orthogonal complements.

The deeper mathematical foundation is **concentration of measure** in high-dimensional spaces. In d > 1000 dimensions, randomly sampled vectors are almost certainly nearly orthogonal. This is a theorem, not an empirical observation. It guarantees that thousands of concept vectors can coexist without interference, that bundling (addition) preserves approximate membership for up to √d items, and that binding (Hadamard product) produces vectors approximately orthogonal to both inputs.

### 5.2 Lambda Calculus Encoding

Lambda terms encode as trees in superposition. Abstraction `λx.body` becomes `bind(VAR_role, x) + bind(BODY_role, encode(body))`. Application `(f a)` becomes `bind(FUNC_role, encode(f)) + bind(ARG_role, encode(a))`. Reading components back uses unbinding: `unbind(FUNC_role, encode(App(f, a))) ≈ encode(f)`.

The hard part is substitution (beta reduction), which requires modifying a distributed representation without corrupting it — equivalent to the binding problem in cognitive science (Smolensky, 1990). Current approaches require cleanup memory (snap-to-nearest) after each reduction step, which is why S2 treats snap as a first-class operation.

Tomkins-Flanagan and Kelly's working Lisp interpreter in HRR is the existence proof. Lambda calculus semantics are implementable in vector space. The price is mandatory periodic cleanup — pure algebraic computation without error correction is limited to short chains.

### 5.3 Turing Completeness

**The honest position:** VSA algebra alone is not Turing-complete. Fixed dimensionality limits superposition capacity. Approximate retrieval introduces compounding errors. Cleanup memory (snap-to-nearest) patches the error problem but introduces circularity (the codebook must contain the correct answer).

S2's Turing completeness claim: **VSA algebra + ANN-backed non-algebraic operations + external graph memory = Turing complete.** The vectors handle local computation (fixed-dimensional but algebraically rich). The graph provides unbounded external memory (the vector state navigates a graph that can grow without bound). This is architecturally identical to a CPU (fixed registers) with RAM (unbounded, addressable memory).

Flanagan et al. (2024) argue for VSA Turing completeness via Cartesian closed categories. We accept their construction but note that cleanup memory does the heavy lifting — the boundary between "VSA computing" and "lookup table computing" is not formalized in their proof. S2 makes this boundary explicit: Tier 2 operations are the VSA; Tier 3 operations are the infrastructure that patches the VSA's limitations.

## 6. Empirical Grounding

### 6.1 Algebraic Structure in Frozen Embeddings

The foundational empirical result (Leonhart, 2026): relational displacement analysis of mxbai-embed-large (1024-dim), nomic-embed-text (768-dim), and all-minilm (384-dim) using Wikidata triples discovers 86 predicates that manifest as consistent vector displacements, with 30 universal across all three models.

The correlation between geometric consistency and prediction accuracy (r = 0.861, 95% CI [0.773, 0.926]) means the algebraic structure is self-calibrating: internally consistent operations are externally useful. This is the critical empirical validation for S2 — it demonstrates that the algebraic structure needed for computation already exists in pre-trained, general-purpose embedding spaces without any VSA-specific training.

### 6.2 Binding and Unbinding in Natural Spaces

VSA operations (binding via Hadamard product, unbinding via approximate inverse) work in naturally learned embedding spaces, not just in spaces designed for VSA. This was initially surprising — natural embeddings are not orthogonal by construction — but is explained by the implicit statistical regularity from training: task-relevant subspaces are sufficiently near-orthogonal for algebraic operations to function.

This finding is critical for S2's empirical initiation: the compiler can expect algebraic operations to work in most well-trained embedding spaces, with correction matrices improving fidelity rather than creating it from scratch.

### 6.3 Substrate Validation: The mxbai Pathology

During the cartographic analysis that grounds S2, a previously unreported defect in mxbai-embed-large was discovered: diacritic characters cause catastrophic embedding collapse via attention sink (a high-magnitude key vector dominates the attention mechanism, overwriting all other token representations). Completely unrelated strings containing diacritics produce cosine similarity > 0.95.

This pathology demonstrates why S2 requires substrate validation as part of empirical initiation. The same analysis that discovered the algebraic structure also discovered a failure mode that would corrupt any computation built on the affected regions of the space. S2's validation gates — minimum requirements for binding dissimilarity, unbinding accuracy, and pathology absence — protect programs from substrate defects that standard benchmarks do not detect.

## 7. Discussion

### 7.1 What S2 Is and Is Not

S2 is a formal system for reasoning under uncertainty. It is not a replacement for Python or C++ — it does not handle I/O, graphics, or systems programming. Its domain is *semantic computation*: inference, reasoning, search, and structured manipulation of meaning in vector space.

The closest analogy is Prolog, which provides a fundamentally different computational paradigm (unification and backtracking) for a specific class of problems (logical inference). S2 provides a different paradigm (geometric operations in continuous semantic space) for a different class of problems (reasoning under uncertainty with learned representations).

### 7.2 Human-AI Collaboration in Language Design

S2 was designed through extensive human-AI conversation. The human designer brought domain insight — the recognition that embedding spaces could serve as computational substrate, the fuzzy-by-default inversion, the three-tier operation model. The AI collaborator helped formalize these ideas, stress-tested them against the theoretical literature, and identified edge cases and failure modes.

The design conversations are archived in the project repository. This collaborative process is itself a finding: AI systems can participate meaningfully in the creative, speculative phase of language design — not just code generation, but conceptual architecture.

### 7.3 Future Directions

**Syntax design.** S2's semantics are solidifying but no concrete syntax has been defined. The syntax must make the three operation tiers visually distinct so programmers can immediately see where expensive non-algebraic operations occur.

**JEPA integration.** S2 naturally connects to Joint Embedding Predictive Architecture (LeCun, 2022). HDC provides algebraic structure; JEPA provides learned prediction. A two-phase training approach (algebraic consistency first, predictive coding second) could produce embedding spaces optimized for S2 computation.

**Product manifold embeddings.** Different semantic relationships naturally live in different geometries: hierarchies in hyperbolic space, analogies in Euclidean space, cycles on spheres. A product manifold embedding combining these geometries could give S2 richer type semantics where the geometry of a subspace determines what operations are natural in it.

**Implementation and benchmarks.** The most important next step. Candidate benchmark tasks: semantic search with algebraic pre-filtering, compositional multi-hop inference via vector arithmetic, and structured prediction exploiting discovered algebraic regularities.

## 8. Conclusion

S2 demonstrates that LLM embedding spaces can serve as a computational substrate for a programming language, not just a lookup table for similarity search. The language's novel contributions — three-tier operations, truth-extraction matrices, empirical initiation, cone traversal as control flow — are grounded in empirical evidence that frozen embedding spaces encode consistent algebraic structure.

The design makes an honest assessment of its own limitations: VSA algebra alone is not Turing-complete, non-algebraic operations are expensive, noise accumulation requires periodic cleanup, and embedding substrates can have silent pathologies. These limitations are explicitly addressed in the language design rather than hidden.

S2 is less like a traditional programming language and more like a formal system for reasoning under uncertainty. It occupies a previously empty niche — continuous semantic computation as a programming paradigm — and provides a concrete framework for exploiting the algebraic structure that neural networks produce but that no existing system treats as a first-class computational resource.

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
