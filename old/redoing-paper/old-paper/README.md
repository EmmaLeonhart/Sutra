# Neurosymbolic GraphRAG — arXiv Paper Repo

Research prototype and working draft for a forthcoming arXiv paper on using runtime Virtual Knowledge Graphs as a semantic space for logic-gated retrieval, compared against standard vector-similarity RAG.

**Read the paper draft:** [emma-leonhart.github.io/arxiv-neurosymbolic-paper](https://emma-leonhart.github.io/arxiv-neurosymbolic-paper/)

## What This Is

Standard RAG retrieves by vector proximity, which fails on multi-hop causal reasoning. By constructing a knowledge graph at runtime from propositional extractions and running a logic engine over it, the system retrieves correct reasoning chains even when intermediate steps have low similarity to the query.

The repo contains:
- `pages/` — The paper draft (deployed to GitHub Pages)
- `prototype/` — Working proof-of-concept with 7 benchmark scenarios
- `exploration_notes.md` — Detailed experimental narratives and analysis
- `experiment_log.md` — Chronological log of every experiment
- `results.json` — Raw benchmark data

## Key Results

- **Benchmark:** Neurosymbolic pipeline achieves 69% mean ground-truth coverage vs 62% for standard RAG across 7 scenarios, with gains up to +50% on causal cascade scenarios.
- **Embedding geometry:** Subject axis contributes 3.5x more to embedding similarity than predicate axis — models encode *what things are about*, not *what relationship holds*.
- **Distributional vs ontological:** dog→animal (0.876) > dog→mammal (0.816) despite mammal being taxonomically closer. Even Linnaean taxonomy shows non-monotonic distance decay. Hyperbolic embeddings won't fix this — the problem is distributional, not geometric.

## Running the Prototype

Requires [Ollama](https://ollama.com/) with `deepseek-r1:8b` and `mxbai-embed-large`, plus Python packages `ollama`, `networkx`, `rdflib`, `numpy`.

```bash
python prototype/run_demo.py       # Side-by-side comparison
python prototype/benchmark.py      # Full 7-scenario benchmark
```

## Reference Paper

> Seshia, S. A., Sadigh, D., & Sastry, S. S. (2022). Toward Verified Artificial Intelligence. *Communications of the ACM*, 65(7). DOI: [10.1145/3503914](https://dl.acm.org/doi/10.1145/3503914)
