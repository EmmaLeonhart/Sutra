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


if __name__ == "__main__":
    unittest.main()
