# Embedding-Mapping: Discovering First-Order Logic in Arbitrary Embedding Spaces

**Geodesic displacement analysis of latent relational structure in general-purpose text embeddings.**

## What This Does

Takes any embedding model and a knowledge base of ground-truth triples (Wikidata), and discovers which first-order logical operations are latently encoded as vector arithmetic — without any training or parameter learning.

The key insight: embedding spaces trained for semantic similarity **already encode logical structure** as a byproduct. We excavate it.

## Key Results (mxbai-embed-large, 1024-dim)

| Metric | Value |
|--------|-------|
| Entities imported | 14,796 |
| Embeddings | 41,725 |
| Geodesics computed | 216,319 |
| Predicates analyzed (≥10 triples) | 159 |
| **Operations discovered** (alignment > 0.5) | **86** |
| Strong operations (alignment > 0.7) | 32 |
| Perfect prediction (MRR = 1.0) | 4 predicates |
| Mean Hits@10 | 0.550 |
| Consistency ↔ accuracy correlation | r = 0.78 |
| Two-hop composition Hits@10 | 0.283 |

### What Works (functional predicates)

| Predicate | Alignment | MRR | Example |
|-----------|-----------|-----|---------|
| demographics of topic | 0.899 | 1.000 | Japan + d → demographics of Japan |
| economy of topic | 0.870 | 1.000 | France + d → economy of France |
| flag | 0.855 | 0.937 | Spain + d → flag of Spain |
| coat of arms | 0.798 | 0.858 | Germany + d → coat of arms of Germany |

### What Fails (relational predicates)

| Predicate | Alignment | Why |
|-----------|-----------|-----|
| sibling | 0.026 | Symmetric — no consistent direction |
| spouse | 0.135 | Symmetric, many-to-many |
| instance of | 0.244 | Too semantically diverse |

## How It Works

1. **Import** entities from Wikidata via BFS from a seed entity
2. **Embed** all entity labels and aliases (mxbai-embed-large via Ollama)
3. **Compute geodesics** — displacement vectors for each triple's subject→object
4. **Discover operations** — test which predicates produce consistent displacements
5. **Validate** — leave-one-out prediction, two-hop composition, failure analysis

## Quick Start

### Prerequisites

- Python 3.10+
- [Ollama](https://ollama.ai) with `mxbai-embed-large` model
- Optional: [SutraDB](https://github.com/EmmaLeonhart/SutraDB) for graph+vector storage

```bash
# Install dependencies
pip install numpy requests ollama rdflib

# Pull the embedding model
ollama pull mxbai-embed-large
```

### Run the Full Pipeline

```bash
# 1. Import entities from Wikidata (BFS from seed)
python random_walk.py Q1342448 --limit 500

# 2. Discover FOL operations
python fol_discovery.py

# 3. Analyze collisions and density
python analyze_collisions.py

# 4. (Optional) Load into SutraDB
sutra serve --port 3030
python import_to_sutra.py --load-existing
```

### Explore the Embedding Space

```bash
# Nearest neighbors
python probe.py neighbors Q513          # Mount Everest

# Interpolate between entities
python probe.py between Q513 Q8502      # Everest ↔ mountain

# Vector arithmetic (displacement)
python probe.py displace Q513 Q8502 Q39231  # (mountain - Everest) + Fuji = ?
```

## Project Structure

```
embedding-mapping/
├── random_walk.py          # BFS Wikidata import pipeline
├── import_wikidata.py      # Core import logic (fetch, embed, geodesics)
├── fol_discovery.py        # FOL operation discovery + evaluation
├── analyze_collisions.py   # Collision detection + density analysis
├── probe.py                # Interactive embedding space explorer
├── compute_geodesics.py    # Standalone geodesic computation
├── embed_entities.py       # Standalone embedding generation
├── sutra_client.py         # SutraDB Python client
├── import_to_sutra.py      # SutraDB import pipeline
├── paper.md                # Full paper draft
├── data/
│   ├── items.json          # Imported Wikidata entities
│   ├── embedding_index.json # Maps vector index → (qid, text, type)
│   ├── embeddings.npz      # All embedding vectors
│   ├── properties.json     # Wikidata property labels
│   ├── property_templates.json  # Propositional realization templates
│   ├── walk_state.json     # BFS queue state (resumable)
│   ├── fol_results.json    # FOL discovery results
│   └── analysis_results.json   # Collision/density results
├── planning/
│   ├── project-vision.md   # Core concepts and goals
│   ├── architecture-decisions.md  # Design rationale
│   ├── geodesics.md        # What geodesics are and aren't
│   ├── roadmap.md          # Development phases
│   └── todo.md             # Current tasks
└── redoing-paper/          # Prior work on neurosymbolic embedding analysis
```

## Key Concepts

### Geodesic
A displacement vector connecting two entities in embedding space that are related by a Wikidata triple. The geodesic for `(Mount Everest, instance-of, mountain)` is `embed("mountain") - embed("Mount Everest")`.

### Discovered Operation
A predicate whose geodesics are geometrically consistent — all instances point in approximately the same direction. If `flag` consistently displaces countries toward their flags, that's a discovered FOL operation.

### The Three Regimes (from companion paper)
- **Oversymbolic**: Dense regions where distinct entities collide (164,084 collisions at cosine ≥ 0.95)
- **Isosymbolic**: Regions where vector arithmetic preserves logical structure
- **Undersymbolic**: Sparse regions with insufficient representational mass

## Novelty

Prior neurosymbolic work (TransE, RotatE, LTN, box embeddings) **constructs** embedding spaces to support logic. We **discover** logic in spaces not built for it. The embedding model has no idea what first-order logic is — we find it anyway.

## Paper

See [paper.md](paper.md) for the full paper: *"Discovering First-Order Logic in Arbitrary Embedding Spaces: Geodesic Displacement Analysis of Latent Relational Structure"*

Submitted to [Claw4S Conference 2026](https://claw4s.github.io/).

## License

MIT

## Citation

```
@article{leonhart2026fol,
  title={Discovering First-Order Logic in Arbitrary Embedding Spaces},
  author={Leonhart, Immanuelle},
  year={2026},
  note={Claw4S Conference 2026}
}
```
