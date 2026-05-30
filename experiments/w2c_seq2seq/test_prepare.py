"""Guards for the weight→code seq2seq data prep (task #19).

Two layers:
- Deterministic unit tests on the tokenizer + normalizer (no corpus needed).
- A corpus-backed integration test (skips if the `corpus/` submodule isn't
  checked out): every produced target round-trips through the tokenizer,
  train/val ids are disjoint, the vocab covers every target char, and no
  normalized target still contains a raw `.csv` filename (the leak the
  normalizer removes).
"""
from __future__ import annotations

import importlib.util
import json
import os

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))


def _mod():
    spec = importlib.util.spec_from_file_location(
        "w2c_prepare", os.path.join(HERE, "prepare.py")
    )
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_normalize_replaces_csv_with_weight_name():
    m = _mod()
    entry = {
        "source": 'matrix M0 = load_matrix("linear_K4_gaussian_s0_M0.csv");\n'
                  'matrix M1 = load_matrix("chain2_K4_perm_s1_M1.csv");',
        "weights": [
            {"name": "M0", "csv": "linear_K4_gaussian_s0_M0.csv"},
            {"name": "M1", "csv": "chain2_K4_perm_s1_M1.csv"},
        ],
    }
    out = m.normalize_source(entry)
    assert 'load_matrix("M0")' in out
    assert 'load_matrix("M1")' in out
    assert ".csv" not in out


def test_tokenizer_round_trips():
    m = _mod()
    targets = [
        'function vector apply(vector x) { return Tensor.MatrixMul(M0, x); }',
        'matrix M0 = load_matrix("M0");\nreturn 2.0 * x + x;',
        "",
    ]
    vocab = m.build_vocab(targets)
    for t in targets:
        ids = m.encode(t, vocab)
        assert m.decode(ids, vocab) == t


def test_split_is_deterministic_and_partitions():
    m = _mod()
    ids = [f"linear_K{k}_gaussian_s{s}" for k in (4, 6, 8) for s in range(10)]
    a = {i: m.is_val(i) for i in ids}
    b = {i: m.is_val(i) for i in ids}
    assert a == b  # deterministic
    # both classes are non-empty for a realistic id set
    assert any(a.values()) and not all(a.values())


def _corpus_dir():
    d = os.path.abspath(os.path.join(HERE, "..", "..", "corpus"))
    p = os.path.join(d, "corpus.jsonl")
    return d if (os.path.isfile(p) and os.path.getsize(p) > 0) else None


@pytest.mark.skipif(_corpus_dir() is None, reason="corpus/ submodule not checked out")
def test_prepare_on_real_corpus(tmp_path):
    m = _mod()
    corpus = _corpus_dir()
    out = str(tmp_path / "data")
    stats = m.prepare(corpus, out, include_gemma=False)

    assert stats["entries"] > 0
    assert stats["train"] > 0 and stats["val"] > 0
    assert stats["train"] + stats["val"] == stats["entries"]

    vocab = json.load(open(os.path.join(out, "vocab.json"), encoding="utf-8"))
    train = [json.loads(l) for l in open(os.path.join(out, "train.jsonl"), encoding="utf-8")]
    val = [json.loads(l) for l in open(os.path.join(out, "val.jsonl"), encoding="utf-8")]

    # no id leakage between splits
    assert set(r["id"] for r in train).isdisjoint(r["id"] for r in val)

    for r in train + val:
        # round-trip + vocab coverage
        assert m.decode(r["target_ids"], vocab) == r["target"]
        assert all(c in vocab for c in r["target"])
        # the CSV-filename leak is gone from the (generation) target
        assert ".csv" not in r["target"]
        # weights actually loaded (template entries reference >=1 matrix)
        assert r["weights"] and all(len(row) for mat in r["weights"] for row in mat)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
