---
name: fol-discovery
description: Discover first-order logic operations latently encoded in arbitrary embedding spaces. Imports entities from Wikidata, embeds them, computes trajectory displacement vectors, and tests which predicates function as consistent vector arithmetic. Reproduces the key finding that 86 predicates encode as discoverable operations with r=0.78 self-diagnostic correlation.
allowed-tools: Bash(python *), Bash(pip *), Bash(ollama *), WebFetch
---

# Discovering First-Order Logic in Arbitrary Embedding Spaces

**Claw 🦞 Co-Author: Barbara (OpenClaw)**
**Submission ID: CLAW4S-2026-FOL-DISCOVERY**
**Deadline: April 5, 2026**

This skill discovers first-order logical operations latently encoded in general-purpose text embedding spaces. Unlike TransE and other neurosymbolic approaches that *construct* spaces for logic, this method *excavates* logic from spaces not built for it.

**Key Innovation:** Given any embedding model + knowledge base, systematically discover which logical relationships manifest as consistent vector displacements — with no training, no learned parameters, and a self-diagnostic quality metric (r = 0.78 correlation between geometric consistency and prediction accuracy).

## Prerequisites

```bash
# Required packages
pip install numpy requests ollama rdflib

# Required: Ollama with mxbai-embed-large model
# Install Ollama from https://ollama.ai, then:
ollama pull mxbai-embed-large
```

Verify Ollama is running and the model is available:

```bash
python -c "import ollama; r = ollama.embed(model='mxbai-embed-large', input=['test']); print(f'OK: {len(r.embeddings[0])}-dim')"
```

Expected Output: `OK: 1024-dim`

## Step 1: Clone and Setup

Description: Clone the repository and verify the environment.

```bash
git clone https://github.com/EmmaLeonhart/Claw4S-submissions.git
cd Claw4S-submissions
mkdir -p papers/fol-discovery/data
```

Verify Python dependencies:

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

Description: Breadth-first search from a seed entity through Wikidata, importing entities with all their triples and computing embeddings via mxbai-embed-large.

```bash
python papers/fol-discovery/scripts/random_walk.py Q1342448 --limit 100
```

This imports 100 entities starting from Engishiki (Q1342448), a Japanese historical text with a dense ontological neighborhood. Each imported entity:
1. Has all Wikidata triples fetched
2. Has its label and aliases embedded (1024-dim)
3. Has all linked entities' labels fetched and embedded
4. Has trajectories (displacement vectors) computed for all entity-entity triples

**Parameters:**
- `Q1342448` — Seed entity (Engishiki). Any QID works.
- `--limit 100` — Number of entities to fully import. More = denser map, longer runtime.
- `--resume` — Continue from a previous run's saved queue state.

Expected Output:
- `[1/100] Importing Q1342448 (queue: 0)...`
- `  Engishiki - <N> triples, discovered <M> linked QIDs`
- ... (progress updates every entity)
- `Final state:`
- `  Items: <N> (hundreds to thousands)`
- `  Embeddings: <N> x 1024`
- `  Trajectories: <N> (hundreds to thousands)`

**Runtime:** ~10-15 minutes for 100 entities (depends on Wikidata API speed and Ollama inference).

**Artifacts:**
- `papers/fol-discovery/data/items.json` — All imported entities with triples
- `papers/fol-discovery/data/embeddings.npz` — Embedding vectors (numpy)
- `papers/fol-discovery/data/embedding_index.json` — Vector index → (qid, text, type) mapping
- `papers/fol-discovery/data/walk_state.json` — Resumable BFS queue state
- `papers/fol-discovery/data/triples.nt` — RDF triples (N-Triples format)
- `papers/fol-discovery/data/geodesics.ttl` — Trajectory objects (Turtle format)

## Step 3: Discover First-Order Logic Operations

Description: The core analysis. For each predicate with sufficient triples, compute displacement vector consistency and evaluate prediction accuracy.

```bash
python papers/fol-discovery/scripts/fol_discovery.py --min-triples 5
```

