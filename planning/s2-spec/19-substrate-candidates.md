# Substrate Candidates for S2

## Key Requirement: Non-Normalized Embeddings

S2 requires embedding spaces where **magnitude is meaningful**. This means:
- Euclidean distance, not cosine similarity, is the primary metric
- Scalar multiplication must change magnitude (confidence/weight) without losing information
- Binding strength and bundling count are encoded in vector magnitude
- The truth-extraction matrix M(v) depends on magnitude information

Normalized embeddings (projected onto the unit sphere) destroy all of this. Cosine similarity = dot product on unit vectors = magnitude is always 1.0 = no information in magnitude. This makes normalized models **useless for S2**.

## Recommended Substrates

### Primary: GTE-large-en-v1.5
- **Dimensionality:** 1024
- **Normalization:** NOT normalized by default — normalization is an explicit optional step
- **Performance:** Strong MTEB scores
- **License:** Open source (Alibaba DAMO Academy)
- **Known pathologies:** None documented
- **Why:** Best drop-in option. High-dimensional, non-normalized out of the box, well-tested, no known defects.

### Research: Raw LLM Hidden States (Llama 3 / Mistral 7B)
- **Dimensionality:** 4096
- **Normalization:** NOT normalized — hidden states have variable magnitude by design
- **Access:** `output_hidden_states=True`, then `outputs.hidden_states[-1]` with mean pooling or last-token extraction
- **Why:** Richest substrate available. Recent research ("Disentangling Direction and Magnitude in Transformer Representations", arxiv 2602.11169) proves that direction and magnitude serve *different functional roles*:
  - **Direction** routes attention — angular perturbations damage language modeling loss 42.9x more than magnitude perturbations
  - **Magnitude** modulates processing intensity — magnitude perturbations damage syntactic processing (20.4% vs 1.6% accuracy drop on subject-verb agreement)
  - This dual-channel information is exactly what S2 needs
- **Tool:** LLM2Vec (McGill NLP) can transform decoder-only LLMs into text encoders. Tested on Llama and Mistral. Output is mean-pooled last hidden states, not normalized.
- **Cost:** More expensive to compute than dedicated embedding models, but the substrate is richer.

### Alternative: GTE-Qwen2-7B / Qwen3-Embedding-8B
- **Dimensionality:** Up to 4096
- **Normalization:** Applied in example code as explicit `F.normalize()` step — easily skipped
- **Why:** Decoder-based embedding model. Large dims. Bridge between dedicated embedding models and raw LLM hidden states.

### Alternative: INSTRUCTOR-XL / INSTRUCTOR-large
- **Dimensionality:** 768
- **Normalization:** Default output is NON-NORMALIZED — normalization is opt-in
- **Why:** Instruction-tunable. You can prefix queries with task descriptions, which could map to S2's context-dependent embedding resolution.

### Alternative: BGE-large-en-v1.5
- **Dimensionality:** 1024
- **Normalization:** Applied in the encode wrapper code, not baked into architecture. Skip `F.normalize` in raw transformers code.
- **Why:** Well-tested, good performance, easy to get non-normalized output.

### Alternative: Jina v3
- **Dimensionality:** 1024
- **Normalization:** Explicit code step, easily skipped
- **Why:** Supports Matryoshka dimensionality reduction (can use 32 to 1024 dims). Interesting for testing S2 at different substrate resolutions.

## Models to Avoid

### OpenAI text-embedding-3 (small/large)
- API always returns unit vectors. No access to pre-normalization output.
- Black box — can't inspect or modify the pipeline.
- **Useless for S2.**

### Cohere embed-v3
- API-only. No normalization control.
- **Useless for S2.**

### mxbai-embed-large
- Has the documented diacritic attention-sink bug (see [Embedding Pathologies](15-embedding-pathologies.md))
- Ollama returns normalized vectors
- Even without normalization, the pathology makes it unreliable
- **Avoid.**

### all-MiniLM-L6-v2
- Has a `2_Normalize` module baked into the sentence-transformers pipeline that runs inside `forward()`
- The `normalize_embeddings=False` parameter does NOT override this
- Workaround exists (reconstruct model without Normalize module) but it's a hack
- Only 384 dims — low capacity for S2
- **Avoid unless necessary.**

### nGPT (NVIDIA)
- Explicitly constrains everything to the unit hypersphere
- Gets 4-20x faster training by normalizing — shows the tradeoff between training efficiency and magnitude information
- Interesting as a counterpoint but **directly incompatible with S2's design**

## How to Get Non-Normalized Output

### For sentence-transformers models with baked-in normalization:
```python
from sentence_transformers import models, SentenceTransformer

transformer = models.Transformer('model-name')
pooling = models.Pooling(transformer.get_word_embedding_dimension(), pooling_mode='mean')
# Don't add the Normalize module
model = SentenceTransformer(modules=[transformer, pooling])
```

### For models that apply F.normalize() in example code:
Just skip that line. Use the raw output from the pooling step.

### For raw LLM hidden states:
```python
from transformers import AutoModel, AutoTokenizer

model = AutoModel.from_pretrained("meta-llama/Llama-3-8B")
tokenizer = AutoTokenizer.from_pretrained("meta-llama/Llama-3-8B")

inputs = tokenizer(text, return_tensors="pt")
outputs = model(**inputs, output_hidden_states=True)
hidden_states = outputs.hidden_states[-1]  # Last layer, non-normalized
embedding = hidden_states.mean(dim=1)       # Mean pooling
# Do NOT normalize — magnitude is meaningful
```

## Relevant Papers

1. **"Disentangling Direction and Magnitude in Transformer Representations"** (arxiv 2602.11169, 2026) — Direction and magnitude serve distinct computational roles. Validates S2's need for non-normalized substrates.

2. **"Weber's Law in Transformer Magnitude Representations"** (arxiv 2603.20642) — How transformers encode numerical magnitude, connecting to psychophysical laws.

3. **"Anisotropy Is Inherent to Self-Attention in Transformers"** (arxiv 2401.12143) — Transformer embeddings naturally occupy a narrow cone. Relevant for understanding S2's substrate geometry.

4. **LLM2Vec** (arxiv 2404.05961) — Method for turning decoder LLMs into text encoders preserving hidden state properties including magnitude.

5. **nGPT** (arxiv 2410.01131) — NVIDIA's normalized transformer. Counterpoint showing the training efficiency vs. magnitude information tradeoff.

## Empirical Initiation Implications

The choice of substrate affects empirical initiation:
- **Non-normalized models:** Euclidean distance is the primary metric. Binding noise measured in Euclidean distance. Bundling capacity measured by SNR in magnitude space.
- **Raw LLM hidden states:** Higher dimensionality (4096 vs 1024) means more capacity for superposition, but the space may be more anisotropic (narrow cone distribution) requiring larger correction matrices during empirical initiation.
- **Validation gates** must include magnitude distribution checks — if a substrate's magnitude distribution is degenerate (all vectors have nearly identical magnitude), it may pass normalization-free checks but still be effectively normalized.
