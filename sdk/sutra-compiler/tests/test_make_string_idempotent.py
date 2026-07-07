"""make_string is idempotent on an already-String vector.

Regression for a double-wrap bug: assigning a String-typed variable from an
initializer that already produces a String (`String g = make_string("hi")`, or a
`String g = "hi"` literal whose coercion the pass also applies) wrapped the value
in a SECOND make_string. The old make_string did `s = str(s)` on a non-str input,
so the inner String vector was re-encoded from its tensor repr → garbage lengths
(every string reported length 97). make_string now returns an already-String
vector unchanged.
"""
from __future__ import annotations

import unittest

from sutra_compiler.lexer import Lexer
from sutra_compiler.parser import Parser
from sutra_compiler.codegen_pytorch import translate_module


def _run_int(src: str, dim: int = 16) -> int:
    lx = Lexer(src, file="<t>")
    ast = Parser(lx.tokenize(), file="<t>", diagnostics=lx.diagnostics).parse_module()
    assert not lx.diagnostics.has_errors(), list(lx.diagnostics)
    ns: dict = {}
    exec(translate_module(ast, llm_model="none", runtime_dim=dim), ns)
    r = ns["main"]()
    v = ns["_VSA"]
    return round(float(r) if r.numel() == 1 else float(r[v.semantic_dim + v.AXIS_REAL]))


class TestMakeStringIdempotent(unittest.TestCase):
    def test_length_of_explicit_make_string(self):
        self.assertEqual(_run_int(
            'function int main(){ String g = make_string("hello"); return string_length(g); }'), 5)

    def test_empty_string_length_zero(self):
        self.assertEqual(_run_int(
            'function int main(){ String g = make_string(""); return string_length(g); }'), 0)

    def test_concat_length(self):
        self.assertEqual(_run_int(
            'function int main(){ String a = make_string("hello"); '
            'String b = make_string("world"); return string_length(string_concat(a, b)); }'), 10)

    def test_literal_coercion_length(self):
        self.assertEqual(_run_int(
            'function int main(){ String g = "hi"; return string_length(g); }'), 2)

    def test_double_make_string_is_idempotent_directly(self):
        # make_string(make_string(x)) == make_string(x)
        lx = Lexer("function string main(){ return \"ok\"; }", file="<t>")
        ast = Parser(lx.tokenize(), file="<t>", diagnostics=lx.diagnostics).parse_module()
        ns: dict = {}
        exec(translate_module(ast, llm_model="none", runtime_dim=16), ns)
        v = ns["_VSA"]
        once = v.make_string("hello")
        twice = v.make_string(once)
        self.assertEqual(round(float(v.string_length(twice))), 5)


if __name__ == "__main__":
    unittest.main()
