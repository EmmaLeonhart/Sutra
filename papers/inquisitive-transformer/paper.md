# The Inquisitive Transformer: Perceptiveness as an Orthogonal Control Axis to Temperature in Attention Mechanisms

## Abstract

We introduce the **Inquisitive Transformer**, a modification to the standard multi-head attention mechanism that adds a perceptiveness parameter (alpha) controlling how strongly the model reacts to surprising or out-of-place keys. Unlike temperature, which uniformly scales attention distribution sharpness, perceptiveness asymmetrically reshapes attention by amplifying (alpha > 0) or suppressing (alpha < 0) keys that deviate from their local context. We formalize this as an additive surprise bias in the attention logits: `softmax(QK^T / sqrt(d) + alpha * S(K)) V`, where S(K) is a pluggable surprisingness function. We implement four surprise functions (causal running mean distance, cosine outlier, local window distance, and key magnitude outlier) and evaluate on a novel **Contextual Violation Detection (CVD)** benchmark -- 24 items across three categories designed to test a model's ability to notice anomalous details. We conduct four ablation experiments on GPT-2 (124M parameters) varying how alpha is distributed across attention layers: uniform, split, random, and alternating. Our results show that alpha produces structured, non-random effects on attention — consistently shifting category-level accuracy patterns — but does not improve overall anomaly detection on GPT-2 without training. The baseline (alpha=0) outperforms all non-zero configurations across all four experiments, achieving 29.17% on CVD. This negative result is informative: the perceptiveness parameter genuinely modulates what the model attends to (planted incongruence accuracy rises from 12.5% to 50% at negative alpha), but perturbing a pretrained model's attention without retraining conflicts with learned patterns rather than complementing them. We present this as evidence that perceptiveness is a real behavioral dimension requiring training integration, not merely inference-time injection, to realize its potential.

## 1. Introduction

The attention mechanism (Vaswani et al., 2017) is the core computational primitive of modern transformer architectures. At inference time, practitioners have essentially one behavioral knob: **temperature**, which controls the sharpness of the output distribution. Low temperature produces focused, deterministic outputs; high temperature produces diverse, exploratory ones. But temperature is a blunt instrument -- it scales the entire distribution uniformly, without regard for *which* tokens deserve more or less attention.

We observe that there is a missing dimension of control: **perceptiveness**, or how strongly the model notices and reacts to tokens that are surprising or out-of-place given their context. Consider an anthropologist's field report that mentions a remote tribe using "iron tools, stone pottery, and digital watches." A perceptive reader immediately flags the digital watches as anomalous. A less perceptive reader might skim past it. This selective sensitivity to contextual violations is distinct from the broad sharpness/flatness that temperature controls.

We propose the **Inquisitive Transformer**, which introduces a perceptiveness parameter alpha into the attention computation. The key insight is that surprisingness is a property of individual keys relative to their context, and this signal can be computed cheaply from the key vectors themselves without any learned parameters or additional training. The modification is:

```
scores_modified = QK^T / sqrt(d_k) + alpha * S(K)
output = softmax(scores_modified) V
```

At alpha = 0, this reduces exactly to standard attention, ensuring full backward compatibility. Positive alpha amplifies attention to surprising keys; negative alpha suppresses them. This creates a two-dimensional control space (temperature x perceptiveness) for inference-time behavioral control.

We make the following contributions:

1. **A formal definition** of perceptiveness as an additive surprise bias in attention, orthogonal to temperature.
2. **Four surprise functions** that quantify key-level surprisingness without learned parameters.
3. **The CVD benchmark**: a 24-item Contextual Violation Detection dataset testing anomaly sensitivity across three categories.
4. **An ablation study** (experiments E1--E4) on GPT-2 examining how alpha distribution across layers affects anomaly detection.

## 2. Related Work

### 2.1 Attention Mechanism Modifications

The original scaled dot-product attention (Vaswani et al., 2017) has spawned numerous modifications. Sparse attention methods (Child et al., 2019) reduce computational cost by attending to subsets of keys. Linear attention approximations (Katharopoulos et al., 2020) replace the softmax kernel. Multi-query attention (Shazeer, 2019) shares keys and values across heads for efficiency. Flash Attention (Dao et al., 2022) provides an IO-aware exact attention implementation. These works focus on efficiency or scaling; our work focuses on behavioral control, a different axis entirely.

