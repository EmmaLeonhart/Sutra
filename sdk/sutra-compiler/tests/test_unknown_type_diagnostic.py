"""SUT0200 — the v0.2 unknown-type diagnostic (a warning, not an error).

The validator now consults the symbol table (v0.2 name resolution) and warns
when a type name cannot resolve. It is open-world scoped, so it only fires on a
LOWERCASE unresolved name — a primitive/container typo like `vec`→`vector` or the
removed `scalar` — and NEVER on a PascalCase one, which may be a sibling `.su`
object file a single-file compile cannot see. That scoping is what keeps the
intentionally-open corpus files (`03_methods.su` referencing `Animal`/`Cat`)
clean; the exhaustive proof lives in
tests/test_symbol_table.py::test_full_valid_corpus_zero_reportable_false_positives.
The source is still valid Sutra (v0.1 leniency), so this is a warning: it must
not turn a valid file into an error.
"""
from __future__ import annotations

import glob
import os
import unittest

from sutra_compiler import validate_file, validate_source


def _codes(src):
    bag = validate_source(src, file="<test>")
    return bag


class TestUnknownTypeWarning(unittest.TestCase):
    def test_lowercase_type_typo_warns_sut0200(self):
        # `vec` is a typo of `vector` — the H1 surface the diagnostic exists for.
        bag = validate_source("function vec f() { return 0; }", file="<test>")
        self.assertFalse(bag.has_errors(), "a type typo is a warning, not an error")
        self.assertIn("SUT0200", [d.code for d in bag.warnings])

    def test_warning_names_the_offending_type(self):
        bag = validate_source("function vec f() { return 0; }", file="<test>")
        warn = next(d for d in bag.warnings if d.code == "SUT0200")
        self.assertIn("vec", warn.message)

    def test_removed_scalar_type_warns(self):
        # `scalar` was removed 2026-06-23; using it now reads as an unknown type.
        bag = validate_source("function scalar f() { return 0; }", file="<test>")
        self.assertIn("SUT0200", [d.code for d in bag.warnings])

    def test_pascalcase_sibling_type_does_not_warn(self):
        # Animal/Cat may be sibling object files — open world must stay silent.
        bag = validate_source(
            "method fuzzy g(Animal a) { return unsafeCast<fuzzy>(0.5); }",
            file="<test>",
        )
        self.assertNotIn("SUT0200", [d.code for d in bag.warnings])

    def test_known_types_do_not_warn(self):
        for src in (
            "function vector f() { return embed(\"x\"); }",
            "function int apply(function f, int v) { return v; }",  # function value type
            "function List<vector> w(vector v) { return [v]; }",     # capitalised container
        ):
            with self.subTest(src=src):
                bag = validate_source(src, file="<test>")
                self.assertNotIn("SUT0200", [d.code for d in bag.warnings])

    def test_declared_class_does_not_warn(self):
        bag = validate_source(
            "class Animal extends object { field vector fur; }\n"
            "method fuzzy g(Animal a) { return unsafeCast<fuzzy>(0.5); }\n",
            file="<test>",
        )
        self.assertNotIn("SUT0200", [d.code for d in bag.warnings])


class TestValidCorpusStaysErrorAndWarningClean(unittest.TestCase):
    def test_no_sut0200_on_any_valid_corpus_file(self):
        """The wired diagnostic must fire on NONE of the valid corpus files —
        the same 0-false-positive gate, exercised through the real validator."""
        valid_dir = os.path.join(os.path.dirname(__file__), "corpus", "valid")
        files = glob.glob(os.path.join(valid_dir, "**", "*.su"), recursive=True)
        self.assertGreater(len(files), 10)
        offenders = {}
        for path in files:
            bag = validate_file(path)
            hits = [d.format() for d in bag.warnings if d.code == "SUT0200"]
            if hits:
                offenders[os.path.basename(path)] = hits
        self.assertEqual(offenders, {}, f"SUT0200 false positives: {offenders}")


if __name__ == "__main__":
    unittest.main()
