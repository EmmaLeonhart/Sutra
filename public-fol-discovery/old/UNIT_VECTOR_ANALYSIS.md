# Unit Vector Analysis: mxbai-embed-large Pre-Normalization

## Discovery (2026-03-31)

All embeddings from Ollama's `mxbai-embed-large` are **L2-normalized to unit norm** (||v|| = 1.0000 exactly). This means every embedding sits on the surface of a 1024-dimensional unit hypersphere.

### Verification

```
Total embeddings: 90,827 (shape: 90827 × 1024)
Overall norm: mean=1.0000, std=0.0000, min=1.0000, max=1.0000
Colliding embeddings (34,291): norm mean=1.0000
Non-colliding embeddings (56,536): norm mean=1.0000
```

There is **zero magnitude variation** — the model normalizes as a final step.

## Implications

### What This Means

1. **Cosine similarity = dot product.** Since ||u|| = ||v|| = 1, cos(u,v) = u·v. All `np.dot(u,v) / (norm(u)*norm(v))` calculations are dividing by 1.0.

2. **Euclidean distance is a function of cosine similarity.** On unit vectors: `||u - v|| = sqrt(2(1 - cos_sim))`. Euclidean distance carries no information beyond cosine similarity.

3. **Displacement magnitude is derived, not independent.** The "magnitude coefficient of variation" metric in FOL discovery measures variation in `||obj - subj||`, which on unit vectors equals `sqrt(2(1 - cos_sim))` — it's a monotonic transform of cosine distance.

4. **No magnitude-based glitch token signal possible.** Classic glitch tokens (Li et al., 2024) have anomalous norms (near-zero / near-centroid). Since mxbai normalizes all outputs, any magnitude anomalies are erased. Our Jinmyōchō collapse is purely directional (cosine crowding), not magnitude-based.

5. **Geodesic vs cosine distance.** On a unit sphere, true geodesic distance = arccos(cos_sim), which differs from cosine distance (1 - cos_sim). Our density analysis uses cosine distance. Since regime assignments use relative percentiles (P25, P75), rankings are preserved — only absolute values differ.

### What Is NOT Affected

- **FOL discovery results are valid.** Consistency metrics use cosine similarity of normalized displacements. The displacement vectors themselves are NOT unit norm (subtracting two unit vectors doesn't produce a unit vector), so the normalization step on displacements is correct and necessary.
- **Prediction accuracy is valid.** The `predicted = subject + mean_displacement` step correctly re-normalizes before nearest-neighbor search.
- **Collision detection is valid.** Cosine similarity ≥ 0.95 threshold is well-defined on unit vectors.
- **Three-regime classification is valid.** Uses relative percentiles, not absolute distance values.
- **Paper 3 dimensional decomposition is valid.** Orthogonal projection breaks unit norm, but scipy's cosine distance re-normalizes implicitly.

### Redundant Operations in Codebase

The following normalization steps are harmless but unnecessary:
- `fol_discovery.py`: cosine similarity calculations divide by `norm(u) * norm(v)` = 1.0
- `analyze_collisions.py`: re-normalizes already-unit embeddings
- `measure_collapse_geometry.py`: same redundant normalization

These are left as-is for safety (if embeddings from a different model are ever used).

## Recommendation for Paper

The paper should disclose:
1. That mxbai-embed-large returns pre-normalized unit vectors
2. That all reported distances are cosine distances (1 - cos_sim)
3. That displacement magnitude metrics are derived from cosine distances on the unit hypersphere

None of these change the conclusions, but they provide important context for reproducibility and interpretation.