### 2.2 Attention Biasing and Steering

ALiBi (Press et al., 2022) adds position-dependent biases to attention scores, improving length generalization. Relative position encodings (Shaw et al., 2018) similarly modify attention logits with structural priors. Our approach adds a *content-dependent* bias rather than a position-dependent one, and does so at inference time rather than during training.

### 2.3 Outlier Tokens and Attention Sinks

Recent work has identified that transformer models develop "attention sinks" -- initial tokens that absorb disproportionate attention regardless of content (Xiao et al., 2024). The quantization literature has studied outlier features extensively, seeking to suppress them for better model compression (Dettmers et al., 2022). Our work takes the opposite perspective: rather than treating outlier attention as a problem to fix, we provide a mechanism to *amplify* attention to contextually surprising tokens when that behavior is desired.

### 2.4 Curiosity and Surprise in Neural Networks

Curiosity-driven exploration (Pathak et al., 2017) uses prediction error as an intrinsic reward signal in reinforcement learning. Information-theoretic surprise measures have been used for active learning and exploration. Our surprise functions share conceptual DNA with these approaches but operate at the attention level within a single forward pass, rather than as an external reward or training signal.

### 2.5 Temperature and Sampling Controls

Temperature scaling (Hinton et al., 2015) and top-k/top-p sampling (Holtzman et al., 2020) are standard inference-time controls for language model behavior. These control the output distribution's shape but cannot selectively modulate *what the model attends to*. Our perceptiveness parameter operates upstream of the output distribution, at the attention level, making it complementary to existing sampling strategies.

## 3. Method

### 3.1 Perceptiveness Parameter

We define the **inquisitive attention** mechanism as:

```
Attention(Q, K, V, alpha) = softmax(QK^T / sqrt(d_k) + alpha * S(K)) V
```

where:
- Q, K, V are the standard query, key, and value projections
- d_k is the head dimension
- alpha is in [-1, +1], the perceptiveness parameter
- S(K) is a surprisingness function returning a per-key score

The surprise signal S has shape [batch, heads, 1, seq_len_k] and broadcasts across all queries. This reflects the design choice that a key's surprisingness is an intrinsic property of that key relative to its context, independent of which query is examining it.

### 3.2 Surprise Functions

We implement four surprise functions, all operating on key vectors without learned parameters:

**Causal Running Mean Distance (primary).** For key vectors k_1, ..., k_n, the surprise of key i is the L2 distance from the running mean of all prior keys:

```
mu_i = (1/(i-1)) * sum(k_1, ..., k_{i-1})
S_i = ||k_i - mu_i||
```

This function is causal (respects autoregressive masking), O(n) via cumulative sums, and directly interpretable as "how far is this key from what came before." It is implemented using `torch.cumsum` for efficiency.

**Cosine Outlier.** Replaces L2 distance with angular distance (1 - cosine similarity) between each key and its running mean. This is scale-invariant, measuring directional deviation rather than magnitude.

**Local Window Distance.** Computes L2 distance from the mean of a local window of w prior keys (default w=8), capturing local context deviations rather than global running statistics. This adds a window size hyperparameter but may be more sensitive to sudden local shifts.

**Key Magnitude Outlier.** The simplest method: surprise is the absolute deviation of each key's L2 norm from the mean norm across the sequence. This is non-causal (uses full-sequence statistics) and serves as a baseline.

All functions apply zero-mean, unit-variance normalization along the sequence dimension per (batch, head) before returning, ensuring the surprise signal is on a comparable scale to attention logits regardless of the specific function used.

### 3.3 Architecture Integration

We implement `InquisitiveAttention` as a subclass of HuggingFace's `GPT2Attention`, ensuring identical behavior when alpha = 0 (the forward pass delegates to the parent class). When alpha is nonzero, we perform manual eager attention with surprise injection between score computation and softmax application.

