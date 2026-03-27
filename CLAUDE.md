# embedding-mapping

## Project Overview
Discovering first-order logic operations in arbitrary embedding spaces via trajectory displacement analysis. Takes a general-purpose embedding model (mxbai-embed-large) and Wikidata triples, discovers which predicates encode as consistent vector arithmetic.

## Workflow Rules
- **Commit early and often.** Every meaningful change gets a commit with a clear message explaining *why*, not just what.
- **Commit and push everything.** Always push to remote after committing. No local-only work.
- **Do not enter planning-only modes.** All thinking must produce files and commits.
- **Keep this file up to date.** Record architectural decisions, conventions, and anything needed to work effectively.
- **Update README.md regularly.** It should always reflect the current state of the project.

## Architecture and Conventions
- **Stack:** Python + numpy + rdflib + Ollama (mxbai-embed-large, 1024-dim)
- **Source data:** Wikidata API + SPARQL endpoint
- **Storage:** Flat files (items.json, embeddings.npz, embedding_index.json) + optional SutraDB
- **Planning docs:** `planning/` directory for design decisions and roadmap

## Two-Paper Structure (Claw4S 2026)
This repo supports two papers for Claw4S Conference 2026 (deadline April 5, 2026):
- **Paper 1: FOL Discovery** (CS) — `papers/fol-discovery/paper.md`
- **Paper 2: AI Investment Bubble** (Economics) — `papers/economics/paper.md`
- **Strategic context:** `planning/strategic-discussion.md`
- **Paper overview:** `papers/README.md`

Both papers share: agent-driven methodology, quantitative falsifiability, replicability by AI reviewers.

## Key Scripts (all in `papers/fol-discovery/scripts/`)
- `random_walk.py` — BFS through Wikidata, imports entities and computes trajectories
- `import_wikidata.py` — Core import logic (fetch, embed, store, trajectories)
- `fol_discovery.py` — **Main analysis:** discovers FOL operations, evaluates prediction, tests composition
- `analyze_collisions.py` — Collision detection, density analysis, regime classification
- `probe.py` — Interactive embedding space exploration
- `sutra_client.py` + `import_to_sutra.py` — SutraDB integration

## Key Results (FOL Discovery, current dataset)
- 41,725 embeddings from 14,796 entities (500 fully imported via BFS from Engishiki Q1342448)
- 86 predicates discovered as FOL operations (alignment > 0.5)
- 32 strong operations (alignment > 0.7), 4 with perfect prediction (MRR = 1.0)
- r = 0.78 correlation between consistency and prediction accuracy
- Two-hop composition: 28.3% Hits@10 on 5,000 tests
- 164,084 cross-entity embedding collisions at cosine ≥ 0.95

## Data Files (in papers/fol-discovery/data/)
All regenerable from Wikidata + Ollama. Gitignored except properties.json and property_templates.json.
- `items.json` — Imported entities with all triples
- `embeddings.npz` — Numpy array of embedding vectors (float64, 1024-dim)
- `embedding_index.json` — Maps vector index → (qid, text, type)
- `walk_state.json` — BFS queue state (resumable)
- `fol_results.json` — FOL discovery output
- `analysis_results.json` — Collision/density output

## Development Philosophy
- **Discovery, not construction.** We don't build spaces for logic. We find logic in existing spaces.
- **Trajectories are first-class objects.** Each trajectory has its own RDF identity with subject, object, predicate, and distance metrics.
- **Adding data IS building the pipeline.** Import tooling and data grow together.
- **Reproducible.** Full analysis runs in ~30 minutes on commodity hardware with local Ollama.

## Submission Target
Claw4S Conference 2026 (deadline April 5, 2026)
- FOL paper: `papers/fol-discovery/paper.md` + `papers/fol-discovery/SKILL.md`
- Economics paper: `papers/economics/paper.md`
- Publish to clawRxiv (http://18.118.210.52)
