"""Tests for the transcendental math intrinsics (exp, log, sin, cos, tan, sqrt, pow).

Both the numpy backend (codegen.py) and the torch backend
(codegen_pytorch.py) emit a `_VSA._real_exp_scalar`,
`_VSA._real_log_scalar`, etc. Tests compile a tiny module, exec the
prelude, and check the math methods give the right answers vs Python's
math module.

The architecture:
- exp(z) for complex z = re + i*im: realExp(re) via Taylor + squaring,
  cos(im) and sin(im) via the eigenrotation primitive (substrate-level
  rotation matrix entries). Composed via make_complex.
- log(z) = ln|z| + i*atan2(im, re). ln via frexp + artanh series.
  atan2 via Gregory series + quadrant decomposition.
- sin/cos handle complex inputs via cosh/sinh (which reuse realExp).
- sqrt = exp(0.5 * log).
- pow(x, y) = exp(y * log(x)).

See planning/findings/2026-04-29-bound-table-capacity-limit.md for why
the bound-table-via-binding architecture (the originally-sketched
design) is used only for cos/sin (where it works exactly via
eigenrotation) and not for exp/log.
"""
from __future__ import annotations

import math
import unittest

from sutra_compiler.codegen import translate_module as np_translate
from sutra_compiler.codegen_pytorch import translate_module as torch_translate
from sutra_compiler.lexer import Lexer
from sutra_compiler.parser import Parser


def _compile_and_exec(translate_fn, src: str) -> dict:
    """Compile the src and exec the prelude part (everything before main)."""
    lexer = Lexer(src, file="<test>")
    tokens = lexer.tokenize()
    parser = Parser(tokens, file="<test>", diagnostics=lexer.diagnostics)
    module = parser.parse_module()
    assert not lexer.diagnostics.has_errors(), list(lexer.diagnostics)
    py_src = translate_fn(module)
    # Trim off main() and below — we only need the _VSA class instance.
    head = py_src.split("def main(")[0]
    namespace = {}
    exec(head, namespace)
    return namespace


# Smallest valid module so codegen emits a full prelude.
TRIVIAL_SRC = 'function vector main() { return basis_vector("x"); }\n'


class TestRealExp(unittest.TestCase):
    """realExp via Taylor + squaring on bounded domain."""

    def setUp(self):
        self.ns = _compile_and_exec(np_translate, TRIVIAL_SRC)
        self.vsa = self.ns["_VSA"]

    def test_exp_zero(self):
        self.assertAlmostEqual(self.vsa._real_exp_scalar(0.0), 1.0, places=15)

    def test_exp_one(self):
        self.assertAlmostEqual(self.vsa._real_exp_scalar(1.0), math.e, places=14)

    def test_exp_negative(self):
        self.assertAlmostEqual(self.vsa._real_exp_scalar(-1.0), 1.0 / math.e, places=14)

    def test_exp_mid_range(self):
        for x in [-5.0, -2.5, -1.0, 0.0, 1.0, 2.5, 5.0, 10.0]:
            self.assertAlmostEqual(
                self.vsa._real_exp_scalar(x), math.exp(x),
                delta=abs(math.exp(x)) * 1e-12,
                msg=f"exp({x})",
            )

    def test_exp_clips_at_bound(self):
        # x > EXP_BOUND clips to EXP_BOUND.
        result = self.vsa._real_exp_scalar(100.0)
        expected = math.exp(self.vsa.EXP_BOUND)
        self.assertAlmostEqual(result, expected,
                               delta=abs(expected) * 1e-10)


class TestRealLog(unittest.TestCase):
    """realLog via frexp + artanh series. FP-precise on positive float64."""

    def setUp(self):
        self.ns = _compile_and_exec(np_translate, TRIVIAL_SRC)
        self.vsa = self.ns["_VSA"]

    def test_log_one(self):
        self.assertEqual(self.vsa._real_log_scalar(1.0), 0.0)

    def test_log_e(self):
        self.assertAlmostEqual(self.vsa._real_log_scalar(math.e), 1.0, places=14)

    def test_log_wide_range(self):
        # frexp range reduction means precision holds across the full
        # positive float64 range, not just near 1.
        for x in [1e-12, 1e-6, 0.001, 0.5, 1.0, 2.0, 10.0, 100.0, 1e6, 1e12]:
            self.assertAlmostEqual(
                self.vsa._real_log_scalar(x), math.log(x),
                delta=abs(math.log(x)) * 1e-13 + 1e-15,
                msg=f"ln({x})",
            )

    def test_log_zero_returns_minus_inf(self):
        self.assertEqual(self.vsa._real_log_scalar(0.0), float("-inf"))

    def test_log_negative_returns_nan(self):
        result = self.vsa._real_log_scalar(-1.0)
        self.assertTrue(math.isnan(result))


