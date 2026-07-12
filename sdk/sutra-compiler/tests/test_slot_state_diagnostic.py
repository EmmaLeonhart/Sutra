"""SUT0206 — multi-axis loop state through the scalar slot plane (round-26).

`slot String acc; loop build(15, acc);` compiled clean and died at
runtime with an opaque index_select error: the slot plane stores one
real-axis scalar per slot, crushing String/vector/complex state on the
first store (measured on the corpus's own do_while.su too). Warning,
not error — the corpus documents `slot vector` loop state as intended
surface, and vector-sized slots for the by-reference form are a later
stage.

Since 2026-07-12 the hint steers to the loop EXPRESSION form
(`TYPE x = loop NAME(cond, initial);`), which bypasses the slot plane and
carries vector/String state correctly (finding 2026-07-12); `recurring`
remains the alternative for non-halting loops.
"""
from __future__ import annotations

import unittest

from sutra_compiler import validate_source


def _sut0206(src: str):
    bag = validate_source(src, file="<t>")
    return [d for d in bag.warnings if d.code == "SUT0206"]


class TestFires(unittest.TestCase):
    def test_string_loop_state(self):
        src = (
            "iterative_loop build(3, String acc) { pass acc; }\n"
            "function string main(){ slot String acc = make_string(\"\"); "
            "loop build(3, acc); return acc; }")
        d = _sut0206(src)
        self.assertEqual(len(d), 1)
        self.assertIn("acc", str(d[0]))
        # Steers to the working expression-form path (primary) and keeps
        # `recurring` as the non-halting-loop alternative.
        self.assertIn("EXPRESSION form", str(d[0]))
        self.assertIn("recurring", str(d[0]))

    def test_vector_loop_state(self):
        src = (
            "do_while wander(1 < 2, vector state) { pass state; }\n"
            "function vector main(){ slot vector s = zero_vector(); "
            "loop wander(1 < 2, s); return s; }")
        self.assertEqual(len(_sut0206(src)), 1)


class TestDoesNotFire(unittest.TestCase):
    def test_scalar_state_clean(self):
        src = (
            "do_while addNumber(x < 11, int x) { pass x + 1; }\n"
            "function int main(){ slot int x = 9; "
            "loop addNumber(x < 11, x); return x; }")
        self.assertEqual(_sut0206(src), [])


if __name__ == "__main__":
    unittest.main()
