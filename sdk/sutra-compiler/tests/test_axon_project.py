"""Tests for the per-receiver projection runtime primitive.

`_TorchVSA.axon_project(axon, requested_keys)` returns an axon
containing only the listed keys' bound contributions, by extracting
each via `axon_item` and re-adding via `axon_add`. Used by routers /
orchestrators that want to slim a multi-key axon down to what a
specific receiver actually reads (per the axon_keys static analysis).

Tests:
  - Project to a subset: extracting a key from the projected axon
    matches extracting it from the original (bound keys preserved).
  - Project to a subset: extracting a NOT-projected key gives a
    different (~zero-ish) result from the original (dropped keys
    are gone — well, replaced with zero, since axon_item on a
    bound key in a fresh axon would return ~zero).
  - Project to empty set: returns an axon that's ~zero
    (the zero_vector starting point with no contributions added).
  - Project preserves device coherence: CPU input → device output.
  - Project of CPU input doesn't crash (the v0.3.4 device fix
    propagates through the new method).
"""

from __future__ import annotations

import pathlib
import sys
import types

import pytest

torch = pytest.importorskip("torch", reason="axon_project test needs torch")

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


@pytest.fixture(scope="module")
def vsa():
    """A bare _TorchVSA instance for direct method-level tests."""
    src = "function int main() { return 0; }"  # minimal program
    mod = _compile(src, file="bare.su")
    return mod._VSA


def test_project_preserves_requested_key_value(vsa) -> None:
    """A key extracted from a projected axon ≈ the same key extracted from the original."""
    a = vsa.zero_vector()
    a = vsa.axon_add(a, "k1", vsa.embed("alice"))
    a = vsa.axon_add(a, "k2", vsa.embed("bob"))
    a = vsa.axon_add(a, "k3", vsa.embed("carol"))

    projected = vsa.axon_project(a, ["k1", "k2"])
    # Extract k1 from both — should be very close.
    orig_k1 = vsa.axon_item(a, "k1")
    proj_k1 = vsa.axon_item(projected, "k1")
    diff = (orig_k1 - proj_k1).abs().max().item()
    # Some bundle-noise from the other still-present keys in `a`,
    # but k1's contribution should dominate. Use a generous tolerance.
    assert diff < 0.5, f"projected-k1 should approximate orig-k1; max diff = {diff}"


def test_project_equivalent_to_built_from_scratch(vsa) -> None:
    """Projecting to {kept} ≈ building a fresh axon with only `kept`.

    This is the right way to test "the projection drops unrequested
    keys" — comparing the projected axon as a whole against an
    axon constructed from scratch with only the kept key. (Comparing
    `axon_item(projected, "dropped")` directly is misleading
    because the unbind operation always produces SOME output —
    leakage from other slots — and that leakage's magnitude isn't
    necessarily small even when the key wasn't bound.)
    """
    # Original: two keys bound.
    a = vsa.zero_vector()
    a = vsa.axon_add(a, "kept", vsa.embed("alice"))
    a = vsa.axon_add(a, "dropped", vsa.embed("bob"))

    # Project to the one we want to keep.
    projected = vsa.axon_project(a, ["kept"])

    # Built-from-scratch with only the kept key.
    built = vsa.zero_vector()
    built = vsa.axon_add(built, "kept", vsa.embed("alice"))

    # The two should agree up to floating-point + bind/unbind
    # round-trip residual. The axon_project path goes through an
    # extract-and-rebind chain so it's not bit-exact, but it
    # should be close.
    diff = (projected - built).abs().max().item()
    assert diff < 0.5, (
        f"axon_project should produce ~the same vector as "
        f"building from scratch with only the kept key; "
        f"max abs diff = {diff}"
    )


def test_project_to_empty_set_is_zero_axon(vsa) -> None:
    """Projecting to no keys returns a zero-vector-shaped axon."""
    a = vsa.zero_vector()
    a = vsa.axon_add(a, "k", vsa.embed("alice"))
    projected = vsa.axon_project(a, [])
    # zero_vector returns torch.zeros — projected should equal it.
    expected = vsa.zero_vector()
    assert (projected - expected).abs().max().item() < 1e-6


def test_project_returns_runtime_device_tensor(vsa) -> None:
    """Projection output is on the runtime device."""
    a = vsa.zero_vector()
    a = vsa.axon_add(a, "k", vsa.embed("alice"))
    projected = vsa.axon_project(a, ["k"])
    assert projected.device.type == vsa.device.type


def test_project_accepts_cpu_input_axon(vsa) -> None:
    """Host-side caller passing a CPU axon doesn't device-mismatch."""
    a = vsa.zero_vector()
    a = vsa.axon_add(a, "k", vsa.embed("alice"))
    cpu_axon = a.cpu()  # explicitly move to CPU
    projected = vsa.axon_project(cpu_axon, ["k"])
    assert projected.device.type == vsa.device.type


def test_project_via_compiled_su_module() -> None:
    """End-to-end: a .su program calls axon_project on a built axon."""
    src = """
        function vector build_then_project() {
            Axon a;
            a.add("alpha", basis_vector("x"));
            a.add("beta",  basis_vector("y"));
            a.add("gamma", basis_vector("z"));
            return a;
        }
    """
    mod = _compile(src, file="end_to_end.su")
    a = mod.build_then_project()
    # Direct runtime-method call from host side.
    projected = mod._VSA.axon_project(a, ["alpha", "gamma"])
    assert projected.device.type == mod._DEVICE.type
    assert projected.shape == a.shape