class TestComplexExp(unittest.TestCase):
    """Complex exp(z) = exp(re)*(cos(im) + i*sin(im)). Composition test."""

    def setUp(self):
        self.ns = _compile_and_exec(np_translate, TRIVIAL_SRC)
        self.vsa = self.ns["_VSA"]

    def _exp(self, re, im):
        v = self.vsa.make_complex(re, im)
        result = self.vsa.exp(v)
        return (
            float(result[self.vsa.semantic_dim + self.vsa.AXIS_REAL]),
            float(result[self.vsa.semantic_dim + self.vsa.AXIS_IMAG]),
        )

    def test_exp_zero(self):
        re, im = self._exp(0.0, 0.0)
        self.assertAlmostEqual(re, 1.0, places=15)
        self.assertAlmostEqual(im, 0.0, places=15)

    def test_exp_real(self):
        re, im = self._exp(1.0, 0.0)
        self.assertAlmostEqual(re, math.e, places=13)
        self.assertAlmostEqual(im, 0.0, places=13)

    def test_exp_pure_imag(self):
        # exp(i * pi/2) = cos(pi/2) + i*sin(pi/2) = 0 + i*1
        re, im = self._exp(0.0, math.pi / 2.0)
        self.assertAlmostEqual(re, 0.0, places=14)
        self.assertAlmostEqual(im, 1.0, places=14)

    def test_exp_minus_pi_i(self):
        # e^(i*pi) = -1
        re, im = self._exp(0.0, math.pi)
        self.assertAlmostEqual(re, -1.0, places=14)
        self.assertAlmostEqual(im, 0.0, places=14)

    def test_exp_one_plus_i(self):
        re, im = self._exp(1.0, 1.0)
        self.assertAlmostEqual(re, math.e * math.cos(1.0), places=13)
        self.assertAlmostEqual(im, math.e * math.sin(1.0), places=13)


class TestComplexLog(unittest.TestCase):
    """Complex log(z) = ln|z| + i*atan2(im, re)."""

    def setUp(self):
        self.ns = _compile_and_exec(np_translate, TRIVIAL_SRC)
        self.vsa = self.ns["_VSA"]

    def _log(self, re, im):
        v = self.vsa.make_complex(re, im)
        result = self.vsa.log(v)
        return (
            float(result[self.vsa.semantic_dim + self.vsa.AXIS_REAL]),
            float(result[self.vsa.semantic_dim + self.vsa.AXIS_IMAG]),
        )

    def test_log_one(self):
        re, im = self._log(1.0, 0.0)
        self.assertEqual(re, 0.0)
        self.assertEqual(im, 0.0)

    def test_log_e(self):
        re, im = self._log(math.e, 0.0)
        self.assertAlmostEqual(re, 1.0, places=14)
        self.assertEqual(im, 0.0)

    def test_log_negative_one(self):
        # ln(-1) = i*pi
        re, im = self._log(-1.0, 0.0)
        self.assertAlmostEqual(re, 0.0, places=14)
        self.assertAlmostEqual(im, math.pi, places=14)

    def test_log_pure_imag(self):
        # ln(i) = i*pi/2
        re, im = self._log(0.0, 1.0)
        self.assertAlmostEqual(re, 0.0, places=14)
        self.assertAlmostEqual(im, math.pi / 2.0, places=14)

    def test_log_zero(self):
        re, im = self._log(0.0, 0.0)
        self.assertEqual(re, float("-inf"))


