"""Precision + compilation tests for the Math.* transcendentals.

Background: from 2026-04-30 to 2026-05-09 these intrinsics were
disabled at codegen because the prior implementations ran host Python
scalar arithmetic at runtime (substrate-purity violation). The
2026-05-10 interpolated-lookup-table architecture
(`planning/findings/2026-05-10-interpolated-lookup-table-works.md`)
re-implemented them as substrate-pure runtime methods. Trig went the
same lookup-table route with input modulo-reduced to (-π, π];
hyperbolic functions beta-reduce to exp.

Renamed from `test_transcendentals_disabled.py` on 2026-05-10 (spec
audit batch 2, finding F12) — the old name described the state
prior to the lookup-table fix.

These tests check that each Math.* call compiles through both
backends AND returns a value within the documented float32 +
lookup-table precision.
"""
from __future__ import annotations

import cmath
import math
import unittest

from sutra_compiler.codegen import translate_module as np_translate
from sutra_compiler.codegen_base import _TRANSCENDENTALS_DISABLED
from sutra_compiler.codegen_pytorch import translate_module as torch_translate
from sutra_compiler.lexer import Lexer
from sutra_compiler.parser import Parser


def _compile_and_run(translate_fn, src: str, fn_name: str):
    lexer = Lexer(src, file="<test>")
    tokens = lexer.tokenize()
    parser = Parser(tokens, file="<test>", diagnostics=lexer.diagnostics)
    module = parser.parse_module()
    assert not lexer.diagnostics.has_errors(), list(lexer.diagnostics)
    py = translate_fn(module)
    ns: dict = {}
    exec(py, ns)
    return ns[fn_name]()


# (program, function_name, true_value, tolerance_relative). Tolerances
# reflect the float32 runtime + N=16384 (or N=4096 for trig) lookup
# table precision. Relax if a real demo needs tighter — bumping table
# N or moving to range-reduction is the principled fix.
_PROGRAMS = [
    ('function scalar f() { return Math.exp(2.0); }\n',  "f", math.exp(2.0),    1e-3),
    ('function scalar f() { return Math.log(2.0); }\n',  "f", math.log(2.0),    1e-3),
    ('function scalar f() { return Math.sqrt(16.0); }\n', "f", 4.0,             1e-3),
    ('function scalar f() { return Math.pow(2.0, 5.0); }\n', "f", 32.0,         1e-2),
    ('function scalar f() { return Math.sin(0.5); }\n',  "f", math.sin(0.5),    1e-3),
    ('function scalar f() { return Math.cos(0.5); }\n',  "f", math.cos(0.5),    1e-3),
    ('function scalar f() { return Math.tan(0.5); }\n',  "f", math.tan(0.5),    1e-3),
    ('function scalar f() { return Math.sinh(1.0); }\n', "f", math.sinh(1.0),   1e-3),
    ('function scalar f() { return Math.cosh(1.0); }\n', "f", math.cosh(1.0),   1e-3),
    ('function scalar f() { return Math.tanh(1.0); }\n', "f", math.tanh(1.0),   1e-3),
]


class TestNoTranscendentalsDisabled(unittest.TestCase):
    """The disabled set is empty as of 2026-05-10."""

    def test_disabled_set_is_empty(self):
        self.assertEqual(_TRANSCENDENTALS_DISABLED, frozenset())


class TestAllTranscendentalsCompileAndCompute(unittest.TestCase):
    """Each Math.* call compiles and returns a value within the
    documented float32-runtime + lookup-table precision."""

    def test_torch_backend(self):
        for src, fn, true, tol in _PROGRAMS:
            with self.subTest(src=src.strip()):
                got = _compile_and_run(torch_translate, src, fn)
                rel = abs(got - true) / (abs(true) + 1e-12)
                self.assertLess(
                    rel, tol,
                    f"got={got}, true={true}, rel={rel:.2e}, tol={tol}",
                )

    def test_numpy_backend(self):
        for src, fn, true, tol in _PROGRAMS:
            with self.subTest(src=src.strip()):
                got = _compile_and_run(np_translate, src, fn)
                rel = abs(got - true) / (abs(true) + 1e-12)
                self.assertLess(
                    rel, tol,
                    f"got={got}, true={true}, rel={rel:.2e}, tol={tol}",
                )


