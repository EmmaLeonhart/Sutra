# Type System Considerations

## No Wrong Types, Only Noise
There are no type errors in S2. Binding two unrelated vectors produces a result — it's just semantically meaningless (low similarity to anything useful). The type system is replaced by **similarity checking**: "does this result look like what I expected?"

## Mixed-Regime Spaces
Not all dimensions need to be the same kind:
- **Binary/ternary dimensions:** Structural roles, categorical membership (crisp)
- **Continuous dimensions:** Similarity, degree, graded properties (fuzzy)
- **Hyperbolic dimensions:** Hierarchical/taxonomic relationships (tree-like)
- **Euclidean dimensions:** Lateral/analogical relationships (flat)

This is speculative but suggests S2's "vector" type could have geometric subtypes reflecting different kinds of semantic structure.

## Entity Resolution Is Native
The same symbol in different contexts maps to different vectors. S2 handles this through context-dependent embedding — entity resolution is part of the runtime, not a preprocessing step. The MCP server maintains context for disambiguation.

## Computational Complexity

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
