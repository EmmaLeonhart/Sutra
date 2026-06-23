"""`scalar` type is a DEPRECATED alias for `number` (CLAUDE.md § "Deprecate
aliases aggressively"). It stays RECOGNIZED for frozen-archive backward compat —
so a program using it still validates with zero errors — but every use emits a
SUT0114 deprecation warning pointing at the canonical `number`.
"""
from __future__ import annotations

import unittest

from sutra_compiler.validator import validate_source


def _validate(src: str):
    return validate_source(src, file="<test>")


class TestScalarDeprecation(unittest.TestCase):
    def test_scalar_warns_but_does_not_error(self):
        bag = _validate("function scalar f(scalar x) { return x; }\n")
        self.assertFalse(bag.has_errors(), [d.format() for d in bag])
        codes = [d.code for d in bag]
        # One warning per `scalar` type occurrence (return type + param).
        self.assertEqual(codes.count("SUT0114"), 2)

    def test_number_does_not_warn(self):
        bag = _validate("function number f(number x) { return x; }\n")
        self.assertNotIn("SUT0114", [d.code for d in bag])
        self.assertFalse(bag.has_errors())


if __name__ == "__main__":
    unittest.main()
