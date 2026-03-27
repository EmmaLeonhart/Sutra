# Embedding-Mapping: Claw4S 2026 Research

**Two papers for Claw4S Conference 2026 (deadline: April 5, 2026)**

## Papers

### Paper 1: Discovering First-Order Logic in Arbitrary Embedding Spaces (CS)
Trajectory displacement analysis of latent relational structure in general-purpose text embeddings. Takes any embedding model and Wikidata triples, discovers which predicates encode as consistent vector arithmetic — without training or parameter learning.

See [`papers/fol-discovery/paper.md`](papers/fol-discovery/paper.md)

### Paper 2: The AI Investment Bubble — A Microeconomic Historical Analysis (Economics)
Agent-driven structural comparison of AI investment against historical bubbles. Falsifiable quantitative thesis with genuine agentic data retrieval.

See [`papers/economics/paper.md`](papers/economics/paper.md)

---

## FOL Discovery: What This Does

Takes any embedding model and a knowledge base of ground-truth triples (Wikidata), and discovers which first-order logical operations are latently encoded as vector arithmetic — without any training or parameter learning.

The key insight: embedding spaces trained for semantic similarity **already encode logical structure** as a byproduct. We excavate it.

## Key Results (mxbai-embed-large, 1024-dim)

| Metric | Value |
|--------|-------|
| Entities imported | 14,796 |
| Embeddings | 41,725 |
| Trajectories computed | 216,319 |
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
3. **Compute trajectories** — displacement vectors for each triple's subject→object
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
python papers/fol-discovery/scripts/random_walk.py Q1342448 --limit 500

# 2. Discover FOL operations
python papers/fol-discovery/scripts/fol_discovery.py

# 3. Analyze collisions and density
python papers/fol-discovery/scripts/analyze_collisions.py

# 4. (Optional) Load into SutraDB
sutra serve --port 3030
python papers/fol-discovery/scripts/import_to_sutra.py --load-existing
```

### Explore the Embedding Space

```bash
# Nearest neighbors
python papers/fol-discovery/scripts/probe.py neighbors Q513          # Mount Everest

# Interpolate between entities
python papers/fol-discovery/scripts/probe.py between Q513 Q8502      # Everest ↔ mountain

# Vector arithmetic (displacement)
python papers/fol-discovery/scripts/probe.py displace Q513 Q8502 Q39231  # (mountain - Everest) + Fuji = ?
```

## Project Structure

```
Claw4S-submissions/
├── papers/
│   ├── README.md                  # Overview of both Claw4S submissions
│   ├── fol-discovery/
│   │   ├── paper.md               # FOL discovery paper (CS category)
│   │   ├── SKILL.md               # Executable review instructions
│   │   ├── scripts/
│   │   │   ├── random_walk.py     # BFS Wikidata import pipeline
│   │   │   ├── import_wikidata.py # Core import logic (fetch, embed, trajectories)
│   │   │   ├── fol_discovery.py   # FOL operation discovery + evaluation
│   │   │   ├── analyze_collisions.py  # Collision detection + density analysis
│   │   │   ├── probe.py           # Interactive embedding space explorer
│   │   │   └── ...                # Additional pipeline scripts
│   │   └── data/
│   │       ├── properties.json    # Wikidata property labels
│   │       ├── property_templates.json  # Propositional realization templates
│   │       └── (regenerable files gitignored)
│   └── economics/
│       ├── paper.md               # AI bubble paper (Economics category)
│       ├── SKILL.md               # Executable review instructions
│       ├── scripts/
│       │   ├── collect_bubble_data.py      # Historical bubble data retrieval
│       │   ├── collect_ai_investment.py    # AI company financial data
│       │   └── structural_comparison.py    # Comparison matrix analysis
│       └── data/                  # Retrieved financial data (committed)
├── planning/
│   ├── project-vision.md          # Core concepts and goals
│   ├── strategic-discussion.md    # Claw4S strategy and competitive analysis
│   ├── architecture-decisions.md  # Design rationale
│   ├── trajectories.md            # What trajectories are and aren't
│   ├── roadmap.md                 # Development phases
│   └── todo.md                    # Current tasks
└── redoing-paper/                 # Prior work on neurosymbolic embedding analysis
```

## Key Concepts

### Trajectory
A displacement vector connecting two entities in embedding space that are related by a Wikidata triple. The trajectory for `(Mount Everest, instance-of, mountain)` is `embed("mountain") - embed("Mount Everest")`.

### Discovered Operation
A predicate whose trajectories are geometrically consistent — all instances point in approximately the same direction. If `flag` consistently displaces countries toward their flags, that's a discovered FOL operation.

### The Three Regimes (from companion paper)
- **Oversymbolic**: Dense regions where distinct entities collide (164,084 collisions at cosine ≥ 0.95)
- **Isosymbolic**: Regions where vector arithmetic preserves logical structure
- **Undersymbolic**: Sparse regions with insufficient representational mass

## Novelty

Prior neurosymbolic work (TransE, RotatE, LTN, box embeddings) **constructs** embedding spaces to support logic. We **discover** logic in spaces not built for it. The embedding model has no idea what first-order logic is — we find it anyway.

## Papers

See [`papers/`](papers/) for both Claw4S 2026 submissions:
- [FOL Discovery paper](papers/fol-discovery/paper.md) — *"Discovering First-Order Logic in Arbitrary Embedding Spaces"* (CS category)
- [Economics paper](papers/economics/paper.md) — *"The AI Investment Bubble"* (Economics category)

Submitted to [Claw4S Conference 2026](https://claw4s.github.io/).

## License

MIT

## Citation

```
@article{leonhart2026fol,
  title={Discovering First-Order Logic in Arbitrary Embedding Spaces},
  author={Leonhart, Emma},
  year={2026},
  note={Claw4S Conference 2026}
}
```
