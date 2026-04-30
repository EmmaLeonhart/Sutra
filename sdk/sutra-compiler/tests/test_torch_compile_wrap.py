"""Tests for the torch.compile wrapping (queue item 1, 'Python is just IO').

Compiled programs with loops get an opt-in `torch.compile` wrapping
appended to the emitted module. Enabled via SUTRA_TORCH_COMPILE=1.
Default off (graph-capture cost dominates cold-start for small loops).

These tests verify (a) the wrap block is in the emitted source when
loops are present, (b) the SUTRA_TORCH_COMPILE=1 path doesn't break
correctness — the compiled loop should produce the same result as
the uncompiled one.
"""
from __future__ import annotations

import os
import unittest

from sutra_compiler.codegen_pytorch import PyTorchCodegen
from sutra_compiler.inliner import inline_stdlib_calls
from sutra_compiler.lexer import Lexer
from sutra_compiler.parser import Parser


SIMPLE_DO_WHILE = """
do_while addNumber(x < 11, int x) {
    pass x + 1;
}

function int main() {
    slot int x = 9;
    loop addNumber(x < 11, x);
    return x;
}
"""


def _compile(src: str) -> str:
    lexer = Lexer(src, file="<test>")
    tokens = lexer.tokenize()
    parser = Parser(tokens, file="<test>", diagnostics=lexer.diagnostics)
    module = parser.parse_module()
    inline_stdlib_calls(module)
    cg = PyTorchCodegen()
    cg._prefetch_strings = []
    return cg.translate(module)


def _run_main(src: str):
    py = _compile(src)
    ns: dict = {}
    exec(py, ns)
    return ns["main"]()


class TestTorchCompileWrap(unittest.TestCase):
    def test_wrap_block_present_when_loop_declared(self):
        py = _compile(SIMPLE_DO_WHILE)
        self.assertIn("SUTRA_TORCH_COMPILE", py,
                      "torch.compile wrap block missing from emitted source")
        self.assertIn("_loop_addNumber = _torch.compile(", py)
        self.assertIn("SUTRA_TORCH_COMPILE_BACKEND", py)

    def test_correctness_with_compile_off(self):
        # Default path: env var unset, no torch.compile.
        old = os.environ.pop("SUTRA_TORCH_COMPILE", None)
        try:
            result = _run_main(SIMPLE_DO_WHILE)
            self.assertAlmostEqual(float(result), 11.0, places=2)
        finally:
            if old is not None:
                os.environ["SUTRA_TORCH_COMPILE"] = old

    def test_correctness_with_compile_on(self):
        # SUTRA_TORCH_COMPILE=1: wrapping kicks in. Should still produce
        # the same result.
        old = os.environ.get("SUTRA_TORCH_COMPILE")
        os.environ["SUTRA_TORCH_COMPILE"] = "1"
        try:
            result = _run_main(SIMPLE_DO_WHILE)
            self.assertAlmostEqual(float(result), 11.0, places=2)
        finally:
            if old is None:
                os.environ.pop("SUTRA_TORCH_COMPILE", None)
            else:
                os.environ["SUTRA_TORCH_COMPILE"] = old


if __name__ == "__main__":
    unittest.main()
