"""Tests for the `matrix_literal` builtin — the 2-D generalization of
`vector_literal`, the source-level form for frozen matrix-valued
constants (lookup / permutation matrices, cached bind/projector
matrices).

Per Emma's 2026-05-28 decision (AskUserQuestion): add matrix-literal
support to the language. It unblocks the `numbers.su` / `logic.su` /
`vectors.su` items flagged "Blocked on: matrix literals" and the
font.su substrate-RNN (Option B: a frozen cyclic-permutation matrix
advanced by `Tensor.MatrixMul`).

Surface mirrors `vector_literal`: a variadic builtin whose args are row
vectors (each typically a `vector_literal`):

    matrix M = matrix_literal(row0, row1, ...);
      -> _VSA.matrix_from_rows([row0, row1, ...])  (torch.stack, dim=0)

This test exercises:
  1. Codegen — matrix_literal emits a runnable _VSA.matrix_from_rows([...]).
  2. Substrate fidelity — the produced 2-D tensor matches the literal
     rows exactly, on the runtime dtype+device.
  3. The motivating use: a frozen cyclic-permutation matrix, MatrixMul'd
     against a one-hot vector, performs the cyclic shift (with wrap) on
     the substrate — the advance step of font.su's substrate-RNN.
"""
from __future__ import annotations

import unittest

import torch

from sutra_compiler.codegen_pytorch import translate_module as torch_translate
from sutra_compiler.lexer import Lexer
from sutra_compiler.parser import Parser


def _compile_and_exec(src: str):
    lexer = Lexer(src, file="<test>")
    tokens = lexer.tokenize()
    parser = Parser(tokens, file="<test>", diagnostics=lexer.diagnostics)
    module = parser.parse_module()
    assert not lexer.diagnostics.has_errors(), list(lexer.diagnostics)
    py = torch_translate(module, runtime_dim=8, runtime_seed=42)
    ns: dict = {}
    exec(py, ns)
    return ns


class TestMatrixLiteral(unittest.TestCase):
    def test_codegen_lowers_to_matrix_from_rows(self):
        src = (
            "function vector make_m() {\n"
            "    matrix M = matrix_literal(vector_literal(1.0, 2.0),\n"
            "                              vector_literal(3.0, 4.0));\n"
            "    return M;\n"
            "}\n"
            'function string main() { return "ok"; }\n'
        )
        lexer = Lexer(src, file="<test>")
        tokens = lexer.tokenize()
        module = Parser(tokens, file="<test>", diagnostics=lexer.diagnostics).parse_module()
        py = torch_translate(module, runtime_dim=8, runtime_seed=42)
        self.assertIn("_VSA.matrix_from_rows([", py)

    def test_rows_round_trip_exactly(self):
        src = (
            "function vector make_m() {\n"
            "    return matrix_literal(vector_literal(0.5, -0.25, 1.0),\n"
            "                          vector_literal(-1.0, 0.0, 0.125));\n"
            "}\n"
            'function string main() { return "ok"; }\n'
        )
        ns = _compile_and_exec(src)
        m = ns["make_m"]()
        self.assertIsInstance(m, torch.Tensor)
        self.assertEqual(tuple(m.shape), (2, 3))
        expected = torch.tensor(
            [[0.5, -0.25, 1.0], [-1.0, 0.0, 0.125]],
            dtype=m.dtype,
            device=m.device,
        )
        self.assertLess(float((m - expected).abs().max()), 1e-7)

    def test_dtype_and_device_match_runtime(self):
        src = (
            "function vector make_m() {\n"
            "    return matrix_literal(vector_literal(0.1, 0.2),\n"
            "                          vector_literal(0.3, 0.4));\n"
            "}\n"
            'function string main() { return "ok"; }\n'
        )
        ns = _compile_and_exec(src)
        m = ns["make_m"]()
        runtime = ns["_VSA"]
        self.assertEqual(m.dtype, runtime.dtype)
        self.assertEqual(m.device.type, runtime.device.type)

    def test_permutation_matrix_advances_one_hot(self):
        # The motivating font.su Option-B use: a frozen 3x3 cyclic-shift
        # permutation P, MatrixMul'd against a one-hot state, shifts the
        # one-hot by one (with wrap) — entirely on the substrate.
        # P[i,j] = 1 iff j == (i-1) % 3, so (P @ v)[i] = v[(i-1)%3].
        src = (
            "function vector advance(vector state) {\n"
            "    matrix P = matrix_literal(\n"
            "        vector_literal(0.0, 0.0, 1.0),\n"
            "        vector_literal(1.0, 0.0, 0.0),\n"
            "        vector_literal(0.0, 1.0, 0.0));\n"
            "    return Tensor.MatrixMul(P, state);\n"
            "}\n"
            'function string main() { return "ok"; }\n'
        )
        ns = _compile_and_exec(src)
        vsa = ns["_VSA"]

        def onehot(i: int) -> torch.Tensor:
            v = [0.0, 0.0, 0.0]
            v[i] = 1.0
            return torch.tensor(v, dtype=vsa.dtype, device=vsa.device)

        # e0 -> e1, e1 -> e2, e2 -> e0 (wrap).
        for i in range(3):
            got = ns["advance"](onehot(i))
            want = onehot((i + 1) % 3)
            self.assertTrue(
                torch.equal(got, want),
                f"P @ e{i}: got {got.tolist()}, want {want.tolist()}",
            )


if __name__ == "__main__":
    unittest.main()
