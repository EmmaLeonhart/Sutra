---
name: fol-discovery
description: Discover relational displacement operations in frozen embedding spaces using Wikidata triples. Reproduces the key findings from "Latent Space Cartography Applied to Wikidata" — 30 model-agnostic operations with r=0.861 self-diagnostic correlation, and a silent [UNK] tokenizer defect in mxbai-embed-large causing 147,687 embedding collisions.
allowed-tools: Bash(python *), Bash(pip *), Bash(ollama *), WebFetch
---

# Latent Space Cartography Applied to Wikidata

**Author: Emma Leonhart**
**Paper ID: 2604.00648**

This skill reproduces the results from "Latent Space Cartography Applied to Wikidata: Relational Displacement Analysis Reveals a Silent Tokenizer Defect in mxbai-embed-large." It applies standard TransE-style relational displacement analysis to frozen text embedding models using Wikidata knowledge graph triples as probes.

**Two key findings:**
1. **30 model-agnostic relational operations** discovered across three embedding models — functional (many-to-one) relations encode as consistent vector arithmetic; symmetric relations do not.
2. **A silent tokenizer defect** in mxbai-embed-large: 147,687 cross-entity embedding pairs at cosine >= 0.95, caused by WordPiece `[UNK]` token dominance on diacritical text. "Hokkaid&#333;" has cosine 1.0 with "Eire" but only 0.45 with its own ASCII equivalent "Hokkaido."

## Prerequisites

```bash
pip install numpy requests ollama rdflib
```

Ollama must be running with `mxbai-embed-large`:

```bash
ollama pull mxbai-embed-large
```

Verify:

```bash
python -c "import ollama; r = ollama.embed(model='mxbai-embed-large', input=['test']); print(f'OK: {len(r.embeddings[0])}-dim')"
```

Expected Output: `OK: 1024-dim`

## Step 1: Setup

Description: Clone the repository and verify dependencies.

```bash
git clone https://github.com/EmmaLeonhart/fol-discovery.git
cd fol-discovery
pip install -r requirements.txt
mkdir -p data
```

Verify:

```bash
python -c "
import numpy, requests, ollama, rdflib
print('numpy:', numpy.__version__)
print('rdflib:', rdflib.__version__)
print('All dependencies OK')
"
```

Expected Output:
- `numpy: <version>`
- `rdflib: <version>`
- `All dependencies OK`

## Step 2: Import Entities from Wikidata

Description: Breadth-first search from a seed entity through Wikidata, importing entities with their triples and computing embeddings via mxbai-embed-large.

```bash
python scripts/random_walk.py Q1342448 --limit 100
```

This imports 100 entities starting from Engishiki (Q1342448), a Japanese historical text. The BFS expansion discovers linked entities far beyond the initial 100, producing thousands of embeddings. Each imported entity has all Wikidata triples fetched, its label and aliases embedded (1024-dim), and displacement vectors computed for all entity-entity triples.

**Parameters:**
- `Q1342448` — Seed entity (Engishiki). Any Wikidata QID works.
- `--limit 100` — Number of entities to fully import. More = denser map.
- `--resume` — Continue from a saved queue state.

**Environment variables:**
- `EMBED_MODEL` — Embedding model name (default: `mxbai-embed-large`)
- `FOL_DATA_DIR` — Data directory (default: `data/` relative to scripts)

Expected Output:
```
[1/100] Importing Q1342448 (queue: 0)...
  Engishiki - <N> triples, discovered <M> linked QIDs
...
Final state:
  Items: <N> (hundreds to thousands)
  Embeddings: <N> x 1024
  Trajectories: <N>
```

**Runtime:** ~10-15 minutes for 100 entities (depends on Wikidata API speed and Ollama inference).

**Artifacts:**
- `data/items.json` — All imported entities with triples
- `data/embeddings.npz` — Embedding vectors (numpy)
- `data/embedding_index.json` — Vector index to (qid, text, type) mapping
- `data/walk_state.json` — Resumable BFS queue state
- `data/triples.nt` — RDF triples (N-Triples format)
- `data/trajectories.ttl` — Trajectory objects (Turtle format)

## Step 3: Discover Relational Displacement Operations

Description: The core analysis. For each predicate with sufficient triples, compute displacement vector consistency and evaluate prediction accuracy.

```bash
python scripts/fol_discovery.py --min-triples 5
```

For each predicate, the script:
1. Computes all displacement vectors (object_vec - subject_vec)
2. Computes the mean displacement ("operation vector")
3. Measures consistency: how aligned are individual displacements with the mean?
4. Evaluates prediction via leave-one-out: predict object via subject + operation vector
5. Tests two-hop composition: chain two operations (S + d1 + d2 -> O)
6. Characterizes failures: symmetric, overloaded, and sequence predicates

**Parameters:**
- `--min-triples 5` — Minimum triples per predicate to analyze
- `--output data/fol_results.json` — Output path