class TestSinCos(unittest.TestCase):
    """sin/cos via eigenrotation (R(theta) applied to (1, 0))."""

    def setUp(self):
        self.ns = _compile_and_exec(np_translate, TRIVIAL_SRC)
        self.vsa = self.ns["_VSA"]

    def test_cos_zero(self):
        v = self.vsa.make_real(0.0)
        result = self.vsa.cos(v)
        self.assertAlmostEqual(
            float(result[self.vsa.semantic_dim + self.vsa.AXIS_REAL]),
            1.0, places=15,
        )

    def test_sin_zero(self):
        v = self.vsa.make_real(0.0)
        result = self.vsa.sin(v)
        self.assertAlmostEqual(
            float(result[self.vsa.semantic_dim + self.vsa.AXIS_REAL]),
            0.0, places=15,
        )

    def test_sin_cos_at_pi_4(self):
        v = self.vsa.make_real(math.pi / 4.0)
        cv = self.vsa.cos(v)
        sv = self.vsa.sin(v)
        cos_val = float(cv[self.vsa.semantic_dim + self.vsa.AXIS_REAL])
        sin_val = float(sv[self.vsa.semantic_dim + self.vsa.AXIS_REAL])
        self.assertAlmostEqual(cos_val, math.sqrt(2) / 2, places=14)
        self.assertAlmostEqual(sin_val, math.sqrt(2) / 2, places=14)

    def test_sin_cos_pythagorean(self):
        # sin^2 + cos^2 = 1 across many angles
        for theta in [-2.0, -1.0, 0.5, 1.5, 2.5]:
            v = self.vsa.make_real(theta)
            cv = self.vsa.cos(v)
            sv = self.vsa.sin(v)
            cos_val = float(cv[self.vsa.semantic_dim + self.vsa.AXIS_REAL])
            sin_val = float(sv[self.vsa.semantic_dim + self.vsa.AXIS_REAL])
            self.assertAlmostEqual(cos_val * cos_val + sin_val * sin_val,
                                   1.0, places=13)


class TestSqrtPowTan(unittest.TestCase):
    """sqrt, pow, tan derived from exp / log / sin / cos."""

    def setUp(self):
        self.ns = _compile_and_exec(np_translate, TRIVIAL_SRC)
        self.vsa = self.ns["_VSA"]

    def _eval(self, fn, *args):
        result = fn(*args)
        return (
            float(result[self.vsa.semantic_dim + self.vsa.AXIS_REAL]),
            float(result[self.vsa.semantic_dim + self.vsa.AXIS_IMAG]),
        )

    def test_sqrt_four(self):
        re, im = self._eval(self.vsa.sqrt, self.vsa.make_real(4.0))
        self.assertAlmostEqual(re, 2.0, places=12)
        self.assertAlmostEqual(im, 0.0, places=12)

    def test_sqrt_two(self):
        re, im = self._eval(self.vsa.sqrt, self.vsa.make_real(2.0))
        self.assertAlmostEqual(re, math.sqrt(2.0), places=12)
        self.assertAlmostEqual(im, 0.0, places=12)

    def test_sqrt_negative_one(self):
        # sqrt(-1) = i
        re, im = self._eval(self.vsa.sqrt, self.vsa.make_real(-1.0))
        self.assertAlmostEqual(re, 0.0, places=13)
        self.assertAlmostEqual(im, 1.0, places=13)

    def test_pow_two_three(self):
        # 2^3 = 8
        re, im = self._eval(
            self.vsa.pow,
            self.vsa.make_real(2.0),
            self.vsa.make_real(3.0),
        )
        self.assertAlmostEqual(re, 8.0, places=12)
        self.assertAlmostEqual(im, 0.0, places=12)

    def test_pow_e_one(self):
        # e^1 = e
        re, im = self._eval(
            self.vsa.pow,
            self.vsa.make_real(math.e),
            self.vsa.make_real(1.0),
        )
        self.assertAlmostEqual(re, math.e, places=13)

    def test_tan_zero(self):
        re, im = self._eval(self.vsa.tan, self.vsa.make_real(0.0))
        self.assertAlmostEqual(re, 0.0, places=14)
        self.assertAlmostEqual(im, 0.0, places=14)

    def test_tan_pi_4(self):
        # tan(pi/4) = 1
        re, im = self._eval(self.vsa.tan, self.vsa.make_real(math.pi / 4.0))
        self.assertAlmostEqual(re, 1.0, places=13)


class TestPyTorchBackend(unittest.TestCase):
    """The pytorch backend should expose the same methods. Spot check."""

    def setUp(self):
        self.ns = _compile_and_exec(torch_translate, TRIVIAL_SRC)
        self.vsa = self.ns["_VSA"]

    def test_exp_one(self):
        v = self.vsa.make_real(1.0)
        result = self.vsa.exp(v)
        re = float(result[self.vsa.semantic_dim + self.vsa.AXIS_REAL].item())
        self.assertAlmostEqual(re, math.e, places=5)  # torch float32

    def test_log_e(self):
        v = self.vsa.make_real(math.e)
        result = self.vsa.log(v)
        re = float(result[self.vsa.semantic_dim + self.vsa.AXIS_REAL].item())
        self.assertAlmostEqual(re, 1.0, places=5)

    def test_cos_zero(self):
        v = self.vsa.make_real(0.0)
        result = self.vsa.cos(v)
        re = float(result[self.vsa.semantic_dim + self.vsa.AXIS_REAL].item())
        self.assertAlmostEqual(re, 1.0, places=6)


if __name__ == "__main__":
    unittest.main()
