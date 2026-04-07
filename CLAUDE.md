# Latent Space Cartography → Hyperdimensional Computing Paper

## Three Pillars (the core contributions)

1. **HDC framework for logical inference on frozen embeddings** — Chains of logical inference implemented as vector operations on existing general-purpose embeddings. Massively cheaper than full model inference. The displacement vectors are binding/unbinding operators, and composition (multi-hop) is sequential binding.

2. **Emergent VSA in frozen embeddings** — General-purpose text embeddings (mxbai-embed-large, nomic-embed-text, all-minilm) spontaneously implement Vector Symbolic Architecture binding/unbinding operations without being trained for them. 30 universal relations manifest across all three models. This is an emergent property, not a trained one.

3. **Critical production defect in mxbai-embed-large** — The [UNK] token dominance defect causes 147,687 cross-entity embedding collisions. Strings with diacritical marks collapse into identical vectors (cosine 1.0 between unrelated entities like "Hokkaidō" and "Éire"). Makes the model nearly useless for any domain with non-ASCII text. Missed by standard benchmarks like MTEB.

## Paper Strategy
- **Quality over quantity** — This is the one paper we're focusing on for Claw4S 2026
- **Aiming for the $5,000 prize**
- **Extended deadline: ~April 20, 2026**
- **Current status:** Post 859, paper_id 2604.00859, v15, Strong Accept
- **Repo:** EmmaLeonhart/latent-space-cartography

## Key Criticisms to Address
- **"It's just TransE"** (10/15 reviews) — Fix by reframing as VSA/HDC, which it actually is
- **"Tautology" in consistency-accuracy correlation** (9/15 reviews) — Fix with proper train/test split
- **"Grandiose framing"** — Don't overclaim. Let the empirical results speak.
- See `planning/` directory for detailed analysis

## Workflow
- Push changes to paper.md or SKILL.md → CI auto-submits to clawRxiv → fetches AI review → commits review to reviews/
- Planning docs in `planning/`
- All 15 historical reviews in `reviews/`

## Technical Notes
- Scripts in `scripts/`, main analysis is `fol_discovery.py`
- Data regenerable from Wikidata + Ollama (mxbai-embed-large, 1024-dim)
- Frozen model weights in `model/` (Git LFS)
- Use `python` not `python3` on this system
