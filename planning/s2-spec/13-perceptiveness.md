# The Inquisitiveness/Perceptiveness Parameter

## The Concept

A novel attention mechanism variant discovered during S2 design conversations. Standard scaled dot-product attention is:

```
Attention(Q, K, V) = softmax(QK^T / sqrt(d)) V
```

The inquisitiveness/perceptiveness variant adds a second term:

```
Attention(Q, K, V, a) = softmax(QK^T / sqrt(d) + a * S(Q, K)) V
```

Where:
- `S(Q, K)` is a **surprisingness function** — how unexpected each key is relative to the query context
- `a in [-1, 1]` is the **perceptiveness parameter** — controls sensitivity to surprising/outlier keys

## What a Does

- **a > 0 (inquisitive):** Amplifies attention to surprising, unexpected keys. The model actively seeks out outliers and novel information. Useful for exploration, creative reasoning, anomaly detection.
- **a = 0 (neutral):** Standard attention. No surprisingness bias.
- **a < 0 (conservative):** Suppresses attention to surprising keys. The model ignores outliers and sticks to expected, familiar patterns. Useful for stable, predictable execution.

## Orthogonality to Temperature

This is **not** the same as temperature scaling. Temperature scales the entire attention distribution uniformly — high temperature makes everything more uniform, low temperature makes everything more peaked. Perceptiveness **selectively** amplifies or suppresses the tail of unexpected keys without affecting the core distribution.

This creates a **2D behavioral space** (temperature x perceptiveness) with four distinct regimes:

| | Low Temperature | High Temperature |
|---|---|---|
| **High a (inquisitive)** | Sharply focused on the most surprising key | Diffuse attention but biased toward novelty |
| **Low a (conservative)** | Sharply focused on the most expected key | Diffuse attention biased toward familiarity |

Each extreme has characteristic failure modes:
- High temp + high a: distracted, chasing every novelty
- High temp + low a: blandly averaging everything familiar
- Low temp + high a: fixated on a single outlier (potentially hallucinating)
- Low temp + low a: stuck in a rut, ignoring all new information

## Geometric Surprisingness

The surprisingness function can be computed cheaply and geometrically:

```
S(K)_i = ||K_i - mean(K_1, ..., K_{i-1})||
```

The distance of each key from the running mean of all previous keys. This is:
- **Cheap:** One subtraction and one norm per key, computed causally
- **No extra parameters:** Uses only the existing key vectors
- **Geometrically meaningful:** Surprisingness is literally "how far is this from what I've seen before?" in embedding space
- **Causal:** Only looks at preceding keys (compatible with autoregressive models)

## Relevance to S2

The perceptiveness parameter is a concrete example of the kind of **tunable fuzzy control knob** that S2 should support as a first-class construct. In S2 terms:

- It's a parameterized transformation over attention distributions
- The parameter controls a continuous behavioral spectrum (not a binary switch)
- The underlying computation is geometric (distance from running mean)
- It's composable — you could have different a values for different layers, attention heads, or even different parts of a single computation

This is also a proof-of-concept that novel computation can be designed by **thinking geometrically about what attention means** rather than just optimizing benchmarks. S2's design philosophy encourages this kind of geometric reasoning about operations.

**Proposed as inference-time only** — no retraining needed. You can adjust a at runtime to change the model's reasoning strategy, which maps to S2's philosophy that runtime behavior should be tunable without recompilation.
