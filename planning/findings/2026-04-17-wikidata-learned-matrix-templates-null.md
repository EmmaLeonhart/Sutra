# 2026-04-17: Sentence-template embeddings don't rescue learned matrices on nomic

Follow-up to `2026-04-17-wikidata-learned-matrix-null.md`, which
hypothesized that embedding *sentence templates* carrying the relation
in the subject side (e.g. "The capital of France is") would increase
between-pair variance enough for a learned role matrix to recover a
nontrivial mapping. It does not.

## What was measured

Four text configurations for the subject, fixed bare text for the object
(so codebook retrieval is apples-to-apples across configs):

| Config | Subject template | Example |
|--------|------------------|---------|
| `bare` | `{s}` | `France` |
| `typed` | `{s} (country)` | `France (country)` |
| `rich` | `{s}, a country` | `France, a country` |
| `relational` | `The capital city of {s} is` | `The capital city of France is` |

Same eight methods as the prior null: identity, mean_object, displacement,
Procrustes, ridge λ∈{1.0, 0.1}, lowrank r=30, random. 5-fold CV. Ollama
`nomic-embed-text` (768-dim, mean-centered + L2-normalized).

Script: `sutra-paper/scripts/learned_matrix_templates.py`
Raw results: `sutra-paper/scripts/learned_matrix_templates_results.json`

## Raw numbers

### capital-of (152 pairs, 138 unique capitals — chance 0.72%)

| Method | bare | typed | rich | relational |
|--------|------|-------|------|------------|
| identity | 0.67% | 2.00% | 1.33% | 2.00% |
| mean_object | 0.67% | 0.67% | 0.67% | 0.67% |
| displacement | 1.33% | 1.33% | 0.67% | 0.67% |
| procrustes | 0.67% | 0.67% | 0.67% | 0.67% |
| ridge_1.0 | 0.67% | 0.67% | 0.67% | 0.67% |
| lowrank_30 | 0.67% | 0.67% | 0.67% | 0.67% |

### continent-of (200 pairs, 10 codebook entries — chance 10%)

| Method | bare | typed | rich | relational |
|--------|------|-------|------|------------|
| identity | 24.5% | 24.5% | 25.0% | 0.5% |
| mean_object | **30.5%** | **30.5%** | **30.5%** | **30.5%** |
| displacement | 24.5% | 25.5% | 29.0% | 30.5% |
| procrustes | 29.0% | 29.0% | 30.0% | 30.0% |
| ridge_1.0 | 30.0% | 30.5% | 30.5% | 30.5% |
| lowrank_30 | 30.0% | 30.5% | 30.5% | 30.5% |

## Interpretation

**No text configuration separates learned matrices from the mean-object
baseline.** On high-entropy predicates (capital-of), everything collapses
to near-chance — the within-cluster structure of capital embeddings is
too tight for any linear operator to pick out the right capital from a
subject vector. On low-entropy predicates (continent-of), the learned
methods tie with `mean_object` at 30%, which is just the majority class
(most countries in the sample are in Europe/Asia). That is not learning
a relational operator; it is learning a prior.

**The relational template actively hurts identity.** On continent-of,
identity drops from 24.5% (bare) to 0.5% (relational). Embedding "The
country France is located on the continent of" pushes the subject vector
far from any continent name, so `S_test @ I` no longer retrieves the
right continent. The learned methods partially compensate by learning
the output distribution (the mean-object prior), but none learns a
subject-specific mapping.

**This is the same failure mode as the bare-name null**, now confirmed
under richer text. The relational signal in nomic's 768-dim space for
short Wikidata entity labels is dominated by the lexical cluster
structure; templates don't inject enough distinguishing information.

## What remains to test

This closes the door on **nomic + short Wikidata labels**. The cartography
paper's positive result used embeddings of structured Wikidata labels
(often with disambiguation context and longer alias strings). Open:

1. **Different substrate.** GTE-large (1024-dim) or BGE-large. The
   mxbai pathology caveat still applies to that model. sentence-
   transformers install required.
2. **Longer text per entity.** Embed Wikipedia lead paragraphs or
   Wikidata descriptions (not labels) as the subject/object text. Slower
   but may carry more relational signal.
3. **Learned affine instead of learned linear.** `M @ s + b` with a
   learned bias vector, since the bias might absorb the mean-object
   prior and free the matrix to learn structure.

## Implication for the Sutra paper

The language paper's limitations bullet ("Current runtime uses a
placeholder binding") is still honest and should stay. Two nulls on the
learned-matrix direction is enough data to not claim it as a headline
contribution. The spec keeps "roles are learned matrices" as the design
vision (per `planning/sutra-spec/binding.md`), but the paper should not
claim the implementation delivers it.
