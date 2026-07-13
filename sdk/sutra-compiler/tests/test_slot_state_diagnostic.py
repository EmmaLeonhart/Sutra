"""SUT0206 is RETIRED — multi-axis loop state works by reference (rung 3 B5).

History: `slot String acc; loop build(15, acc);` compiled clean and died
at runtime with an opaque index_select error — the old slot plane stored
one real-axis scalar per slot, crushing String/vector/complex state on
the first store (finding 2026-07-08; SUT0206 warned about it from
round-26 until 2026-07-12). Under the unified d-dim slot store (Emma's
Option B, vector-loop-state rung 3) slots hold FULL dim-vectors, the
crush is gone, and the warning would be FALSE — so it was removed.

These tests lock in the new reality from both sides:
1. No SUT0206 (or any) diagnostic fires on multi-axis loop state.
2. The workload the old warning protected against actually RUNS and
   produces the right value (decoded ground truth, not "it ran").
"""
from __future__ import annotations

import unittest

from sutra_compiler import validate_source
from sutra_compiler.codegen_pytorch import PyTorchCodegen
from sutra_compiler.inliner import inline_stdlib_calls
from sutra_compiler.lexer import Lexer
from sutra_compiler.parser import Parser


def _sut0206(src: str):
    bag = validate_source(src, file="<t>")
    return [d for d in bag.warnings if d.code == "SUT0206"]


STRING_STATE_SRC = (
    "iterative_loop build(3, String acc) "
    "{ pass string_concat(acc, make_string(\"x\")); }\n"
    "function string main(){ slot String acc = make_string(\"\"); "
    "loop build(3, acc); return acc; }")


class TestRetired(unittest.TestCase):
    """The old 'fires' cases now emit NO SUT0206 — the crush is gone."""

    def test_string_loop_state_no_warning(self):
        self.assertEqual(_sut0206(STRING_STATE_SRC), [])

    def test_vector_loop_state_no_warning(self):
        src = (
            "do_while wander(1 < 2, vector state) { pass state; }\n"
            "function vector main(){ slot vector s = zero_vector(); "
            "loop wander(1 < 2, s); return s; }")
        self.assertEqual(_sut0206(src), [])

    def test_scalar_state_still_clean(self):
        src = (
            "do_while addNumber(x < 11, int x) { pass x + 1; }\n"
            "function int main(){ slot int x = 9; "
            "loop addNumber(x < 11, x); return x; }")
        self.assertEqual(_sut0206(src), [])


class TestStringStateByReferenceRuns(unittest.TestCase):
    """The exact workload the retired warning protected against runs
    end-to-end by reference and decodes to ground truth."""

    def test_string_accumulator_by_reference(self):
        lexer = Lexer(STRING_STATE_SRC, file="<t>")
        parser = Parser(lexer.tokenize(), file="<t>",
                        diagnostics=lexer.diagnostics)
        module = parser.parse_module()
        self.assertFalse(list(lexer.diagnostics.errors))
        inline_stdlib_calls(module)
        cg = PyTorchCodegen()
        cg._prefetch_strings = []
        ns: dict = {}
        exec(cg.translate(module), ns)
        # 3 iterations, each appends "x" — decoded ground truth.
        self.assertEqual(ns["_VSA"].string_to_python(ns["main"]()), "xxx")


if __name__ == "__main__":
    unittest.main()
