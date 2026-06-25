"""`snap` diagnostics: warn early, reject clearly, steer to argmax_cosine.

`snap` is a spec'd cleanup primitive whose attractor circuit the substrate
doesn't implement yet (tutorial 03). A program that calls it is structurally
valid Sutra but cannot be lowered. The contract:

- the validator emits a SUT0151 *warning* (not an error — the source is valid)
  so an editor / `sutrac check` flags it before codegen, and
- codegen still rejects it, but with a backend-accurate message that points at
  `argmax_cosine` instead of the old, misleading "pure-numpy substrate" text.

Both surfaces name `argmax_cosine` so a newcomer who hits the trap is not left
at a dead end.
"""
from __future__ import annotations

import unittest

from sutra_compiler import validate_source
from sutra_compiler.codegen_base import CodegenNotSupported
from sutra_compiler.codegen import translate_module as translate_numpy
from sutra_compiler.codegen_pytorch import translate_module as translate_pytorch
from sutra_compiler.lexer import Lexer
from sutra_compiler.parser import Parser

_SNAP_SRC = (
    "vector q = embed(\"q\");\n"
    "function vector main() {\n"
    "  return snap(q);\n"
    "}\n"
)


def _parse(src: str):
    lexer = Lexer(src, file="<test>")
    tokens = lexer.tokenize()
    parser = Parser(tokens, file="<test>", diagnostics=lexer.diagnostics)
    module = parser.parse_module()
    assert not lexer.diagnostics.has_errors(), list(lexer.diagnostics)
    return module


class TestSnapValidatorWarning(unittest.TestCase):
    def test_snap_emits_sut0151_warning_not_error(self):
        bag = validate_source(_SNAP_SRC, file="<test>")
        # Source is valid Sutra: no errors (the valid corpus relies on this —
        # see tests/corpus/valid/15_four_state_conditional.su, 24_map_literal.su).
        self.assertFalse(
            bag.has_errors(),
            msg=f"snap source should not error: {[d.format() for d in bag.errors]}",
        )
        codes = [d.code for d in bag.warnings]
        self.assertIn("SUT0151", codes)

    def test_warning_points_at_argmax_cosine(self):
        bag = validate_source(_SNAP_SRC, file="<test>")
        warn = next(d for d in bag.warnings if d.code == "SUT0151")
        self.assertIn("argmax_cosine", (warn.hint or "") + warn.message)

    def test_plain_argmax_cosine_does_not_warn(self):
        src = (
            "vector a = embed(\"a\");\n"
            "vector q = embed(\"q\");\n"
            "function vector main() {\n"
            "  return argmax_cosine(q, [a]);\n"
            "}\n"
        )
        bag = validate_source(src, file="<test>")
        self.assertNotIn("SUT0151", [d.code for d in bag])


class TestSnapCodegenRejection(unittest.TestCase):
    def _assert_rejected(self, translate):
        module = _parse(_SNAP_SRC)
        with self.assertRaises(CodegenNotSupported) as ctx:
            translate(module)
        msg = ctx.exception.message
        # Backend-accurate (no more "pure-numpy substrate") + a way forward.
        self.assertNotIn("pure-numpy", msg)
        self.assertIn("argmax_cosine", msg)

    def test_numpy_backend_rejects_with_hint(self):
        self._assert_rejected(translate_numpy)

    def test_pytorch_backend_rejects_with_hint(self):
        self._assert_rejected(translate_pytorch)


if __name__ == "__main__":
    unittest.main()
