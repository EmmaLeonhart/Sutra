"""End-to-end tests for Sutra-native arrow / anonymous function values.

Sutra has no runtime closures (planning/open-questions/function-
taxonomy-and-closure.md). An arrow `(params) => expr` is desugared at
parse time into a hoisted top-level function with a fresh name
(`__arrow_N`); the arrow expression is replaced by an Identifier
referencing it. Captured enclosing-scope locals are lifted to extra
trailing parameters and threaded as extra arguments at every *direct*
call site.

These tests RUN each verification target on the PyTorch backend at
runtime_dim=64 and compare the decoded result against ground truth —
"it parsed" is not sufficient (per CLAUDE.md integrity rules).

Capture boundary (asserted below):
  - no-capture arrows: work, including when passed to a higher-order
    function (the function value is just a name).
  - capturing arrows called directly (or via a `var` alias that is
    directly called): work — the captured local is threaded at the
    call site.
  - capturing arrows passed as a *value* to a higher-order function:
    rejected with SUT0140 (a clear compile error, never a miscompile),
    because the captured local cannot travel with the reference in a
    closure-free language.
"""
from __future__ import annotations

import unittest

import torch

from sutra_compiler.codegen_pytorch import translate_module
from sutra_compiler.lexer import Lexer
from sutra_compiler.parser import Parser


def _parse(src: str):
    lexer = Lexer(src, file="<test>")
    tokens = lexer.tokenize()
    parser = Parser(tokens, file="<test>", diagnostics=lexer.diagnostics)
    module = parser.parse_module()
    return module, lexer.diagnostics


def _decode(result, ns) -> float:
    """Decode a `main()` result to a scalar off the real axis.

    Int-typed returns already come back decoded as a Python float at
    this runtime config; a raw substrate vector is projected onto the
    real axis via `dot(result, make_real(1.0))`. Both paths reduce to
    the same scalar.
    """
    if isinstance(result, torch.Tensor):
        return float(torch.dot(result, ns["_VSA"].make_real(1.0)))
    return float(result)


def _run(src: str, fn: str = "main") -> float:
    module, diags = _parse(src)
    assert not diags.has_errors(), [d.format() for d in diags]
    ns: dict = {}
    exec(translate_module(module, runtime_dim=64), ns)
    return _decode(ns[fn](), ns)


class TestArrowFunctions(unittest.TestCase):
    def test_no_capture_passed_to_higher_order(self):
        # Verification target 1: `apply((int x) => x * 2, 5)` -> 10.
        src = (
            "function int apply(function f, int v) { return f(v); }\n"
            "function int main() { return apply((int x) => x * 2, 5); }\n"
        )
        self.assertAlmostEqual(_run(src), 10.0, places=4)

    def test_block_body(self):
        # Verification target 2: block-body arrow -> 6.
        src = (
            "function int apply(function f, int v) { return f(v); }\n"
            "function int main() {\n"
            "  return apply((int x) => { return x + 1; }, 5);\n"
            "}\n"
        )
        self.assertAlmostEqual(_run(src), 6.0, places=4)

    def test_direct_call_capture(self):
        # Verification target 3 (direct-call form): the captured
        # `multiplier` is lifted to a trailing param and threaded at the
        # `scale(7)` call site -> 35.
        src = (
            "function int main() {\n"
            "  int multiplier = 5;\n"
            "  var scale = (int x) => x * multiplier;\n"
            "  return scale(7);\n"
            "}\n"
        )
        self.assertAlmostEqual(_run(src), 35.0, places=4)

    def test_immediately_invoked_no_capture_alias(self):
        # A no-capture arrow bound to a var and called directly.
        src = (
            "function int main() {\n"
            "  var d = (int x) => x * 3;\n"
            "  return d(4);\n"
            "}\n"
        )
        self.assertAlmostEqual(_run(src), 12.0, places=4)

    def test_higher_order_capture_is_rejected(self):
        # Boundary: a capturing arrow passed as a value to a higher-
        # order function is a clear compile error (SUT0140), NOT a
        # silent miscompile.
        src = (
            "function int apply(function f, int v) { return f(v); }\n"
            "function int main() {\n"
            "  int multiplier = 5;\n"
            "  return apply((int x) => x * multiplier, 7);\n"
            "}\n"
        )
        module, diags = _parse(src)
        self.assertTrue(diags.has_errors())
        codes = [d.code for d in diags]
        self.assertIn("SUT0140", codes)

    def test_two_arrows_get_distinct_deterministic_names(self):
        # Two arrows in one program hoist to __arrow_0 and __arrow_1
        # (deterministic, no Math.random / Date).
        src = (
            "function int apply(function f, int v) { return f(v); }\n"
            "function int main() {\n"
            "  return apply((int x) => x * 2, 3)\n"
            "       + apply((int y) => y + 10, 3);\n"
            "}\n"
        )
        module, diags = _parse(src)
        self.assertFalse(diags.has_errors(), [d.format() for d in diags])
        names = {it.name for it in module.items if hasattr(it, "name")}
        self.assertIn("__arrow_0", names)
        self.assertIn("__arrow_1", names)
        # 3*2 + (3+10) = 6 + 13 = 19.
        self.assertAlmostEqual(_run(src), 19.0, places=4)


if __name__ == "__main__":
    unittest.main()
