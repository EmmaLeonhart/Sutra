# Known Defects and Risks

## Noise Accumulation
Without periodic snap-to-nearest, computation degrades over long chains. The tension between algebraic purity (stay in continuous space) and practical reliability (discretize periodically) is a core design challenge. Every snap-to-nearest is an admission that the algebra alone isn't enough — but without them, the algebra produces garbage after a few steps.

## Iteration
No clean solution yet. Fixed unrolling limits expressiveness. Convergence-based termination is elegant but hard to guarantee. State encoding with counter binding is the most VSA-native approach but accumulates noise per iteration. This is the biggest open problem.

Note: bounded integer iteration (`repeat N:`) exists as a primitive operation and covers the most common case pragmatically.

## Substrate Pathologies
Documented in detail in [Embedding Pathologies](15-embedding-pathologies.md). The computational substrate can have silent failure modes that propagate into all computation built on it. Empirical initiation with validation gates is the mitigation.

## Cleanup Memory Circularity
Snap-to-nearest requires a codebook of "correct" vectors. But for arbitrary computation, the set of correct intermediate results is not known in advance. The codebook must either be (a) precomputed for a specific problem domain (limiting generality), (b) grown during computation (requiring a policy for when to add entries), or (c) universal (impractically large). This is the circularity at the heart of the Turing completeness argument.

## Permutation May Be Unnecessary
VSA traditionally includes permutation (cyclic shift) as a third operation alongside binding and bundling, used to encode sequential order. In S2, sequential/positional relationships are more naturally encoded via relation types (binding with a POSITION_role) rather than permutation. Permutation is also not differentiable (it's a discrete operation) which makes it awkward in continuous embedding spaces. Current assessment: probably drop permutation from S2, use relation-typed binding instead. This is an open question pending more design work.
