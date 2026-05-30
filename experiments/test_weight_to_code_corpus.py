"""Consistency test for the weights<->code corpus generator (v0).

The corpus's value as training data rests on one invariant: each entry's
(source, weights) must REPRODUCE its recorded IO when recompiled and run
on the substrate. This test generates a tiny corpus into a temp dir, then
for every entry rebuilds the program from its stored `source` + weight
CSVs, recompiles (model-free), runs it on the recorded inputs, and checks
the outputs match — i.e. the (code <-> weights <-> behavior) triple is
self-consistent.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile

import pytest

torch = pytest.importorskip("torch", reason="Sutra substrate requires torch")

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(REPO, "sdk", "sutra-compiler"))

from sutra_compiler.codegen_pytorch import translate_module as torch_translate  # noqa: E402
from sutra_compiler.lexer import Lexer  # noqa: E402
from sutra_compiler.parser import Parser  # noqa: E402


def _recompile_entry(entry, corpus_dir):
    # The stored source references weight CSVs by relative basename; map
    # each to its absolute path in the corpus dir so load_matrix resolves.
    src = entry["source"]
    for w in entry["weights"]:
        abs_csv = os.path.join(corpus_dir, w["csv"]).replace("\\", "/")
        src = src.replace(f'"{w["csv"]}"', f'"{abs_csv}"')
    lx = Lexer(src, file="<recompile>")
    ast = Parser(lx.tokenize(), file="<recompile>", diagnostics=lx.diagnostics).parse_module()
    assert not lx.diagnostics.has_errors(), list(lx.diagnostics)
    ns: dict = {}
    exec(torch_translate(ast, llm_model="none", runtime_dim=entry["K"]), ns)
    return ns


@pytest.fixture(scope="module")
def corpus():
    tmp = tempfile.mkdtemp()
    r = subprocess.run(
        [sys.executable, os.path.join(HERE, "weight_to_code_corpus.py"),
         "--out", tmp, "--ks", "4,6", "--kinds", "gaussian,perm", "--seeds", "0"],
        capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stderr
    entries = [
        json.loads(line)
        for line in open(os.path.join(tmp, "corpus.jsonl"), encoding="utf-8")
    ]
    return tmp, entries


def test_corpus_nonempty_and_well_formed(corpus):
    _, entries = corpus
    assert len(entries) == 3 * 2 * 2  # structures × Ks × kinds
    for e in entries:
        assert e["llm_model"] == "none"          # model-free
        assert e["runtime_dim"] == e["K"]        # dim-audit honest
        assert "load_matrix(" in e["source"]     # file-backed weights
        assert e["weights"] and e["io"]


def test_every_entry_is_weights_code_behavior_consistent(corpus):
    corpus_dir, entries = corpus
    for e in entries:
        ns = _recompile_entry(e, corpus_dir)
        apply_fn, vsa = ns["apply"], ns["_VSA"]
        for pair in e["io"]:
            x = torch.tensor(pair["input"], dtype=vsa.dtype, device=vsa.device)
            got = apply_fn(x).tolist()
            want = pair["output"]
            for g, w in zip(got, want):
                assert abs(g - w) < 1e-4, (
                    f"{e['id']}: recompiled output {g} != recorded {w}"
                )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