The discovery procedure for each predicate:
1. Compute all trajectories (object_vec - subject_vec) for the predicate's triples
2. Compute the mean displacement = the "operation vector"
3. Measure consistency: how aligned are individual displacements with the mean?
4. Evaluate prediction: leave-one-out, predict object via subject + operation vector
5. Test composition: chain two operations (S + d₁ + d₂ → O)
6. Analyze failures: characterize predicates that resist vector encoding

**Parameters:**
- `--min-triples 5` — Minimum triples per predicate to analyze (lower = more predicates tested, noisier results)
- `--output papers/fol-discovery/data/fol_results.json` — Output file path

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
  P2633      geography of topic           18  0.9101  0.8185  0.097  0.200
  ...

PHASE 2: PREDICTION EVALUATION
  Mean MRR:              <value>
  Mean Hits@1:           <value>
  Mean Hits@10:          <value>
  Correlation (alignment ↔ MRR):   <r-value>

PHASE 3: COMPOSITION TEST
  Two-hop compositions tested: <N>
  Hits@10: <value>

PHASE 4: FAILURE ANALYSIS
  WEAKEST OPERATIONS:
  P3373 sibling    0.026  (Symmetric)
  P155  follows    0.050  (Sequence)
  ...
```

**Key metrics to verify:**
- At least some predicates with alignment > 0.7 (discovered operations)
- Positive correlation between alignment and MRR (self-diagnostic property)
- Symmetric predicates (sibling, spouse) should have alignment near 0

**Runtime:** ~5-15 minutes depending on dataset size.

**Artifacts:**
- `papers/fol-discovery/data/fol_results.json` — Complete results with discovered operations, prediction scores, and failure analysis

## Step 4: Collision and Density Analysis (Optional)

Description: Detect embedding collisions (distinct entities with near-identical vectors) and classify regions by density.

```bash
python papers/fol-discovery/scripts/analyze_collisions.py --threshold 0.95 --k 10
```

Expected Output:
- Cross-entity collisions found at the threshold
- Density statistics (mean k-NN distance, regime classification)
- Trajectory consistency per predicate

**Artifacts:**
- `papers/fol-discovery/data/analysis_results.json` — Collision and density results

## Step 5: Verify Results

Description: Confirm the key findings are reproducible.

```bash
python -c "
import json
import numpy as np

# Load FOL results
with open('papers/fol-discovery/data/fol_results.json', encoding='utf-8') as f:
    results = json.load(f)

summary = results['summary']
ops = results['discovered_operations']
preds = results['prediction_results']

print('=== VERIFICATION ===')
print(f'Embeddings: {summary[\"total_embeddings\"]}')
print(f'Predicates analyzed: {summary[\"predicates_analyzed\"]}')
print(f'Strong operations (>0.7): {summary[\"strong_operations\"]}')
print(f'Total discovered (>0.5): {summary[\"strong_operations\"] + summary[\"moderate_operations\"]}')

# Check self-diagnostic correlation
if preds:
    aligns = [p['alignment'] for p in preds]
    mrrs = [p['mrr'] for p in preds]
    corr = np.corrcoef(aligns, mrrs)[0,1]
    print(f'Alignment-MRR correlation: {corr:.3f}')
    assert corr > 0.5, f'Correlation too low: {corr}'
    print('Correlation check: PASS')

# Check that symmetric predicates fail
sym_ops = [o for o in ops if o['predicate'] in ['P3373', 'P26', 'P47', 'P530']]
if sym_ops:
    max_sym = max(o['mean_alignment'] for o in sym_ops)
    print(f'Max symmetric predicate alignment: {max_sym:.3f}')
    assert max_sym < 0.3, f'Symmetric predicate too high: {max_sym}'
    print('Symmetric failure check: PASS')

# Check that at least some operations have high alignment
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
- `Alignment-MRR correlation: >0.5`
- `Correlation check: PASS`
- `Symmetric failure check: PASS`
- `Operation discovery check: PASS`
- `All checks passed.`

## Interpretation Guide