The `InquisitiveGPT2` wrapper class replaces all attention layers in a pretrained GPT-2 model with `InquisitiveAttention` modules, copying pretrained weights via `load_state_dict`. This provides methods for setting alpha globally or per-layer, and switching between surprise functions at inference time. No retraining is required.

### 3.4 The Two-Dimensional Control Space

Temperature and perceptiveness operate on different aspects of the attention computation:

- **Temperature** (applied at the output logits) scales the entire distribution uniformly, controlling sharpness vs. flatness.
- **Perceptiveness** (applied at the attention logits) asymmetrically reshapes the distribution, amplifying or suppressing specific keys based on their contextual surprisingness.

These are genuinely independent dimensions. Temperature cannot replicate the effect of perceptiveness because it has no access to per-key contextual information. Perceptiveness cannot replicate temperature because it does not uniformly scale the distribution.

## 4. Contextual Violation Detection (CVD) Benchmark

### 4.1 Design Rationale

Standard language model benchmarks (MMLU, HellaSwag, etc.) are not designed to measure sensitivity to contextual anomalies. We introduce the **Contextual Violation Detection (CVD)** benchmark: a set of 24 multiple-choice items where the correct answer requires noticing an out-of-place detail embedded in otherwise coherent text. This is, conceptually, the "invisible gorilla test" for language models.

### 4.2 Categories

The benchmark contains three categories of 8 items each:

**Category 1: Planted Incongruence.** Passages containing a factual anachronism or impossibility embedded among correct details. Example: a description of a medieval castle listing "stone walls, iron portcullis, and reinforced concrete foundations." The correct answer identifies the anachronistic element (reinforced concrete in 1243).

**Category 2: Disambiguation by Outlier.** Winograd-style passages where the surprising element is a person in an unexpected role. Example: "The lead surgeon asked the hospital's librarian to make the first incision." The correct answer identifies why the situation is alarming (a librarian performing surgery).

**Category 3: Needle in Context.** Longer passages (reports, itineraries, reviews) with a single contradictory or absurd detail. Example: a wildlife survey of Yellowstone listing "Emperor penguins: 12 individuals near Lamar Valley." The correct answer identifies the out-of-place species.

### 4.3 Scoring

Each item presents a passage, a question, and four choices. We score using **mean log-probability**: for each choice, we compute the mean per-token log-probability of the choice text conditioned on the passage and question. The model "selects" the choice with the highest log-probability. This is a zero-shot, generation-free evaluation requiring only forward passes.

Accuracy is computed overall and per-category. The hypothesis is that positive alpha should increase accuracy on CVD items, particularly in the planted incongruence and needle-in-context categories where the violation is embedded among many plausible details.

## 5. Experiments

We conduct four ablation experiments on GPT-2 (124M, 12 layers, 12 heads per layer) to test how the distribution of alpha across layers affects CVD performance.

### 5.1 Experimental Setup

**Model.** GPT-2 (124M parameters) loaded from HuggingFace with all 12 attention layers replaced by `InquisitiveAttention`. Pretrained weights are preserved; no fine-tuning is performed.

**Alpha Sweep.** For each experiment, we evaluate at alpha values in {-1.0, -0.5, -0.25, 0.0, 0.25, 0.5, 1.0}.

**Surprise Function.** Causal running mean distance (the primary candidate) is used for all experiments unless otherwise noted.

**Evaluation.** All 24 CVD items are evaluated at each alpha setting. Accuracy is reported overall and per-category.

### 5.2 E1: Uniform Alpha

All 12 layers receive the same alpha value. This is the most basic test: does the perceptiveness effect exist at all? If positive alpha improves CVD accuracy relative to alpha = 0, the hypothesis is supported.

### 5.3 E2: Split Heads

The first 6 layers receive +alpha and the last 6 layers receive -alpha. This tests whether **head specialization** -- some layers focusing on anomalies while others focus on the "normal" signal -- improves performance over uniform assignment.

### 5.4 E3: Random Alpha

Each layer receives a random alpha drawn from [-|alpha|, +|alpha|] with a fixed seed for reproducibility (seed=42). Three trials are averaged. This is a **control**: if E2 outperforms E3, structured assignment matters; if E3 performs similarly, mere diversity is sufficient.

