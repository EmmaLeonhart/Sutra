"""Unit tests for the v0.2 symbol-table collector (name-resolution foundation).

Collection only — asserts `build_symbol_table` enumerates file-scope classes
(+ members), top-level functions, and top-level methods (+ arity), and that the
`is_known_*` queries behave over primitives / containers / collected symbols.
No diagnostics are emitted at this rung, so these tests assert data, not
warnings. See `symbol_table.py` for the deliberate non-wiring note.
"""
from __future__ import annotations

import unittest

from sutra_compiler import ast_nodes as ast
from sutra_compiler.lexer import Lexer
from sutra_compiler.parser import Parser
from sutra_compiler.symbol_table import build_symbol_table, local_names


def _module(src: str):
    lexer = Lexer(src, file="<test>")
    tokens = lexer.tokenize()
    parser = Parser(tokens, file="<test>", diagnostics=lexer.diagnostics)
    return parser.parse_module()


class SymbolTableCollectionTest(unittest.TestCase):
    def test_collects_top_level_functions_with_arity(self):
        m = _module(
            "function number add(number a, number b) { return a; }\n"
            "function vector greet(string name) { return embed(name); }\n"
        )
        t = build_symbol_table(m)
        self.assertIn("add", t.functions)
        self.assertIn("greet", t.functions)
        self.assertEqual(t.functions["add"].arity, 2)
        self.assertEqual(t.functions["greet"].arity, 1)
        self.assertTrue(t.is_known_function("add"))
        self.assertFalse(t.is_known_function("nope"))

    def test_collects_top_level_methods(self):
        # A Sutra file acts as an object declaration: methods sit at file scope
        # and their implicit `this` is NOT counted in arity.
        m = _module(
            "method string GetName() { return this.name; }\n"
            "method fuzzy SimilarTo(Animal other) { return unsafeCast<fuzzy>(0.5); }\n"
        )
        t = build_symbol_table(m)
        self.assertIn("GetName", t.methods)
        self.assertIn("SimilarTo", t.methods)
        self.assertEqual(t.methods["GetName"].arity, 0)
        self.assertEqual(t.methods["SimilarTo"].arity, 1)
        self.assertTrue(t.methods["SimilarTo"].is_method)
        self.assertTrue(t.is_known_function("SimilarTo"))

    def test_collects_classes_with_members(self):
        m = _module(
            "class Cat extends Animal {\n"
            "  field vector fur;\n"
            "  method number legs() { return 4; }\n"
            "}\n"
        )
        t = build_symbol_table(m)
        self.assertIn("Cat", t.classes)
        self.assertEqual(t.classes["Cat"].parent_name, "Animal")
        self.assertIn("legs", t.classes["Cat"].method_names)
        self.assertIn("fur", t.classes["Cat"].field_names)
        self.assertTrue(t.is_known_type("Cat"))

    def test_primitive_and_container_types_known(self):
        t = build_symbol_table(_module(""))
        for name in ("number", "vector", "string", "bool", "matrix"):
            self.assertTrue(t.is_known_type(name), name)
        for name in ("list", "dict", "set", "array"):
            self.assertTrue(t.is_known_type(name), name)

    def test_numeric_type_arg_is_not_flagged(self):
        # BigInt<512> -> the "512" type-arg name must never read as unknown.
        t = build_symbol_table(_module(""))
        self.assertTrue(t.is_known_type("512"))

    def test_unknown_type_reads_unknown_at_this_rung(self):
        # Foundation-only: a genuinely-undeclared type is unknown here. (An
        # externally-declared type like Animal is the later cross-file rung's
        # job; this only asserts the collector doesn't invent symbols.)
        t = build_symbol_table(_module(""))
        self.assertFalse(t.is_known_type("Wobble"))
        self.assertFalse(t.is_known_type(""))


class LocalScopeTest(unittest.TestCase):
    """Rung 2: local-scope tracking — params + body var/const are in scope."""

    def test_params_and_body_locals(self):
        m = _module(
            "function number f(number a, number b) {\n"
            "  var x = a;\n"
            "  const y = b;\n"
            "  return x;\n"
            "}\n"
        )
        f = m.items[0]
        self.assertEqual(local_names(f), {"a", "b", "x", "y"})

    def test_nested_block_local_is_in_scope(self):
        # a var declared inside a nested block (loop body) is still collected
        m = _module(
            "function number g(number n) {\n"
            "  loop (n) {\n"
            "    var inner = n;\n"
            "  }\n"
            "  return n;\n"
            "}\n"
        )
        g = m.items[0]
        names = local_names(g)
        self.assertIn("n", names)
        self.assertIn("inner", names)

    def test_function_valued_local_is_callable_name(self):
        # An arrow assigned to a local desugars at PARSE TIME into a hoisted
        # top-level function (`__arrow_N`), and the local holds a reference to it.
        # So the arrow lands as its own module item (do not assume m.items[0] is
        # `h`); the local name `scale` must still be in scope inside `h` so it
        # isn't later flagged as an unknown function when called.
        m = _module(
            "function vector h(vector v) {\n"
            "  var scale = (vector u) => u;\n"
            "  return scale(v);\n"
            "}\n"
        )
        h = next(it for it in m.items
                 if isinstance(it, ast.FunctionDecl) and it.name == "h")
        names = local_names(h)
        self.assertIn("v", names)
        self.assertIn("scale", names)


if __name__ == "__main__":
    unittest.main()
