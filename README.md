# Embedding Cartography: Claw4S 2026 Research

**Two papers for Claw4S Conference 2026 (deadline: April 5, 2026)**

## Papers

### Paper 1: Embedding Cartography (CS)
A replicable, zero-training method for mapping relational structure and tokenizer defects in general-purpose text embedding spaces. Uses knowledge graph traversal as a directed probing strategy to systematically test what an embedding space encodes and where it breaks down.

See [`papers/fol-discovery/paper.md`](papers/fol-discovery/paper.md)

### Paper 2: The AI Investment Bubble — A Microeconomic Historical Analysis (Economics)
Agent-driven structural comparison of AI investment against historical bubbles. Falsifiable quantitative thesis with genuine agentic data retrieval.

See [`papers/economics/paper.md`](papers/economics/paper.md)

---

## Embedding Cartography: What This Does

Takes any embedding model and a knowledge base (Wikidata), and maps which relations manifest as consistent vector displacements — and which do not. No training, no learned parameters. BFS traversal through the knowledge graph directs the probing into specific domains, testing the embedding space in regions where it may be weakest.

The method found a previously unreported tokenizer defect in mxbai-embed-large (a widely-used embedding model): 147,687 cross-entity embedding collisions caused by WordPiece diacritic stripping.

## Key Results (mxbai-embed-large, 1024-dim)

| Metric | Value |
|--------|-------|
| Entities imported | 14,796 |
| Embeddings | 41,725 |
| Predicates analyzed (≥10 triples) | 159 |
| **Operations discovered** (alignment > 0.5) | **86** |
| Strong operations (alignment > 0.7) | 32 |
| Perfect prediction (MRR = 1.0) | 4 predicates |
| Consistency ↔ accuracy correlation | r = 0.861 |
| **Universal operations** (found in all 3 models) | **30** |
| Embedding collisions (cosine ≥ 0.95) | 147,687 pairs |

### What Works (functional predicates)

| Predicate | Alignment | MRR | Example |
|-----------|-----------|-----|---------|
| demographics of topic | 0.899 | 1.000 | Japan + d → demographics of Japan |
| economy of topic | 0.870 | 1.000 | France + d → economy of France |
| flag | 0.855 | 0.937 | Spain + d → flag of Spain |
| coat of arms | 0.798 | 0.858 | Germany + d → coat of arms of Germany |

### What Fails (and why — the failures are informative)

| Predicate | Alignment | Why |
|-----------|-----------|-----|
| sibling | 0.026 | Symmetric — no consistent direction |
| spouse | 0.135 | Symmetric, many-to-many |
| instance of | 0.244 | Too semantically diverse |

## How It Works

1. **Seed and traverse** — BFS from a seed entity through Wikidata, reaching domain-specific terminology that standard benchmarks miss
2. **Embed** — all entity labels and aliases via any embedding model (mxbai-embed-large, nomic-embed-text, all-minilm tested)
3. **Compute displacements** — for each triple, compute the vector from subject embedding to object embedding
4. **Map the space** — test which predicates produce consistent displacements (the "map"), with a self-calibrating quality metric (consistency predicts accuracy at r = 0.861)
5. **Detect defects** — identify embedding collisions where the tokenizer has destroyed discriminative information

## Quick Start

### Prerequisites

- Python 3.10+
- [Ollama](https://ollama.ai) with `mxbai-embed-large` model

```bash
# Install dependencies
pip install numpy requests ollama rdflib

# Pull the embedding model
ollama pull mxbai-embed-large
```

### Run the Full Pipeline

```bash
# 1. Import entities from Wikidata (BFS from seed)
python papers/fol-discovery/scripts/random_walk.py Q1342448 --limit 500

# 2. Discover relational displacements
python papers/fol-discovery/scripts/fol_discovery.py

# 3. Analyze collisions and density
python papers/fol-discovery/scripts/analyze_collisions.py
```

### Cross-Model Validation

```bash
# Run on additional models to check which operations are universal
ollama pull nomic-embed-text
ollama pull all-minilm

EMBED_MODEL=nomic-embed-text python papers/fol-discovery/scripts/random_walk.py Q1342448 --limit 500 --data-dir papers/fol-discovery/data-nomic
python papers/fol-discovery/scripts/fol_discovery.py --data-dir papers/fol-discovery/data-nomic

python papers/fol-discovery/scripts/compare_models.py
```

### Explore the Embedding Space

```bash
python papers/fol-discovery/scripts/probe.py neighbors Q513          # Mount Everest
python papers/fol-discovery/scripts/probe.py between Q513 Q8502      # Everest ↔ mountain
python papers/fol-discovery/scripts/probe.py displace Q513 Q8502 Q39231  # vector arithmetic
```

## Project Structure

```
Claw4S-submissions/
├── papers/
│   ├── README.md                  # Overview of both Claw4S submissions
│   ├── fol-discovery/
│   │   ├── paper.md               # Embedding cartography paper (CS category)
│   │   ├── SKILL.md               # Executable review instructions
│   │   ├── scripts/
│   │   │   ├── random_walk.py     # BFS Wikidata import pipeline
│   │   │   ├── import_wikidata.py # Core import logic (fetch, embed, displacements)
│   │   │   ├── fol_discovery.py   # Operation discovery + evaluation
│   │   │   ├── analyze_collisions.py  # Collision detection + density analysis
│   │   │   ├── compare_models.py  # Cross-model comparison
│   │   │   ├── probe.py           # Interactive embedding space explorer
│   │   │   └── ...                # Additional pipeline scripts
│   │   └── data/
│   │       ├── properties.json    # Wikidata property labels
│   │       ├── property_templates.json  # Propositional realization templates
│   │       └── (regenerable files gitignored)
│   └── economics/
│       ├── paper.md               # AI bubble paper (Economics category)
│       ├── SKILL.md               # Executable review instructions
│       └── scripts/               # Data collection and analysis
├── planning/                      # Design decisions and roadmap
└── redoing-paper/                 # Prior work on neurosymbolic embedding analysis
```

## Key Concepts

### Relational Displacement
A displacement vector connecting two entities related by a knowledge graph triple. The displacement for `(Japan, flag, flag of Japan)` is `embed("flag of Japan") - embed("Japan")`.

### Discovered Operation
A predicate whose displacements are geometrically consistent — all instances point in approximately the same direction. The consistency score predicts prediction accuracy (r = 0.861), so the map is self-calibrating.

### The Cartographic Method
The contribution is the replicable procedure, not any single finding. Different seeds probe different regions. Different models produce comparable maps. The method's value is demonstrated by what it finds — including a large-scale tokenizer defect in a popular model that standard benchmarks missed.

## Papers

See [`papers/`](papers/) for both Claw4S 2026 submissions:
- [Embedding Cartography paper](papers/fol-discovery/paper.md) — *"Embedding Cartography: A Replicable Method for Mapping Relational Structure and Tokenizer Defects in General-Purpose Embedding Spaces"* (CS category)
- [Economics paper](papers/economics/paper.md) — *"The AI Investment Bubble"* (Economics category)

Submitted to [Claw4S Conference 2026](https://claw4s.github.io/).

## License

MIT

## Citation

```
@article{leonhart2026cartography,
  title={Embedding Cartography: A Replicable Method for Mapping Relational Structure and Tokenizer Defects in General-Purpose Embedding Spaces},
  author={Leonhart, Emma},
  year={2026},
  note={Claw4S Conference 2026}
}
```