### What the Numbers Mean

- **Alignment > 0.7**: Strong discovered operation. The predicate reliably functions as vector arithmetic. You can use `subject + operation_vector ≈ object` for prediction.
- **Alignment 0.5 - 0.7**: Moderate operation. Works sometimes, noisy.
- **Alignment < 0.3**: Not a vector operation. The relationship is real but doesn't have a consistent geometric direction.
- **MRR = 1.0**: Perfect prediction — the correct entity is always the nearest neighbor to the predicted point.
- **Correlation > 0.7**: The self-diagnostic works — you can trust the alignment score to predict which operations will be useful.

### Why Some Predicates Fail

1. **Symmetric predicates** (sibling, spouse): `A→B` and `B→A` produce opposite vectors. No consistent direction.
2. **Semantically overloaded** (instance-of): "Tokyo instance-of city" and "7 instance-of prime" have nothing in common geometrically.
3. **Sequence predicates** (follows): "Monday→Tuesday" and "Chapter 1→Chapter 2" point in unrelated directions.

These failures are **informative**: they reveal what embedding spaces *cannot* represent as geometry.

## Step 6: Cross-Model Generalization (Key Novelty Claim)

Description: Re-run the full pipeline on multiple embedding models to demonstrate that discovered operations are model-agnostic — not artifacts of a single model's training.

### Setup: Pull additional embedding models

```bash
ollama pull nomic-embed-text    # 768-dim, different architecture
ollama pull all-minilm           # 384-dim, much smaller model
```

### Run pipeline for each model

The import script accepts an `--embed-model` flag (or edit `EMBED_MODEL` in `papers/fol-discovery/scripts/import_wikidata.py`). Each model writes to a separate data directory.

```bash
# Model 2: nomic-embed-text (768-dim)
EMBED_MODEL=nomic-embed-text python papers/fol-discovery/scripts/random_walk.py Q1342448 --limit 500 --data-dir papers/fol-discovery/data-nomic
python papers/fol-discovery/scripts/fol_discovery.py --data-dir papers/fol-discovery/data-nomic

# Model 3: all-minilm (384-dim)
EMBED_MODEL=all-minilm python papers/fol-discovery/scripts/random_walk.py Q1342448 --limit 500 --data-dir papers/fol-discovery/data-minilm
python papers/fol-discovery/scripts/fol_discovery.py --data-dir papers/fol-discovery/data-minilm
```

### Compare: Cross-Model Operation Overlap

```bash
python papers/fol-discovery/scripts/compare_models.py
```

This produces:
- Which operations are discovered by ALL models (robust, model-agnostic operations)
- Which are model-specific (artifacts of training data)
- Correlation between consistency scores across models
- Comparison table for paper inclusion

**Expected finding:** Functional predicates (flag, coat of arms, demographics) should appear across all models. Symmetric predicates should fail across all models. The overlap set is the core evidence for model-agnostic neuro-symbolic reasoning.

**Runtime:** ~45-60 min per model for import + ~10 min for discovery = ~2-3 hours total for 3 models.

## Step 7: Multi-Seed Robustness Check

Description: Run from different seed entities to show results aren't specific to the Engishiki domain.

```bash
# Seed 2: Mountain (Q8502) — geography/geology domain
python papers/fol-discovery/scripts/random_walk.py Q8502 --limit 500 --data-dir papers/fol-discovery/data-mountain
python papers/fol-discovery/scripts/fol_discovery.py --data-dir papers/fol-discovery/data-mountain

# Seed 3: Human (Q5) — biographical/social domain
python papers/fol-discovery/scripts/random_walk.py Q5 --limit 500 --data-dir papers/fol-discovery/data-human
python papers/fol-discovery/scripts/fol_discovery.py --data-dir papers/fol-discovery/data-human
```

Operations discovered from all 3 seeds are robust across domains. Operations found from only 1 seed reflect domain-specific structure.

**Runtime:** ~45-60 min per seed for import + ~10 min for discovery.

## Step 8: Statistical Rigor Verification

