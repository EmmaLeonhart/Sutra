"""SUT0205 — unknown VARIABLE diagnostic (round-18 audit).

Before this: `return totl + 1;` (typo of `total`) validated CLEAN and
died at runtime as a raw Python NameError — while functions (SUT0201),
types (SUT0200), arity (SUT0202) all had polished diagnostics.
Variables were the one hole left.

Fires as a WARNING (source is still valid v0.1 Sutra) on a bare
identifier expression that resolves to no local/param, file-scope
name, function, class, type param, contextual keyword, or Python
builtin. Callee positions are owned by SUT0201/0204 and never
double-report. Zero false positives over the valid corpus is the
shipped bar (checked by test_corpus-style sweep below).
"""
from __future__ import annotations

import glob
import os
import unittest

from sutra_compiler import validate_source


def _diags(src: str):
    bag = validate_source(src, file="<t>")
    return [d for d in bag.warnings if d.code == "SUT0205"]


class TestFires(unittest.TestCase):
    def test_undefined_variable(self):
        d = _diags("function int main(){ return undefined_var + 1; }")
        self.assertEqual(len(d), 1)
        self.assertIn("undefined_var", str(d[0]))

    def test_typo_of_local_gets_suggestion(self):
        d = _diags("function int main(){ int total = 5; return totl + 1; }")
        self.assertEqual(len(d), 1)
        self.assertIn("total", str(d[0]))  # did-you-mean

    def test_typo_of_file_scope_var(self):
        d = _diags(
            'vector greeting = embed("hi");\n'
            "function vector main(){ return greetng; }")
        self.assertEqual(len(d), 1)
        self.assertIn("greeting", str(d[0]))


class TestDoesNotFire(unittest.TestCase):
    def _clean(self, src: str):
        self.assertEqual(_diags(src), [])

    def test_locals_and_params(self):
        self._clean("function int add(int a, int b){ int c = a + b; return c; }")

    def test_file_scope_var(self):
        self._clean(
            'vector g = embed("hi");\n'
            "function vector main(){ return g; }")

    def test_foreach_loop_var(self):
        self._clean(
            "function int main(){ int s = 0; "
            "foreach (int x in [1, 2, 3]) { s = s + x; } return s; }")

    def test_iterator_keyword_in_iterative_loop(self):
        self._clean(
            "iterative_loop count(3, int acc) { pass acc + iterator; }\n"
            "function int main(){ return loop count(3, 0); }")

    def test_loop_state_params(self):
        self._clean(
            "while_loop grow(x < 10, int x) { pass x + 1; }\n"
            "function int main(){ return loop grow(1); }")

    def test_callee_position_not_double_reported(self):
        # unknown FUNCTION is SUT0201's job; SUT0205 must stay silent.
        d = _diags(
            'function int main(){ vector w = argmaxcosine(embed("a"), '
            '[embed("b")]); return 1; }')
        self.assertEqual(d, [])

    def test_this_in_method(self):
        self._clean(
            "class Cat { int lives; method int get(){ return this.lives; } }\n"
            "function int main(){ return 9; }")

    def test_class_name_as_namespace(self):
        self._clean("function number main(){ return Math.PI; }")


class TestCorpusZeroFalsePositives(unittest.TestCase):
    def test_valid_corpus_produces_no_sut0205(self):
        from sutra_compiler import validate_file
        here = os.path.dirname(os.path.abspath(__file__))
        pattern = os.path.join(here, "corpus", "valid", "*.su")
        files = sorted(glob.glob(pattern))
        assert files, "corpus not found"
        offenders = []
        for path in files:
            bag = validate_file(path)
            for d in bag.warnings:
                if d.code == "SUT0205":
                    offenders.append(f"{os.path.basename(path)}: {d}")
        self.assertEqual(offenders, [],
                         "SUT0205 false positives:\n" + "\n".join(offenders))


if __name__ == "__main__":
    unittest.main()
