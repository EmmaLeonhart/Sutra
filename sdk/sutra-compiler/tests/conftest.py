"""Pytest config for the Sutra compiler suite.

Pin the embedding backend to Ollama for the test session. The compiler test
suite's numeric thresholds (axon crosstalk margins, classifier separations,
retrieval expectations) were measured and tuned against **Ollama's** nomic-embed-text
geometry. The in-process transformers backend is the same model family but a
different realization (mean cosine vs Ollama ~0.88), so a few capacity/crosstalk
stress tests collide under it (e.g. short words like "go" near "telephone").

So the correctness gate runs on its tuned substrate. The in-process backend is
the zero-config default for END USERS running their own programs without a daemon
(see `sutra_compiler/embedding.py`); it is exercised by the example smoke test,
not gated here.

`setdefault` — an explicit `SUTRA_EMBED_BACKEND=transformers` in the environment
still wins, so the in-process path can be tested deliberately.
"""
import os

os.environ.setdefault("SUTRA_EMBED_BACKEND", "ollama")
