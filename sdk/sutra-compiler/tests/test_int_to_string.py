"""int_to_string — the substrate integer→String formatter
(strings.md § "Integer formatting").

Digit extraction is mod-free (two floors); leading zeros gate on the
quotient-significance mask; negatives gate a '-' into slot 0. Verified
against Python str() across the exactness bound (7 digits at float32).
Decode at the terminal boundary via string_to_python.
"""
from __future__ import annotations

import unittest

from sutra_compiler.lexer import Lexer
from sutra_compiler.parser import Parser
from sutra_compiler.codegen_pytorch import translate_module


def _vsa(dim: int = 64):
    lx = Lexer("function int main(){ return 0; }", file="<t>")
    ast = Parser(lx.tokenize(), file="<t>", diagnostics=lx.diagnostics).parse_module()
    ns: dict = {}
    exec(translate_module(ast, llm_model="none", runtime_dim=dim), ns)
    return ns["_VSA"]


def _run_text(src: str, dim: int = 64) -> str:
    lx = Lexer(src, file="<t>")
    ast = Parser(lx.tokenize(), file="<t>", diagnostics=lx.diagnostics).parse_module()
    assert not lx.diagnostics.has_errors(), list(lx.diagnostics)
    ns: dict = {}
    exec(translate_module(ast, llm_model="none", runtime_dim=dim), ns)
    return ns["_VSA"].string_to_python(ns["main"]())


class TestRuntimeSweep(unittest.TestCase):
    def test_matches_python_str_across_range(self):
        v = _vsa()
        cases = (list(range(0, 21)) + [42, 99, 100, 101, 999, 1000, 12345,
                 99999, 100000, 1234567, 9999999]
                 + [-1, -9, -10, -42, -100, -12345, -9999999])
        for n in cases:
            with self.subTest(n=n):
                self.assertEqual(v.string_to_python(v.int_to_string(n)), str(n))

    def test_round_contract_on_fractional_input(self):
        # INT contract: a fractional runtime value rounds first. (The
        # SURFACE walls only let int-typed values reach here; this pins
        # the runtime behaviour for values that arrive anyway.)
        v = _vsa()
        self.assertEqual(v.string_to_python(v.int_to_string(3.7)), "4")

    def test_string_length_of_render(self):
        v = _vsa()
        self.assertEqual(round(float(v.string_length(v.int_to_string(12345)))), 5)
        self.assertEqual(round(float(v.string_length(v.int_to_string(-7)))), 2)


class TestSurfaceWiring(unittest.TestCase):
    def test_string_cast_of_int_var(self):
        self.assertEqual(_run_text(
            "function string main(){ int n = 42; "
            "string s = (string) n; return s; }"), "42")

    def test_string_cast_of_int_literal(self):
        self.assertEqual(_run_text(
            "function string main(){ return (string) 5; }"), "5")

    def test_interpolation_of_int_var(self):
        self.assertEqual(_run_text(
            'function string main(){ int n = 7; return $"n={n}!"; }'),
            "n=7!")

    def test_interpolation_mixes_int_and_string(self):
        self.assertEqual(_run_text(
            'function string main(){ int n = 12; string u = "kg"; '
            'return $"{n} {u}"; }'), "12 kg")

    def test_bare_intrinsic_call(self):
        self.assertEqual(_run_text(
            "function string main(){ return int_to_string(-305); }"), "-305")


if __name__ == "__main__":
    unittest.main()
