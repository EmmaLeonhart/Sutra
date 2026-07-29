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


def pytest_report_header(config):
    """Say up front whether the pinned substrate is actually reachable.

    Without this, a checkout with no Ollama fails ~50 tests whose traceback
    bottoms out in `ModuleNotFoundError: No module named 'ollama'` several
    frames below whatever the test was checking — inside `_embed_ollama`, called
    from generated code, called from the compile step. It reads as a broken
    checkout rather than a missing daemon, which costs a new contributor real
    time before they find the one `setdefault` above.

    Deliberately a header note, not a skip. Skipping would hide a red suite and
    weaken the correctness gate; the tests SHOULD fail when their substrate is
    absent. This only makes the reason legible before the failures scroll past.
    """
    backend = os.environ.get("SUTRA_EMBED_BACKEND", "auto")
    lines = [f"sutra: embedding backend = {backend}"]

    if backend != "ollama":
        return lines

    try:
        import ollama  # noqa: F401
    except ImportError:
        lines += [
            "sutra: WARNING - the 'ollama' package is NOT installed, and this suite is pinned to it.",
            "sutra:   Embedding-dependent tests (~50) will fail with ModuleNotFoundError",
            "sutra:   raised deep inside generated code. That is a missing dependency,",
            "sutra:   not a code defect. To run the full gate:",
            "sutra:     pip install ollama && ollama serve && ollama pull nomic-embed-text",
            "sutra:   The 'ollama' package is intentionally in no extra; end users on the",
            "sutra:   default in-process backend do not need it; only this suite does.",
            "sutra:   To exercise the in-process path instead: SUTRA_EMBED_BACKEND=transformers",
        ]
        return lines

    # Package present — check the daemon too, since importing it proves nothing.
    try:
        import ollama

        ollama.list()
    except Exception as exc:  # noqa: BLE001 — any failure means "not reachable"
        lines += [
            f"sutra: WARNING - 'ollama' imports but the daemon is unreachable ({type(exc).__name__}).",
            "sutra:   Embedding-dependent tests will fail. Start it with: ollama serve",
            "sutra:   and ensure the model is pulled: ollama pull nomic-embed-text",
        ]

    return lines
