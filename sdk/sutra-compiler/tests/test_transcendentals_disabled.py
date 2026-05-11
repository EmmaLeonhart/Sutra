"""Verify all transcendentals compile + return correct values.

This file used to assert that {log, sqrt, exp, sin, cos, tan, pow}
were rejected at codegen — that was the state from 2026-04-30 to
2026-05-09 after the host-Python implementations were withdrawn for
substrate-purity violations.

The 2026-05-10 interpolated-lookup-table architecture (see
`planning/findings/2026-05-10-interpolated-lookup-table-works.md`)
re-implemented all of them as substrate-pure runtime methods on
`_VSA`. Trig went the same lookup-table route with input modulo-
reduced to (-π, π]; hyperbolic functions beta-reduce to exp.
The disabled set is now empty.

The file name `test_transcendentals_disabled.py` is misleading at
this point — kept temporarily for git-blame continuity. When the
math-precision test suite lands, this file becomes redundant and
should be deleted.
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
