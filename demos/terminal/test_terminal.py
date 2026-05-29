"""Tests for the migrated kernel-free terminal demo (Phase-3).

terminal.py composes the two already-migrated kernel-free demos
(demos/echo + demos/calc) behind a host command-dispatch loop — no Yantra
kernel. echo decodes the substrate round-trip verbatim; calc evaluates on
switch.su and refuses anything inexact. Needs torch + Ollama. Mirrors the
demos/echo + demos/calc test structure.
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


def _load_terminal():
    spec = importlib.util.spec_from_file_location(
        "terminal_demo", os.path.join(HERE, "terminal.py")
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def term_mod():
    _ollama_or_skip()
    return _load_terminal()


@pytest.fixture(scope="module")
def term(term_mod):
    return term_mod.Terminal()


@pytest.mark.parametrize("text", ["hello", "world", "Sutra", "echo me"])
def test_echo_command_is_substrate_roundtrip(term, text):
    # `echo <text>` decodes the substrate round-trip verbatim.
    assert term.run(f"echo {text}") == text


@pytest.mark.parametrize("expr,expected", [
    ("calc 2 + 3 * 4 =", "14"),
    ("calc (10 - 2) * 5", "40"),
    ("calc 15 / 3", "5"),
    ("calc 7 / 2", "3.5"),
])
def test_calc_command_exact(term, expr, expected):
    assert term.run(expr) == expected


def test_calc_refuses_inexact(term, term_mod):
    # 10/3 is non-terminating -> calc refuses -> wrapped as CommandError.
    with pytest.raises(term_mod.CommandError):
        term.run("calc 10 / 3")


def test_help_lists_commands(term):
    out = term.run("help")
    for name in ("echo", "calc", "help"):
        assert name in out


def test_unknown_command_raises(term, term_mod):
    with pytest.raises(term_mod.CommandError):
        term.run("nosuchcmd foo")


def test_empty_line_is_empty(term):
    assert term.run("   ") == ""


def test_terminal_is_kernel_free():
    src = open(os.path.join(HERE, "terminal.py"), encoding="utf-8").read()
    for forbidden in ("import kernel", "from kernel"):
        assert forbidden not in src, f"kernel import found: {forbidden!r}"
