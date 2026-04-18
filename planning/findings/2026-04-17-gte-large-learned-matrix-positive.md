# 2026-04-17: GTE-large rescues learned-matrix binding on 2/4 predicates

Follow-up to the nomic nulls (`2026-04-17-wikidata-learned-matrix-null.md`
and `2026-04-17-wikidata-learned-matrix-templates-null.md`). Running the
same Wikidata + sentence-template eval on a different substrate — GTE-large
(1024-dim, sentence-transformers `thenlper/gte-large`) — gives substrate-
dependent positive results on 2 of 4 usable predicates. The learned-matrix
direction is **not** substrate-independent-null; nomic's result was a nomic
result, not a general result.

## What was measured

Five predicates pulled fresh from Wikidata SPARQL (no ORDER BY — whatever
the endpoint returned in order today). For each predicate, four subject-
text configurations (`bare`, `typed`, `rich`, `relational` — same templates
as the nomic eval). Object side stays bare for apples-to-apples codebook
retrieval. Eight matrix methods: identity, mean_object, displacement,
Procrustes, ridge (λ=1.0, λ=0.1), lowrank (r=30), random Gaussian. 5-fold
CV with top-1 retrieval against per-predicate codebook.

Script: `sutra-paper/scripts/learned_matrix_templates.py --model thenlper/gte-large`
Raw: `sutra-paper/scripts/learned_matrix_gte_large_results.json`

## Top-1 accuracy on `bare` config (the cleanest case)

| Predicate | N | CB | Chance | identity | mean_obj | displacement | procrustes | ridge 0.1 | Best ≠ id |
|-----------|---|----|--------|----------|----------|-------------|-----------|-----------|-----------|
| capital-of         | 143 | 143 | 0.7% | **82.1%** | 0.0% | 81.4% | 59.3% | 47.9% | identity wins |
| located-in-country | 195 |  21 | 4.8% | 41.5% | 39.0% | 60.0% | 69.7% | **76.4%** | **+34.9 lift** |
| author-of          | 198 | 144 | 0.7% |  6.7% |  9.2% |  7.2% |  5.1% | 7.2% | near-chance, no signal |
| continent-of       | 200 |  10 | 10%  | 68.5% | 19.5% | 82.0% | 85.5% | **87.0%** | **+18.5 lift** |
| country-of-citizenship | 200 | **1** | 100% | 100% | 100% | 100% | 100% | 100% | query broken (monocultural sample) |

Template configs (`typed`, `rich`, `relational`) land within ±3 points of
`bare` for every predicate — templates don't help and don't hurt much on
GTE-large. Full per-config table in the JSON.

## Interpretation

- **located-in-country and continent-of show real learned-matrix lift.**
  On continent-of, Procrustes (85.5%) and ridge-0.1 (87.0%) beat both
  identity (68.5%) and mean_object (19.5%) by 18-point margins. This is
  the "roles are matrices" design working as specified: a rotation/ridge
  fit on (subject, object) pairs generalizes held-out subjects into their
  correct object cluster. On located-in-country, ridge-0.1 gives a
  35-point lift over identity.
- **capital-of is identity-saturated.** Identity alone hits 82% — the
  subject and object embeddings are already in cosine correspondence in
  GTE-large, and learned methods don't add value (ridge_0.1 drops to 48%,
  probably overfitting on 143-class codebook with ~115-row training set).
  Displacement ties identity at 81%, which is consistent with the
  cartography-paper finding that a shared displacement vector exists —
  but here it doesn't beat just reading off the subject vector directly.
- **author-of has no learnable signal.** Everything is at chance (6-11%
  on a 144-class codebook). Author and book titles are too disparate as
  text, and a book title with the author's name in it is not predictable
  from the author's embedding alone.
- **country-of-citizenship is broken.** The SPARQL filter
  `?s wikibase:sitelinks > 20` combined with no random ordering returns
  200 people all with the same citizenship — the codebook collapses to
  size 1, making the whole column trivially 100%. Needs a query fix
  (ORDER BY RAND() or DISTINCT ?o) before being scored.

## Implication for the Sutra paper

This is the headline number the language paper needs. The earlier drafts
claimed "learned matrices are the design vision but the implementation
uses a placeholder" based on null nomic results. That limitation bullet
can come out — there is now a substrate (GTE-large) on which learned-
matrix binding works on real Wikidata relational triples:

- `continent-of`: ridge-0.1 matrix at 87.0% top-1 on a 10-class codebook,
  chance 10%. The matrix is learning a subject-conditional operator, not
  a mean-object prior (mean_object is 19.5%).
- `located-in-country`: ridge-0.1 matrix at 76.4% top-1 on a 21-class
  codebook, chance 4.8%. Learned methods beat both identity and
  mean_object baselines.

Non-defensive framing for the paper: learned-matrix binding works when
(a) the substrate has enough between-pair variance that subject vectors
are not already in direct correspondence with object vectors, and
(b) the predicate has enough low-entropy structure that a linear fit
generalizes. GTE-large satisfies both for located-in-country and
continent-of; nomic does not for any predicate; GTE-large does not for
author-of (too-open output space) or capital-of (already identity-close).

## What remains to test

1. **Fix country-of-citizenship query** so the codebook is non-trivial,
   re-run that column. The person→country relation is the most classic
   VSA role-filler case and deserves a clean number.
2. **Try the longer-text variant on nomic** (queue item 2) to rule out
   that nomic's null is a label-length artifact rather than a nomic
   artifact. If longer text rescues nomic, the substrate story is weaker;
   if it doesn't, GTE-large really is the only substrate that works here.
3. **BGE-large** as a third substrate. If BGE also shows lift, the claim
   generalizes to "sentence-transformer-class embeddings support learned
   matrix binding."