Description: Verify key claims with proper statistical methods.

```bash
python papers/fol-discovery/scripts/statistical_analysis.py
```

This produces:
- Bootstrap confidence intervals for the alignment-MRR correlation
- Effect sizes (Cohen's d) for functional vs relational predicate performance
- Bonferroni/Holm correction across all reported statistical tests
- Ablation: how discovery count changes with min-triple threshold (5, 10, 20, 50)

## Step 9: Generate Figures and PDF

Description: Generate all publication figures and compile the paper as a PDF with embedded figures.

```bash
pip install fpdf2 matplotlib

# Generate figures
python papers/fol-discovery/scripts/generate_figures.py

# Generate PDF with figures embedded
python papers/fol-discovery/scripts/generate_pdf.py
```

Expected Output:
- `papers/fol-discovery/figures/` — 7 PNG figures at 300 DPI
- `papers/fol-discovery/paper.pdf` — Complete paper with embedded figures (~12 pages)

Figures produced:
1. Alignment vs MRR scatter plot (self-diagnostic correlation)
2. Operation discovery distribution histogram
3. Collision type breakdown (genuine semantic vs trivial)
4. Three-zone regime diagram with empirical data
5. Cross-model comparison (after Step 6)
6. Ablation study (after Step 8)
7. Bootstrap distribution of correlation (after Step 8)

## Dependencies

- Python 3.10+
- numpy
- requests
- ollama (Python client)
- rdflib
- Ollama server with embedding models:
  - `mxbai-embed-large` (1024-dim, primary)
  - `nomic-embed-text` (768-dim, cross-model validation)
  - `all-minilm` (384-dim, cross-model validation)

**No GPU required.** All models run on CPU via Ollama (slower but functional).

## Timing

| Step | ~Time (100 entities) | ~Time (500 entities) |
|------|---------------------|---------------------|
| Step 2: Import (per model) | 10-15 min | 45-60 min |
| Step 3: FOL Discovery | 3-5 min | 10-15 min |
| Step 4: Collision Analysis | 2-5 min | 15-30 min |
| Step 5: Verification | <10 sec | <10 sec |
| Step 6: Cross-Model (3 models) | 30-45 min | 2-3 hours |
| Step 7: Multi-Seed (3 seeds) | 30-45 min | 2-3 hours |
| Step 8: Statistical Analysis | <1 min | <1 min |
| **Total (full pipeline)** | **~1.5 hours** | **~6-8 hours** |

For a quick validation run (Steps 1-5 only): ~20 min at 100 entities.

## Success Criteria

This skill is successfully executed when:

**Core pipeline (Steps 1-5):**
- ✓ Entities imported, embeddings generated without errors
- ✓ At least some operations discovered with alignment > 0.7
- ✓ Positive correlation between alignment and prediction MRR
- ✓ Symmetric predicates show low alignment (<0.3)
- ✓ Verification checks pass

**Cross-model (Step 6):**
- ✓ All 3 models produce discovered operations
- ✓ Overlap set is non-empty (some operations found across all models)
- ✓ Functional predicates appear in overlap; symmetric predicates fail in all models

**Robustness (Step 7):**
- ✓ All 3 seeds produce discovered operations
- ✓ The self-diagnostic correlation (alignment ↔ MRR) holds across seeds

**Statistical (Step 8):**
- ✓ Bootstrap CI for alignment-MRR correlation excludes zero
- ✓ Ablation shows monotonic relationship between min-triple threshold and mean alignment

## References

- Bordes et al. (2013). Translating Embeddings for Modeling Multi-relational Data. NeurIPS.
- Li et al. (2024). Glitch Tokens in Large Language Models. Proc. ACM Softw. Eng. (FSE).
- Mikolov et al. (2013). Distributed Representations of Words and Phrases. NeurIPS.
- Sun et al. (2019). RotatE: Knowledge Graph Embedding by Relational Rotation. ICLR.
- Claw4S Conference: https://claw4s.github.io/
- Repository: https://github.com/EmmaLeonhart/Claw4S-submissions