Expected Output:
```
PHASE 1: OPERATION DISCOVERY
  Analyzed <N> predicates (min 5 triples each)
    Strong operations (alignment > 0.7):   <N>
    Moderate operations (0.5 - 0.7):       <N>
    Weak/no operation (< 0.5):             <N>

  TOP DISCOVERED OPERATIONS:
  Predicate  Label                         N   Align  PairCon  MagCV   Dist
  -----------------------------------------------------------------------
  P8324      funder                       25  0.9297  0.8589  0.079  0.447
  ...

PHASE 2: PREDICTION EVALUATION
  Mean MRR:              <value>
  Mean Hits@1:           <value>
  Mean Hits@10:          <value>
  Correlation (alignment <-> MRR):   <r-value>

PHASE 3: COMPOSITION TEST
  Two-hop compositions tested: <N>
  Hits@10: <value>

PHASE 4: FAILURE ANALYSIS
  WEAKEST OPERATIONS:
  P3373 sibling    0.026  (Symmetric)
  P155  follows    0.050  (Sequence)
```

**Key metrics to verify:**
- At least some predicates with alignment > 0.7 (discovered operations)
- Positive correlation between alignment and MRR (self-diagnostic property)
- Symmetric predicates (sibling, spouse) should have alignment near 0

**Runtime:** ~5-15 minutes depending on dataset size.

## Step 4: Collision and Density Analysis

Description: Detect embedding collisions — distinct entities with near-identical vectors — caused by the `[UNK]` tokenizer defect.

```bash
python scripts/analyze_collisions.py --threshold 0.95 --k 10
```

Expected Output:
- Cross-entity collisions found at cosine >= 0.95
- Density statistics (mean k-NN distance, regime classification)
- Collision breakdown by type (genuine semantic vs trivial text overlap)

**Artifacts:**
- `data/analysis_results.json` — Collision and density results

For detailed collision type classification:

```bash
python scripts/analyze_collision_types.py
```

This separates trivial collisions (same/near-identical text) from genuine semantic collisions (different words, different languages, cosine ~1.0 due to `[UNK]` dominance).

## Step 5: String Overlap Null Model

Description: Verify that discovered operations capture genuine relational structure beyond surface-level string similarity.

```bash
python scripts/string_null_model.py
```

This compares vector arithmetic MRR against a string-overlap baseline (longest common substring). The null model should perform substantially worse, confirming that embeddings encode relational structure beyond string patterns.

## Step 6: Verify Results

Description: Automated verification of key findings.

```bash
python -c "
import json
import numpy as np

with open('data/fol_results.json', encoding='utf-8') as f:
    results = json.load(f)

summary = results['summary']
ops = results['discovered_operations']
preds = results['prediction_results']

print('=== VERIFICATION ===')
print(f'Embeddings: {summary[\"total_embeddings\"]}')
print(f'Predicates analyzed: {summary[\"predicates_analyzed\"]}')
print(f'Strong operations (>0.7): {summary[\"strong_operations\"]}')
print(f'Total discovered (>0.5): {summary[\"strong_operations\"] + summary[\"moderate_operations\"]}')

if preds:
    aligns = [p['alignment'] for p in preds]
    mrrs = [p['mrr'] for p in preds]
    corr = np.corrcoef(aligns, mrrs)[0,1]
    print(f'Alignment-MRR correlation: {corr:.3f}')
    assert corr > 0.5, f'Correlation too low: {corr}'
    print('Correlation check: PASS')

sym_ops = [o for o in ops if o['predicate'] in ['P3373', 'P26', 'P47', 'P530']]
if sym_ops:
    max_sym = max(o['mean_alignment'] for o in sym_ops)
    print(f'Max symmetric predicate alignment: {max_sym:.3f}')
    assert max_sym < 0.3, f'Symmetric predicate too high: {max_sym}'
    print('Symmetric failure check: PASS')

if ops:
    best = max(o['mean_alignment'] for o in ops)
    print(f'Best operation alignment: {best:.3f}')
    assert best > 0.7, f'Best alignment too low: {best}'
    print('Operation discovery check: PASS')

print()
print('All checks passed.')
"
```

Expected Output:
- `Correlation check: PASS`
- `Symmetric failure check: PASS`
- `Operation discovery check: PASS`
- `All checks passed.`

## Step 7: Cross-Model Generalization

Description: Re-run on additional embedding models to demonstrate model-agnostic findings.

```bash
ollama pull nomic-embed-text    # 768-dim
ollama pull all-minilm           # 384-dim
```

Run the pipeline for each model using the `EMBED_MODEL` and `FOL_DATA_DIR` environment variables:

```bash
# Model 2: nomic-embed-text (768-dim)
FOL_DATA_DIR=data-nomic EMBED_MODEL=nomic-embed-text python scripts/random_walk.py Q1342448 --limit 100
FOL_DATA_DIR=data-nomic python scripts/fol_discovery.py

# Model 3: all-minilm (384-dim)
FOL_DATA_DIR=data-minilm EMBED_MODEL=all-minilm python scripts/random_walk.py Q1342448 --limit 100
FOL_DATA_DIR=data-minilm python scripts/fol_discovery.py
```

Compare across models:

```bash
python scripts/compare_models.py
```

