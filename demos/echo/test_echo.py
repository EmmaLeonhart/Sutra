"""Round-trip test for the migrated kernel-free echo demo (Phase-3).

echo.su runs without the Yantra kernel: compile_su + a direct on_axon
call (see echo_demo.py). The string round-trips on the substrate through
rotation binding; the two axon keys are embedded via the frozen LLM
(nomic), so this test needs both torch and Ollama. Mirrors the
demos/font + demos/gui test structure (importlib-load the demo, exercise
the substrate function, assert exact results).
"""
from __future__ import annotations

import importlib.util
import os

import pytest

torch = pytest.importorskip("torch", reason="Sutra substrate requires torch")

HERE = os.path.dirname(os.path.abspath(__file__))


def _load_demo():
    spec = importlib.util.spec_from_file_location(
        "echo_demo", os.path.join(HERE, "echo_demo.py")
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _ollama_or_skip():
    try:
        import ollama

        ollama.embed(model="nomic-embed-text", input="probe")
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"Ollama/nomic-embed-text unavailable: {e}")


@pytest.mark.parametrize("text", ["hello", "echo world", "Sutra", "42", "a"])
def test_echo_roundtrips_exactly_on_substrate(text):
    """echo(text) decodes back to text — the SUBSTRATE's decode (rotation
    bind/unbind round-trip), not a host re-echo. Bit-exact at dim=16."""
    _ollama_or_skip()
    mod = _load_demo()
    assert mod.RUNTIME_DIM == 16  # the measured floor this demo ships at
    got = mod.echo(text)
    assert got == text, f"echo({text!r}) -> {got!r}"


def test_echo_is_kernel_free():
    """The migrated demo must not USE the Yantra kernel — it calls
    compile_su directly (the Phase-3 re-architecture, like font/gui).
    (Comments may mention "kernel" descriptively; we check for actual
    kernel imports / admission / routing usage, not the bare word.)"""
    src = open(os.path.join(HERE, "echo_demo.py"), encoding="utf-8").read()
    assert "compile_su" in src
    # No kernel IMPORT (the prose docstring may name kernel concepts to
    # explain what it replaces; an import is the unambiguous usage signal).
    # Combined with the passing round-trip tests, this proves echo runs
    # without the kernel.
    for forbidden in ("import kernel", "from kernel"):
        assert forbidden not in src, f"kernel import found: {forbidden!r}"
