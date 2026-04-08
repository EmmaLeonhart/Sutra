# Open Questions

- **Syntax:** Semantics are solidifying but no concrete syntax yet. The syntax needs to make algebraic vs. non-algebraic operations visually distinct so programmers can see where the expensive ops are.
- **Iteration:** Which approach (unrolling, convergence, state encoding) works best? Likely task-dependent — may need all three as options.
- **`is_true` fixed-point behavior:** Converge, oscillate, or tunable? Needs formal analysis and empirical testing.
- **Mixed-regime dimensions:** How to express geometric heterogeneity (hyperbolic, Euclidean, spherical) in source code? This may require a richer type system than "everything is a vector."
- **Permutation:** Probably not needed for S2. Confirm and drop.
- **Cosine vs Euclidean:** When does magnitude matter? Should similarity metric be configurable per operation?
- **Codebook design:** What vectors are "known good"? How is the codebook populated, maintained, and grown during computation?
- **Perceptiveness parameter integration:** How does the inquisitiveness/perceptiveness parameter generalize beyond attention? Could similar tunable behavioral parameters exist for other operations?
- **Canonicalization semantics:** What does `canonicalize(v, context)` return exactly? A codebook vector? A Wikidata QID? A point in a canonical entity space? All three?
- **Training pipeline:** How to train a model that produces S2-friendly embedding spaces (Phase 1 + Phase 2 from [JEPA Hybrid](12-jepa-hybrid.md))?
- **Benchmark suite:** What tasks should S2 be benchmarked on to demonstrate practical value?