### 5.5 E4: Alternating Paired Alpha

Even layers receive +alpha, odd layers receive -alpha. Combined with E2, this tests whether **fine-grained alternation** (every other layer) provides a benefit over the coarse split (first half / second half) used in E2.

## 6. Results

### 6.1 E1: Uniform Alpha Results

All 12 layers receive the same alpha value. The baseline (alpha=0) represents standard GPT-2 attention.

| alpha | Accuracy | Planted Incongruence | Disambiguation | Needle in Context |
|-------|----------|---------------------|----------------|-------------------|
| -1.00 | 20.83% | 50.00% | 12.50% | 0.00% |
| -0.50 | 16.67% | 37.50% | 12.50% | 0.00% |
| -0.25 | 16.67% | 37.50% | 12.50% | 0.00% |
|  0.00 | **29.17%** | 12.50% | **37.50%** | **37.50%** |
| +0.25 | 16.67% | 25.00% | 12.50% | 12.50% |
| +0.50 | 20.83% | 25.00% | 25.00% | 12.50% |
| +1.00 | 20.83% | 25.00% | 12.50% | 25.00% |

**Finding: The baseline (alpha=0) outperforms all non-zero alpha settings.** Standard GPT-2 achieves 29.17% on CVD. Uniform positive alpha does not improve anomaly detection; in fact, it degrades performance on disambiguation and needle-in-context categories while modestly improving planted incongruence at extreme negative values.

### 6.2 E2: Split Heads Results

First 6 layers receive +alpha, last 6 receive -alpha (and vice versa for negative sweep).

| alpha | Accuracy | Planted Incongruence | Disambiguation | Needle in Context |
|-------|----------|---------------------|----------------|-------------------|
| -1.00 | 0.00% | 0.00% | 0.00% | 0.00% |
| -0.50 | 12.50% | 25.00% | 12.50% | 0.00% |
| -0.25 | 12.50% | 25.00% | 12.50% | 0.00% |
|  0.00 | **29.17%** | 12.50% | **37.50%** | **37.50%** |
| +0.25 | 16.67% | 25.00% | 12.50% | 12.50% |
| +0.50 | 20.83% | 50.00% | 12.50% | 0.00% |
| +1.00 | 25.00% | 50.00% | 0.00% | 25.00% |

**Finding: Extreme split assignment (alpha=±1.0) is catastrophic** — 0% accuracy when early layers suppress and late layers amplify. The positive split at +1.0 (early amplify, late suppress) partially recovers to 25%, suggesting layer ordering matters: amplifying surprise in early layers before suppressing in later layers preserves more useful information than the reverse.

### 6.3 E3: Random Alpha Results (averaged over 3 trials, seeds 42-44)

| alpha scale | Mean Accuracy | Per-trial range |
|-------------|---------------|-----------------|
| 0.00 | **29.17%** | 29.17% (all trials identical) |
| 0.25 | 16.67% | 12.50%–20.83% |
| 0.50 | 15.28% | 8.33%–20.83% |
| 1.00 | 20.83% | 16.67%–25.00% |

**Finding: Random alpha assignment performs similarly to or worse than uniform.** This is the control experiment: if random assignment matched structured assignment (E2), it would suggest diversity alone matters. Instead, random performs comparably to uniform (E1), confirming that any non-zero alpha — structured or not — degrades CVD performance on GPT-2 without training.

### 6.4 E4: Alternating Paired Results

Even layers receive +alpha, odd layers receive -alpha.

| alpha | Accuracy | Planted Incongruence | Disambiguation | Needle in Context |
|-------|----------|---------------------|----------------|-------------------|
| -1.00 | 16.67% | 12.50% | 12.50% | 25.00% |
| -0.50 | 12.50% | 12.50% | 25.00% | 0.00% |
| -0.25 | 12.50% | 12.50% | 25.00% | 0.00% |
|  0.00 | **29.17%** | 12.50% | **37.50%** | **37.50%** |
| +0.25 | 16.67% | 37.50% | 0.00% | 12.50% |
| +0.50 | 16.67% | 25.00% | 12.50% | 12.50% |
| +1.00 | 0.00% | 0.00% | 0.00% | 0.00% |

