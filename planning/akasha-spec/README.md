# Akasha Language Specification (Draft)

Akasha is a vector programming language that uses LLM embedding spaces as its computational substrate. Named after the concept of a fundamental substrate or medium pervading all things — the language literally implements deliberate, effortful reasoning by computing in continuous semantic space.

Akasha is not a scripting language bolted onto an AI. It is a formal system for reasoning under uncertainty, closer to Prolog than Python, but operating in continuous rather than discrete space. Code compiles to vector operations that execute inside an embedding space the way conventional code compiles to machine instructions that execute on silicon.

## Spec Documents

### Core Language
- [Design Principles](01-design-principles.md) — fuzzy-by-default, vectors as only type, computation is geometry
- [Operations](02-operations.md) — three-tier model: primitive, algebraic/VSA, non-algebraic/vector-graph
- [Control Flow](03-control-flow.md) — fuzzy branching, cone traversal, iteration
- [Defuzzification](04-defuzzification.md) — `is_true` and recursive confidence extraction
- [Type System](05-type-system.md) — no wrong types (only noise), mixed-regime spaces, entity resolution

### Runtime & Compilation
- [Runtime Architecture](06-runtime.md) — S1/Akasha dual runtime, MCP server as runtime component
- [Empirical Initiation](07-empirical-initiation.md) — probing, correction matrices, validation gates, cross-substrate compilation
- [Abstraction Level](08-abstraction-level.md) — "C-tier" for vector spaces, what the compiler handles vs. what the programmer writes

### Theoretical Foundations
- [Lambda Calculus Encoding](09-lambda-calculus.md) — term mapping, substitution problem, de Bruijn indices, Smolensky, Tomkins-Flanagan
- [Turing Completeness](10-turing-completeness.md) — CCC argument, what was proven, two obstacles, non-algebraic patch
- [VSA Mathematical Grounding](11-vsa-math.md) — VSA vs HDC, concentration of measure, eight axioms, domain-agnostic embeddings

### Extensions & Research
- [JEPA Hybrid Architecture](12-jepa-hybrid.md) — two-phase training, mixed-regime latent spaces, staged commitment, product manifolds
- [Perceptiveness Parameter](13-perceptiveness.md) — novel attention mechanism, geometric surprisingness, 2D behavioral space
- [Entity Resolution](14-entity-resolution.md) — fidelity mismatch, canonicalization endpoint, active retrieval during inference

### Risks & Status
- [Embedding Pathologies](15-embedding-pathologies.md) — mxbai diacritic bug, attention sink mechanism, blast radius
- [Known Defects](16-known-defects.md) — noise accumulation, iteration, cleanup circularity, permutation question
- [Open Questions](17-open-questions.md) — syntax, iteration, benchmarks, and everything else unresolved
- [Compute Savings](18-compute-savings.md) — adjacent benchmarks, the missing FLOPS benchmark, what Akasha needs to prove
