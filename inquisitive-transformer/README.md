# Inquisitive Transformer

A novel attention mechanism modification that introduces **perceptiveness** as an independent,
orthogonal control axis to temperature in transformer models.

## The Idea

Standard attention treats all keys uniformly. Temperature controls the *sharpness* of the
attention distribution, but it does so uniformly -- it can't selectively amplify or suppress
surprising tokens.

The **Inquisitive Transformer** adds a perceptiveness parameter `alpha` that controls how
strongly the model reacts to unexpected or out-of-place keys:

```
Standard:     Attention(Q, K, V) = softmax(QK^T / sqrt(d)) V
Inquisitive:  Attention(Q, K, V, alpha) = softmax(QK^T / sqrt(d) + alpha * S(K)) V
```

Where `S(K)` measures per-key surprisingness (how out-of-place each key is given its context),
and `alpha` in [-1, +1] controls the effect:

- **alpha > 0** (high perceptiveness): Surprising keys get *amplified* -- the model interrogates
  anomalies, notices what doesn't fit
- **alpha = 0**: Standard attention (backward compatible)
- **alpha < 0** (low perceptiveness): Surprising keys get *suppressed* -- the model smooths over
  oddities, answers the "average" question

## Why This Matters

Temperature and perceptiveness are genuinely independent dimensions. You cannot achieve
perceptiveness effects by tuning temperature alone. This gives users a new behavioral control
knob that's particularly useful for:

- **AI therapy/counseling** -- catch what the patient *almost* said
- **Document analysis** -- spot the incongruent detail in a long report
- **Creative applications** -- high perceptiveness latches onto the weirdest part of a prompt

## Status

**Phase 2: Experiments ready** -- Core modules, CVD benchmark (24 items across 3 categories),
and all 4 ablation experiments implemented. 51 unit tests passing. CI via GitHub Actions.

See [planning/](planning/) for detailed project plan and technical specification.

## Getting Started

```bash
pip install -r requirements.txt
```

## Quick Usage

```python
from src.inquisitive_gpt2 import InquisitiveGPT2

model = InquisitiveGPT2.from_pretrained("gpt2")
model.set_alpha(0.5)  # amplify surprising keys
print(model.generate("The anthropologist noticed", max_new_tokens=50))
```

## Running Experiments

```bash
# E1: Uniform alpha -- does the effect exist?
python -m experiments.e1_uniform

# E2: Split heads -- does specialization help?
python -m experiments.e2_split

# E3: Random alpha -- is structure necessary?
python -m experiments.e3_random

# E4: Alternating paired -- does fine-grained alternation help?
python -m experiments.e4_doubled

# Add --temperature-control to include temperature sweep as control
python -m experiments.e1_uniform --temperature-control
```

Results are saved to `results/` as JSON (full details) and CSV (summary).

## Project Structure

```
src/
  surprise_functions.py      # S(K) implementations (causal running mean, cosine, etc.)
  inquisitive_attention.py   # Modified GPT-2 attention with alpha parameter
  inquisitive_gpt2.py        # Model wrapper with alpha control API
  benchmark/
    cvd_dataset.py           # 24-item Contextual Violation Detection benchmark
    evaluate.py              # Log-prob scoring and evaluation harness
experiments/
  e1_uniform.py              # All heads same alpha
  e2_split.py                # Half +alpha, half -alpha
  e3_random.py               # Random alpha per layer
  e4_doubled.py              # Alternating +/- alpha per layer
  common.py                  # Shared experiment utilities
tests/                       # 51 unit tests
planning/                    # Project plans, technical specs
```

## References

- [Attention Is All You Need](https://arxiv.org/abs/1706.03762) (Vaswani et al., 2017)
- [Keys, Queries & Values](http://emmaleonhart.com/attention/) -- Interactive attention explainer
