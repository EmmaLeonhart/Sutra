"""SUT0201 — the v0.2 unknown-FUNCTION diagnostic ("did you mean", a warning).

Unlike types, function calls cannot use a case heuristic: unresolved names are
pervasive and legitimate in the corpus — cross-file method calls (`Cosine`,
`Bind`), external async producers (`network_lookup`), and undeclared stubs
(`matrix_rows()`). Measured 2026-07-06: real typos sit 1-2 edits from a known
function (`argmaxcosine`→`argmax_cosine`), those legitimate externals sit 7-9
away. So the diagnostic is a "did you mean" typo detector, not a plain
unresolved→warn rule: it fires ONLY when an unresolved lowercase bare call is a
near-miss (≤2 edits) of a known lowercase function. Warning, not error — the
source is still valid v0.1 Sutra.
"""
from __future__ import annotations

import glob
import os
import unittest

from sutra_compiler import validate_file, validate_source
from sutra_compiler.symbol_table import function_typo_suggestion


def _sut0201(src):
    bag = validate_source(src, file="<test>")
    return [d for d in bag.warnings if d.code == "SUT0201"], bag


class TestFunctionTypoSuggestion(unittest.TestCase):
    def test_known_typos_suggest_the_right_name(self):
        self.assertEqual(function_typo_suggestion("argmaxcosine"), "argmax_cosine")
        self.assertEqual(function_typo_suggestion("similarty"), "similarity")
        self.assertEqual(function_typo_suggestion("bundel"), "bundle")

    def test_far_names_and_pascalcase_suggest_nothing(self):
        # legitimate externals sit far from any known name
        self.assertIsNone(function_typo_suggestion("network_lookup"))
        self.assertIsNone(function_typo_suggestion("matrix_rows"))
        # PascalCase is the method convention, never compared to lowercase builtins
        self.assertIsNone(function_typo_suggestion("Cosine"))
        self.assertIsNone(function_typo_suggestion("Bind"))

    def test_exact_known_name_is_not_its_own_typo(self):
        self.assertIsNone(function_typo_suggestion("bundle"))


class TestUnknownFunctionWarning(unittest.TestCase):
    def test_argmaxcosine_typo_warns(self):
        hits, bag = _sut0201(
            "function vector m(vector a, vector b) { return argmaxcosine(a, [b]); }"
        )
        self.assertFalse(bag.has_errors())
        self.assertEqual(len(hits), 1)
        self.assertIn("argmax_cosine", hits[0].message)

    def test_legit_builtin_does_not_warn(self):
        hits, _ = _sut0201(
            "function vector m(vector a, vector b) { return bundle(a, b); }"
        )
        self.assertEqual(hits, [])

    def test_external_producer_does_not_warn(self):
        hits, _ = _sut0201(
            "async function Promise<vector> f(vector q) {\n"
            "  vector r = await network_lookup(q);\n"
            "  return r;\n"
            "}"
        )
        self.assertEqual(hits, [])

    def test_pascalcase_cross_file_call_does_not_warn(self):
        hits, _ = _sut0201(
            "function fuzzy m(vector a, vector b) { return Cosine(a, b); }"
        )
        self.assertEqual(hits, [])

    def test_first_class_function_local_is_not_flagged(self):
        # a local holding a function value, called by name, resolves via the
        # local-scope table — even if its name were near a builtin.
        hits, _ = _sut0201(
            "function vector apply(function f, vector v) { return f(v); }"
        )
        self.assertEqual(hits, [])


class TestValidCorpusHasNoSut0201(unittest.TestCase):
    def test_no_sut0201_on_any_valid_corpus_file(self):
        valid_dir = os.path.join(os.path.dirname(__file__), "corpus", "valid")
        files = glob.glob(os.path.join(valid_dir, "**", "*.su"), recursive=True)
        self.assertGreater(len(files), 10)
        offenders = {}
        for path in files:
            bag = validate_file(path)
            hits = [d.format() for d in bag.warnings if d.code == "SUT0201"]
            if hits:
                offenders[os.path.basename(path)] = hits
        self.assertEqual(offenders, {}, f"SUT0201 false positives: {offenders}")


if __name__ == "__main__":
    unittest.main()
