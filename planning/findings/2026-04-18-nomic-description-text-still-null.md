# 2026-04-18: Wikidata description text doesn't rescue nomic either

Third nomic null, closing the "maybe it was label length" door from
`2026-04-17-wikidata-learned-matrix-templates-null.md`. Adding the
Wikidata description to the subject text (`"{s}: {desc}"` — typically
30–80 chars instead of a 5–15-char bare label) does not move nomic
off its collapse attractor. The substrate is the problem, not the
text length.

## What was measured

Five predicates fetched from Wikidata SPARQL with both `?sLabel` and
`?sDesc` (schema:description in English). Two subject-text configs:
`bare` (the label alone, e.g. "France") and `descr` (label + colon +
description, e.g. "France: country in Western Europe"). Object side
stays bare for apples-to-apples codebook retrieval. Same matrix-method
suite and 5-fold CV as prior evals.

Script: `sutra-paper/scripts/learned_matrix_templates.py --model nomic-embed-text --configs bare descr`
Raw: `sutra-paper/scripts/learned_matrix_nomic_descr_results.json`

## Top-1 accuracy, `bare` vs `descr` on nomic

| Predicate | CB | Chance | bare best | descr best | Δ |
|-----------|----|--------|-----------|------------|---|
| capital-of         | 126 | 0.79% | 1.5% (disp)  | 1.5% (identity) | 0 |
| country-of-citizenship | **1** | 100% | 100% | 100% | broken (collapsed codebook, ignore) |
| located-in-country |  21 | 4.76% | 41.0% (procr/mean) | 40.0% (displacement) | –1 |
| author-of          | 169 | 0.59% | 0.5% | 2.1% (procr) | +1.5 |
| continent-of       |   7 | 14.29% | 1.5% (identity) | 4.0% (procr) | +2.5 |

All movement is within noise. On continent-of and capital-of, every
method (learned or identity) scores well below chance because nomic's
country and city embeddings are so tight in cosine space (identity
mean_cos = 0.95 on continent-of) that ranking is dominated by
substrate-level structure unrelated to the predicate. On located-in-
country, mean_object and the learned matrices all tie around 40% —
the majority-class prior that was also the ceiling in the template
experiment.

**The story is unchanged: nomic collapses across all text richness
levels.** Bare names, typed names, rich paraphrases, relational
sentence templates, and now label+description text all produce the
same picture. On the side, the extra description content pulls the
subject vector *away* from the object vector (identity mean_cos drops
from 0.95 → 0.62 on continent-of) without buying top-1 accuracy.

## Comparison to GTE-large

Same script, same predicates, different substrate: on GTE-large, the
bare config gives ridge-0.1 = 87% on continent-of and 76% on located-
in-country (see `2026-04-17-gte-large-learned-matrix-positive.md`).
On nomic, the same config gives ~2% and ~40% (mean_object-tied). The
gap is substrate, not text.

Hypothesis: nomic-embed-text was trained with a heavy retrieval-
matching objective that compresses entity labels from the same topical
domain (countries, cities, books) into a tight anisotropic cluster.
Relational operators don't survive that compression because the
within-domain geometry is too flat for a linear map to separate
specific entities.

## Implication for the Sutra paper

The paper's numpy demo backend currently uses `nomic-embed-text`
(`sdk/sutra-compiler/sutra_compiler/codegen_numpy.py`). This is the
wrong default for demonstrating learned-matrix binding. Either:

1. Swap the demo embedding to GTE-large (sentence-transformers — adds
   a heavier dependency but gets the demo aligned with the result
   the paper claims), or
2. Keep nomic as the "fast-to-run demo" substrate but clearly frame
   the learned-matrix evaluation as happening on GTE-large, with
   nomic as a worked null counter-example.

Option 2 is cleaner for the paper — the nomic null is a useful
illustration that substrate choice matters for Sutra's semantic
binding. The language paper can present both numbers side-by-side:
"on GTE-large, ridge-0.1 gives 87% on continent-of; on nomic, all
methods collapse to the majority-class prior — substrate matters
more than template choice."

## What remains to test

Already queue-covered: item 3 is Shiu library ops, item 4 is many-to-
many replication. Nomic substrate analysis is done unless there's
a reason to try a fourth text variant (e.g. full Wikipedia lead
paragraphs) — probably not worth the cost since three null variants
(bare, templates, descr) already converge on the same answer.
