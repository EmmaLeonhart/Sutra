"""Tests for the migrated kernel-free calc demo (Phase-3).

calc.py runs without the Yantra kernel: switch.su is compiled with
compile_su and its on_axon called directly per binary op (see calc.py).
Arithmetic runs on the substrate (operator selected on the substrate from
its codepoint); the host parser + exact-rational oracle refuse anything
inexact. Needs torch + Ollama (switch.su embeds its axon keys via nomic).
Mirrors the demos/font + demos/echo test structure.
"""
from __future__ import annotations

import importlib.util
import os

import pytest

torch = pytest.importorskip("torch", reason="Sutra substrate requires torch")

HERE = os.path.dirname(os.path.abspath(__file__))


def _ollama_or_skip():
    try:
        import ollama

        ollama.embed(model="nomic-embed-text", input="probe")
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"Ollama/nomic-embed-text unavailable: {e}")


def _load_calc():
    spec = importlib.util.spec_from_file_location(
        "calc_demo", os.path.join(HERE, "calc.py")
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def calc():
    _ollama_or_skip()
    return _load_calc().Calculator()


# (expression, exact expected value) — arithmetic decided on the substrate.
_CASES = [
    ("2 + 3 =", 5), ("7 * 8", 56), ("100 - 50", 50), ("15 / 3", 5),
    ("2 + 3 * 4", 14), ("(10 - 2) * 5", 40), ("-5 + 2", -3),
    ("7 / 2", 3.5), ("(1 + 2) * (3 + 4)", 21), ("0 - 9", -9),
    ("1000 + 234", 1234),
]


@pytest.mark.parametrize("expr,expected", _CASES)
def test_evaluate_exact_on_substrate(calc, expr, expected):
    assert calc.evaluate(expr) == expected


# Things the substrate cannot confirm exactly are REFUSED, never approximated.
_REFUSED = ["10 / 3", "5 / 0", "1 +", "", "2 ** 3", "abc"]


@pytest.mark.parametrize("expr", _REFUSED)
def test_refuses_inexact_or_unparseable(calc, expr):
    with pytest.raises((ValueError, RuntimeError)):
        calc.evaluate(expr)


@pytest.mark.parametrize("value,expected", [
    (5, "5"), (14, "14"), (50, "50"), (2050, "2050"), (9999, "9999"),
    (0, "0"), (-3, "-3"),
])
def test_result_string_decomposed_on_substrate(calc, value, expected):
    assert calc.result_string(value) == expected


def test_result_string_out_of_range_refused(calc):
    with pytest.raises(ValueError):
        calc.result_string(10000)


def test_calc_is_kernel_free():
    src = open(os.path.join(HERE, "calc.py"), encoding="utf-8").read()
    assert "compile_su" in src
    for forbidden in ("import kernel", "from kernel"):
        assert forbidden not in src, f"kernel import found: {forbidden!r}"


def test_operator_select_signal_separation_gap():
    """The four-operator select is a real substrate decision, not a host artifact:
    the score for the matched operator is exactly 0 and every wrong operator scores
    <= -1000 (CLAUDE.md "Subtler substrate breaches" #3 signal-separation rule).
    See demos/calc/measure_select_gap.py."""
    spec = importlib.util.spec_from_file_location(
        "measure_select_gap", os.path.join(HERE, "measure_select_gap.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    r = mod.measure(runtime_dim=8)
    assert abs(r["min_selected"]) < 1e-3, r           # matched operator scores 0
    assert r["max_leaked"] <= -1000.0 + 1e-3, r       # wrong operators <= -1000
    assert r["gap"] >= 1000.0 - 1e-3, r               # clean separation, gap ~1000
