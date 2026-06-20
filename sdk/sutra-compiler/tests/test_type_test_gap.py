"""Signal-separation gap table for the substrate tag type-tests.

CLAUDE.md § "Subtler substrate breaches" rule 3: every substrate classifier ships
with a measured `gap = min(positive_class) - max(negative_class)`. The two supported
predicates (`is_string_truth`, `is_number_truth`, codegen_pytorch) read the
AXIS_STRING_FLAG and scatter onto AXIS_TRUTH, so a clean ±1 separation between String
and number is expected; this test measures it on the real substrate and pins it.

These are the predicates the Elixir/Erlang `when is_binary/is_number(...)` guards lower
to (planning/findings/2026-06-18-substrate-type-tests.md). SCOPE: only the String flag
is a clean runtime tag, so only String-vs-number is separated. `is_number_truth` is
"NOT-a-String"; it does NOT distinguish a number from an axon (the AXIS_AXON_POPULATED
attempt was reverted — it corrupted nested-axon reads). So this table covers String and
number only; an axon is (intentionally) classified as a number by is_number_truth.
"""
from __future__ import annotations

import types

import pytest

torch = pytest.importorskip("torch")

from sutra_compiler.codegen_pytorch import translate_module  # noqa: E402
from sutra_compiler.lexer import Lexer  # noqa: E402
from sutra_compiler.parser import Parser  # noqa: E402


def _vsa(runtime_dim: int = 16):
    src = "function int main() { return 0; }"
    lx = Lexer(src, file="t.su")
    ps = Parser(lx.tokenize(), file="t.su", diagnostics=lx.diagnostics)
    py = translate_module(ps.parse_module(), llm_model="none", runtime_dim=runtime_dim)
    m = types.ModuleType("t")
    exec(compile(py, "t.su", "exec"), m.__dict__)
    return m._VSA


def _truth(v, out):
    return float(out[v.semantic_dim + v.AXIS_TRUTH])


def _samples(v):
    return {"string": v.make_string("hello"), "number": v.make_real(42.0)}


@pytest.mark.parametrize(
    "method,positive",
    [
        ("is_string_truth", "string"),
        ("is_number_truth", "number"),
    ],
)
def test_type_test_signal_separation_gap(method, positive):
    v = _vsa()
    samples = _samples(v)
    pred = getattr(v, method)
    pos_truths = [_truth(v, pred(val)) for k, val in samples.items() if k == positive]
    neg_truths = [_truth(v, pred(val)) for k, val in samples.items() if k != positive]
    gap = min(pos_truths) - max(neg_truths)
    assert gap >= 1.9, (
        f"{method}: positive={pos_truths} negative={neg_truths} gap={gap:.4f}"
    )


def test_gap_table_is_exact():
    """The measured gap table (reported, not just asserted): String vs number."""
    v = _vsa()
    samples = _samples(v)
    table = {}
    for method, positive in [
        ("is_string_truth", "string"),
        ("is_number_truth", "number"),
    ]:
        pred = getattr(v, method)
        pos = min(_truth(v, pred(val)) for k, val in samples.items() if k == positive)
        neg = max(_truth(v, pred(val)) for k, val in samples.items() if k != positive)
        table[method] = pos - neg
    for method, gap in table.items():
        assert abs(gap - 2.0) < 1e-6, f"{method} gap={gap} (table={table})"


def test_is_number_truth_is_not_a_string():
    """is_number_truth is the negation of is_string_truth on the String flag: a String
    reads -1, anything without the flag reads +1 (a number; also an axon, which it does
    NOT distinguish — the documented scope limit)."""
    v = _vsa()
    assert _truth(v, v.is_number_truth(v.make_real(7.0))) == pytest.approx(1.0)
    assert _truth(v, v.is_number_truth(v.make_string("x"))) == pytest.approx(-1.0)
