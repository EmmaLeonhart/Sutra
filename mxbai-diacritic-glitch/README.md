# mxbai-embed-large Diacritic Collision Glitch

## Summary

The `mxbai-embed-large` embedding model (mixedbread-ai/mxbai-embed-large-v1) has a systematic failure mode: its WordPiece tokenizer strips diacritical marks during normalization, causing semantically unrelated terms to produce near-identical embeddings.

This means "Hokkaidō" and "Hokkaido", "Tōkyō" and "Tokyo", "România" and "Romania" all tokenize identically — and more critically, unrelated terms whose only distinguishing feature is a diacritic (ō vs o, ñ vs n, ç vs c) collapse into the same region of embedding space.

## The Japanese ō Problem

The most dramatic case involves the Japanese long vowel mark (macron): ō. In romanized Japanese (Hepburn romanization), the macron distinguishes completely different words:

- **o** (お) vs **ō** (おう/おお) — different vowels, different meanings
- **Shōtoku** (聖徳) vs **Shotoku** — the macron carries semantic content
- **Jinmyōchō** (神名帳) — a specific historical register — collides with 504 other entities

But the actual behavior is worse than simple stripping. The model doesn't map "Hokkaidō" close to "Hokkaido" — it maps **all** diacritic-containing short terms to the **same point**, regardless of language or meaning:

| Text A | Text B | Cosine | Related? |
|--------|--------|--------|----------|
| Jinmyōchō (Japanese register) | kugyō (Japanese court rank) | 1.0000 | No |
| Hokkaidō (Japanese island) | Éire (Ireland in Irish) | 1.0000 | No |
| Filasṭīn (Palestine in Arabic) | Jinmyōchō | 1.0000 | No |
| Aikanã (Brazilian language) | kugyō | 1.0000 | No |
| naïve (English/French) | Zürich (Swiss city) | 1.0000 | No |
| Hokkaidō | Hokkaido (its own ASCII form) | 0.4500 | Yes! |

The diacritic version of a word is **closer to every other diacritic-containing word on Earth** (cosine 1.0) than to its own ASCII equivalent (cosine ~0.45). The model collapses all diacritic-rich inputs into a single point in embedding space.

## Scale of the Problem

In our Engishiki-seeded dataset (from [Leonhart 2026](../papers/fol-discovery/paper.md)):

- **164,084** cross-entity embedding pairs at cosine ≥ 0.95
- **147,687** genuine semantic collisions (different text, near-identical vector)
- "Hokkaidō" alone collides with **1,428** other entities
- Collisions span romanized Japanese, Arabic, Irish, Brazilian indigenous languages, and IPA

## Why This Matters

If your RAG pipeline, semantic search, or knowledge graph uses mxbai-embed-large with multilingual text, you will get wrong retrievals. The model returns confident, well-formed embeddings — they just happen to be indistinguishable from hundreds of other inputs.

This is not a rare edge case. Any corpus containing romanized Japanese, Vietnamese, Turkish, Romanian, Irish, or Arabic text will trigger it.

## Reproducing

```bash
# Requires: Ollama running locally with mxbai-embed-large pulled
ollama pull mxbai-embed-large
python demo_collisions.py
```

This generates `collisions.csv` showing cosine similarities between diacritic/non-diacritic pairs and between semantically unrelated terms that collide due to diacritic stripping.

## Root Cause

**Tokenizer:** WordPiece (BERT-based)
**Behavior:** Unicode normalization strips combining diacritical marks before subword tokenization
**Effect:** `ō` → `o`, `ñ` → `n`, `ç` → `c`, `ü` → `u` at the token level

The embedding model never sees the diacritics. It cannot learn to distinguish inputs that differ only by diacritical marks because that information is destroyed before it reaches the model.

## Reference

This glitch is documented in detail in Section 5.4 of:

> Leonhart, E. (2026). "Relational Displacement in Arbitrary Embedding Spaces: Oversymbolic Collapse and the Limits of Vector Arithmetic." Claw4S Conference 2026.
