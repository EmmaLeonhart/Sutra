"""Corpus-level tests.

Walk the tests/corpus/valid/ tree and assert that every file parses
and validates cleanly. Walk tests/corpus/invalid/ and assert that
every file produces at least one error (or, for 11_casing_drift.su,
at least one warning).
"""

import os
import unittest

from sutra_compiler import validate_file


CORPUS_DIR = os.path.join(os.path.dirname(__file__), "corpus")
VALID_DIR = os.path.join(CORPUS_DIR, "valid")
INVALID_DIR = os.path.join(CORPUS_DIR, "invalid")


def _ak_files(directory):
    out = []
    for entry in sorted(os.listdir(directory)):
        if entry.endswith(".su"):
            out.append(os.path.join(directory, entry))
    return out


class TestValidCorpus(unittest.TestCase):
    def test_every_valid_file_has_zero_errors(self):
        for path in _ak_files(VALID_DIR):
            with self.subTest(file=os.path.basename(path)):
                bag = validate_file(path)
                errors = [d.format() for d in bag.errors]
                self.assertFalse(
                    bag.has_errors(),
                    msg=f"Expected 0 errors in {path}, got {len(bag.errors)}:\n"
                        + "\n".join(errors),
                )


class TestInvalidCorpus(unittest.TestCase):
    # Files that are expected to trigger only warnings, not errors.
    WARNING_ONLY = {"11_casing_drift.su"}

    def test_every_invalid_file_triggers_a_diagnostic(self):
        for path in _ak_files(INVALID_DIR):
            name = os.path.basename(path)
            with self.subTest(file=name):
                bag = validate_file(path)
                if name in self.WARNING_ONLY:
                    self.assertGreater(
                        len(bag.warnings),
                        0,
                        msg=f"Expected at least one warning in {path}",
                    )
                else:
                    self.assertTrue(
                        bag.has_errors(),
                        msg=f"Expected at least one error in {path}, got none",
                    )

    def test_specific_error_codes(self):
        """Each invalid file should trigger the diagnostic code its
        filename advertises."""
        expected = {
            "01_var_with_type.su": "SUT0103",
            "03_unterminated_string.su": "SUT0002",
            "05_pipe_forward.su": "SUT0110",
            "06_string_literal_cast.su": "SUT0111",
            "07_public_private_conflict.su": "SUT0112",
            "09_unterminated_block_comment.su": "SUT0001",
            "10_unsafe_cast_missing_type.su": "SUT0105",
            "11_casing_drift.su": "SUT0113",
        }
        for name, code in expected.items():
            with self.subTest(file=name):
                path = os.path.join(INVALID_DIR, name)
                bag = validate_file(path)
                codes = [d.code for d in bag]
                self.assertIn(
                    code,
                    codes,
                    msg=f"{name} should emit {code}, emitted {codes}",
                )


if __name__ == "__main__":
    unittest.main()
