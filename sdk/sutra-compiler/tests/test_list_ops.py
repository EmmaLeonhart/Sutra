"""End-to-end tests for immutable list-building + higher-order list ops.

Emma's design decision (2026-06-20): IMMUTABLE list-building — `concat`,
`map`, `filter` each build a NEW binding-array from pieces and NEVER
mutate an input (pure-functional, fits the substrate).

These tests RUN each verification target on the PyTorch backend at
runtime_dim=64 and read the results back through the runtime's
binding-array reads (`_VSA.array_length` / `_VSA.array_get`), comparing
the decoded element values to ground truth — "it parsed / it ran" is not
sufficient (CLAUDE.md integrity rules).

Surface names match the existing builtin convention (`array_length`,
`array_get`): `array_concat`, `array_map`, `array_filter`. The plain
`map` / `filter` spellings are unavailable as call names because `map`
is a TYPE keyword (`map<K, V>`); `array_*` is the convention-matching
choice the task permits.

Element math is host-scalar today (Sutra numbers are host floats at this
runtime config — a separate leg moves them to the substrate), so the ops
operate on the packed scalar elements.
"""
from __future__ import annotations

import unittest

import torch

from sutra_compiler.codegen_pytorch import translate_module
from sutra_compiler.lexer import Lexer
from sutra_compiler.parser import Parser


def _parse(src: str):
    lexer = Lexer(src, file="<test>")
    tokens = lexer.tokenize()
    parser = Parser(tokens, file="<test>", diagnostics=lexer.diagnostics)
    module = parser.parse_module()
    return module, lexer.diagnostics


def _build(src: str):
    """Parse + compile `src`, exec it, return the runtime namespace."""
    module, diags = _parse(src)
    assert not diags.has_errors(), [d.format() for d in diags]
    ns: dict = {}
    exec(translate_module(module, runtime_dim=64), ns)
    return ns


def _read_array(ns: dict, arr) -> list:
    """Read a binding-array tensor back to a Python list of element floats
    using the runtime's own binding-array reads."""
    vsa = ns["_VSA"]
    n = vsa.array_length(arr)
    return [float(vsa.array_get(arr, i)) for i in range(n)]


