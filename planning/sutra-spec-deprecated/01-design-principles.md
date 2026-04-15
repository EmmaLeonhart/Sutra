# Design Principles

## Fuzzy-by-Default
Uncertainty is the ground truth; precision is the special case. Every value carries implicit confidence. This inverts conventional languages where you have crisp logic and bolt on probabilistic stuff as a library.

## Vectors Are the Only Type
One type: the hypervector. There are no integers, strings, or booleans as primitives. Numbers, symbols, and structures are all represented as vectors in semantic space. Addition is bundling. Multiplication is binding. There are no "wrong type" errors — only noisy or meaningless results. Equality is replaced by similarity.

## Computation Is Geometry
Operations are similarity, projection, interpolation, rotation, scaling. Programs navigate and transform regions of semantic space. The execution environment is fundamentally semantic rather than symbolic — operations have meaning in a way that silicon arithmetic doesn't.

## Commutative
Every object is a vector that can be decomposed with certain operations. The algebraic operations are commutative.

## Long-Range Dependencies
The semantics are too rich and context-dependent for any single file to capture. IDE/MCP tooling is load-bearing, not optional. This is a feature — the tooling becomes part of the language runtime.
