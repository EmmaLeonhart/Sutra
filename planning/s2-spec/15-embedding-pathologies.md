# Embedding Model Pathologies

## The mxbai-embed-large Diacritic Bug

During development of the FOL discovery system in this repo, a major defect was discovered in mxbai-embed-large (the 1024-dimensional embedding model used as S2's initial substrate). Diacritic characters — specifically macron vowels (o-macron, u-macron, etc.) used in Japanese romanization — cause **catastrophic embedding collapse**.

## The Mechanism: Attention Sink

The bug is not a simple out-of-vocabulary collapse. The pathological token has a **high-magnitude key vector** that dominates the attention mechanism:

1. The diacritic character tokenizes to a token with an unusually high-magnitude key vector
2. During the attention computation, this high-magnitude key attracts disproportionate attention from all query vectors
3. The attention distribution collapses — nearly all attention weight goes to the pathological token
4. All other tokens' representations get overwritten by the pathological token's value vector
5. The final embedding (which pools over all token positions) is dominated by the single pathological token

The result: completely unrelated strings containing diacritic characters produce nearly identical embeddings (cosine similarity > 0.95). The model produces **confident-looking but completely corrupted** embeddings — there is no error signal, no NaN, no obvious failure. The embeddings look normal until you check that "Shinto shrine architecture" and "Tokyo ramen restaurant" have cosine similarity 0.98.

## Blast Radius

Any text containing diacritic characters is affected:
- **Japanese romanization** (romaji): shrine names, place names, historical terms
- **Polynesian languages**: Hawaiian, Maori, Samoan — macron vowels are standard orthography
- **Academic/linguistic text**: IPA transcriptions, transliterations, medieval manuscript studies
- **Music**: tempo markings, non-English musical terms

This is not a niche issue. Entire languages and academic fields are silently broken.

## Model-Specific

The bug is **mxbai-specific**. The same texts embedded with OpenAI's text-embedding-3-small, nomic-embed-text, or BGE-large produce correct, discriminating embeddings. The pathological attention sink behavior points to either:
- A training data issue (diacritic characters underrepresented or corrupted in training)
- A tokenizer issue (pathological tokenization of diacritic characters)
- An architectural issue (no attention sink mitigation in the model design)

The exact cause is unknown but the defect is reliably reproducible.

## Implications for S2

This is a **foundational risk** for S2. If the computational substrate has silent corruption modes, all computation built on it is unreliable in ways that are invisible without explicit checking.

S2 must include:

1. **Substrate validation at empirical initiation time.** When S2 probes a target embedding space, it should test for known pathologies (attention sinks, degenerate dimensions, collapse modes). A model that fails validation should be rejected as a substrate.

2. **Runtime integrity checking.** Vectors produced by computation should be periodically checked for degeneracy — unexpectedly high magnitude, unexpectedly high similarity to unrelated vectors, collapse to a low-dimensional subspace. These are symptoms of substrate pathology propagating into computation.

3. **Substrate abstraction.** S2 programs should be substrate-agnostic — the same program runs on any embedding model that passes validation. If mxbai has a defect, swap to nomic or BGE without changing the program. This is already part of the design (empirical initiation produces different mappings for different models) but the pathology risk makes it load-bearing rather than just convenient.

4. **Defensive codebook design.** The snap-to-nearest codebook should be tested for collision sensitivity — if two unrelated codebook entries are unusually close in the substrate space (possibly due to a diacritic-style collapse), flag it.