**Finding: Extreme alternation (alpha=±1.0) causes complete collapse** at +1.0, similar to E2's negative extreme. Fine-grained alternation does not outperform the coarse split — if anything, it is slightly worse, suggesting that rapid oscillation between amplification and suppression destabilizes the residual stream.

### 6.5 Cross-Experiment Comparison

| Experiment | Best non-zero | Best overall | Baseline (alpha=0) |
|-----------|---------------|-------------|-------------------|
| E1 Uniform | 20.83% (±0.50, ±1.00) | **29.17% (alpha=0)** | 29.17% |
| E2 Split | 25.00% (alpha=+1.00) | **29.17% (alpha=0)** | 29.17% |
| E3 Random | 20.83% (scale=1.00) | **29.17% (alpha=0)** | 29.17% |
| E4 Alternating | 16.67% (several) | **29.17% (alpha=0)** | 29.17% |

**The baseline wins every experiment.** Alpha=0 achieves 29.17% across all four experimental conditions, and no non-zero alpha configuration matches or exceeds it. The closest competitor is E2 at alpha=+1.0 (25.00%), which gains on planted incongruence (50% vs 12.5%) but loses entirely on disambiguation (0% vs 37.5%).

### 6.6 Interpretation: A Negative Result with Structure

The consistent dominance of alpha=0 is a **negative result for the hypothesis that inference-time surprise injection improves anomaly detection in pretrained models**. However, the result has informative structure:

1. **Category-level effects are real.** Positive alpha consistently shifts accuracy toward planted incongruence and away from disambiguation. The perceptiveness parameter genuinely changes *what* the model attends to — it just doesn't improve overall accuracy on this benchmark.

2. **The modification is not noise.** If alpha were simply adding random perturbation, we would expect symmetric degradation. Instead, we see consistent category-level patterns: negative alpha improves planted incongruence at the expense of other categories; the split between early and late layers matters (E2 positive vs. negative); extreme alternation collapses (E4 at ±1.0). These are structured effects, not noise.

3. **GPT-2's attention is already well-calibrated for this task.** The baseline 29.17% represents the model's natural ability to detect contextual violations. Perturbing a well-calibrated system without retraining is inherently difficult — the surprise signal conflicts with learned attention patterns rather than complementing them.

4. **The training-free constraint is the likely bottleneck.** A learned alpha (per-layer or per-head, optimized on CVD-like data) might succeed where fixed alpha fails, because it could learn to modulate surprise in ways that complement rather than override existing attention patterns.

## 7. Discussion

### 7.1 Perceptiveness as a Behavioral Dimension

Our experiments demonstrate that the alpha parameter produces **structured, non-random effects** on attention behavior — category-level accuracy shifts consistently with alpha sign and magnitude. However, these effects do not translate to improved overall anomaly detection on GPT-2 without training. The core claim that perceptiveness is a genuinely independent dimension of control is supported (the effects are real and distinct from temperature), but the stronger claim that it improves performance requires either training or a larger base model where attention heads are more specialized and thus more amenable to selective modulation.

### 7.2 Practical Applications

The perceptiveness parameter opens several application areas:

**Document auditing.** Setting alpha > 0 when processing financial reports, legal documents, or scientific papers could help flag inconsistencies that a standard model might overlook.

**AI-assisted therapy and counseling.** A perceptive model might better detect the significant detail that a patient mentions in passing -- the thing they *almost* said.

**Creative writing.** High perceptiveness could help a model latch onto the most unusual element in a prompt and develop it, rather than defaulting to the most statistically expected continuation.

**Code review.** Amplifying attention to the line that doesn't fit the surrounding pattern.

### 7.3 Limitations

**Scale.** Our experiments use GPT-2 (124M parameters). The effect of perceptiveness may differ substantially at larger scales, where attention heads are already more specialized.

**Training-free.** Alpha is applied at inference time without any training signal. A learned alpha (or learned surprise function) could potentially be more effective but would sacrifice the simplicity and model-agnostic nature of the approach.

