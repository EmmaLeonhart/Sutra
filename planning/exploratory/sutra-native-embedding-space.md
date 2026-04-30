# Sutra-native embedding space

**Date opened:** 2026-04-28.
**Status:** Research direction. Compute-bound; not actionable today.
Captured here so the design doesn't fall off the radar — this is the
most concrete sketch in the archive of *what comes next once Sutra
is mature*.

## The question

Every embedding space Sutra has ever run against was built for
**retrieval** — cosine similarity between text passages, nearest-
neighbor over documents. None of them were built for **computation**
— a programming language addressing presidential dimensions of a
person vector, or doing arithmetic in currency space, or expecting
clean separable dimensions for ontological categories.

Sutra works against retrieval-trained spaces because the geometry the
retrieval objective produces is a useful approximation to the geometry
a computational substrate would want. That's a happy accident, not a
design property. **What would change if you trained an embedding
space to be a computational substrate?**

## What a Sutra-native space would do differently

The computational requirements that retrieval losses don't satisfy:

- **Ontological categories should be geometrically separable.** A
  Sutra `class Country` claims a region of space; the retrieval
  objective doesn't promise that region exists with clean
  boundaries. Training would.
- **Class hierarchies should have corresponding geometric structure.**
  `Human` and `President` should have a clean subspace relationship
  (one is a refinement of the other). Retrieval embeddings don't
  optimize for this.
- **Arithmetic properties should be preserved.** Currency dimensions
  should behave like numbers. Date dimensions should ordinal-order
  cleanly. Today the geometric structure that supports these claims
  is whatever happened to fall out of the retrieval objective; with
  a Sutra-native objective it would be guaranteed.
- **Synthetic dimensions should be explicitly reserved and
  documented.** The compiler knows what to look for; the model
  should know what to leave alone.
- **The space should be versioned and stable** so compiled programs
  don't break when the model updates.

## The novel loss function — traversal compositionality

Current embedding-model training uses three classes of objective:

- **Contrastive losses** — similar things should be close,
  dissimilar things far.
- **Retrieval losses** — the right document should rank higher than
  wrong documents.
- **Reconstruction losses** — encode and decode faithfully.

None of these say anything about whether a programming language can
*walk* the space coherently. Sutra has a many-to-many traversal
mechanism — given a query vector and a relation, it walks to the
target. **The natural Sutra-native loss says: traversal paths should
be geometrically coherent across many entities and many relations,
and the same offset that walks `Human → President` for one human
should walk it for any human.**

That's the compositionality `king − man + woman ≈ queen`
demonstrated, deliberately trained for rather than emerging by
accident. It's a perfectly well-defined loss:

- For each (relation, entity) pair, measure how clean the traversal
  is (distance from the predicted target to the canonical target).
- For each relation, measure how consistent the offset is across
  many entities.
- Compose pairs of relations and check that the composition lands
  where the chained traversal predicts.

Apply backprop, and the embedding space gets shaped to support these
operations. That's a complete training objective.

## Knowledge-graph embedding as related prior art

Knowledge-graph embedding is a real research area that's been
attacking adjacent problems:

- **TransE** (Bordes et al. 2013) — relation as translation:
  `head + relation = tail`. Direct ancestor of the
  `country + capital_of = capital` Sutra design.
- **RotatE** (Sun et al. 2019) — relation as rotation in complex
  space. Captures asymmetric relations TransE can't.
- **ComplEx** (Trouillon et al. 2016) — complex-valued embeddings;
  bilinear product as the scoring function. Good at antisymmetric
  relations.

These trained embeddings to preserve knowledge-graph structure for
**link prediction** — guessing missing edges in the graph. What they
*didn't* do:

- Use geometric consistency of the knowledge graph as a component
  of a more general embedding space loss (theirs was the only loss).
- Co-design the loss with a programming language's computational
  needs.
- Combine knowledge-graph consistency with traversal compositionality
  as a joint objective.

