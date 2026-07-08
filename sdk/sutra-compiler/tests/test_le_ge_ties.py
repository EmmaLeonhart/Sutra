"""`<=` / `>=` at exact ties (Emma decided 2026-07-08: adopt or(<, ==)).

Before: stdlib le/ge collapsed to the strict ops — `2 <= 2` read
tanh(0) = 0 (NEUTRAL), so the standard loop guard `i <= n` misbehaved
at the boundary. Now `le = or(<, ==)` / `ge = or(>, ==)` with the ==
component on the exact num_eq indicator: ties read +1, and both
false directions stay exactly -1 (max(-1, -1)).
"""
from __future__ import annotations

import unittest

from sutra_compiler.lexer import Lexer
from sutra_compiler.parser import Parser
from sutra_compiler.codegen_pytorch import translate_module


def _truth(expr: str, dim: int = 16) -> float:
    src = f"function fuzzy main(){{ int x = 2; int y = 2; return {expr}; }}"
    lx = Lexer(src, file="<t>")
    ast = Parser(lx.tokenize(), file="<t>", diagnostics=lx.diagnostics).parse_module()
    assert not lx.diagnostics.has_errors(), list(lx.diagnostics)
    ns: dict = {}
    exec(translate_module(ast, llm_model="none", runtime_dim=dim), ns)
    r = ns["main"]()
    v = ns["_VSA"]
    if not hasattr(r, "ndim") or r.ndim == 0:
        return float(r)
    return float(r[v.semantic_dim + v.AXIS_TRUTH])


class TestTies(unittest.TestCase):
    def test_le_tie_true(self):
        self.assertAlmostEqual(_truth("2 <= 2"), 1.0, places=4)

    def test_ge_tie_true(self):
        self.assertAlmostEqual(_truth("2 >= 2"), 1.0, places=4)

    def test_var_tie(self):
        self.assertAlmostEqual(_truth("x <= y"), 1.0, places=4)


class TestStrictUnchanged(unittest.TestCase):
    def test_le_true_direction(self):
        self.assertAlmostEqual(_truth("2 <= 3"), 1.0, places=4)

    def test_le_false_direction_stays_crisp(self):
        self.assertAlmostEqual(_truth("3 <= 2"), -1.0, places=4)

    def test_ge_false_direction_stays_crisp(self):
        self.assertAlmostEqual(_truth("2 >= 3"), -1.0, places=4)

    def test_strict_lt_tie_still_neutral(self):
        # strict < at a tie is tanh(0) = 0 — deliberately unchanged.
        self.assertAlmostEqual(_truth("2 < 2"), 0.0, places=4)


if __name__ == "__main__":
    unittest.main()
