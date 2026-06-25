"""`sutrac --run` surfaces runtime problems as diagnostics, not Python tracebacks.

- A runtime error in the generated module (e.g. a type mismatch the v0.1 validator
  can't catch) prints `<file>: runtime error: <Type>: <msg>` to stderr and exits 1 —
  not an uncaught Python stack trace.
- A file with no `main()` prints a `no main() found` notice instead of exiting silently.

Execs the generated torch module, so it needs `torch` at test time (like the other
run-on-substrate tests). The programs here use no `embed`, so no model is loaded.
"""
from __future__ import annotations

import contextlib
import io
import os
import tempfile
import unittest

from sutra_compiler.__main__ import _run_execute


def _run(src: str):
    with tempfile.NamedTemporaryFile(
        "w", suffix=".su", delete=False, encoding="utf-8"
    ) as f:
        f.write(src)
        path = f.name
    try:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = _run_execute(path, runtime_dim=50, runtime_seed=0)
        return code, out.getvalue(), err.getvalue()
    finally:
        os.unlink(path)


class TestRunErrorDiagnostics(unittest.TestCase):
    def test_runtime_error_is_a_clean_diagnostic_not_a_traceback(self):
        code, _out, err = _run(
            'function int main() { int x = "hello"; return x; }\n'
        )
        self.assertEqual(code, 1)
        self.assertIn("runtime error:", err)
        self.assertNotIn("Traceback", err)

    def test_no_main_prints_a_notice(self):
        code, _out, err = _run("function int helper() { return 1; }\n")
        self.assertEqual(code, 0)
        self.assertIn("no main()", err)


if __name__ == "__main__":
    unittest.main()
