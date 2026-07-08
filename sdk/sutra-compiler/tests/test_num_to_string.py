"""num_to_string — the decimal display formatter (strings.md § Decimal
formatting; Emma re-flagged the interpolation tail 2026-07-08).

Contract: shortest decimal with at most 6 fractional digits
(round-half-away at the 6th), trailing fractional zeros trimmed,
integral values render with no decimal point ("3.0" -> "3" — documented
divergence from Python str). Expected strings are EXPLICIT here, not
compared to str(), because the contract deliberately differs.
"""
from __future__ import annotations

import unittest

from sutra_compiler.lexer import Lexer
from sutra_compiler.parser import Parser
from sutra_compiler.codegen_pytorch import translate_module


def _vsa(dim: int = 96):
    lx = Lexer("function int main(){ return 0; }", file="<t>")
    ast = Parser(lx.tokenize(), file="<t>", diagnostics=lx.diagnostics).parse_module()
    ns: dict = {}
    exec(translate_module(ast, llm_model="none", runtime_dim=dim), ns)
    return ns["_VSA"]


class TestDecimalRendering(unittest.TestCase):
    def test_cases(self):
        v = _vsa()
        cases = [
            (3.14, "3.14"),
            (0.5, "0.5"),
            (-0.5, "-0.5"),
            (3.0, "3"),
            (0.0, "0"),
            (-3.14, "-3.14"),
            (3.05, "3.05"),
            (0.000125, "0.000125"),
            (12.345678, "12.345678"),
            (1.9999995, "2"),          # rounds at the 6th place, carries
            (42.0, "42"),
            (-7.25, "-7.25"),
        ]
        for x, exp in cases:
            with self.subTest(x=x):
                got = v.string_to_python(v.num_to_string(x))
                self.assertEqual(got, exp)


class TestSurfaceWiring(unittest.TestCase):
    def _run_text(self, src: str, dim: int = 96) -> str:
        lx = Lexer(src, file="<t>")
        ast = Parser(lx.tokenize(), file="<t>",
                     diagnostics=lx.diagnostics).parse_module()
        assert not lx.diagnostics.has_errors(), list(lx.diagnostics)
        ns: dict = {}
        exec(translate_module(ast, llm_model="none", runtime_dim=dim), ns)
        return ns["_VSA"].string_to_python(ns["main"]())

    def test_number_interpolant(self):
        self.assertEqual(self._run_text(
            'function string main(){ number x = make_real(3.14); '
            'return $"pi={x}"; }'), "pi=3.14")

    def test_string_cast_of_number(self):
        self.assertEqual(self._run_text(
            "function string main(){ number x = make_real(0.5); "
            "return (string) x; }"), "0.5")

    def test_int_interpolant_still_integer_shaped(self):
        self.assertEqual(self._run_text(
            'function string main(){ int n = 7; return $"n={n}"; }'), "n=7")


if __name__ == "__main__":
    unittest.main()
