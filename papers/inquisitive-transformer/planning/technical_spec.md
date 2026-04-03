# Inquisitive Transformer - Technical Specification

## 1. Mathematical Formulation

### 1.1 Standard Multi-Head Attention (Baseline)

For a single attention head with dimension d_k:

```
Attention(Q, K, V) = softmax(QK^T / sqrt(d_k)) V
```

Where Q, K, V are projected from the input embeddings X:
```
Q = X W_Q,  K = X W_K,  V = X W_V
```

### 1.2 Inquisitive Attention

We introduce an additive surprise bias before softmax:

```
scores = QK^T / sqrt(d_k)
surprise = S(K)                    # per-key surprisingness signal
scores_modified = scores + alpha * surprise
output = softmax(scores_modified) V
```

Where:
- `alpha` in [-1, +1] is the perceptiveness parameter (set at inference time)
- `S(K)` produces a surprise score per key position
- At alpha = 0, this reduces exactly to standard attention

### 1.3 Surprisingness Function S(K)

**Primary candidate: Causal Running Mean Distance**

For a sequence of key vectors k_1, ..., k_n:
```
S_i = ||k_i - mu_i|| / sigma_i

where:
  mu_i = (1 / (i-1)) * sum(k_1 ... k_{i-1})     # running mean of prior keys
  sigma_i = std(||k_j - mu_i|| for j < i)         # running std for normalization
```

Properties:
- **Causal**: only looks at prior keys (respects autoregressive masking)
- **Cheap**: O(n) with running statistics, no extra parameters
- **Interpretable**: literally "how far is this key from what came before"
- **No circularity**: doesn't depend on attention scores

**Alternative candidates to test**:

| Method | Formula | Pros | Cons |
|--------|---------|------|------|
| Key magnitude | `\|\|k_i\|\| - mean(\|\|K\|\|)` | Simplest | Non-causal, less meaningful |
| Key cosine outlier | `1 - cos(k_i, mu_i)` | Angular, scale-invariant | Misses magnitude info |
| Local window distance | `\|\|k_i - mean(k_{i-w}..k_{i-1})\|\|` | Local context | Window size hyperparameter |
| Learned MLP | `MLP(k_i, mu_i)` | Most expressive | Requires training, breaks inference-only |

### 1.4 Broadcasting Surprise to Attention Scores

The surprise signal `S` has shape `[seq_len]` (one value per key position).
The attention scores have shape `[seq_len_q, seq_len_k]`.

We broadcast: each query sees the same surprise profile across keys:
```
scores_modified[i, j] = scores[i, j] + alpha * S[j]
```

This means "key j is surprising regardless of which query is looking at it."

An alternative (query-dependent surprise) would be:
```
S(q_i, k_j) = ||k_j - expected_key(q_i)||
```
But this is more complex and the simpler version should be tested first.

## 2. Architecture Changes

### 2.1 Modified Attention Module

Starting from HuggingFace GPT-2 attention (`transformers.models.gpt2.modeling_gpt2`):

```python
class InquisitiveAttention(nn.Module):
    """Drop-in replacement for GPT2Attention with perceptiveness parameter."""

    def __init__(self, config, layer_idx=None):
        super().__init__()
        # ... standard GPT-2 attention init ...
        self.alpha = 0.0  # default: standard attention

    def _compute_surprise(self, key_states):
        """Compute per-position surprisingness from key vectors.

        Args:
            key_states: [batch, num_heads, seq_len, head_dim]

        Returns:
            surprise: [batch, num_heads, 1, seq_len] (broadcastable to attn scores)
        """
        # Causal running mean distance
        batch, heads, seq_len, dim = key_states.shape

        # Cumulative sum for running mean
        cumsum = torch.cumsum(key_states, dim=2)  # [B, H, S, D]
        counts = torch.arange(1, seq_len + 1, device=key_states.device)
        counts = counts.view(1, 1, -1, 1)  # broadcast shape

        # Running mean (shifted by 1 to be causal)
        running_mean = torch.zeros_like(key_states)
        running_mean[:, :, 1:, :] = cumsum[:, :, :-1, :] / counts[:, :, :-1, :]

        # Distance from running mean
        diff = key_states - running_mean
        surprise = torch.norm(diff, dim=-1)  # [B, H, S]

        # Normalize per-sequence
        surprise = (surprise - surprise.mean(dim=-1, keepdim=True)) / (
            surprise.std(dim=-1, keepdim=True) + 1e-8
        )

        return surprise.unsqueeze(2)  # [B, H, 1, S]

    def forward(self, hidden_states, attention_mask=None, **kwargs):
        # ... standard Q, K, V projection ...

        attn_weights = torch.matmul(query, key.transpose(-1, -2))
        attn_weights = attn_weights / math.sqrt(self.head_dim)

        # === INQUISITIVE MODIFICATION ===
        if self.alpha != 0.0:
            surprise = self._compute_surprise(key)
            attn_weights = attn_weights + self.alpha * surprise
        # === END MODIFICATION ===

        if attention_mask is not None:
            attn_weights = attn_weights + attention_mask

        attn_weights = nn.functional.softmax(attn_weights, dim=-1)
        attn_output = torch.matmul(attn_weights, value)

        return attn_output
```

