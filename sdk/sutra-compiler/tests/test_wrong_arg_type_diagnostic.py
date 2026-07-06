"""SUT0203 — the v0.2 wrong-argument-type diagnostic (a warning).

Powered by expression type inference + collected callee param types. It fires on
exactly ONE measured conflict: passing a `string` where a concrete non-text
primitive is expected (or the reverse) — the `similarity("cat","dog")` newcomer
error, where a raw codepoint array is handed to a slot wanting an embedding
vector. The numeric/vector family interconverts freely on the substrate, generics
accept anything, and inference returns None when unsure, so this holds 0 corpus
false positives. Warning, not error — the source is still valid v0.1 Sutra.
"""
from __future__ import annotations

import glob
import os
import unittest

from sutra_compiler import validate_file, validate_source


def _sut0203(src):
    bag = validate_source(src, file="<test>")
    return [d for d in bag.warnings if d.code == "SUT0203"], bag


class TestWrongArgTypeWarning(unittest.TestCase):
    def test_string_literal_where_vector_expected_warns(self):
        hits, bag = _sut0203(
            "function number m() { return similarity(\"cat\", \"dog\"); }"
        )
        self.assertFalse(bag.has_errors())
        self.assertEqual(len(hits), 2)  # both args
        self.assertIn("string", hits[0].message)
        self.assertIn("vector", hits[0].message)

    def test_hint_steers_to_embed(self):
        hits, _ = _sut0203(
            "function number m() { return similarity(\"cat\", \"dog\"); }"
        )
        self.assertIn("embed", hits[0].hint)

    def test_embedded_vectors_do_not_warn(self):
        hits, _ = _sut0203(
            "function number m() {\n"
            "  vector a = embed(\"cat\");\n"
            "  vector b = embed(\"dog\");\n"
            "  return similarity(a, b);\n"
            "}"
        )
        self.assertEqual(hits, [])

    def test_untyped_builtin_args_not_checked(self):
        # bundle has no declared param types -> cannot check, never a conflict.
        hits, _ = _sut0203(
            "function vector m() { return bundle(\"a\", \"b\"); }"
        )
        self.assertEqual(hits, [])

    def test_numeric_vector_family_does_not_warn(self):
        # a vector arg to a vector param, via a typed local, is fine.
        hits, _ = _sut0203(
            "function number m(vector a, vector b) { return similarity(a, b); }"
        )
        self.assertEqual(hits, [])


class TestValidCorpusHasNoSut0203(unittest.TestCase):
    def test_no_sut0203_on_any_valid_corpus_file(self):
        valid_dir = os.path.join(os.path.dirname(__file__), "corpus", "valid")
        files = glob.glob(os.path.join(valid_dir, "**", "*.su"), recursive=True)
        self.assertGreater(len(files), 10)
        offenders = {}
        for path in files:
            bag = validate_file(path)
            hits = [d.format() for d in bag.warnings if d.code == "SUT0203"]
            if hits:
                offenders[os.path.basename(path)] = hits
        self.assertEqual(offenders, {}, f"SUT0203 false positives: {offenders}")


if __name__ == "__main__":
    unittest.main()
