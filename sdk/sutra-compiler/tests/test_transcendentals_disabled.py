"""Verify which transcendentals are still rejected at compile time.

Background:
- The 2026-04-29 transcendental implementations (commit e45d373) were
  withdrawn 2026-04-30 because they ran as host Python scalar
  arithmetic at runtime, not as substrate tensor ops.
- The 2026-05-10 interpolated-lookup-table architecture (see
  `planning/findings/2026-05-10-interpolated-lookup-table-works.md`)
  re-implemented exp / log / pow / sqrt as substrate-pure tensor-op
  lookups. These four now compile + run end-to-end.
- sin / cos / tan are still rejected — they need the rotation-matrix
  path (`sin(θ) = imag(exp(iθ))`) wired through, which depends on the
  complex-exp implementation.

These tests assert the still-rejected set is exactly {sin, cos, tan}
and that the now-supported set actually compiles. When trig lands,
the rejection-test halves of this file should be deleted (and any
correctness assertions added to a real math-precision test suite).
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
    return translate_fn(module)


# Trig family — still rejected pending rotation-matrix wiring.
_DISABLED_PROGRAMS = [
    ("sin", 'function scalar main() { return sin(0.5); }\n'),
    ("cos", 'function scalar main() { return cos(0.5); }\n'),
    ("tan", 'function scalar main() { return tan(0.5); }\n'),
]

# Interpolated-lookup-table family — now compiles. We only check that
# codegen produces output without raising; precision and runtime
# behavior are exercised by the runtime fixtures.
_ENABLED_PROGRAMS = [
    ("log",  'function scalar main() { return log(3.14); }\n'),
    ("sqrt", 'function scalar main() { return sqrt(2.0); }\n'),
    ("exp",  'function scalar main() { return exp(1.0); }\n'),
    ("pow",  'function scalar main() { return pow(2.0, 3.0); }\n'),
]


class TestTrigStillRejectedAtCompileTime(unittest.TestCase):
    """sin / cos / tan still raise CodegenNotSupported on both backends."""

    def test_numpy_backend_rejects_trig(self):
        for name, src in _DISABLED_PROGRAMS:
            with self.subTest(name=name, backend="numpy"):
                with pytest.raises(CodegenNotSupported) as exc_info:
                    _try_compile(np_translate, src)
                msg = str(exc_info.value)
                self.assertIn(name, msg)

    def test_torch_backend_rejects_trig(self):
        for name, src in _DISABLED_PROGRAMS:
            with self.subTest(name=name, backend="torch"):
                with pytest.raises(CodegenNotSupported) as exc_info:
                    _try_compile(torch_translate, src)
                msg = str(exc_info.value)
                self.assertIn(name, msg)


class TestExpLogPowSqrtCompile(unittest.TestCase):
    """exp / log / pow / sqrt now compile through both backends without
    raising. Runtime correctness is covered by the fixture tests under
    `sdk/sutra-from-ts/tests/fixtures/math_basic/` and the
    `experiments/interpolated_lookup_table.py` precision study."""

    def test_numpy_backend_compiles_each(self):
        for name, src in _ENABLED_PROGRAMS:
            with self.subTest(name=name, backend="numpy"):
                py = _try_compile(np_translate, src)
                self.assertIn("class _NumpyVSA", py)

    def test_torch_backend_compiles_each(self):
        for name, src in _ENABLED_PROGRAMS:
            with self.subTest(name=name, backend="torch"):
                py = _try_compile(torch_translate, src)
                self.assertIn("class _TorchVSA", py)


if __name__ == "__main__":
    unittest.main()
