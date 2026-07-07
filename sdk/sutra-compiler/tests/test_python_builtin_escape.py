"""SUT0204 — the Python-builtin host-escape-hatch diagnostic (a warning).

Unknown call-position names lower to bare Python names, so a `.su` that calls a
Python builtin (`print`, `str`, `len`) silently executes on the host — against the
no-mid-computation-I/O identity (finding 2026-07-04-python-builtin-fallthrough.md).
SUT0204 warns on a call whose name is a callable Python builtin AND resolves to no
Sutra function/local/class. It takes priority over the SUT0201 typo guess (naming
the builtin beats "did you mean <near Sutra fn>"). Warning, not error; measured 0
valid-corpus false positives.
"""
from __future__ import annotations

import glob
import os
import unittest

from sutra_compiler import validate_file, validate_source


def _codes(src, code):
    return [d for d in validate_source(src, file="<t>").warnings if d.code == code]


class TestPythonBuiltinEscape(unittest.TestCase):
    def test_print_warns(self):
        hits = _codes('function vector m() { print(embed("x")); return embed("x"); }', "SUT0204")
        self.assertEqual(len(hits), 1)
        self.assertIn("print", hits[0].message)

    def test_str_len_warn(self):
        hits = _codes('function string m() { return str(len("ab")); }', "SUT0204")
        self.assertEqual({"str", "len"}, {w.message.split("`")[1] for w in hits})

    def test_takes_priority_over_typo_suggestion(self):
        # `len` is within edit distance of a Sutra fn (would draw SUT0201) — the
        # escape-hatch warning must win instead.
        src = 'function number m() { return len("ab"); }'
        self.assertEqual(len(_codes(src, "SUT0204")), 1)
        self.assertEqual(_codes(src, "SUT0201"), [])

    def test_real_typo_still_gets_suggestion(self):
        # a genuine Sutra-function typo (not a Python builtin) still gets SUT0201.
        src = "function vector m(vector a, vector b) { return argmaxcosine(a, [b]); }"
        self.assertEqual(_codes(src, "SUT0204"), [])
        self.assertEqual(len(_codes(src, "SUT0201")), 1)

    def test_legit_sutra_calls_silent(self):
        for src in ('function vector m() { return embed("x"); }',
                    'function vector m(vector a, vector b) { return bundle(a, b); }'):
            self.assertEqual(_codes(src, "SUT0204"), [])


class TestValidCorpusNoSut0204(unittest.TestCase):
    def test_no_sut0204_on_valid_corpus(self):
        d = os.path.join(os.path.dirname(__file__), "corpus", "valid")
        root = os.path.abspath(os.path.join(d, "..", "..", ".."))
        files = (glob.glob(os.path.join(d, "**", "*.su"), recursive=True)
                 + glob.glob(os.path.join(root, "examples", "**", "*.su"), recursive=True))
        offenders = {os.path.basename(f): [w.format() for w in validate_file(f).warnings if w.code == "SUT0204"]
                     for f in files}
        offenders = {k: v for k, v in offenders.items() if v}
        self.assertEqual(offenders, {})


if __name__ == "__main__":
    unittest.main()