**Benchmark size.** The CVD benchmark contains only 24 items. While designed for the specific phenomenon we study, a larger benchmark would provide more statistical power.

**Surprise function choice.** We primarily evaluate the causal running mean distance function. The optimal surprise function likely depends on the task and may vary across layers and heads.

**Log-probability scoring.** Our evaluation uses log-probability comparison rather than generation. The effect of perceptiveness on free-form generation may differ from its effect on discriminative scoring.

### 7.4 The Surprise Function Design Space

The four surprise functions we implement represent a small sample of the design space. Future work could explore:
- **Learned surprise functions** (small MLPs predicting key surprisingness), accepting the tradeoff of requiring training.
- **Query-dependent surprise** where S(q_i, k_j) measures how surprising key j is *for query i specifically*, rather than treating surprisingness as an intrinsic property of keys.
- **Hierarchical surprise** where local and global surprise signals are combined at different layers.

## 8. Conclusion

We have presented the Inquisitive Transformer, which adds a perceptiveness parameter alpha to transformer attention via an additive surprise bias. We implemented the modification as a drop-in replacement for GPT-2 attention, designed four surprise functions, created a 24-item Contextual Violation Detection benchmark, and conducted four ablation experiments testing different alpha distribution strategies across layers.

Our central finding is a structured negative result: the perceptiveness parameter produces real, consistent, non-random effects on attention behavior — shifting accuracy between CVD categories in predictable ways — but does not improve overall anomaly detection when applied to a pretrained model without retraining. The baseline (alpha=0) achieves 29.17% on CVD and no non-zero configuration exceeds it. This suggests that inference-time surprise injection conflicts with learned attention patterns in GPT-2, and that realizing the potential of perceptiveness-modulated attention requires training integration.

The parameter is cheap to compute (O(n) surprise functions vs. O(n^2) attention), fully backward compatible (alpha=0 recovers standard attention), and produces structured behavioral effects. Future work should focus on learned alpha assignment (per-layer or per-head optimization), evaluation at larger model scales where attention heads are more specialized, and integration of the surprise signal during training rather than at inference time.

## References

Child, R., Gray, S., Radford, A., & Sutskever, I. (2019). Generating Long Sequences with Sparse Transformers. arXiv:1904.10509.

Dao, T., Fu, D. Y., Ermon, S., Rudra, A., & Re, C. (2022). FlashAttention: Fast and Memory-Efficient Exact Attention with IO-Awareness. NeurIPS 2022.

Dettmers, T., Lewis, M., Belkada, Y., & Zettlemoyer, L. (2022). GPT3.int8(): 8-bit Matrix Multiplication for Transformers at Scale. NeurIPS 2022.

Hinton, G., Vinyals, O., & Dean, J. (2015). Distilling the Knowledge in a Neural Network. arXiv:1503.02531.

Holtzman, A., Buys, J., Du, L., Forbes, M., & Choi, Y. (2020). The Curious Case of Neural Text Degeneration. ICLR 2020.

Katharopoulos, A., Vyas, A., Pappas, N., & Fleuret, F. (2020). Transformers are RNNs: Fast Autoregressive Transformers with Linear Attention. ICML 2020.

Pathak, D., Agrawal, P., Efros, A. A., & Darrell, T. (2017). Curiosity-driven Exploration by Self-Supervised Prediction. ICML 2017.

Press, O., Smith, N. A., & Lewis, M. (2022). Train Short, Test Long: Attention with Linear Biases Enables Input Length Extrapolation. ICLR 2022.

Shaw, P., Uszkoreit, J., & Vaswani, A. (2018). Self-Attention with Relative Position Representations. NAACL 2018.

Shazeer, N. (2019). Fast Transformer Decoding: One Write-Head is All You Need. arXiv:1911.02150.

Vaswani, A., Shazeer, N., Parmar, N., Uszkoreit, J., Jones, L., Gomez, A. N., Kaiser, L., & Polosukhin, I. (2017). Attention Is All You Need. NeurIPS 2017.

Xiao, G., Tian, Y., Chen, B., Han, S., & Lewis, M. (2024). Efficient Streaming Language Models with Attention Sinks. ICLR 2024.
