"""Tests for the `vector_literal` builtin — the .su-emittable bake-back
form for trained vector-valued parameters.

Per `planning/sutra-spec/matrix-valued-bake-back.md`, vector_literal
is the one concrete prerequisite that unblocks matrix-valued
constrain-train experiments (rank-k is_X, defuzz polynomial
coefficients, etc.). Lean Option A: variadic float args lowering to
`_VSA.vector_from_floats([...])` — a substrate-side torch.tensor
constructor on the runtime device+dtype.

This test exercises:
  1. Codegen — `vector_literal(...)` emits a runnable
     `_VSA.vector_from_floats([...])` call.
  2. Substrate fidelity — the produced tensor matches the literal
     values exactly (within float32 rounding).
  3. Round-trip — re-emitting the same .su source produces the
     same tensor (deterministic; bake-back precondition).
  4. Composition — vector_literal values can be consumed by other
     builtins (bundle, similarity) without losing substrate purity.
"""
from __future__ import annotations

import unittest

import torch

from sutra_compiler.codegen_pytorch import translate_module as torch_translate
from sutra_compiler.lexer import Lexer
from sutra_compiler.parser import Parser


def _compile_and_exec(src: str):
    """Compile a .su source via the PyTorch codegen and return the
    executed-module namespace. Tests then call functions in `ns`
    directly."""
    lexer = Lexer(src, file="<test>")
    tokens = lexer.tokenize()
    parser = Parser(tokens, file="<test>", diagnostics=lexer.diagnostics)
    module = parser.parse_module()
    assert not lexer.diagnostics.has_errors(), list(lexer.diagnostics)
    py = torch_translate(
        module, runtime_dim=8, runtime_seed=42, loop_max_iterations=10
    )
    ns: dict = {}
    exec(py, ns)
    return ns


class TestVectorLiteral(unittest.TestCase):
    def test_basic_values_round_trip(self):
        """vector_literal(...) produces a tensor with the exact emitted
        values (within float32 representation precision)."""
        src = (
            "function vector make_v() {\n"
            "    return vector_literal(0.123, -0.045, 0.312, 1.0,\n"
            "                          0.0, -1.0, 0.5, -0.5);\n"
            "}\n"
            'function string main() { return "ok"; }\n'
        )
        ns = _compile_and_exec(src)
        v = ns["make_v"]()
        self.assertIsInstance(v, torch.Tensor)
        self.assertEqual(tuple(v.shape), (8,))
        expected = torch.tensor(
            [0.123, -0.045, 0.312, 1.0, 0.0, -1.0, 0.5, -0.5],
            dtype=v.dtype,
            device=v.device,
        )
        max_diff = float((v - expected).abs().max())
        self.assertLess(max_diff, 1e-7)

    def test_dtype_and_device_match_runtime(self):
        """vector_literal honors the runtime's dtype + device — the
        substrate-purity invariant. Not host numpy, not CPU-by-accident
        when the runtime is on CUDA."""
        src = (
            "function vector make_v() { return vector_literal(0.1, 0.2, 0.3); }\n"
            'function string main() { return "ok"; }\n'
        )
        ns = _compile_and_exec(src)
        v = ns["make_v"]()
        runtime = ns["_VSA"]
        self.assertEqual(v.dtype, runtime.dtype)
        self.assertEqual(v.device.type, runtime.device.type)

    def test_deterministic_repeats(self):
        """Two calls to the same vector_literal must return identical
        tensors — bake-back precondition (the recompile round-trip
        cannot depend on RNG)."""
        src = (
            "function vector make_v() {\n"
            "    return vector_literal(0.7, -0.3, 0.001, 42.0);\n"
            "}\n"
            'function string main() { return "ok"; }\n'
        )
        ns = _compile_and_exec(src)
        v1 = ns["make_v"]()
        v2 = ns["make_v"]()
        self.assertTrue(torch.equal(v1, v2))

    def test_consumed_by_other_builtins(self):
        """vector_literal output feeds into bundle (etc.) without
        dtype/device drift — a composed expression stays on the
        substrate end-to-end. We use bundle here rather than similarity,
        because emitted similarity collapses to a Python float (the
        separate substrate-purity issue surfaced in
        `planning/findings/2026-05-18-differentiable-training-is-a-
        proxy-not-compiled.md`); that issue is orthogonal to
        vector_literal and outside this test's scope."""
        src = (
            "function vector bundle_two() {\n"
            "    vector a = vector_literal(1.0, 0.0, 0.0, 0.0,\n"
            "                              0.0, 0.0, 0.0, 0.0);\n"
            "    vector b = vector_literal(0.0, 1.0, 0.0, 0.0,\n"
            "                              0.0, 0.0, 0.0, 0.0);\n"
            "    return bundle(a, b);\n"
            "}\n"
            'function string main() { return "ok"; }\n'
        )
        ns = _compile_and_exec(src)
        out = ns["bundle_two"]()
        self.assertIsInstance(out, torch.Tensor)
        self.assertEqual(tuple(out.shape), (8,))
        runtime = ns["_VSA"]
        self.assertEqual(out.dtype, runtime.dtype)
        self.assertEqual(out.device.type, runtime.device.type)


if __name__ == "__main__":
    unittest.main()
