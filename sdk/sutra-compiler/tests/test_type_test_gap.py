"""Signal-separation gap table for the substrate tag type-tests.

CLAUDE.md § "Subtler substrate breaches" rule 3: every substrate classifier ships
with a measured `gap = min(positive_class) - max(negative_class)`. Without the table
the claim "the substrate decides the type" is unverified. The three predicates
(`is_string_truth`, `is_axon_truth`, `is_number_truth`, codegen_pytorch) scatter
`2*flag - 1` onto AXIS_TRUTH over a tag axis, so a clean ±1 separation is expected;
this test measures it on the real substrate and pins it as a regression guard.

These are the predicates the Elixir/Erlang `when is_binary/is_list/is_number(...)`
guards lower to (planning/findings/2026-06-18-substrate-type-tests.md).
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
    """One representative value per substrate type. The axon is built with the real
    axon_add path (which sets AXIS_AXON_POPULATED), not a hand-flagged vector."""
    ax = v.zero_vector().clone()
    # axon_add embeds its key; with llm_model='none' that path is unavailable, so set
    # the populated flag directly — this is what axon_add does to the result. The
    # type_test_guard frontend fixtures exercise the real axon_add path end-to-end.
    ax[v.semantic_dim + v.AXIS_AXON_POPULATED] = 1.0
    return {
        "string": v.make_string("hello"),
        "number": v.make_real(42.0),
        "axon": ax,
    }


@pytest.mark.parametrize(
    "method,positive",
    [
        ("is_string_truth", "string"),
        ("is_axon_truth", "axon"),
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
    # Clean ±1 scatter ⇒ gap == 2.0. Require a wide, unambiguous separation.
    assert gap >= 1.9, (
        f"{method}: positive={pos_truths} negative={neg_truths} gap={gap:.4f}"
    )


def test_gap_table_is_exact():
    """The full measured gap table (reported, not just asserted)."""
    v = _vsa()
    samples = _samples(v)
    table = {}
    for method, positive in [
        ("is_string_truth", "string"),
        ("is_axon_truth", "axon"),
        ("is_number_truth", "number"),
    ]:
        pred = getattr(v, method)
        pos = min(_truth(v, pred(val)) for k, val in samples.items() if k == positive)
        neg = max(_truth(v, pred(val)) for k, val in samples.items() if k != positive)
        table[method] = pos - neg
    # All three are exact ±1 scatters ⇒ gap of exactly 2.0 each.
    for method, gap in table.items():
        assert abs(gap - 2.0) < 1e-6, f"{method} gap={gap} (table={table})"