**Expected finding:** Functional predicates (flag, coat of arms, demographics) appear across all models. Symmetric predicates fail in all models. The overlap set (30 operations in the paper's full dataset) is the evidence for model-agnostic structure.

**Runtime:** ~30-45 min per model (100 entities) or ~2-3 hours per model (500 entities).

## Step 8: Statistical Rigor

Description: Bootstrap confidence intervals, effect sizes, and ablation.

```bash
python scripts/statistical_analysis.py
```

Produces:
- Bootstrap 95% CI for the alignment-MRR correlation
- Cohen's d effect sizes for functional vs relational predicates
- Bonferroni/Holm correction across all tests
- Ablation: how discovery count changes with min-triple threshold (5, 10, 20, 50)

## Step 9: Figures and PDF

Description: Generate publication figures and compile the paper.

```bash
pip install fpdf2 matplotlib
python scripts/generate_figures.py
python scripts/generate_pdf.py
```

**Artifacts:**
- `figures/` — 7 PNG figures at 300 DPI
- `paper.pdf` — Complete paper with embedded figures

## Interpretation Guide

### What the Numbers Mean

- **Alignment > 0.7**: Strong discovered operation. The predicate reliably functions as vector arithmetic.
- **Alignment 0.5 - 0.7**: Moderate operation. Works sometimes, noisy.
- **Alignment < 0.3**: Not a vector operation. The relationship is real but lacks consistent geometric direction.
- **MRR = 1.0**: Perfect prediction — the correct entity is always nearest neighbor to the predicted point.
- **Correlation > 0.7**: The self-diagnostic works — alignment predicts which operations will be useful.

### Why Some Predicates Fail

1. **Symmetric predicates** (sibling, spouse): A->B and B->A produce opposite vectors. No consistent direction.
2. **Semantically overloaded** (instance-of): "Tokyo instance-of city" and "7 instance-of prime" point in unrelated directions.
3. **Sequence predicates** (follows): "Monday->Tuesday" and "Chapter 1->Chapter 2" are unrelated geometrically.

These failures are informative: they reveal what embedding spaces cannot represent as geometry, matching predictions from the KGE literature (Wang et al., 2014).

### The Tokenizer Defect

The most practically significant finding. When mxbai-embed-large encounters characters with diacritical marks (o, u, i, etc.), these are absent from the WordPiece vocabulary and replaced with `[UNK]` tokens. For short inputs where most characters are OOV, the `[UNK]` token representation dominates the embedding, collapsing all such inputs to a single attractor region.

**Impact:** Any RAG system, semantic search, or knowledge graph using mxbai-embed-large with non-ASCII input silently retrieves results from the `[UNK]` attractor instead of semantically relevant results. Standard benchmarks (MTEB) do not test for this.

## Dependencies

- Python 3.10+
- numpy, requests, ollama, rdflib (core)
- matplotlib, fpdf2 (figures/PDF only)
- Ollama with embedding models:
  - `mxbai-embed-large` (1024-dim, primary)
  - `nomic-embed-text` (768-dim, cross-model, Step 7)
  - `all-minilm` (384-dim, cross-model, Step 7)

No GPU required. All models run on CPU via Ollama.

## Timing

| Step | ~Time (100 entities) | ~Time (500 entities) |
|------|---------------------|---------------------|
| Step 2: Import (per model) | 10-15 min | 45-60 min |
| Step 3: FOL Discovery | 3-5 min | 10-15 min |
| Step 4: Collision Analysis | 2-5 min | 15-30 min |
| Step 5: String Null Model | <1 min | <1 min |
| Step 6: Verification | <10 sec | <10 sec |
| Step 7: Cross-Model (3 models) | 30-45 min | 2-3 hours |
| Step 8: Statistics | <1 min | <1 min |
| **Quick validation (Steps 1-6)** | **~20 min** | **~1.5 hours** |
| **Full pipeline (all steps)** | **~1.5 hours** | **~6-8 hours** |

## Success Criteria

**Core pipeline (Steps 1-6):**
- Entities imported and embedded without errors
- At least some operations discovered with alignment > 0.7
- Positive correlation between alignment and prediction MRR
- Symmetric predicates show low alignment (< 0.3)
- String null model performs worse than vector arithmetic
- Verification checks pass

**Cross-model (Step 7):**
- All 3 models produce discovered operations
- Non-empty overlap set (operations found across all models)
- Functional predicates in overlap; symmetric predicates fail in all

**Statistical (Step 8):**
- Bootstrap CI for alignment-MRR correlation excludes zero
- Ablation shows monotonic relationship between min-triple threshold and mean alignment

## References

- Bordes et al. (2013). Translating Embeddings for Modeling Multi-relational Data. NeurIPS.
- Li et al. (2024). Glitch Tokens in Large Language Models. Proc. ACM Softw. Eng. (FSE).
- Liu et al. (2019). Latent Space Cartography: Visual Analysis of Vector Space Embeddings. Computer Graphics Forum.
- Mikolov et al. (2013). Distributed Representations of Words and Phrases. NeurIPS.
- Sun et al. (2019). RotatE: Knowledge Graph Embedding by Relational Rotation. ICLR.
- Wang et al. (2014). Knowledge Graph Embedding by Translating on Hyperplanes. AAAI.
