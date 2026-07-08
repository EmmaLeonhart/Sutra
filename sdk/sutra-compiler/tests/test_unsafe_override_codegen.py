"""unsafeOverride(v) codegen: the pure passthrough (round-19 audit).

It suppresses a call-site type check and never changes the value —
before this it was the last special call form with no codegen
(`unsupported expression: UnsafeOverrideExpr`, hit by the corpus's
own 07_casts.su).
"""
from __future__ import annotations

import unittest

from sutra_compiler.lexer import Lexer
from sutra_compiler.parser import Parser
from sutra_compiler.codegen_pytorch import translate_module


def _run(src: str, dim: int = 16):
    lx = Lexer(src, file="<t>")
    ast = Parser(lx.tokenize(), file="<t>", diagnostics=lx.diagnostics).parse_module()
    assert not lx.diagnostics.has_errors(), list(lx.diagnostics)
    ns: dict = {}
    exec(translate_module(ast, llm_model="none", runtime_dim=dim), ns)
    return ns["main"](), ns["_VSA"]


class TestUnsafeOverridePassthrough(unittest.TestCase):
    def test_value_unchanged(self):
        r, v = _run(
            "function number main(){ number x = make_real(7.0); "
            "return unsafeOverride(x); }")
        self.assertAlmostEqual(
            float(r[v.semantic_dim + v.AXIS_REAL]), 7.0, places=5)

    def test_as_call_argument(self):
        r, v = _run(
            "function int main(){ String s = make_string(\"abc\"); "
            "return string_length(unsafeOverride(s)); }")
        self.assertEqual(round(float(r)), 3)


if __name__ == "__main__":
    unittest.main()
