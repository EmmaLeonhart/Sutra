# S2 Substrate Comparison — Empirical Initiation Results

All tests run on 20 diverse English sentences. Euclidean distance as primary metric.
Non-normalized output (raw mean-pooled last hidden states, no F.normalize).

## Results Summary

| Model | Dims | Mag Mean | Mag Std | Binding | Unbinding | Bundling | Capacity | Approved? |
|-------|------|----------|---------|---------|-----------|----------|----------|-----------|
| **GTE-large** | 1024 | 19.08 | 0.43 | PASS (cos 0.13) | PASS | PASS (0.92 vs 0.77) | ~4 | YES |
| **BGE-large-en-v1.5** | 1024 | 17.29 | 0.46 | PASS | PASS | PASS | ~4 | YES |
| **Jina-v2-base-en** | 768 | 26.43 | 1.43 | PASS | PASS | PASS | ~3 | YES |
| **mxbai-embed-large** | 1024 | 17.38 | 0.46 | PASS | PASS | PASS | ~5 | YES* |

*mxbai passes algebraic tests but has documented diacritic attention-sink pathology not covered by these gates.

## Key Observations

### Magnitude Distribution
- **All four models produce non-normalized vectors** when accessed via raw transformers (not through Ollama or sentence-transformers normalization layers)
- Magnitudes range from ~17 to ~26, NOT ~1.0
- **Jina has the highest magnitude variation** (CV = 0.054) — most information in magnitude
- GTE and BGE are comparable (~17-19 magnitude, ~0.43-0.46 std)

### Binding Quality
- All models show strong binding encryption (cosine to inputs drops to 0.08-0.17)
- GTE-large has the best binding: cosine drops to ~0.13 (most dissimilar from inputs)
- This is the core operation for S2 — all substrates support it

### Unbinding Quality
- All models recover targets better than random baseline
- This is the noisiest operation — the fundamental limit on chain depth
- Snap-to-nearest is required after ~2-3 unbinding operations

### Bundling Capacity
- **All substrates have low capacity (~3-5 items)** before SNR degrades
- This is much lower than theoretical √d ≈ 32 because natural embeddings are NOT random orthogonal vectors — they share significant structure (anisotropy)
- Implication: S2 programs on natural embedding substrates must use snap-to-nearest aggressively
- Higher capacity would require either (a) higher dimensionality or (b) VSA-trained embeddings

### mxbai Passes Algebra, Fails Integrity
- mxbai's algebraic operations work fine — the diacritic bug is an attention-mechanism pathology, not an algebraic one
- This proves that validation gates need BOTH algebraic tests AND pathology detection
- A substrate can be algebraically sound but still have silent corruption modes

## Recommendation for S2 Paper

**Primary substrate: GTE-large.** Best binding quality, good magnitude variation, no known pathologies, 1024 dimensions.

**Include comparison table in paper** to show S2 works across multiple substrates — this validates the empirical initiation concept (same tests, different models, comparable results).

**Note the capacity limitation** honestly — ~4 items is real and means snap-to-nearest is load-bearing, not optional. This is a finding, not a weakness — it quantifies something the VSA literature often hand-waves.
