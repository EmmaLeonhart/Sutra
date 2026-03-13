# Roadmap

## Phase 1: Wikidata Import Pipeline (current)
- [ ] SPARQL query to fetch triples for a domain (e.g. mountains, geographic features)
- [ ] Parse triples into subject-predicate-object
- [ ] Get or generate embeddings for each entity (labels → embedding model)
- [ ] Store as: RDF graph (rdflib) + entity-to-vector mapping (numpy arrays)
- [ ] Each triple = an edge (line) between two points in embedding space

## Phase 2: Geometric Analysis
- [ ] Compute displacement vectors for all edges (object_vec - subject_vec)
- [ ] Cluster displacement vectors to find consistent relational axes
- [ ] Compare: do triples sharing the same predicate cluster in displacement space?
- [ ] Visualize embedding space with edges overlaid

## Phase 3: Structure Extraction
- [ ] Identify implicit class structure from embedding geometry
- [ ] Test whether vector arithmetic encodes subsumption (is-a) relations
- [ ] Check if "scale", "elevation", or other domain axes emerge as geometric directions
- [ ] Express discovered structure as new RDF triples (ontology induction output)

## Phase 4: Propositions and Sentences
- [ ] Extend beyond nouns to propositional content
- [ ] Embed sentences/claims, not just entity labels
- [ ] Map logical relations between propositions in embedding space

## Open Questions
- Which embedding model? (word2vec, fasttext, sentence-transformers, etc.)
- Supervised grounding vs unsupervised discovery — try both?
- What domain to start with? Mountains was discussed but any Wikidata domain works.
- How to handle entities with no clean text label for embedding?
