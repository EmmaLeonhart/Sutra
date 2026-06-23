# In-process embeddings drop the Ollama-daemon cold-start (2026-06-22)

## Why

Usability assessment (queue was empty of usability work; the whole backlog is
correctness/substrate-purity). The single biggest barrier between "I heard about
Sutra" and "I ran a Sutra program" was the **runtime hard-dependency on the Ollama
daemon**: every emitted program did `import ollama; ollama.embed(...)` with no
fallback, so `pip install sutra-dev` could not run `hello_world.su` until the user
separately installed Ollama (hundreds of MB) and `ollama pull nomic-embed-text`.

Emma's call: `nomic-embed-text` is a *frozen* off-the-shelf model Sutra never
customizes, so there is no reason to require a separate server — load the same
model in-process and embed directly.

## What changed

- New host-side provider `sutra_compiler/embedding.py` with `embed_texts(names, model)`.
  Backend via `SUTRA_EMBED_BACKEND`: `auto` (default — in-process first, Ollama
  fallback), `transformers`/`hf`, or `ollama`. Embedding is a compile/IO-boundary
  concern (populates the codebook at module init, never the substrate hot path), so
  this is legitimately host code.
- Both codegens (`codegen_pytorch.py` canonical, `codegen.py` numpy/deprecated) now
  emit a call to the provider instead of inlining `import ollama`.
- On-disk embedding cache is now **backend-aware** (`{model}-d{dim}-{backend}.pt`):
  the two backends realize the same model with different geometry, so they must not
  share a cache file or one reads the other's vectors.
- `pyproject.toml`: new `embed` extra (`sentence-transformers`, `einops`).
- Test suite pinned to Ollama via `tests/conftest.py` (its tuned substrate).

## Measured

In-process `nomic-ai/nomic-embed-text-v1.5` (sentence-transformers, no task prefix)
is **NOT numerically identical** to Ollama's quantized-GGUF `nomic-embed-text`:

| comparison | mean cosine | min cosine |
|---|---|---|
| in-process vs Ollama, 10 words | **0.8788** | 0.3589 |

So they are two *substrates for the same model family*, not the same vectors. Per
Sutra's design (program structure is substrate-independent; coordinates are not),
that is acceptable — but it has consequences that were measured, not assumed:

- **Example smoke test PASSES end-to-end on the in-process substrate** with a fresh
  cache and no Ollama (`SUTRA_EMBED_BACKEND=transformers`): all gated demos OK
  (`fuzzy_branching` 16/16, `classifier` 9/9, `analogy` 5/5, `knowledge_graph` 5/5,
  `nearest_phrase` 25/25, `sequence` 11/11). `fuzzy_dispatch` 2/4 is the
  pre-existing documented soft case (gate is `>=2`), not a new regression.
- **One compiler test collides under the in-process substrate**:
  `test_axon_op_cache_under_cap_never_evicts` — a 10-key axon bind/unbind stress
  test where short word "go" sits near "telephone" in HF-nomic space, so the
  readback for "go" (len 2) bleeds to 9.0. The test comment already flags this exact
  crosstalk-collision risk. It passes 6/6 under Ollama. This is why the test suite is
  pinned to its tuned substrate (Ollama) rather than re-tuned wholesale to the
  in-process geometry.

## Decision

- **Default user experience (no env, fresh pip install): in-process, no daemon.**
- **Correctness-critical suites (compiler tests, paper reproduction): Ollama**, the
  substrate they were measured/tuned against — no regressions, no doctored numbers.

Re-tuning the whole suite to the in-process geometry is a separate, larger effort;
not bundled here.
