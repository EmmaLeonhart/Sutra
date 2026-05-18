"""End-to-end tests for the implicit tail-recursive loop desugar
(`loop(expr){ body }` -> synthesized iterative_loop loop-function;
queue.md item 0, Emma's model).

Compiles + runs through BOTH backends and checks the numeric
result, plus the no-regression case (literal-bound `loop(N){...}`
still compile-time-unrolls and is untouched by the pass).
"""
from __future__ import annotations

import unittest

from sutra_compiler.codegen import translate_module as np_translate
from sutra_compiler.codegen_base import CodegenNotSupported
from sutra_compiler.codegen_pytorch import translate_module as torch_translate
from sutra_compiler.lexer import Lexer
from sutra_compiler.parser import Parser


def _run(translate_fn, src: str, fn: str = "main"):
    lexer = Lexer(src, file="<test>")
    tokens = lexer.tokenize()
    parser = Parser(tokens, file="<test>", diagnostics=lexer.diagnostics)
    module = parser.parse_module()
    assert not lexer.diagnostics.has_errors(), list(lexer.diagnostics)
    ns: dict = {}
    exec(translate_fn(module), ns)
    return ns[fn]()


class TestImplicitLoopDesugar(unittest.TestCase):
    SINGLE = (
        "function int main() {\n"
        "  int i = 0;\n"
        "  int x = 5;\n"
        "  loop(x) { i = i + 1; }\n"
        "  return i;\n"
        "}\n"
    )
    MULTI = (
        "function int main() {\n"
        "  int n1 = 0;\n"
        "  int n2 = 0;\n"
        "  int x = 5;\n"
        "  loop(x) { n1 = n1 + 1; n2 = n2 + 2; }\n"
        "  return n1 + n2;\n"
        "}\n"
    )
    LITERAL = (  # count != None -> compile-time unroll, pass must NOT touch
        "function int main() {\n"
        "  int s = 0;\n"
        "  loop(3) { s = s + 1; }\n"
        "  return s;\n"
        "}\n"
    )

    def test_single_var_torch(self):
        self.assertAlmostEqual(float(_run(torch_translate, self.SINGLE)), 5.0,
                               places=4)

    def test_single_var_numpy(self):
        self.assertAlmostEqual(float(_run(np_translate, self.SINGLE)), 5.0,
                               places=4)

    def test_multi_var_torch(self):
        # n1 -> 5, n2 -> 10, sum 15. The multi-var implicit axon.
        self.assertAlmostEqual(float(_run(torch_translate, self.MULTI)), 15.0,
                               places=4)

    def test_multi_var_numpy(self):
        self.assertAlmostEqual(float(_run(np_translate, self.MULTI)), 15.0,
                               places=4)

    def test_literal_bound_still_unrolls_torch(self):
        self.assertAlmostEqual(float(_run(torch_translate, self.LITERAL)),
                               3.0, places=4)

    def test_literal_bound_still_unrolls_numpy(self):
        self.assertAlmostEqual(float(_run(np_translate, self.LITERAL)),
                               3.0, places=4)

    def test_param_captured_name_is_clear_error_not_miscompile(self):
        # `acc` is a parameter, not a local VarDecl -> the desugar
        # must reject with a clear CodegenNotSupported, never silently
        # miscompile (fail-safe by design).
        src = (
            "function int run(int acc) {\n"
            "  int x = 3;\n"
            "  loop(x) { acc = acc + 1; }\n"
            "  return acc;\n"
            "}\n"
        )
        with self.assertRaises(CodegenNotSupported):
            _run(torch_translate, src, "run")


if __name__ == "__main__":
    unittest.main()