### 2.2 Model Wrapper

```python
class InquisitiveGPT2(GPT2LMHeadModel):
    """GPT-2 with per-head or global perceptiveness control."""

    def set_alpha(self, alpha: float, heads: list[int] | None = None):
        """Set perceptiveness. If heads specified, only those heads."""
        for block in self.transformer.h:
            attn = block.attn
            if heads is None:
                attn.alpha = alpha
            else:
                attn.per_head_alpha[heads] = alpha
```

## 3. Experimental Design

### 3.1 Ablation Ladder

| Experiment | Config | Question |
|-----------|--------|----------|
| E1: Uniform | All heads same alpha | Does the effect exist at all? |
| E2: Split | Half heads alpha=+0.5, half alpha=-0.5 | Does head specialization help? |
| E3: Random | Random alpha per head | Is structure necessary or just diversity? |
| E4: Doubled | 2x heads, paired high/low | Does capacity matter? |

### 3.2 Alpha Sweep

For each experiment, sweep alpha over: {-1.0, -0.5, -0.25, 0.0, 0.25, 0.5, 1.0}

### 3.3 Benchmarks

#### Standard (sanity check -- should NOT degrade much)
- Perplexity on WikiText-103
- HellaSwag completion accuracy

#### Custom: Contextual Violation Detection (CVD) Benchmark

Design a benchmark where the correct answer requires noticing an anomalous detail:

**Category 1: Planted Incongruence**
- Passages with a factual error embedded in otherwise correct text
- "The anthropologist studying the tribe noticed they used iron tools, stone pottery, and digital watches"
- Q: "What was unusual about the tribe's tools?" -- requires *noticing* the anomaly

**Category 2: Disambiguation by Outlier**
- Winograd-style sentences where the answer depends on an unexpected word
- "The doctor prescribed rest, but the patient's *mechanic* disagreed"
- Q: "Why would this person's opinion matter?" -- requires noticing mechanic is unexpected

**Category 3: Needle in Context**
- Long documents with a single detail that contradicts the overall narrative
- Financial reports where one line item doesn't match the summary
- Q: "Is there anything inconsistent in this report?"

**Scoring**: For each item, measure P(correct_answer | alpha) across the alpha sweep.
The hypothesis is that higher alpha increases accuracy on these tasks.

### 3.4 Controls

- **Temperature sweep**: For each alpha config, also sweep temperature to confirm the axes
  are genuinely independent (temperature alone cannot achieve what alpha does)
- **Random baseline**: Random alpha assignments should perform worse than structured ones
  on the split experiment

## 4. Implementation Stack

| Component | Choice | Reason |
|-----------|--------|--------|
| Language | Python | Standard for ML research |
| Framework | PyTorch + HuggingFace Transformers | Full access to attention internals |
| Base model | GPT-2 (124M) | Small, fast iteration, well-understood |
| Testing | pytest | Per CLAUDE.md conventions |
| CI | GitHub Actions | Per CLAUDE.md conventions |
| Experiment tracking | Simple CSV/JSON + matplotlib | Keep it minimal |

## 5. File Structure (Planned)

```
inquisitive-transformer/
  planning/              # This directory -- plans and specs
  src/
    inquisitive_attention.py   # Core modified attention module
    inquisitive_gpt2.py        # Model wrapper
    surprise_functions.py      # S(Q,K) implementations
    benchmark/
      cvd_dataset.py           # Contextual Violation Detection benchmark
      evaluate.py              # Evaluation harness
  experiments/
    e1_uniform.py              # Experiment scripts
    e2_split.py
    e3_random.py
    e4_doubled.py
  tests/
    test_attention.py          # Unit tests for attention modification
    test_surprise.py           # Unit tests for S functions
  results/                     # Experiment outputs (gitignored except summaries)
  requirements.txt
  README.md
```

## 6. Dependencies

```
torch>=2.0
transformers>=4.35
datasets  # for WikiText-103
matplotlib  # for result visualization
pytest
```

## 7. Risk Assessment

| Risk | Mitigation |
|------|-----------|
| S(K) adds too much compute overhead | Profile early; running mean is O(n), should be negligible vs attention O(n^2) |
| Effect doesn't show on GPT-2 scale | GPT-2 is proof of concept; null result on small model is still informative |
| CVD benchmark is too easy/hard | Pilot test with standard GPT-2 first, calibrate difficulty |
| Alpha destabilizes softmax | Normalize surprise scores; test numerical stability at extreme alpha |
| Existing work closer than we think | Deep literature search before writing paper |