class TestListOps(unittest.TestCase):
    def test_concat(self):
        # Target 1: concat([1,2], [3,4]) -> length 4, [1,2,3,4].
        src = (
            "function int main() { return 0; }\n"
        )
        ns = _build(src)
        vsa = ns["_VSA"]
        a = vsa.array_from_literal(1, 2)
        b = vsa.array_from_literal(3, 4)
        out = vsa.array_concat(a, b)
        self.assertEqual(vsa.array_length(out), 4)
        self.assertEqual(_read_array(ns, out), [1.0, 2.0, 3.0, 4.0])
        # Immutability: inputs unchanged.
        self.assertEqual(_read_array(ns, a), [1.0, 2.0])
        self.assertEqual(_read_array(ns, b), [3.0, 4.0])

    def test_concat_accepts_python_list_literal(self):
        # The builtin lowers a bare `[...]` array literal (a Python list)
        # transparently — _as_binding_array normalizes it.
        ns = _build("function int main() { return 0; }\n")
        vsa = ns["_VSA"]
        out = vsa.array_concat([1, 2], [3, 4])
        self.assertEqual(_read_array(ns, out), [1.0, 2.0, 3.0, 4.0])

    def test_map_arrow(self):
        # Target 2: map((x) => x * 2, [1,2,3]) -> [2,4,6].
        ns = _build("function int main() { return 0; }\n")
        vsa = ns["_VSA"]
        arr = vsa.array_from_literal(1, 2, 3)
        out = vsa.array_map(lambda x: x * 2, arr)
        self.assertEqual(_read_array(ns, out), [2.0, 4.0, 6.0])
        # Immutability.
        self.assertEqual(_read_array(ns, arr), [1.0, 2.0, 3.0])

    def test_map_named_fn(self):
        # Target 3: map(named_fn, [1,2,3]) with `function int dbl(int x){...}`
        # -> [2,4,6]. The named function value is a plain Python callable
        # in the emitted module.
        src = (
            "function int dbl(int x) { return x * 2; }\n"
            "function int main() { return 0; }\n"
        )
        ns = _build(src)
        vsa = ns["_VSA"]
        arr = vsa.array_from_literal(1, 2, 3)
        out = vsa.array_map(ns["dbl"], arr)
        self.assertEqual(_read_array(ns, out), [2.0, 4.0, 6.0])

    def test_filter_arrow(self):
        # Target 4: filter((x) => x > 1, [1,2,3]) -> [2,3] (length 2).
        # The predicate returns a Sutra truth value (truth-axis vector);
        # array_filter decodes it via truth_axis and keeps truth > 0.
        src = (
            "function fuzzy gt_one(int x) { return x > 1; }\n"
            "function int main() { return 0; }\n"
        )
        ns = _build(src)
        vsa = ns["_VSA"]
        arr = vsa.array_from_literal(1, 2, 3)
        out = vsa.array_filter(ns["gt_one"], arr)
        self.assertEqual(vsa.array_length(out), 2)
        self.assertEqual(_read_array(ns, out), [2.0, 3.0])
        # Immutability.
        self.assertEqual(_read_array(ns, arr), [1.0, 2.0, 3.0])

    def test_filter_drops_all(self):
        # Predicate false everywhere -> empty array (length 0).
        src = (
            "function fuzzy gt_ten(int x) { return x > 10; }\n"
            "function int main() { return 0; }\n"
        )
        ns = _build(src)
        vsa = ns["_VSA"]
        arr = vsa.array_from_literal(1, 2, 3)
        out = vsa.array_filter(ns["gt_ten"], arr)
        self.assertEqual(vsa.array_length(out), 0)

    def test_su_source_uses_builtins(self):
        # The builtins are callable from .su source (not only via the
        # _VSA methods): a function builds arrays and a higher-order map
        # over a named function, all through the surface names.
        src = (
            "function int dbl(int x) { return x * 2; }\n"
            "function vector concat_then_map() {\n"
            "  var a = array_concat([1, 2], [3, 4]);\n"
            "  return array_map(dbl, a);\n"
            "}\n"
            "function int main() { return 0; }\n"
        )
        ns = _build(src)
        vsa = ns["_VSA"]
        out = ns["concat_then_map"]()
        self.assertEqual(_read_array(ns, out), [2.0, 4.0, 6.0, 8.0])

    def test_filter_from_su_source(self):
        src = (
            "function fuzzy keep(int x) { return x > 1; }\n"
            "function vector do_filter() {\n"
            "  return array_filter(keep, [1, 2, 3]);\n"
            "}\n"
            "function int main() { return 0; }\n"
        )
        ns = _build(src)
        out = ns["do_filter"]()
        self.assertEqual(_read_array(ns, out), [2.0, 3.0])

    def test_examples_list_ops_su_runs_end_to_end(self):
        # The user-facing example (examples/list_ops.su) compiles + runs and its
        # three functions decode to the documented results. This is the example
        # the docs/list-operations.md page walks through; keep it honest.
        import os

        here = os.path.dirname(os.path.abspath(__file__))
        path = os.path.join(here, "..", "..", "..", "examples", "list_ops.su")
        with open(path, encoding="utf-8") as f:
            ns = _build(f.read())
        self.assertEqual(_read_array(ns, ns["concat_then_double"]()), [2.0, 4.0, 6.0, 8.0])
        self.assertEqual(_read_array(ns, ns["map_with_arrow"]()), [10.0, 20.0, 30.0])
        self.assertEqual(_read_array(ns, ns["keep_big"]()), [2.0, 3.0])


if __name__ == "__main__":
    unittest.main()
