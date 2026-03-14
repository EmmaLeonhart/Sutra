# Roadmap

## Phase 1: Wikidata Import Pipeline (current)
- [x] Fetch items from Wikidata API (QID, English label, English aliases, all properties)
- [x] Store all properties as triples by QID (no need to import linked items fully)
- [x] Generate embeddings for labels and each alias separately (mxbai-embed-large, 1024-dim)
- [x] Store as: RDF graph (N-Triples) + embedding vectors (NPZ) + index mapping
- [ ] Scale up: spam more Wikidata items into the embedding map (beyond mountains)
- [ ] English only for now; plan for all language labels later

## Phase 2: Density Analysis
- [ ] Calculate density of vectors within regions of the embedding space
- [ ] Identify clusters, voids, and concentration patterns
- [ ] Correlate density with ontological categories (do related items cluster?)
- [ ] Analyze how aliases distribute relative to their canonical labels

## Phase 3: HNSW Index (longer term)
- [ ] Implement Hierarchical Navigable Small World index over the embedding space
- [ ] Use HNSW graph structure itself as a semantic artifact
- [ ] Compare HNSW connectivity patterns against Wikidata's triple structure

## Phase 4: Geometric Analysis
- [ ] Compute displacement vectors for triples (object_vec - subject_vec)
- [ ] Cluster displacement vectors to find consistent relational axes
- [ ] Compare: do triples sharing the same predicate cluster in displacement space?
- [ ] Visualize embedding space with edges overlaid

## Phase 5: Structure Extraction
- [ ] Identify implicit class structure from embedding geometry
- [ ] Test whether vector arithmetic encodes subsumption (is-a) relations
- [ ] Express discovered structure as new RDF triples (ontology induction output)

## Phase 6: Propositions and Sentences
- [ ] Extend beyond nouns to propositional content
- [ ] Embed sentences/claims, not just entity labels
- [ ] Map logical relations between propositions in embedding space

## Resolved Questions
- Embedding model: mxbai-embed-large (1024-dim, via Ollama) — matches redoing-paper
- Starting domain: mountains (Q8502)
- Each entity gets separate embeddings for label and each alias
- Triples stored by QID reference — linked items don't need full import
