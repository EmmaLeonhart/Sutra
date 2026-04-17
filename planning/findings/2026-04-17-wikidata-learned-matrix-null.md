# 2026-04-17: Wikidata-scale learned-matrix binding — null result on nomic

## What was measured

Four candidate role-matrix methods (displacement, orthogonal Procrustes,
ridge regression, low-rank regression at ranks 10/30/50) on four Wikidata
predicates (capital-of, located-in-country, author-of, country-of-citizenship),
with nomic-embed-text (768-dim, mean-centered + L2-normalized) embeddings
of bare entity names. 5-fold CV, top-1 retrieval against per-predicate
object codebooks.

## Setup

- Script: `sutra-paper/scripts/learned_matrix_eval.py`
- Model: nomic-embed-text via Ollama
- 167–200 (subject, object) pairs per predicate from Wikidata SPARQL
- Baselines: identity (M = I), mean-object (constant centroid), random Gaussian

## Raw numbers

```
capital-of (167 pairs, 157 unique objects):
  identity       top1=60.6%  mean_cos=0.960
  mean_object    top1=83.0%  mean_cos=0.983
  displacement   top1=60.6%  mean_cos=0.962
  procrustes     top1=59.4%  mean_cos=0.957
  ridge_1.0      top1=83.0%  mean_cos=0.983
  lowrank_30     top1=83.0%  mean_cos=0.983

country-of-citizenship (200 pairs, 1 unique object):
  DEGENERATE — all 200 people mapped to same country.

located-in-country (196 pairs, 15 unique countries):
  identity       top1=0.5%   mean_cos=0.890  (chance=6.7%)
  mean_object    top1=3.1%   mean_cos=0.999
  displacement   top1=2.1%   mean_cos=0.930
  procrustes     top1=2.1%   mean_cos=0.922
  ridge_1.0      top1=2.1%   mean_cos=0.999

author-of (198 pairs, 147 unique works):
  identity       top1=24.1%  mean_cos=0.898
  mean_object    top1=24.6%  mean_cos=0.921
  displacement   top1=24.1%  mean_cos=0.901
  procrustes     top1=26.2%  mean_cos=0.903  ← best, +2pp over identity
  ridge_1.0      top1=24.6%  mean_cos=0.920

instance-of: Wikidata SPARQL timeout.
```

## Interpretation

**No method meaningfully beats identity.** The learned methods (ridge,
lowrank) converge to the mean-object baseline because they are severely
underdetermined (768² params from ~160 training pairs, regularized to
the centroid). Procrustes edges identity by 2pp on author-of — marginal.

**The underlying problem is substrate-level clustering.** Nomic
embeddings for short entity names (country names, capital names, author
names, book titles) are all extremely correlated — cos > 0.95 between
virtually any pair within a predicate's domain. This means:

1. The relational signal (France→Paris vs France→Berlin) is tiny
   compared to the global cluster structure
2. Any method that learns from (subj, obj) pairs mostly learns "the
   average object embedding" because the variance across objects is
   negligible relative to their distance from the origin
3. Identity "works" for capital-of (60%) only because country names
   happen to be nearby their own capitals — a lexical-proximity effect,
   not a learned relational one

**This is the same failure mode as the 30-sentence probe**
(`2026-04-15-nomic-object-matrix-identity-wins.md`) at 5× the scale.
The explanation is consistent: nomic's semantic compression puts short
entity names in a tight cluster; the within-cluster structure does not
support linear role extraction.

## What this does NOT mean

- **It does not mean "roles can't be matrices."** It means bare entity
  names in nomic don't have enough variance for the matrix to learn from.
  Longer texts (full Wikipedia abstracts, multi-sentence descriptions),
  a larger/different embedding model, or predicate-specific featurization
  might all change the picture.
- **It does not rescue sign-flip binding.** Sign-flip is still rejected.
  The right response to "learned matrices don't work on nomic with bare
  names" is "fix the experimental setup," not "go back to random roles."
- **It does not invalidate the cartography displacements.** Those were
  measured on structured Wikidata labels with more context. The
  experimental setup here (bare entity names only) is more impoverished
  than the cartography setup.

## Follow-up experiments

1. **Richer texts.** Embed "France is a country in Europe" rather than
   just "France". The cartography paper embedded Wikidata labels which
   sometimes include disambiguating context.
2. **Different substrate.** Try GTE-large (1024-dim) or text-embedding-3-large.
   The anisotropy might be less severe on larger models.
3. **Predicate-specific text templates.** "The capital of France is ___"
   vs just "France" — structural templates that tell the embedding model
   what role to attend to.
4. **More discriminative predicates.** "Continent of" (only 7 classes,
   well-separated), "language family" (distinct semantic clusters),
   "chemical element → symbol" (very distinct).
