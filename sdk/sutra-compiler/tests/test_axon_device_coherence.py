"""Regression test: pytorch axon ops handle host-side (CPU) tensor inputs.

Yantra surfaced this 2026-05-14: when a host-side caller (a Python
orchestrator, the kernel's SutraService wrapper, etc.) passes a CPU
torch.Tensor into a compiled .su program that calls `Axon.add(...)`,
the runtime would fail with `Expected all tensors to be on the same
device, but got mat is on cuda:0, different from other tensors on
cpu`.

Root cause: `_TorchVSA.bind` did `Q @ filler` where `Q` lives on
`self.device` (cuda when available) but `filler` arrives on whatever
device the caller used (cpu when the caller didn't pin it). Same
shape can bite `unbind`, `axon_add`, `axon_item`.

Fix: defensive `_torch.as_tensor(..., dtype=self.dtype, device=
self.device)` coercion at the entry of each method. No-op for
tensors already on the right device, coerce-once for anything
else. Same pattern `bundle()` already used.

This test exercises the full chain: compile a .su with `Axon a;
a.add("k", input)`, run it with a CPU input tensor, expect no
exception. Skipped when torch is not installed.
"""

from __future__ import annotations

import pathlib
import sys
import types

import pytest

torch = pytest.importorskip("torch", reason="device-coherence test needs torch")

HERE = pathlib.Path(__file__).resolve().parent
SDK = HERE.parent
sys.path.insert(0, str(SDK))

from sutra_compiler.lexer import Lexer
from sutra_compiler.parser import Parser
from sutra_compiler.codegen_pytorch import translate_module


def _compile(src: str, file: str = "<test>") -> types.ModuleType:
    lexer = Lexer(src, file=file)
    tokens = lexer.tokenize()
    parser = Parser(tokens, file=file, diagnostics=lexer.diagnostics)
    module = parser.parse_module()
    py_src = translate_module(module, llm_model="nomic-embed-text", runtime_dim=768)
    mod = types.ModuleType(file)
    exec(compile(py_src, file, "exec"), mod.__dict__)
    return mod


def test_axon_add_accepts_cpu_input_tensor() -> None:
    """`a.add("key", cpu_tensor)` runs without device-mismatch."""
    src = """
        function vector on_axon(vector input_axon) {
            Axon a;
            a.add("key_one", input_axon);
            return a;
        }
    """
    mod = _compile(src, file="cpu_input_axon_add.su")
    cpu_input = torch.randn(mod._VSA.dim)  # default device = cpu
    result = mod.on_axon(cpu_input)
    # Result should land on the runtime device, regardless of input.
    assert result.device.type == mod._DEVICE.type
    assert result.shape == (mod._VSA.dim,)


def test_axon_add_accepts_multiple_cpu_input_tensors() -> None:
    """The original Yantra-side failing case — multiple `add`s on a CPU input."""
    src = """
        function vector on_axon(vector input_axon) {
            Axon a;
            a.add("key_one", input_axon);
            a.add("key_two", input_axon);
            return a;
        }
    """
    mod = _compile(src, file="cpu_input_axon_add_x2.su")
    cpu_input = torch.randn(mod._VSA.dim)
    result = mod.on_axon(cpu_input)
    assert result.device.type == mod._DEVICE.type


def test_axon_item_accepts_cpu_input_tensor() -> None:
    """`axon_item(cpu_tensor, "key")` runs without device-mismatch."""
    src = """
        function vector on_axon(vector input_axon) {
            return axon_item(input_axon, "some_key");
        }
    """
    mod = _compile(src, file="cpu_input_axon_item.su")
    cpu_input = torch.randn(mod._VSA.dim)
    result = mod.on_axon(cpu_input)
    assert result.device.type == mod._DEVICE.type


def test_round_trip_add_then_item_with_cpu_input() -> None:
    """Same .su both binds and reads — confirm both paths handle CPU input.

    The narrow purpose of this test is device coherence: that
    `add` + `axon_item` chained together don't trip the
    device-mismatch error when the input arrives on CPU. The
    mathematical round-trip recovery (does the unbind reconstruct
    the original filler) is governed by the axon-math properties
    of bind/unbind on extended-state vectors and is exercised
    elsewhere — see `examples/multi_program_axon/_run.py` and the
    Sutra paper's appendix on bundle decoding margins.
    """
    src = """
        function vector on_axon(vector input_axon) {
            Axon a;
            a.add("k", input_axon);
            return axon_item(a, "k");
        }
    """
    mod = _compile(src, file="cpu_input_round_trip.su")
    cpu_input = torch.randn(mod._VSA.dim)
    result = mod.on_axon(cpu_input)
    # Just verifying no device-mismatch error and the result lands
    # on the runtime device. Mathematical recovery is a separate
    # concern with a separate test surface.
    assert result.device.type == mod._DEVICE.type
    assert result.shape == (mod._VSA.dim,)


def test_device_coercion_is_idempotent_for_correct_device_input() -> None:
    """Tensors already on the runtime device pass through unchanged."""
    src = """
        function vector on_axon(vector input_axon) {
            Axon a;
            a.add("k", input_axon);
            return a;
        }
    """
    mod = _compile(src, file="device_native_input.su")
    native_input = torch.randn(mod._VSA.dim, device=mod._DEVICE)
    result = mod.on_axon(native_input)
    assert result.device.type == mod._DEVICE.type
