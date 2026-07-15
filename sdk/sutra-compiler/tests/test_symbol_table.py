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
from sutra_compiler.symbol_table import (
    _walk,
    build_project_symbol_table,
    build_symbol_table,
    local_names,
)


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

    def test_stdlib_bare_call_resolves_case_insensitively(self):
        # Emma 2026-07-15: bare stdlib names resolve case-insensitively, so a
        # case-variant (`Log`/`LOG` of intrinsic `log`) must be recognized as
        # known — no spurious SUT0201 unknown-function warning on code that
        # codegen now compiles to `_VSA.log`. User names stay case-sensitive.
        m = _module("function number main() { return log(2.0); }\n")
        t = build_symbol_table(m)
        self.assertTrue(t.is_known_function("log"))     # exact
        self.assertTrue(t.is_known_function("Log"))     # case-variant
        self.assertTrue(t.is_known_function("LOG"))     # case-variant
        self.assertFalse(t.is_known_function("Nope"))   # user/unknown, unaffected

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


class ExternResolutionTest(unittest.TestCase):
    """Rung 3: stdlib + builtins fold into the queries (diagnostic-grade)."""

    def test_builtin_functions_are_known(self):
        t = build_symbol_table(_module(""))
        for name in ("bundle", "bind", "argmax_cosine"):  # substrate BUILTINS
            self.assertTrue(t.is_known_function(name), name)

    def test_stdlib_functions_known_qualified_and_bare(self):
        t = build_symbol_table(_module(""))
        self.assertTrue(t.is_known_function("Embedding.embed"))
        self.assertTrue(t.is_known_function("embed"))  # bare last component

    def test_stdlib_classes_and_float_are_known_types(self):
        t = build_symbol_table(_module(""))
        for name in ("Axon", "BigInt", "Embedding"):  # stdlib class names
            self.assertTrue(t.is_known_type(name), name)
        self.assertTrue(t.is_known_type("float"))  # measured real type gap

    def test_genuinely_unknown_still_unknown(self):
        t = build_symbol_table(_module(""))
        self.assertFalse(t.is_known_function("definitely_not_a_function_xyz"))
        self.assertFalse(t.is_known_type("Wobble"))

    def test_include_extern_false_restricts_to_module_scope(self):
        m = _module("function number f(number a) { return a; }\n")
        t = build_symbol_table(m)
        t.include_extern = False
        self.assertTrue(t.is_known_function("f"))        # declared here
        self.assertFalse(t.is_known_function("bundle"))  # extern, now excluded
        self.assertFalse(t.is_known_type("Axon"))        # extern, now excluded


class CrossFileExternalTypeTest(unittest.TestCase):
    """Rung: cross-file / external-type handling. `function`, capitalised
    containers, and open-world scoping of undeclared sibling types."""

    def test_function_value_type_is_known(self):
        # `function f` as a parameter type — the type of a first-class function
        # value (14_arrow_functions.su / higher_order_functions.su).
        t = build_symbol_table(_module(""))
        self.assertTrue(t.is_known_type("function"))

    def test_capitalised_containers_are_known(self):
        # `List<vector>`, `Array<int, 10>` — same containers, PascalCase spelling.
        t = build_symbol_table(_module(""))
        for name in ("List", "Array", "Dict", "Set"):
            self.assertTrue(t.is_known_type(name), name)

    def test_pascalcase_unknown_not_reported_open_world(self):
        # An undeclared sibling class (Animal/Cat) may be another file — open
        # world must NOT flag it (keeps 03_methods.su clean).
        t = build_symbol_table(_module(""))
        self.assertFalse(t.is_reportable_unknown_type("Animal"))
        self.assertFalse(t.is_reportable_unknown_type("Cat"))

    def test_lowercase_typo_is_reported_open_world(self):
        # A lowercase unresolved name can only be a primitive/container typo —
        # this is the H1 surface the diagnostic must still catch.
        t = build_symbol_table(_module(""))
        self.assertTrue(t.is_reportable_unknown_type("vec"))    # -> vector
        self.assertTrue(t.is_reportable_unknown_type("scalar"))  # removed type

    def test_closed_world_flags_pascalcase_unknown(self):
        # With the whole project unioned in, an unresolved PascalCase name is
        # genuinely unknown (a real typo of a class), so it becomes reportable.
        proj = build_project_symbol_table([_module("")])
        self.assertTrue(proj.closed_world)
        self.assertTrue(proj.is_reportable_unknown_type("Aniaml"))  # typo of Animal

    def test_project_union_resolves_sibling_types(self):
        # Animal declared in one module resolves a Cat-in-another reference;
        # file-type-names stand in for sibling `.su` object files.
        mod_animal = _module("class Animal extends object { field vector fur; }\n")
        mod_ref = _module("method fuzzy f(Animal a) { return unsafeCast<fuzzy>(0.5); }\n")
        proj = build_project_symbol_table([mod_animal, mod_ref], file_type_names=["Cat"])
        self.assertTrue(proj.is_known_type("Animal"))  # declared in a sibling module
        self.assertTrue(proj.is_known_type("Cat"))     # a sibling .su object file
        self.assertFalse(proj.is_reportable_unknown_type("Animal"))

    def test_full_valid_corpus_zero_reportable_false_positives(self):
        """THE GATE for this rung: scanning every valid corpus file + every
        example, the unknown-type diagnostic must fire on NONE of them (0 false
        positives). This is what makes the intentionally-open files stay clean."""
        import glob
        import os

        root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
        files = sorted(
            glob.glob(os.path.join(os.path.dirname(__file__), "corpus", "valid", "**", "*.su"), recursive=True)
            + glob.glob(os.path.join(root, "examples", "**", "*.su"), recursive=True)
        )
        self.assertGreater(len(files), 50, "corpus scan found too few files")
        offenders = {}
        for f in files:
            src = open(f, encoding="utf-8").read()
            m = _module(src)
            st = build_symbol_table(m)
            bad = sorted({n.name for n in _walk(m)
                          if isinstance(n, ast.TypeRef)
                          and st.is_reportable_unknown_type(n.name)})
            if bad:
                offenders[os.path.relpath(f, root)] = bad
        self.assertEqual(offenders, {}, f"reportable-unknown type false positives: {offenders}")


if __name__ == "__main__":
    unittest.main()
