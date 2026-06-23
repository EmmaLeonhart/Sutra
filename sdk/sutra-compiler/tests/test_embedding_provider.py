"""Tests for the host-side embedding provider (sutra_compiler/embedding.py).

The provider is the `embed()` compile/IO boundary: it resolves strings to frozen
LLM vectors at module init. The in-process (transformers) path needs a model
download, so it is exercised only when sentence-transformers is importable; the
Ollama path and the pure dispatch/mapping logic are always tested.
"""
import importlib.util
import os

import pytest

from sutra_compiler import embedding


def test_hf_id_maps_known_names_and_passes_through_unknown():
    assert embedding._hf_id("nomic-embed-text") == "nomic-ai/nomic-embed-text-v1.5"
    assert embedding._hf_id("all-minilm") == "sentence-transformers/all-MiniLM-L6-v2"
    # An unknown name passes through so a user can name any HF repo directly.
    assert embedding._hf_id("some-org/some-model") == "some-org/some-model"


def test_empty_input_returns_empty_without_any_backend():
    # No backend touched for an empty request — pure short-circuit.
    assert embedding.embed_texts([], "nomic-embed-text") == []


def _ollama_available() -> bool:
    if importlib.util.find_spec("ollama") is None:
        return False
    try:
        import ollama

        ollama.list()
        return True
    except Exception:
        return False


@pytest.mark.skipif(not _ollama_available(), reason="Ollama daemon not available")
def test_ollama_backend_returns_vectors_of_model_dim():
    out = embedding.embed_texts(["hello", "world"], "nomic-embed-text")
    assert len(out) == 2
    # nomic-embed-text is 768-d; the provider returns raw (pre-Sutra-postproc) vectors.
    assert len(out[0]) == 768
    assert all(isinstance(x, float) for x in out[0])


@pytest.mark.skipif(not _ollama_available(), reason="Ollama daemon not available")
def test_explicit_ollama_backend_is_honored(monkeypatch):
    monkeypatch.setenv("SUTRA_EMBED_BACKEND", "ollama")
    out = embedding.embed_texts(["cat"], "nomic-embed-text")
    assert len(out) == 1 and len(out[0]) == 768


@pytest.mark.skipif(
    importlib.util.find_spec("sentence_transformers") is None,
    reason="sentence-transformers (in-process backend) not installed",
)
def test_transformers_backend_returns_vectors(monkeypatch):
    monkeypatch.setenv("SUTRA_EMBED_BACKEND", "transformers")
    out = embedding.embed_texts(["hello"], "nomic-embed-text")
    assert len(out) == 1 and len(out[0]) == 768
