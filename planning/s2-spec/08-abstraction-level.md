# Abstraction Level

S2 sits between assembly and a high-level language — "C-tier" for vector spaces. The programmer is always aware they're in hypervector space but doesn't manage codebooks manually. You think in terms of binding roles to fillers, superposing alternatives, and querying similarity — not in terms of individual float operations or ANN index parameters.

The compiler handles:
- Empirical initiation (probing the target embedding space, fitting matrices)
- Codebook management (building, maintaining, growing the snap-to-nearest codebook)
- ANN infrastructure (indexing for snap, cone, and hop operations)
- Substrate validation (detecting pathologies, enforcing validation gates)
- Noise budgeting (inserting snap-to-nearest operations where noise would exceed thresholds)

The programmer writes in terms of semantic operations. The compiler makes them run on a specific substrate.
