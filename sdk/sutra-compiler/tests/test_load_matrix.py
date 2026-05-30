"""Tests for the `load_matrix(path)` builtin — file-backed matrix
constants (Emma 2026-05-29, AskUserQuestion "load_matrix(path) general").

The LARGE-matrix counterpart to `matrix_literal`: `matrix M =
load_matrix("weights.su.csv")` reads a CSV (comma-separated floats, one
row per line; blank / '#' lines skipped) at the path into a frozen
substrate matrix on the runtime device+dtype, cached by path. Lets trained
weights live in a file (a weights store) instead of a 768²-entry inline
literal. Consumed by Tensor.MatrixMul.
"""
from __future__ import annotations

import os
import tempfile
import unittest

import torch

from sutra_compiler.codegen_pytorch import translate_module as torch_translate
from sutra_compiler.lexer import Lexer
from sutra_compiler.parser import Parser


def _compile(src: str, **kw):
    lx = Lexer(src, file="<t>")
    ast = Parser(lx.tokenize(), file="<t>", diagnostics=lx.diagnostics).parse_module()
    assert not lx.diagnostics.has_errors(), list(lx.diagnostics)
    py = torch_translate(ast, **kw)
    ns: dict = {}
    exec(py, ns)
    return ns, py


def _apply_src(csv_path: str) -> str:
    p = csv_path.replace("\\", "/")
    return (
        "function vector apply(vector x) {\n"
        f'    matrix M = load_matrix("{p}");\n'
        "    return Tensor.MatrixMul(M, x);\n"
        "}\n"
        'function string main() { return "ok"; }\n'
    )


class TestLoadMatrix(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()

    def _write_csv(self, name, text):
        p = os.path.join(self.d, name)
        with open(p, "w", encoding="utf-8") as f:
            f.write(text)
        return p

    def test_lowers_to_load_matrix(self):
        csv = self._write_csv("m.su.csv", "1,2\n3,4\n")
        _, py = _compile(_apply_src(csv), llm_model="none", runtime_dim=2)
        self.assertIn("_VSA.load_matrix(", py)

    def test_csv_permutation_matrix_shifts_one_hot(self):
        # 3x3 cyclic-shift permutation: P @ e_i = e_{(i+1)%3}. Comment +
        # blank lines are skipped.
        csv = self._write_csv(
            "P.su.csv", "# cyclic shift-by-1\n0,0,1\n\n1,0,0\n0,1,0\n"
        )
        ns, _ = _compile(_apply_src(csv), llm_model="none", runtime_dim=3)
        vsa = ns["_VSA"]
        for i in range(3):
            e = torch.zeros(3, dtype=vsa.dtype, device=vsa.device)
            e[i] = 1.0
            got = ns["apply"](e)
            want = (i + 1) % 3
            self.assertEqual(int(got.argmax()), want)
            self.assertAlmostEqual(float(got[want]), 1.0, places=6)

    def test_matches_matrix_literal_for_same_matrix(self):
        # load_matrix(csv) == matrix_literal(rows) for the same data.
        rows = [[0.5, -0.25, 1.0], [-1.0, 0.0, 0.125], [2.0, 3.0, -4.0]]
        csv = self._write_csv(
            "w.su.csv", "\n".join(",".join(str(v) for v in r) for r in rows)
        )
        ns_file, _ = _compile(_apply_src(csv), llm_model="none", runtime_dim=3)
        lit_rows = ",\n".join(
            "vector_literal(" + ", ".join(f"{v:.8f}" for v in r) + ")" for r in rows
        )
        lit_src = (
            "function vector apply(vector x) {\n"
            f"    matrix M = matrix_literal(\n{lit_rows});\n"
            "    return Tensor.MatrixMul(M, x);\n"
            "}\n"
            'function string main() { return "ok"; }\n'
        )
        ns_lit, _ = _compile(lit_src, llm_model="none", runtime_dim=3)
        vsa = ns_file["_VSA"]
        for i in range(3):
            e = torch.zeros(3, dtype=vsa.dtype, device=vsa.device)
            e[i] = 1.0
            a = ns_file["apply"](e)
            b = ns_lit["apply"](e)
            self.assertLess(float((a - b).abs().max()), 1e-6)

    def test_cached_by_path(self):
        # Repeat calls reuse the loaded constant (cached by path).
        csv = self._write_csv("c.su.csv", "1,0\n0,1\n")
        ns, _ = _compile(_apply_src(csv), llm_model="none", runtime_dim=2)
        vsa = ns["_VSA"]
        e = torch.tensor([1.0, 0.0], dtype=vsa.dtype, device=vsa.device)
        ns["apply"](e)
        ns["apply"](e)
        self.assertIn(csv.replace("\\", "/"), vsa._matrix_cache)


if __name__ == "__main__":
    unittest.main()
