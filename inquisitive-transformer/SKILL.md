# SKILL.md -- Executable Reproduction Instructions

## Prerequisites

- Python 3.10+ (tested on Python 3.13)
- A machine with at least 2GB RAM (GPT-2 124M fits in CPU memory)
- CUDA GPU optional but recommended for faster evaluation

## Installation

```bash
cd papers/inquisitive-transformer
pip install -r requirements.txt
```

The key dependencies are:
- `torch` (>= 2.0)
- `transformers` (>= 4.35) -- provides GPT-2 model and tokenizer
- `pytest` -- for running the test suite

GPT-2 weights will be downloaded automatically from HuggingFace on first run (~500MB).

## Running Experiments

All experiments are run from the `papers/inquisitive-transformer/` directory. On Windows, use `python` (not `python3`).

### E1: Uniform Alpha

Tests whether the perceptiveness effect exists at all. All attention heads receive the same alpha.

```bash
python -m experiments.e1_uniform
```

Expected output: A table of accuracy values across 7 alpha values (-1.0 to +1.0) on 24 CVD items, with per-category breakdowns. Results saved to `results/e1_uniform_full.json` and `results/e1_uniform_summary.csv`.

### E2: Split Heads

Tests whether head specialization helps. First 6 layers get +alpha, last 6 get -alpha.

```bash
python -m experiments.e2_split
```

Expected output: Same format as E1. Results saved to `results/e2_split_*.{json,csv}`.

### E3: Random Alpha

Control experiment. Each layer gets a random alpha. Three trials are averaged.

```bash
python -m experiments.e3_random
```

Expected output: Three trials, each with 7 alpha scale values. Averaged summary printed at end. Results saved to `results/e3_random_trial{0,1,2}_*.{json,csv}`.

### E4: Alternating Paired Alpha

Even layers get +alpha, odd layers get -alpha. Tests fine-grained alternation vs. coarse split.

```bash
python -m experiments.e4_doubled
```

Expected output: Same format as E1. Results saved to `results/e4_alternating_*.{json,csv}`.

### Temperature Control (optional, for any experiment)

Add `--temperature-control` to include a temperature sweep at alpha=0 as a control:

```bash
python -m experiments.e1_uniform --temperature-control
```

### All Experiments in Sequence

```bash
python -m experiments.e1_uniform && python -m experiments.e2_split && python -m experiments.e3_random && python -m experiments.e4_doubled
```

## Running the Test Suite

```bash
pytest tests/ -v
```

Expected: 51 tests passing. Tests cover:
- Surprise function correctness (output shapes, normalization, causality)
- InquisitiveAttention behavior (alpha=0 matches standard, nonzero alpha modifies output)
- InquisitiveGPT2 wrapper (model loading, alpha setting, per-layer control)
- CVD dataset structure (24 items, 3 categories, valid format)
- Evaluation harness (scoring, result aggregation)

## Verification Criteria

1. **Alpha = 0 baseline**: At alpha = 0, InquisitiveAttention must produce identical output to standard GPT2Attention. This is verified by the test suite.

2. **Nonzero alpha effect**: At alpha != 0, attention outputs must differ from baseline. This is verified by comparing tensors in the test suite.

3. **Surprise function properties**:
   - Output shape is [batch, heads, 1, seq_len] for all functions
   - Causal functions (running mean, cosine, local window) produce zero surprise at position 0
   - All functions produce normalized output (approximately zero mean, unit variance)

4. **CVD benchmark**: All 24 items load correctly with valid structure (passage, question, 4 choices, correct index 0-3).

5. **Experiment outputs**: Each experiment produces both a JSON file (full per-item results) and a CSV file (summary with alpha, accuracy, per-category accuracy).

## Output Files

After running all experiments, the `results/` directory will contain:

```
results/
  e1_uniform_full.json        # Full per-item results for E1
  e1_uniform_summary.csv      # Summary table for E1
  e2_split_full.json
  e2_split_summary.csv
  e3_random_trial0_full.json
  e3_random_trial0_summary.csv
  e3_random_trial1_full.json
  e3_random_trial1_summary.csv
  e3_random_trial2_full.json
  e3_random_trial2_summary.csv
  e4_alternating_full.json
  e4_alternating_summary.csv
```

## Troubleshooting

- **ModuleNotFoundError for `src`**: Make sure you are running from the `papers/inquisitive-transformer/` directory, not the repo root.
- **CUDA out of memory**: GPT-2 124M is small and should fit on any GPU. If issues arise, use `--device cpu`.
- **Slow execution**: Each experiment evaluates 24 items at 7 alpha values = 168 evaluations, each requiring 4 forward passes (one per choice). On CPU this takes 5-15 minutes per experiment. GPU reduces this to 1-3 minutes.
- **`python3` not found (Windows)**: Use `python` instead.
