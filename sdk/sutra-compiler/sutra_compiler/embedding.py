"""Host-side embedding provider — the frozen-LLM `embed()` boundary.

Sutra values live in a frozen LLM embedding space. Resolving a string to its
embedding is a **compile/IO-boundary** concern: it runs once at module init to
populate the runtime's `_codebook`, never on the substrate hot path. So this is
legitimately host code (numpy/torch tensor construction from a model's output),
not a substrate operation.

Why this module exists: until 2026-06-22 the only way to fetch an embedding was
the **Ollama daemon** — every emitted program did `import ollama; ollama.embed(...)`
with no fallback, so `pip install sutra-dev` could not run a single program until
the user also installed Ollama and pulled a model. nomic-embed-text is a *frozen*
off-the-shelf model that Sutra never customizes, so there is no reason to require
a separate server: we load the same model **in-process** (sentence-transformers /
HuggingFace) and embed directly. Ollama stays available as a backend for users who
already run it or who want its exact GGUF realization.

Backend selection (env var `SUTRA_EMBED_BACKEND`):
  - "auto" (default) — try in-process transformers first; fall back to Ollama.
  - "transformers" / "hf" — in-process only (raise if unavailable).
  - "ollama" — Ollama daemon only (the pre-2026-06-22 behavior).

The two realizations are NOT numerically identical (Ollama runs a quantized GGUF;
mean cosine vs the in-process model ~0.88). They are two substrates for the same
model family. Per Sutra's design (a program's structure is substrate-independent;
the coordinates are not), a program should use ONE backend consistently — which is
what the per-process model cache below enforces.

`embed_texts` returns the **raw** model vectors. The codegen's `embed()` does the
Sutra post-processing (mean-center, L2-normalize, fit to the semantic block,
append the zero synthetic block) identically regardless of backend.
"""
from __future__ import annotations

import os
from typing import List

# Short Sutra/Ollama model name -> HuggingFace repo id for the in-process load.
# These are the same frozen models, just loaded directly instead of via Ollama.
_HF_MODEL_IDS = {
    "nomic-embed-text": "nomic-ai/nomic-embed-text-v1.5",
    "all-minilm": "sentence-transformers/all-MiniLM-L6-v2",
    "mxbai-embed-large": "mixedbread-ai/mxbai-embed-large-v1",
}

# Per-process cache of loaded SentenceTransformer instances, keyed by HF id.
# Loading a model is seconds + hundreds of MB; reuse it across every program
# compiled in the same process (e.g. the smoke test compiles ~11 modules).
_ST_CACHE: dict = {}


def _hf_id(model: str) -> str:
    """Map a Sutra/Ollama model name to a HuggingFace repo id.

    Unknown names pass through unchanged so a user can name any HF repo
    directly in `// @embedding:` / atman.toml.
    """
    return _HF_MODEL_IDS.get(model, model)


def _get_st_model(model: str):
    """Lazily load + cache the in-process SentenceTransformer for `model`."""
    hf_id = _hf_id(model)
    cached = _ST_CACHE.get(hf_id)
    if cached is not None:
        return cached
    # First load of this model in the process. The very first time on a machine
    # this also downloads weights (hundreds of MB), which otherwise looks like a
    # hang with no output. Announce it on stderr so it never corrupts --emit
    # stdout. Suppressible with SUTRA_QUIET=1.
    if os.environ.get("SUTRA_QUIET", "").strip() not in ("1", "true", "yes"):
        import sys

        print(
            f"[sutra] loading embedding model '{hf_id}' in-process "
            f"(first run downloads it, ~hundreds of MB; cached afterward). "
            f"Set SUTRA_EMBED_BACKEND=ollama to use a daemon instead, or "
            f"SUTRA_QUIET=1 to silence this.",
            file=sys.stderr,
            flush=True,
        )
    from sentence_transformers import SentenceTransformer

    # nomic-bert ships custom modeling code, hence trust_remote_code.
    st = SentenceTransformer(hf_id, trust_remote_code=True)
    _ST_CACHE[hf_id] = st
    return st


def _embed_transformers(names: List[str], model: str) -> List[List[float]]:
    """In-process embedding via sentence-transformers / HuggingFace."""
    st = _get_st_model(model)
    # No task prefix: Sutra embeds bare concepts, and no-prefix is the closest
    # match to Ollama's behavior. `normalize_embeddings=False` -> raw vectors;
    # the codegen's embed() applies Sutra's mean-center + normalize afterward.
    vecs = st.encode(list(names), normalize_embeddings=False)
    return [list(map(float, v)) for v in vecs]


def _embed_ollama(names: List[str], model: str) -> List[List[float]]:
    """Embedding via the Ollama daemon (the pre-2026-06-22 path)."""
    import ollama

    r = ollama.embed(model=model, input=list(names))
    return [list(map(float, e)) for e in r["embeddings"]]


def embed_texts(names: List[str], model: str) -> List[List[float]]:
    """Return raw frozen-LLM embeddings for `names` under `model`.

    Backend chosen by `SUTRA_EMBED_BACKEND` (auto | transformers/hf | ollama).
    "auto" prefers the in-process model and falls back to Ollama, so a plain
    pip install works with neither a daemon nor a manual choice.
    """
    if not names:
        return []
    backend = os.environ.get("SUTRA_EMBED_BACKEND", "auto").strip().lower()

    if backend in ("transformers", "hf", "huggingface", "sentence-transformers"):
        return _embed_transformers(names, model)
    if backend == "ollama":
        return _embed_ollama(names, model)

    # auto: in-process first, Ollama as fallback.
    try:
        return _embed_transformers(names, model)
    except Exception as in_proc_err:
        try:
            return _embed_ollama(names, model)
        except Exception as ollama_err:
            raise RuntimeError(
                "Sutra could not obtain embeddings for "
                f"{names[:3]}{'...' if len(names) > 3 else ''} under model "
                f"{model!r}. In-process load failed ({type(in_proc_err).__name__}: "
                f"{in_proc_err}); Ollama fallback failed ({type(ollama_err).__name__}: "
                f"{ollama_err}). Install the in-process stack (`pip install "
                "sentence-transformers`) or run an Ollama daemon with the model "
                "pulled. Set SUTRA_EMBED_BACKEND to force one backend."
            ) from ollama_err


__all__ = ["embed_texts"]