class TestNumberScalarAlias(unittest.TestCase):
    """`number` is the canonical type name; `scalar` is a DEPRECATED
    ALIAS retained only so the frozen NeurIPS archive
    (paper/neurips/**, uneditable) keeps compiling. Both must compile
    and produce identical results.

    A `scalar` is a 0-d tensor; a Sutra `number` is a value on the
    number axis of a d-dim vector — conceptually different, which is
    why `scalar` misleads and `number` is canonical (Emma 2026-05-17).
    The existing `scalar` programs elsewhere in this suite double as
    the alias-still-works regression guard; this adds the explicit
    equivalence + canonical-name checks on both backends."""

    _PAIRS = [
        # (number_src, scalar_src, fn, expected)
        ("function number f() { number x = 2.5; return x; }\n",
         "function scalar f() { scalar x = 2.5; return x; }\n",
         "f", 2.5),
        ("function number f() { return Math.cos(0.0); }\n",
         "function scalar f() { return Math.cos(0.0); }\n",
         "f", 1.0),
        ("function number f() { return Math.exp(1.0); }\n",
         "function scalar f() { return Math.exp(1.0); }\n",
         "f", math.e),
    ]

    def _both_backends(self, src, fn):
        return (
            _compile_and_run(torch_translate, src, fn),
            _compile_and_run(np_translate, src, fn),
        )

    def test_number_canonical_and_scalar_alias_equivalent(self):
        for num_src, scal_src, fn, expected in self._PAIRS:
            with self.subTest(src=num_src.strip()):
                nt, nn = self._both_backends(num_src, fn)
                st, sn = self._both_backends(scal_src, fn)
                for got in (nt, nn, st, sn):
                    self.assertLess(
                        abs(got - expected), 1e-3,
                        f"{num_src.strip()} / scalar-alias: got={got}, "
                        f"expected={expected}",
                    )
                # number and its scalar alias must agree exactly per
                # backend (same lowering, alias is purely a parse-time
                # synonym).
                self.assertEqual(nt, st, "torch: number vs scalar alias")
                self.assertEqual(nn, sn, "numpy: number vs scalar alias")


class TestComplexArgumentCosine(unittest.TestCase):
    """`Math.ccos(complex z)` = (e^(i z) + e^(-i z))/2, the complex-
    argument cosine. Ground-truth vs Python `cmath.cos`.

    Torch backend only: the numpy codegen is deprecated and has no
    `cexp` (the keystone ccos reduces onto), so it cannot express this
    op. Asserting it there would be testing a backend the spec is
    retiring; the canonical compile target is PyTorch (CLAUDE.md).

    Cases cover: real argument (imag 0 — must equal the paper-cited
    real cos and carry zero imaginary part), pure-imaginary argument
    (cos(i) = cosh 1, the geometric imaginary-output path), and two
    general complex points. Absolute tolerance 2e-2 — float32 runtime
    + N=16384 exp / N=4096 trig lookup tables, the same precision
    class as the `pow` case above; near-zero components make a
    relative bound meaningless, so the bound is absolute per
    component. Measured, not tuned: if a real demo needs tighter, the
    principled fix is bigger tables / range reduction, not a looser
    bound here."""

    # (a, b) for z = a + b*i
    _CASES = [
        (0.0, 0.0),
        (0.5, 0.0),   # real arg: must match real cos, imag == 0
        (0.0, 1.0),   # cos(i) = cosh(1) ≈ 1.5430806, imag 0
        (0.5, 1.0),   # general: ≈ 1.38423 - 0.63496 i
        (1.0, 2.0),   # general: ≈ 2.03272 - 3.05190 i
    ]
    _TOL = 2e-2

    def _run_part(self, a: float, b: float, part: str) -> float:
        src = (
            f"function scalar f() {{ return "
            f"Math.ccos(complex_number({a!r}, {b!r})).{part}(); }}\n"
        )
        return _compile_and_run(torch_translate, src, "f")

    def test_ccos_vs_cmath(self):
        for a, b in self._CASES:
            true = cmath.cos(complex(a, b))
            with self.subTest(z=f"{a}+{b}i", part="real"):
                got_r = self._run_part(a, b, "real")
                self.assertLess(
                    abs(got_r - true.real), self._TOL,
                    f"Re ccos({a}+{b}i): got={got_r}, "
                    f"true={true.real}, |Δ|={abs(got_r - true.real):.2e}",
                )
            with self.subTest(z=f"{a}+{b}i", part="imag"):
                got_i = self._run_part(a, b, "imag")
                self.assertLess(
                    abs(got_i - true.imag), self._TOL,
                    f"Im ccos({a}+{b}i): got={got_i}, "
                    f"true={true.imag}, |Δ|={abs(got_i - true.imag):.2e}",
                )


if __name__ == "__main__":
    unittest.main()
