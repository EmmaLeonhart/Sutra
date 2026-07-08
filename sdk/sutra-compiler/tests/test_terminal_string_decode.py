"""A `main()` that returns a String prints its text, not its first codepoint.

Regression for the terminal-decode bug: `function string main() { return "hello
world"; }` printed `104.0` ('h') because a String is a `dim`-length tensor and the
real axis coincides with the first codepoint, so the number-vector decode fired
before the string check. `_decode_terminal_result` now checks `is_string` first and
decodes via the sanctioned `string_to_python` boundary. The number path must still
decode to the real-axis value.

This execs the generated torch module, so it needs `torch` at test time (same as the
codegen_pytorch run-on-substrate tests). runtime_dim=50 matches the CLI default.
"""
from __future__ import annotations

import os
import tempfile
import types
import unittest

from sutra_compiler.__main__ import _compile_to_python, _decode_terminal_result


def _run_main(src: str):
    with tempfile.NamedTemporaryFile(
        "w", suffix=".su", delete=False, encoding="utf-8"
    ) as f:
        f.write(src)
        path = f.name
    try:
        py = _compile_to_python(path, runtime_dim=50, runtime_seed=0)
        assert py is not None, "expected the program to compile"
        mod = types.ModuleType("_sutra_run_test")
        exec(compile(py, "<generated>", "exec"), mod.__dict__)
        return _decode_terminal_result(mod, mod.main())
    finally:
        os.unlink(path)


class TestTerminalStringDecode(unittest.TestCase):
    def test_string_literal_main_returns_text_not_codepoint(self):
        result = _run_main(
            'function string main() { return "hello world"; }\n'
        )
        self.assertEqual(result, "hello world")

    def test_number_main_still_decodes_to_real_axis(self):
        result = _run_main("function number main() { return 6 * 7; }\n")
        self.assertIsInstance(result, float)
        self.assertAlmostEqual(result, 42.0, places=3)


if __name__ == "__main__":
    unittest.main()


class TestTruthAxisDecode(unittest.TestCase):
    """A fuzzy/bool main() prints its truth reading, not the real axis
    (round-25: `(15 % 3) == 0` printed 0.0 despite being true — the
    +1 lives on AXIS_TRUTH)."""

    def test_true_comparison_prints_true(self):
        out = _run_main("function fuzzy main(){ return (15 % 3) == 0; }")
        self.assertIn("true", str(out))

    def test_false_comparison_prints_false(self):
        out = _run_main("function fuzzy main(){ return (16 % 3) == 0; }")
        self.assertIn("false", str(out))

    def test_number_result_still_prints_real(self):
        out = _run_main("function number main(){ return make_real(7.0); }")
        self.assertEqual(float(out), 7.0)
