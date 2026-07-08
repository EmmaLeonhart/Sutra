"""`+` on text values concatenates (round-17 audit fix).

Before the fix: `string a + string b` (lowercase primitive type) fell
through to ELEMENT-WISE VECTOR ADD — 'ab' + 'cd' summed codepoint axes
into two garbage characters, silently; two string LITERALS crashed at
runtime (host strs reached string_concat). Both routes now dispatch to
`_VSA.string_concat` when BOTH operands are provably text; mixed
text/number expressions are untouched (still the numeric/element-wise
paths).
"""
from __future__ import annotations

import unittest

from sutra_compiler.lexer import Lexer
from sutra_compiler.parser import Parser
from sutra_compiler.codegen_pytorch import translate_module


def _run_text(src: str, dim: int = 64) -> str:
    lx = Lexer(src, file="<t>")
    ast = Parser(lx.tokenize(), file="<t>", diagnostics=lx.diagnostics).parse_module()
    assert not lx.diagnostics.has_errors(), list(lx.diagnostics)
    ns: dict = {}
    exec(translate_module(ast, llm_model="none", runtime_dim=dim), ns)
    return ns["_VSA"].string_to_python(ns["main"]())


def _run_real(src: str, dim: int = 64) -> float:
    lx = Lexer(src, file="<t>")
    ast = Parser(lx.tokenize(), file="<t>", diagnostics=lx.diagnostics).parse_module()
    assert not lx.diagnostics.has_errors(), list(lx.diagnostics)
    ns: dict = {}
    exec(translate_module(ast, llm_model="none", runtime_dim=dim), ns)
    r = ns["main"]()
    v = ns["_VSA"]
    if not hasattr(r, "numel") or r.numel() == 1:
        return float(r)
    return float(r[v.semantic_dim + v.AXIS_REAL])


class TestTextPlusConcat(unittest.TestCase):
    def test_lowercase_string_vars(self):
        self.assertEqual(_run_text(
            'function string main(){ string a = "ab"; string b = "cd"; '
            'return a + b; }'), "abcd")

    def test_two_literals(self):
        self.assertEqual(_run_text(
            'function string main(){ return "ab" + "cd"; }'), "abcd")

    def test_chained_literals(self):
        self.assertEqual(_run_text(
            'function string main(){ return "a" + "b" + "c"; }'), "abc")

    def test_var_plus_literal(self):
        self.assertEqual(_run_text(
            'function string main(){ string a = "hi "; return a + "there"; }'),
            "hi there")

    def test_uppercase_String_vars_still_work(self):
        self.assertEqual(_run_text(
            'function string main(){ String a = make_string("x"); '
            'String b = make_string("y"); return a + b; }'), "xy")

    def test_interp_plus_literal(self):
        self.assertEqual(_run_text(
            'function string main(){ int n = 3; return $"n={n}" + "!"; }'),
            "n=3!")


class TestNumericPlusUntouched(unittest.TestCase):
    def test_int_plus_int(self):
        self.assertAlmostEqual(_run_real(
            "function int main(){ return 2 + 3; }"), 5.0, places=5)

    def test_number_var_plus_literal(self):
        self.assertAlmostEqual(_run_real(
            "function number main(){ number x = 1.5; return x + 2.0; }"),
            3.5, places=4)


class TestUserFunctionReturnConcat(unittest.TestCase):
    def test_user_string_function_plus_literal(self):
        # Round-23 regression: `f(x) + " "` with a user-declared
        # `function string f` crashed at runtime (Tensor + str) — the
        # text dispatch only knew stdlib/class return types, so the
        # literal stayed a host str on the numeric path.
        self.assertEqual(_run_text(
            'function string shout(string s){ return s + "!"; }\n'
            'function string main(){ return shout("hi") + " there"; }'),
            "hi! there")

    def test_chained_user_calls(self):
        self.assertEqual(_run_text(
            'function string tag(int n){ return int_to_string(n); }\n'
            'function string main(){ return tag(1) + "-" + tag(2); }'),
            "1-2")


if __name__ == "__main__":
    unittest.main()
