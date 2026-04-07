# axiv-neurosymbolic-paper

## Workflow Rules
- **Commit early and often.** Every meaningful change gets a commit with a clear message explaining *why*, not just what.
- **Do not enter planning-only modes.** All thinking must produce files and commits. If scope is unclear, create a `planning/` directory and write `.md` files there instead of using an internal planning mode.
- **Keep this file up to date.** As the project takes shape, record architectural decisions, conventions, and anything needed to work effectively in this repo.
- **Update README.md regularly.** It should always reflect the current state of the project for human readers.

## Project Description

Research prototype and forthcoming arXiv paper on **Neurosymbolic GraphRAG** — using runtime Virtual Knowledge Graphs (VKGs) as a semantic space for logic-gated retrieval, compared against standard vector-similarity RAG.

**Core thesis:** Standard RAG retrieves by vector proximity, which fails on multi-hop causal reasoning. By constructing a knowledge graph at runtime from propositional extractions and running a logic engine over it, the system retrieves correct reasoning chains even when intermediate steps have low similarity to the query.

**Current state:** Working prototype in `prototype/` demonstrating 100% ground truth coverage vs 75% for standard RAG on a causal reasoning benchmark. Paper writing has not yet begun.

### Reference Paper
This project builds on:

> **"Toward Verified Artificial Intelligence"**
> Sanjit A. Seshia (UC Berkeley), Dorsa Sadigh (Stanford), S. Shankar Sastry (UC Berkeley)
> *Communications of the ACM*, Volume 65, Issue 7, 2022
> DOI: [10.1145/3503914](https://dl.acm.org/doi/10.1145/3503914)

## Architecture and Conventions

### File Structure
- `prototype/` — All runnable code lives here
  - `knowledge_base.py` — Curated corpus, query, and ground truth definitions
  - `pillar1_extraction.py` — Propositional extraction via LLM (subject, predicate, object triples)
  - `pillar2_mapping.py` — Embedding + VKG construction with entity bridging (NetworkX + RDFLib)
  - `pillar3_logic.py` — Multi-hop chain search, contradiction detection via SPARQL, pruning
  - `standard_rag.py` — Baseline: cosine similarity retrieval
  - `neurosymbolic_rag.py` — Full pipeline orchestrating all 3 pillars
  - `run_demo.py` — Entry point: side-by-side comparison of both approaches
  - `scenarios.py` — 7 benchmark scenarios across diverse domains
  - `benchmark.py` — Multi-scenario benchmark runner with JSON export
  - `explore_embeddings.py` — Embedding geometry exploration for proposition families
  - `semantic_grid.py` — 3x3x3 subject/predicate/object grid for isolating embedding axes
- `exploration_notes.md` — Narrative interpretation of experimental results
- `experiment_log.md` — Chronological log of every experiment run
- `results.json` — Benchmark results from 7-scenario suite
- `gemini_conversation.md` — Original 5-turn conversation that seeded the idea
- `paper_names.md` — 12 candidate paper titles
- `todo.md` — Project task tracker

### Key Decisions
- **Local-only inference:** Ollama with `deepseek-r1:8b` (reasoning) and `mxbai-embed-large` (embeddings)
- **Dual graph representation:** NetworkX DiGraph for path-finding, RDFLib for formal semantics/SPARQL
- **Proposition-first ontology:** Entire claims are embedded rather than entity-relation triples
- **Entity bridging:** Propositions are linked in the VKG through shared entities, not just vector similarity

### Experiment Logging
- **Every experiment must be logged** to `experiment_log.md` with: date, what was run, key findings, and paths to output artifacts.
- Log entries are append-only and chronological. Each entry gets a numbered header.
- Raw data artifacts (`.json`, `.npz`, etc.) live alongside their scripts in `prototype/`.
- Narrative interpretation goes in `exploration_notes.md` (updated as findings accumulate).

### Conventions
- Python scripts use `python` (not `python3`) on this Windows system
- Commit messages explain *why*, not just what
- README.md must always reflect current project state
- **Cosine similarity is a loss function, not an analysis.** When designing experiments, cosine similarity should be used as the error metric for evaluating models (regression, synthesis, etc.), not as the primary analytical tool. Comparing pairwise cosine similarities between sentences is rarely the right first step — instead, frame the question as a transformation, regression, or logical operation, and use cosine to measure how well the predicted output matches the target.
