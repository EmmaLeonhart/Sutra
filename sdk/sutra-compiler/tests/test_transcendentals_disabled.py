"""Verify transcendental intrinsics are rejected at compile time.

Background: the 2026-04-29 transcendental implementations (commit
e45d373) were withdrawn 2026-04-30 because they ran as host Python
scalar arithmetic at runtime, not as substrate tensor ops. The
codegen now rejects calls to {log, sqrt, exp, sin, cos, tan, pow}
with `CodegenNotSupported` before they reach any backend.

These tests assert the rejection actually happens with a clear
error message — so a future session that tries to use these
intrinsics gets a fast, informative compile error pointing at
`stdlib/math.su` for the rationale, instead of an obscure runtime
failure or (worse) a silent wrong-architecture implementation.

When the transcendentals are properly re-implemented (eigenrotation-
as-modulus per the math.su TODO), this file should be deleted and
replaced with a real correctness + substrate-purity test suite.
"""
from __future__ import annotations

import unittest

import pytest

from sutra_compiler.codegen import translate_module as np_translate
from sutra_compiler.codegen_base import CodegenNotSupported
from sutra_compiler.codegen_pytorch import translate_module as torch_translate
from sutra_compiler.lexer import Lexer
from sutra_compiler.parser import Parser


def _try_compile(translate_fn, src: str):
    lexer = Lexer(src, file="<test>")
    tokens = lexer.tokenize()
    parser = Parser(tokens, file="<test>", diagnostics=lexer.diagnostics)
    module = parser.parse_module()
    assert not lexer.diagnostics.has_errors(), list(lexer.diagnostics)
    # This is the call that should raise.
    return translate_fn(module)


# Each transcendental name with a minimal program calling it. `pow`
# takes two args; the rest take one.
_PROGRAMS = [
    ("log",  'function scalar main() { return log(3.14); }\n'),
    ("sqrt", 'function scalar main() { return sqrt(2.0); }\n'),
    ("exp",  'function scalar main() { return exp(1.0); }\n'),
    ("sin",  'function scalar main() { return sin(0.5); }\n'),
    ("cos",  'function scalar main() { return cos(0.5); }\n'),
    ("tan",  'function scalar main() { return tan(0.5); }\n'),
    ("pow",  'function scalar main() { return pow(2.0, 3.0); }\n'),
]


class TestTranscendentalsRejectedAtCompileTime(unittest.TestCase):
    """Each of the seven names raises CodegenNotSupported on both backends.

    The error message must mention `stdlib/math.su` so the user finds
    the rationale doc.
    """

    def test_numpy_backend_rejects_each(self):
        for name, src in _PROGRAMS:
            with self.subTest(name=name, backend="numpy"):
                with pytest.raises(CodegenNotSupported) as exc_info:
                    _try_compile(np_translate, src)
                msg = str(exc_info.value)
                self.assertIn(name, msg)
                self.assertIn("math.su", msg)

    def test_torch_backend_rejects_each(self):
        for name, src in _PROGRAMS:
            with self.subTest(name=name, backend="torch"):
                with pytest.raises(CodegenNotSupported) as exc_info:
                    _try_compile(torch_translate, src)
                msg = str(exc_info.value)
                self.assertIn(name, msg)
                self.assertIn("math.su", msg)


class TestErrorMessageQuality(unittest.TestCase):
    """The error message should explain WHY (not just THAT) and point
    at the rationale doc.
    """

    def test_message_mentions_substrate_purity(self):
        with pytest.raises(CodegenNotSupported) as exc_info:
            _try_compile(np_translate,
                         'function scalar main() { return exp(1.0); }\n')
        msg = str(exc_info.value)
        # Should reference substrate-purity / Python-at-runtime as the why.
        self.assertTrue(
            "substrate" in msg.lower() or "python" in msg.lower(),
            f"error message should explain why; got: {msg}",
        )

    def test_message_points_at_findings_doc(self):
        with pytest.raises(CodegenNotSupported) as exc_info:
            _try_compile(np_translate,
                         'function scalar main() { return log(2.0); }\n')
        msg = str(exc_info.value)
        self.assertIn("planning/findings", msg)


if __name__ == "__main__":
    unittest.main()
