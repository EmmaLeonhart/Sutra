# SKILL.md — Structured Matching Primitive for Many-to-Many Matching

## Executable Demonstration

This paper's core claim — that the three-part structured matching primitive (directional selection + control projection + residual similarity) outperforms both naive cosine similarity and control-only projection — is fully reproducible via a single script.

## Prerequisites

- Python 3.10+
- Ollama running locally with models: `mxbai-embed-large`, `nomic-embed-text`, `all-minilm`
- Python packages: `numpy`, `scipy`, `ollama`
Install:
```bash
pip install numpy scipy ollama
```

Pull Ollama models:
```bash
ollama pull mxbai-embed-large
ollama pull nomic-embed-text
ollama pull all-minilm
```

## Running the Experiments

### Single model (fastest, ~30 seconds):
```bash
cd papers/many-to-many
python scripts/structured_matching.py --model mxbai-embed-large
```

### All models (~2 minutes):
```bash
python scripts/structured_matching.py --all-models
```

### Custom output location:
```bash
python scripts/structured_matching.py --all-models --output results.json
```

## What the Script Does

For each of three datasets (biomedical protein matching, labor/hiring, ontological categorization):

1. **Embeds** all query, candidate, and group texts using the selected model
2. **Derives a control vector** as the mean displacement between two groups representing the confounding dimension (e.g., human vs. mouse organism context)
3. **Ranks candidates** by naive cosine similarity to the query
4. **Projects away** the control vector from all embeddings via orthogonal projection
5. **Re-ranks candidates** by cosine similarity in the projected space
6. **Reports** MRR, Precision@k, mean rank, and query-control alignment before/after

## Expected Output

Results are saved to `data/decomposition_results.json`. Expected behavior:

- **10/12 experiments show MRR improvement** (83% success rate)
- **Query-control alignment drops to ~0** after projection (proving the confounding dimension is eliminated)
- **No experiment shows degradation** — projection is a Pareto non-degradation at worst
- **Ontology experiments show largest improvements** — domain register is a stronger confounder than organism context or gender coding

## Verification Criteria

The following must hold for the results to validate the paper's claims:

1. **Structural elimination**: Query-control alignment after projection < 10⁻⁶ for all experiments
2. **Non-degradation**: No experiment shows MRR decrease > 0.01 (projection should never significantly hurt)
3. **Cross-model consistency**: Improvement observed on at least 3 of 4 models
4. **Mean MRR improvement**: Positive across all experiments combined

## Datasets

Each dataset is constructed to create a scenario where a confounding dimension contaminates similarity:

| Dataset | Query | Correct matches | Confounders | Control dimension |
|---------|-------|----------------|-------------|-------------------|
| Biomedical | Cancer protein in mouse context | Cancer proteins (any organism) | Cardiovascular proteins in mouse context | Human vs. mouse organism framing |
| Labor | Male software engineer | Software engineers (any gender) | Male non-engineers | Male vs. female gender coding |
| Ontology | Religious leader (abbot) | Leaders in any domain | Religious non-leaders | Religious vs. military register |

## Reproducing from Scratch

The entire pipeline runs end-to-end with no external data dependencies. All datasets are self-contained in the script. The only requirements are embedding model access (Ollama for local models, HuggingFace for BioBERT).

Total runtime: ~30 seconds per model, ~2 minutes for all 4 models.
