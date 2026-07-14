"""InterpolatedString codegen: `$"hello {s}!"` desugars to a
make_string / string_concat chain — all substrate ops.

Scope (usability round 16 item 2b): STRING-TYPED interpolants only.
A non-string interpolant (number/fuzzy/...) needs the substrate
number→string formatter, which is not built — those reject at codegen
with a steer, exactly like the text-cast wall in test_cast_codegen.py.

Verification decodes the returned String at the terminal boundary via
string_to_python (the sanctioned monitoring/decode boundary).
"""
from __future__ import annotations

import unittest

from sutra_compiler.lexer import Lexer
from sutra_compiler.parser import Parser
from sutra_compiler.codegen_base import CodegenNotSupported
from sutra_compiler.codegen_pytorch import translate_module


def _compile(src: str, dim: int = 16):
    lx = Lexer(src, file="<t>")
    ast = Parser(lx.tokenize(), file="<t>", diagnostics=lx.diagnostics).parse_module()
    assert not lx.diagnostics.has_errors(), list(lx.diagnostics)
    ns: dict = {}
    exec(translate_module(ast, llm_model="none", runtime_dim=dim), ns)
    return ns


def _run_text(src: str) -> str:
    ns = _compile(src)
    return ns["_VSA"].string_to_python(ns["main"]())


class TestInterpStringDesugar(unittest.TestCase):
    def test_literal_only(self):
        self.assertEqual(_run_text(
            'function string main(){ return $"hello"; }'), "hello")

    def test_one_string_interpolant(self):
        self.assertEqual(_run_text(
            'function string main(){ string s = "world"; '
            'return $"hello {s}!"; }'), "hello world!")

    def test_interpolant_at_start_and_end(self):
        self.assertEqual(_run_text(
            'function string main(){ string a = "ab"; string b = "cd"; '
            'return $"{a}-{b}"; }'), "ab-cd")

    def test_adjacent_interpolants(self):
        self.assertEqual(_run_text(
            'function string main(){ string a = "x"; string b = "y"; '
            'return $"{a}{b}"; }'), "xy")

    def test_string_literal_interpolant(self):
        self.assertEqual(_run_text(
            'function string main(){ return $"a{"b"}c"; }'), "abc")

    def test_interp_assigned_to_string_var(self):
        self.assertEqual(_run_text(
            'function string main(){ string s = "hi"; '
            'string t = $"[{s}]"; return t; }'), "[hi]")


class TestNonStringInterpolantsReject(unittest.TestCase):
    def _reject(self, src: str, needle: str):
        with self.assertRaises(CodegenNotSupported) as cm:
            _compile(src)
        self.assertIn(needle, str(cm.exception))

    def test_number_interpolant_renders_decimal(self):
        # number interpolants render via num_to_string since 2026-07-08
        # (decimal contract in test_num_to_string.py).
        self.assertEqual(_run_text(
            'function string main(){ number n = make_real(2.5); '
            'return $"n={n}"; }'), "n=2.5")

    def test_unknown_type_interpolant_rejected(self):
        # 2026-07-13: fixture moved off `similarity(...)` — stdlib calls
        # now resolve their declared return type, so that interpolant
        # legitimately formats (see the test below). A module-level user
        # function's call stays genuinely uninferable today.
        self._reject(
            'function vector mystery(){ return zero_vector(); }\n'
            'function string main(){ return $"v={mystery()}"; }',
            "statically inferable")

    def test_stdlib_number_call_interpolant_now_formats(self):
        # Improved inference (2026-07-13 Call-return-type branch):
        # `similarity` declares `number`, so the interpolant routes to
        # num_to_string — this exact form used to be rejected.
        out = _run_text(
            'function string main(){ return $"v={similarity("a", "a")}"; }')
        self.assertTrue(out.startswith("v="), out)


if __name__ == "__main__":
    unittest.main()
