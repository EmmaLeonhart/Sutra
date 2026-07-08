"""Number-family `==` via the exact relu indicator (Emma 2026-07-08).

Cosine `==` is degenerate at the zero vector — `(15 % 3) == 0` read
NEUTRAL, making zero-testing (divisibility, emptiness, termination)
unreachable (finding 2026-07-08-zero-equality-reads-neutral...).
Emma's pick: number-family operands route through
`truth = 2·relu(1 − |x−y|) − 1` — +1 at equal, −1 at |diff| ≥ 1,
exact gap 2.0 at integer spacing, all tensor ops, differentiable a.e.
Cosine `==` stays for vector/semantic operands; the Euclidean
`eq_synthetic` stays for string/char/complex.
"""
from __future__ import annotations

import unittest

from sutra_compiler.lexer import Lexer
from sutra_compiler.parser import Parser
from sutra_compiler.codegen_pytorch import translate_module


def _truth(src: str, dim: int = 16) -> float:
    lx = Lexer(src, file="<t>")
    ast = Parser(lx.tokenize(), file="<t>", diagnostics=lx.diagnostics).parse_module()
    assert not lx.diagnostics.has_errors(), list(lx.diagnostics)
    ns: dict = {}
    exec(translate_module(ast, llm_model="none", runtime_dim=dim), ns)
    r = ns["main"]()
    v = ns["_VSA"]
    if not hasattr(r, "ndim") or r.ndim == 0:
        return float(r)
    return float(r[v.semantic_dim + v.AXIS_TRUTH])


class TestZeroEquality(unittest.TestCase):
    def test_mod_zero_is_true(self):
        # THE finding case: was 0.0 (neutral), must be +1.
        self.assertAlmostEqual(_truth(
            "function fuzzy main(){ return (15 % 3) == 0; }"), 1.0, places=4)

    def test_mod_nonzero_is_false(self):
        self.assertAlmostEqual(_truth(
            "function fuzzy main(){ return (16 % 3) == 0; }"), -1.0, places=4)

    def test_runtime_zero_vars(self):
        self.assertAlmostEqual(_truth(
            "function fuzzy main(){ number x = make_real(0.0); "
            "return x == 0; }"), 1.0, places=4)


class TestIntegerEquality(unittest.TestCase):
    def test_equal_ints(self):
        self.assertAlmostEqual(_truth(
            "function fuzzy main(){ int a = 2; int b = 2; return a == b; }"),
            1.0, places=4)

    def test_unequal_ints(self):
        self.assertAlmostEqual(_truth(
            "function fuzzy main(){ int a = 2; int b = 3; return a == b; }"),
            -1.0, places=4)

    def test_neq(self):
        self.assertAlmostEqual(_truth(
            "function fuzzy main(){ int a = 2; int b = 3; return a != b; }"),
            1.0, places=4)
        self.assertAlmostEqual(_truth(
            "function fuzzy main(){ int a = 2; int b = 2; return a != b; }"),
            -1.0, places=4)


class TestFizzBuzzEndToEnd(unittest.TestCase):
    def test_fizzbuzz_via_select(self):
        src = '''
function string fizzbuzz(int n) {
    number s3 = (number) ((n % 3) == 0);
    number s5 = (number) ((n % 5) == 0);
    return select(
        [10 * (s3 + s5), 10 * (s3 - s5), 10 * (s5 - s3), 10 * (0 - s3 - s5)],
        [make_string("fizzbuzz"), make_string("fizz"),
         make_string("buzz"), int_to_string(n)]);
}
function string main() {
    return fizzbuzz(15) + " " + fizzbuzz(3) + " " + fizzbuzz(5) + " " + fizzbuzz(7);
}
'''
        lx = Lexer(src, file="<t>")
        ast = Parser(lx.tokenize(), file="<t>",
                     diagnostics=lx.diagnostics).parse_module()
        assert not lx.diagnostics.has_errors()
        ns: dict = {}
        exec(translate_module(ast, llm_model="none", runtime_dim=64), ns)
        got = ns["_VSA"].string_to_python(ns["main"]())
        self.assertEqual(got, "fizzbuzz fizz buzz 7")


if __name__ == "__main__":
    unittest.main()
