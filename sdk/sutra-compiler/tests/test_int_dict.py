"""Regression guard — `dict<int, int>` (scalar-keyed dict) is exact on the substrate.

Emma 2026-06-13: integers get a SEPARATE dict object backed by preallocated
synthetic-space slots (one dimension per integer key), routed at compile time to
`_VSA.int_dict_{new,set,get}`. The rotation-hashmap CANNOT back this — rotations
are identity on the synthetic axes where scalar numbers live, so it returns
Σ-of-all-values for every key (measured; finding
2026-06-06-dict-int-keys-broken-blocks-arrays.md). Dedicated slots make each key
address its own dimension: no rotation, no crosstalk, exact.

Model-free (llm_model="none"); the slot addressing is substrate-pure (round +
one-hot ==, no host .item()). This is the test that proves the previous
Σ-of-values crosstalk is gone.
"""
from __future__ import annotations

import os
import sys
import unittest


def _rv(_vsa, _vec):
    return float(_vec[_vsa.semantic_dim + _vsa.AXIS_REAL])


def _compile_src(src: str, dim: int = 8):
    from sutra_compiler.lexer import Lexer
    from sutra_compiler.parser import Parser
    from sutra_compiler.codegen_pytorch import translate_module
    lx = Lexer(src, file="<test>")
    toks = lx.tokenize()
    ast = Parser(toks, file="<test>", diagnostics=lx.diagnostics).parse_module()
    assert not lx.diagnostics.has_errors(), list(lx.diagnostics)
    ns: dict = {}
    exec(translate_module(ast, llm_model="none", runtime_dim=dim), ns)
    return ns


class TestIntDict(unittest.TestCase):
    def _run(self, src: str) -> float:
        ns = _compile_src(src)
        return _rv(ns["_VSA"], ns["main"]())

    def test_single_entry(self):
        self.assertAlmostEqual(self._run(
            "function int main() { dict<int, int> a; a[0] = 42; return a[0]; }"),
            42.0, places=3)

    def test_three_entries_no_crosstalk(self):
        # The exact case that returned 148 (=42+7+99) through the rotation-hashmap.
        for key, want in ((0, 42.0), (1, 7.0), (2, 99.0)):
            src = ("function int main() { dict<int, int> a;"
                   " a[0] = 42; a[1] = 7; a[2] = 99;"
                   f" return a[{key}]; }}")
            self.assertAlmostEqual(self._run(src), want, places=3,
                                   msg=f"key {key} should read {want}, not the sum")

    def test_runtime_variable_key_and_overwrite(self):
        self.assertAlmostEqual(self._run(
            "function int main() { dict<int, int> a; int k = 3;"
            " a[k] = 55; a[k] = 77; return a[k]; }"),
            77.0, places=3)

    def test_absent_key_reads_zero(self):
        self.assertAlmostEqual(self._run(
            "function int main() { dict<int, int> a; a[0] = 42; return a[9]; }"),
            0.0, places=3)

    def test_distinct_slots_scale(self):
        self.assertAlmostEqual(self._run(
            "function int main() { dict<int, int> a;"
            " a[0] = 10; a[5] = 20; a[10] = 30; a[15] = 40;"
            " return a[0] + a[5] + a[10] + a[15]; }"),
            100.0, places=3)


if __name__ == "__main__":
    unittest.main()
