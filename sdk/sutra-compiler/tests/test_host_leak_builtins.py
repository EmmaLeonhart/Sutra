"""Host-Python builtins (`print`, `input`, `eval`, ...) must not leak.

The codegen emits any non-builtin call identifier verbatim as a Python call, so
`print("x")` used to lower to a raw `print('x')` and actually print — silently
breaking Sutra's no-I/O model (CLAUDE.md §"NO introspection", docs/host-bridge.md).
The validator now rejects a bare call to a host-Python builtin with SUT0152, unless
the program declares its own function of that name.
"""
from __future__ import annotations

import unittest

from sutra_compiler import validate_source


def _codes(src: str):
    return [d.code for d in validate_source(src, file="<test>")]


class TestHostLeakBuiltins(unittest.TestCase):
    def test_print_is_rejected(self):
        bag = validate_source(
            'function string main() { print("hi"); return "x"; }\n', file="<test>"
        )
        self.assertTrue(bag.has_errors())
        diag = next(d for d in bag if d.code == "SUT0152")
        # The steer points at the no-I/O / return-from-main model.
        self.assertIn("main()", (diag.hint or ""))

    def test_other_host_builtins_rejected(self):
        for name in ("input", "open", "eval", "exec", "compile", "__import__"):
            with self.subTest(builtin=name):
                src = f'function string main() {{ {name}(); return "x"; }}\n'
                self.assertIn("SUT0152", _codes(src), f"{name} should be SUT0152")

    def test_user_declared_function_shadows_the_builtin(self):
        # If the program defines its own `print`, the call is legitimate.
        src = (
            "function void print() { }\n"
            'function string main() { print(); return "x"; }\n'
        )
        self.assertNotIn("SUT0152", _codes(src))

    def test_ordinary_program_is_clean(self):
        src = (
            'vector a = embed("a");\n'
            "function vector main() { return bundle(a, a); }\n"
        )
        self.assertNotIn("SUT0152", _codes(src))


if __name__ == "__main__":
    unittest.main()
