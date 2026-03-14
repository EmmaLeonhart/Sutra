# Architecture Decisions

## AD-1: Storage — RDF Triple Store (Fuseki) + Numpy for Vectors

**Decision:** Use Apache Jena Fuseki for the RDF/SPARQL layer and numpy/scipy for vector math. No dedicated vector database initially.

**Rationale from conversation:**
- The project is ontology-heavy — RDF/SPARQL is the natural fit for the ground-truth logical layer
- At mountain-domain scale, cosine similarity with numpy is fast enough; FAISS earns its keep at millions of vectors
- Neo4j has built-in vector indexes but the Community/Enterprise licensing wall is frustrating
- GraphDB is feature-complete for smaller deployments but licensing key management is annoying
- Fuseki is fully open source (Apache 2.0), no licensing friction
- Keeping vectors in numpy arrays avoids the sync problem of two databases

**Tradeoff:** Brute-force similarity is fine for initial exploration. HNSW will be implemented for efficient nearest-neighbor structure discovery (see AD-5).

## AD-5: HNSW Index for Structure Discovery

**Decision:** Implement Hierarchical Navigable Small World (HNSW) indexing over the embedding space.

**Rationale:**
- HNSW builds a navigable graph over the embedding space — the graph structure itself is semantically interesting
- The layered proximity graph HNSW constructs is a natural representation of how the embedding space clusters
- Enables efficient nearest-neighbor queries needed for displacement vector analysis at scale
- Can be implemented in pure Python or via hnswlib/FAISS — no external database needed

## AD-2: Start with Wikidata as Source

**Decision:** Import from Wikidata SPARQL endpoint. Each triple becomes an edge between two embedded concepts.

**Rationale:**
- Wikidata has rich ontology (especially geographic features — good for mountains domain)
- Provides real is-a hierarchies to compare against embedding geometry
- User has extensive Wikidata experience (see global CLAUDE.md)

## AD-3: Python as Primary Language

**Decision:** Python for everything (data pipeline, vector math, SPARQL queries, analysis).

**Rationale:** numpy, scipy, rdflib, SPARQLWrapper all native. User's existing toolchain.

## AD-4: No Dedicated Graph Database Yet

**Decision:** Defer Neo4j/GraphDB. Use rdflib for local RDF and Fuseki only if persistence/SPARQL querying becomes necessary.

**Rationale:** Start simple. rdflib can serialize to Turtle/N-Triples files. Add a server only when the query patterns demand it.
