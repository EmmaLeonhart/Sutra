"""Deterministic test of the Gemma-codegen validation filter.

The live generation (gemma_codegen_corpus.main) needs ollama + gemma3:12b
and is nondeterministic, so this tests `validate()` + `split_programs()`
on FIXED known-good / known-bad sources — the filter Emma's free-form
plan relies on (only programs that compile + run on the substrate enter
the corpus).
"""
from __future__ import annotations

import importlib.util
import os

import pytest

torch = pytest.importorskip("torch", reason="Sutra substrate requires torch")

HERE = os.path.dirname(os.path.abspath(__file__))


def _mod():
    spec = importlib.util.spec_from_file_location(
        "gemma_codegen_corpus", os.path.join(HERE, "gemma_codegen_corpus.py")
    )
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


MAIN = '\nfunction string main() { return "ok"; }\n'

GOOD_LINEAR = (
    "function vector apply(vector x) { matrix M = matrix_literal("
    "vector_literal(0.0, 1.0), vector_literal(1.0, 0.0)); "
    "return Tensor.MatrixMul(M, x); }" + MAIN
)
GOOD_ARITH = "function vector apply(vector x) { return 2.0 * x + x; }" + MAIN
# 2x1 matrix @ vector -> shape mismatch at every input dim: must be rejected.
BAD_SHAPE = (
    "function vector apply(vector x) { return Tensor.MatrixMul("
    "matrix_literal(vector_literal(1.0), vector_literal(1.0)), x); }" + MAIN
)
NO_APPLY = 'function vector f(vector x) { return x; }' + MAIN
PARSE_ERR = "function vector apply(vector x) { return @@@; }" + MAIN


def test_good_linear_accepted_at_K2():
    v = _mod().validate(GOOD_LINEAR)
    assert v is not None
    K, io = v
    assert K == 2 and len(io) == 3
    # swap matrix applied to [a,b] -> [b,a]
    x = io[0]["input"]
    assert io[0]["output"] == [x[1], x[0]]


def test_good_arithmetic_accepted():
    v = _mod().validate(GOOD_ARITH)
    assert v is not None
    K, io = v
    # 2x + x = 3x
    for pair in io:
        for xi, yi in zip(pair["input"], pair["output"]):
            assert abs(yi - 3.0 * xi) < 1e-4


def test_shape_mismatch_rejected():
    assert _mod().validate(BAD_SHAPE) is None


def test_missing_apply_rejected():
    assert _mod().validate(NO_APPLY) is None


def test_parse_error_rejected():
    assert _mod().validate(PARSE_ERR) is None


def test_committed_gemma_corpus_is_consistent():
    """Every committed Gemma entry must recompile + reproduce its recorded
    IO on the substrate (the corpus self-consistency invariant — the guard
    the template corpus has). Skips if the submodule isn't checked out or
    Ollama is unavailable (free-form entries may use embeddings)."""
    import json

    path = os.path.abspath(os.path.join(HERE, "..", "corpus", "gemma_corpus.jsonl"))
    if not os.path.isfile(path) or os.path.getsize(path) == 0:
        pytest.skip("corpus/gemma_corpus.jsonl not present (submodule not init?)")
    try:
        import ollama
        ollama.embed(model="nomic-embed-text", input="probe")
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"Ollama unavailable (free-form entries may need it): {e}")
    m = _mod()
    entries = [json.loads(line) for line in open(path, encoding="utf-8") if line.strip()]
    assert entries
    for e in entries:
        ok, d = m.verify_entry(e)
        assert ok, f"gemma entry {e.get('id')} inconsistent (max|delta|={d})"


def test_split_programs_handles_fences_and_separators():
    m = _mod()
    text = "```sutra\n" + GOOD_ARITH + "\n```\n---\n" + GOOD_LINEAR
    progs = m.split_programs(text)
    assert len(progs) == 2
    assert all("function vector apply" in p for p in progs)
    assert all("function string main" in p for p in progs)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
