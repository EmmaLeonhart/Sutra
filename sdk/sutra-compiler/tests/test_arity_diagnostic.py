"""SUT0202 — arity checking on calls to file-declared functions (a warning).

Sutra function parameters are fixed-arity: the `Param` node carries no default
value and the parser has no varargs/optional/spread syntax, so a call to a
file-declared function must pass exactly as many args as it has params. A
mismatch is surfaced as a warning (the source is still valid v0.1 Sutra). Scoped
to plain functions — methods thread the implicit `this` separately, and
builtins/stdlib arity is not in the table. Measured 2026-07-06: 0 mismatches
across the 111 file-declared-function calls in the valid corpus.
"""
from __future__ import annotations

import glob
import os
import unittest

from sutra_compiler import validate_file, validate_source


def _sut0202(src):
    bag = validate_source(src, file="<test>")
    return [d for d in bag.warnings if d.code == "SUT0202"], bag


class TestArityWarning(unittest.TestCase):
    def test_too_few_args_warns(self):
        hits, bag = _sut0202(
            "function number add(number a, number b) { return a; }\n"
            "function number main() { return add(1); }\n"
        )
        self.assertFalse(bag.has_errors())
        self.assertEqual(len(hits), 1)
        self.assertIn("expects 2 arguments but got 1", hits[0].message)

    def test_too_many_args_warns(self):
        hits, _ = _sut0202(
            "function number id(number a) { return a; }\n"
            "function number main() { return id(1, 2, 3); }\n"
        )
        self.assertEqual(len(hits), 1)
        self.assertIn("expects 1 argument but got 3", hits[0].message)

    def test_correct_arity_does_not_warn(self):
        hits, _ = _sut0202(
            "function number add(number a, number b) { return a; }\n"
            "function number main() { return add(1, 2); }\n"
        )
        self.assertEqual(hits, [])

    def test_zero_arg_function_called_with_args_warns(self):
        hits, _ = _sut0202(
            "function number answer() { return 42; }\n"
            "function number main() { return answer(1); }\n"
        )
        self.assertEqual(len(hits), 1)
        self.assertIn("expects 0 arguments but got 1", hits[0].message)

    def test_unknown_and_builtin_calls_are_not_arity_checked(self):
        # bundle is a builtin (no table arity); Cosine is an undeclared cross-file
        # method — neither is a file-declared function, so no SUT0202.
        hits, _ = _sut0202(
            "function vector main(vector a, vector b) { return bundle(a, b, a, b); }"
        )
        self.assertEqual(hits, [])


class TestValidCorpusHasNoSut0202(unittest.TestCase):
    def test_no_sut0202_on_any_valid_corpus_file(self):
        valid_dir = os.path.join(os.path.dirname(__file__), "corpus", "valid")
        files = glob.glob(os.path.join(valid_dir, "**", "*.su"), recursive=True)
        self.assertGreater(len(files), 10)
        offenders = {}
        for path in files:
            bag = validate_file(path)
            hits = [d.format() for d in bag.warnings if d.code == "SUT0202"]
            if hits:
                offenders[os.path.basename(path)] = hits
        self.assertEqual(offenders, {}, f"SUT0202 false positives: {offenders}")


if __name__ == "__main__":
    unittest.main()