So there's prior art on the knowledge-graph side, but the specific
combination — geometric consistency of ontological class relations as
part of a loss function that also optimizes for Sutra's traversal
properties — has not been done.

## The Wikidata pollution caveat

The obvious training corpus is Wikidata: it's the largest open
ontology with class hierarchies and typed relations. The cartography
work has used it extensively.

**It's also notoriously polluted.** The class hierarchy is
inconsistent: things are categorized differently depending on who
edited them, there are circular relationships, redundant classes,
conflicting type assignments. Donald Trump might be simultaneously
`instance-of human, politician, businessperson, television
personality` with no clear geometric interpretation of how those
relate.

For general retrieval that's fine — coverage matters more than
consistency. **For training a space where geometric consistency is
the loss signal, training on inconsistent data is worse than not
training at all.** You'd be telling the model to be consistent with
inconsistency.

## Cleaner ontology candidates

- **WordNet** — much cleaner hierarchy, carefully curated, but
  limited to language concepts.
- **CYC** — extremely carefully curated logical ontology, but
  proprietary and old.
- **Schema.org** — cleaner than Wikidata, designed for structured
  data, reasonable class hierarchy.
- **BioPortal ontologies** — biology takes ontologies very seriously,
  the structures are extremely rigorous.
- **A purpose-built ontology** — closing the loop. Sutra's type
  hierarchy is the ontology, and the space is trained to be
  geometrically consistent with Sutra's own class structure. The
  language defines its own ground truth. Most interesting
  long-term path.

## Realistic compute paths

Training a competitive general-purpose embedding model from scratch
is the kind of compute only well-funded labs have. nomic-embed,
which is one of the smaller competitive models, still required
significant resources and a large team.

Cheaper-and-still-meaningful alternatives:

- **Fine-tuning an existing model.** Take nomic-embed or a sentence
  transformer; fine-tune with the traversal-compositionality loss.
  Not training from scratch — nudging a good space toward better
  geometric structure for Sutra's needs. Far more feasible.
- **Adapter layers.** Even cheaper — add a small learned
  transformation on top of an existing model that remaps the space
  to be more geometrically consistent. The base model is frozen;
  only the adapter trains.
- **Synthetic data generation.** Use an LLM to generate clean
  ontological triples consistent with a chosen Sutra type
  hierarchy. Sidesteps the Wikidata-pollution problem without
  requiring a massive knowledge graph. Generate exactly the
  relationships you care about.

Fine-tuning is probably the most realistic near-term path. The
defining loss is traversal compositionality plus ontological
geometric consistency, applied to a frozen base.

## Why this would be a real research contribution

Nobody has built an embedding space explicitly designed to serve as
a computational substrate for a programming language. Embedding
spaces have been built for retrieval, for representation learning,
for transfer to downstream tasks — never for "a programming language
will compile against this." That's a new thing.

The paper writes itself: *"we present an embedding space co-designed
with a programming language, and show that programs compiled against
it have properties X, Y, Z that are impossible with general-purpose
retrieval embeddings."*

It's also a contribution that pulls embedding-space research in a
direction it wouldn't have gone otherwise — a co-evolution analogous
to how C and CPUs shaped each other. Most languages consume their
substrate passively. A Sutra-native embedding space would mean Sutra
is actively reshaping its substrate.

## What would have to be true for this to become real work

- [ ] Sutra's language and runtime stable enough that the loss can
  be measured against real programs (not just synthetic test cases).
- [ ] A clear set of compositional traversal patterns the loss
  should optimize for — not just `country + capital_of`, but a
  catalog of relations and a way to weight them.
- [ ] Compute access. Fine-tuning is feasible on modest hardware;
  adapter layers fit on a single GPU.
- [ ] A target ontology — ideally Sutra's own type hierarchy applied
  to a synthetic-data-generated training corpus, avoiding the
  Wikidata pollution issue.

None of these are blocked on anything except sequencing. Tracked
here, not in `queue.md`, until the language matures enough to
support the next step.
