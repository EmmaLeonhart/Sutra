# Inquisitive Transformer - Project Plan

## Vision

The **Inquisitive Transformer** introduces a novel attention mechanism modification: a
**perceptiveness parameter** (alpha) that controls how strongly a transformer model reacts to
unexpected or out-of-place tokens in context. This is an independent, orthogonal axis to
temperature -- temperature controls distribution sharpness uniformly, while perceptiveness
controls *which part* of the distribution gets amplified (specifically the tail of surprising keys).

### The 2D Control Space

```
            High Perceptiveness (alpha = +1)
            Notices anomalies, interrogates oddities
                        |
                        |
Low Temp ---------------+--------------- High Temp
(sharp, focused)        |        (flat, exploratory)
                        |
            Low Perceptiveness (alpha = -1)
            Smooths over anomalies, answers the "average" question
```

- **Temperature** = sharpness of the whole attention distribution
- **Perceptiveness** = asymmetric reshaping -- amplifies or suppresses surprising keys

These are genuinely independent dimensions. You cannot achieve perceptiveness effects by tuning
temperature alone.

## Core Formula

Standard attention:
```
Attention(Q, K, V) = softmax(QK^T / sqrt(d)) V
```

Inquisitive attention:
```
Attention(Q, K, V, alpha) = softmax(QK^T / sqrt(d) + alpha * S(Q, K)) V
```

Where:
- `alpha` in [-1, +1] is the perceptiveness parameter
- `S(Q, K)` is a surprisingness function measuring how out-of-place each key is
- When alpha = 0, you get standard attention (backward compatible)

## Why This Matters

### Practical Applications
1. **AI Therapy / Counseling** -- High perceptiveness catches the thing the patient *almost* said
2. **AI Career Coaching** -- Notices the unusual detail in someone's background that's actually their strength
3. **Document Analysis** -- Catches the incongruent detail in a long document (the anthropologist example)
4. **Code Review** -- Flags the line that doesn't fit the pattern
5. **Creative Writing** -- High perceptiveness latches onto the weirdest thing in a prompt and runs with it

### Why It Hasn't Been Done
- Most attention research is driven by capability scaling or efficiency, not behavioral control
- Outlier token research exists but focuses on *suppressing* outliers for quantization, not *amplifying* them
- Nobody's been asking "how do we give users a knob to tune what the model notices"
- The framing as an explicit orthogonal control axis to temperature is novel

## Novelty Assessment

- **Adjacent prior work**: sparse attention, entropy-regularized attention, attention biasing
- **Key differentiator**: This is a *behavioral control*, not an efficiency trick
- **The 2D framing** (temperature x perceptiveness) as explicit, orthogonal inference-time controls has not been cleanly proposed and tested
- **Publishable** if experiments bear out the hypothesis

## Collaborator

- **ash_blanc** (Discord username) -- collaborator who is helping with implementation and has
  discussed the project extensively. Working on their own coding agent project ("Cooper") and
  has interest in research grants (Lambda, etc.) to fund compute.

## Key Decisions Made

1. **Target model**: GPT-2 (small, well-understood, HuggingFace has full implementation)
2. **Implementation**: Modify HuggingFace attention class directly (not Ollama, not prompt engineering)
3. **Inference-time knob**: alpha is set at inference, not trained (keeps it clean and model-agnostic)
4. **Python + HuggingFace Transformers**: the standard research stack

## Open Questions

1. **S(Q,K) function** -- What's the best surprisingness measure?
   - Running mean distance: `S_i = ||k_i - mean(k_1..k_{i-1})||` (cheap, causal, no extra params)
   - Key magnitude outliers: `S_i = ||k_i - mean(K)|| / std(K)` (no circularity)
   - Attention-based: low average attention across queries (chicken-and-egg problem)
   - Learned small network (more powerful but requires training, breaks inference-only goal)

2. **Per-head behavior** -- Should alpha be uniform across heads or per-head?

3. **Benchmark** -- Standard benchmarks (MMLU, HellaSwag) won't capture this. Need a custom
   benchmark based on "contextual violation detection" (invisible gorilla for text).

## Timeline / Phases

### Phase 1: Foundation (Current)
- [x] Concept and formula definition
- [x] Literature review / novelty check
- [ ] Repository setup with proper structure
- [ ] Implement basic GPT-2 with modified attention

### Phase 2: Core Experiments
- [ ] Experiment 1: Uniform alpha across all heads (validate the effect exists)
- [ ] Experiment 2: Half heads low alpha, half high alpha (does specialization help?)
- [ ] Experiment 3: Random alpha per head (control -- is structure necessary?)
- [ ] Experiment 4: 2x heads with low/high split (does capacity matter?)

### Phase 3: Evaluation
- [ ] Design contextual violation benchmark ("invisible gorilla for text")
  - Passages with planted incongruent details
  - Winograd-style items requiring disambiguation
  - Needle-in-a-haystack with contextual violations
- [ ] Evaluate across the ablation ladder
- [ ] Compare against temperature-only baselines

### Phase 4: Write-up
- [ ] Paper outline
- [ ] Figures (2D control space, attention heatmaps, benchmark results)
- [ ] Submit to arXiv / workshop
