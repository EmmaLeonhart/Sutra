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

    def test_sibling_unimplemented_builtins_also_warn(self):
        # make_rotation / compile_prototypes / geometric_loop share snap's trap
        # (codegen-rejected, spec'd-but-unimplemented) and now warn at SUT0151
        # too — but with the "no implemented substitute" hint, not argmax_cosine.
        for name in ("make_rotation", "compile_prototypes", "geometric_loop"):
            with self.subTest(builtin=name):
                src = (
                    "vector q = embed(\"q\");\n"
                    "function vector main() {\n"
                    f"  return {name}(q);\n"
                    "}\n"
                )
                bag = validate_source(src, file="<test>")
                self.assertFalse(bag.has_errors())
                warn = next((d for d in bag.warnings if d.code == "SUT0151"), None)
                self.assertIsNotNone(warn, f"{name} should emit SUT0151")
                self.assertIn(name, warn.message)
                self.assertNotIn("argmax_cosine", (warn.hint or ""))

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


class TestCodegenRejectionIsCleanDiagnostic(unittest.TestCase):
    """A backend codegen rejection must reach the user as a `file:line:col:
    codegen: <msg>` diagnostic on stderr (and a None compile result that the
    CLI turns into exit 1), NOT an uncaught Python traceback. Single choke
    point: __main__._compile_to_python, which --run / --emit both call."""

    def test_compile_to_python_prints_diagnostic_not_traceback(self):
        import contextlib
        import io
        import os
        import tempfile

        from sutra_compiler.__main__ import _compile_to_python

        with tempfile.NamedTemporaryFile(
            "w", suffix=".su", delete=False, encoding="utf-8"
        ) as f:
            f.write(_SNAP_SRC)
            path = f.name
        try:
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                result = _compile_to_python(path, runtime_dim=64, runtime_seed=0)
            # Rejected cleanly: None (→ CLI exit 1), not a raised exception.
            self.assertIsNone(result)
            msg = err.getvalue()
            self.assertIn("codegen:", msg)        # diagnostic shape, not a traceback
            self.assertNotIn("Traceback", msg)
            self.assertIn("argmax_cosine", msg)   # still steers the user
            self.assertIn(path, msg)              # file path prepended
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
