"""Unit tests for the Sutra parser.

Tests cover the major grammar productions and the specific
disambiguation rules (cast vs paren, generic vs comparison).
"""

import unittest

from sutra_compiler import ast_nodes as ast
from sutra_compiler.lexer import Lexer
from sutra_compiler.parser import Parser


def parse(src):
    lexer = Lexer(src)
    tokens = lexer.tokenize()
    parser = Parser(tokens, diagnostics=lexer.diagnostics)
    module = parser.parse_module()
    return module, lexer.diagnostics


class TestTopLevel(unittest.TestCase):
    def test_empty_file(self):
        module, diag = parse("")
        self.assertEqual(len(module.items), 0)
        self.assertFalse(diag.has_errors())

    def test_single_function(self):
        module, diag = parse("function void Foo() { return; }")
        self.assertFalse(diag.has_errors())
        self.assertEqual(len(module.items), 1)
        fn = module.items[0]
        self.assertIsInstance(fn, ast.FunctionDecl)
        self.assertEqual(fn.name, "Foo")
        self.assertEqual(fn.return_type.name, "void")
        self.assertEqual(fn.params, [])

    def test_function_with_params(self):
        module, diag = parse(
            "function vector Blend(vector a, vector b) { return a + b; }"
        )
        self.assertFalse(diag.has_errors())
        fn = module.items[0]
        self.assertEqual(len(fn.params), 2)
        self.assertEqual(fn.params[0].name, "a")
        self.assertEqual(fn.params[0].type_ref.name, "vector")

    def test_method(self):
        module, diag = parse("method string GetName() { return this.name; }")
        self.assertFalse(diag.has_errors())
        self.assertIsInstance(module.items[0], ast.MethodDecl)

    def test_static_method(self):
        module, diag = parse(
            "static method Animal GetArchetype() { return (Animal) embed(\"animal\"); }"
        )
        self.assertFalse(diag.has_errors())
        m = module.items[0]
        self.assertIsInstance(m, ast.MethodDecl)
        self.assertTrue(m.modifiers.is_static)

    def test_operator_decl(self):
        module, diag = parse("function operator +(vector a, vector b) { return a; }")
        self.assertFalse(diag.has_errors())
        fn = module.items[0]
        self.assertIsInstance(fn, ast.FunctionDecl)
        self.assertTrue(fn.is_operator)

    def test_generic_function(self):
        module, diag = parse("function T Identity<T>(T value) { return value; }")
        self.assertFalse(diag.has_errors())
        fn = module.items[0]
        self.assertEqual(fn.type_params, ["T"])


class TestDeclarations(unittest.TestCase):
    def test_var_inferred(self):
        module, diag = parse("function void F() { var x = 1; }")
        self.assertFalse(diag.has_errors())
        fn = module.items[0]
        decl = fn.body.statements[0]
        self.assertIsInstance(decl, ast.VarDecl)
        self.assertTrue(decl.is_var_inferred)
        self.assertIsNone(decl.type_ref)

    def test_var_with_type_is_error(self):
        _, diag = parse("function void F() { var vector x = embed(\"cat\"); }")
        self.assertTrue(diag.has_errors())
        self.assertTrue(any(d.code == "SUT0103" for d in diag))

    def test_typed_decl(self):
        module, diag = parse("function void F() { vector x = embed(\"cat\"); }")
        self.assertFalse(diag.has_errors())
        decl = module.items[0].body.statements[0]
        self.assertIsInstance(decl, ast.VarDecl)
        self.assertFalse(decl.is_var_inferred)
        self.assertEqual(decl.type_ref.name, "vector")

    def test_const_inferred(self):
        module, diag = parse("function void F() { const x = 0.5; }")
        self.assertFalse(diag.has_errors())
        decl = module.items[0].body.statements[0]
        self.assertTrue(decl.is_const)

    def test_const_typed(self):
        module, diag = parse("function void F() { const scalar x = 0.5; }")
        self.assertFalse(diag.has_errors())
        decl = module.items[0].body.statements[0]
        self.assertTrue(decl.is_const)
        self.assertEqual(decl.type_ref.name, "scalar")


class TestControlFlow(unittest.TestCase):
    def test_if_else(self):
        module, diag = parse(
            "function void F(bool x) { if (x) { return; } else { return; } }"
        )
        self.assertFalse(diag.has_errors())
        stmt = module.items[0].body.statements[0]
        self.assertIsInstance(stmt, ast.IfStmt)
        self.assertIsNotNone(stmt.else_branch)

    def test_else_if_chain(self):
        module, diag = parse(
            "function void F(scalar x) { "
            "if (x < 0.0) { return; } else if (x > 1.0) { return; } else { return; } "
            "}"
        )
        self.assertFalse(diag.has_errors())

    def test_while(self):
        module, diag = parse("function void F(bool x) { while (x) { return; } }")
        self.assertFalse(diag.has_errors())

    def test_for(self):
        module, diag = parse(
            "function void F() { for (var i = 0; i < 10; i++) { Process(i); } }"
        )
        self.assertFalse(diag.has_errors())

    def test_foreach(self):
        module, diag = parse(
            "function void F(tuple t) { foreach (var x in t) { Process(x); } }"
        )
        self.assertFalse(diag.has_errors())

    def test_do_while(self):
        module, diag = parse(
            "function void F() { do { Process(); } while (true); }"
        )
        self.assertFalse(diag.has_errors())

    def test_try_catch(self):
        module, diag = parse(
            "function void F(Animal a) { try { Cat c = (Cat) a; } catch { return; } }"
        )
        self.assertFalse(diag.has_errors())


class TestExpressions(unittest.TestCase):
    def test_arithmetic_precedence(self):
        module, diag = parse("function scalar F() { return 1 + 2 * 3; }")
        self.assertFalse(diag.has_errors())
        ret = module.items[0].body.statements[0]
        # Top-level should be a +, with * on the right side.
        self.assertIsInstance(ret.value, ast.BinaryOp)
        self.assertEqual(ret.value.op, "+")
        self.assertEqual(ret.value.right.op, "*")

    def test_cast_expression(self):
        module, diag = parse("function vector F(Animal a) { return (vector) a; }")
        self.assertFalse(diag.has_errors())
        ret = module.items[0].body.statements[0]
        self.assertIsInstance(ret.value, ast.CastExpr)
        self.assertEqual(ret.value.target_type.name, "vector")

    def test_parenthesized_group(self):
        module, diag = parse("function scalar F() { return (1 + 2) * 3; }")
        self.assertFalse(diag.has_errors())
        ret = module.items[0].body.statements[0]
        # Outer should be *, left should be Parenthesized(1+2).
        self.assertIsInstance(ret.value, ast.BinaryOp)
        self.assertEqual(ret.value.op, "*")
        self.assertIsInstance(ret.value.left, ast.Parenthesized)

    def test_generic_call(self):
        module, diag = parse("function void F(Cat c) { Cat x = Identity<Cat>(c); }")
        self.assertFalse(diag.has_errors())

    def test_method_chain(self):
        module, diag = parse("function void F(Animal a) { a.GetEmbedding().Normalize(); }")
        self.assertFalse(diag.has_errors())

    def test_unsafe_cast(self):
        module, diag = parse(
            "function fuzzy F(vector v) { return unsafeCast<fuzzy>(v); }"
        )
        self.assertFalse(diag.has_errors())
        ret = module.items[0].body.statements[0]
        self.assertIsInstance(ret.value, ast.UnsafeCastExpr)

    def test_defuzzy(self):
        module, diag = parse(
            "function bool F(fuzzy s) { return defuzzy(s); }"
        )
        self.assertFalse(diag.has_errors())
        ret = module.items[0].body.statements[0]
        self.assertIsInstance(ret.value, ast.DefuzzyExpr)

    def test_embed(self):
        module, diag = parse(
            'function vector F() { return embed("cat"); }'
        )
        self.assertFalse(diag.has_errors())
        ret = module.items[0].body.statements[0]
        self.assertIsInstance(ret.value, ast.EmbedExpr)

    def test_interpolated_string(self):
        module, diag = parse(
            'function string F(string name) { return $"hello {name}"; }'
        )
        self.assertFalse(diag.has_errors())
        ret = module.items[0].body.statements[0]
        self.assertIsInstance(ret.value, ast.InterpolatedString)

    def test_function_dot_prefix(self):
        module, diag = parse(
            "function void F() { function.Main(); }"
        )
        self.assertFalse(diag.has_errors())

    def test_array_literal_empty(self):
        module, diag = parse("function void F() { var xs = []; }")
        self.assertFalse(diag.has_errors())
        decl = module.items[0].body.statements[0]
        self.assertIsInstance(decl.initializer, ast.ArrayLiteral)
        self.assertEqual(decl.initializer.elements, [])

    def test_array_literal_multi(self):
        module, diag = parse(
            "function void F() { var xs = [1, 2, 3]; }"
        )
        self.assertFalse(diag.has_errors())
        decl = module.items[0].body.statements[0]
        self.assertIsInstance(decl.initializer, ast.ArrayLiteral)
        self.assertEqual(len(decl.initializer.elements), 3)

    def test_array_literal_as_call_argument(self):
        module, diag = parse(
            "function vector F(vector q) "
            "{ return argmax_cosine(q, [a, b, c, d]); }"
        )
        self.assertFalse(diag.has_errors())
        call = module.items[0].body.statements[0].value
        self.assertIsInstance(call, ast.Call)
        self.assertEqual(len(call.args), 2)
        self.assertIsInstance(call.args[1], ast.ArrayLiteral)
        self.assertEqual(len(call.args[1].elements), 4)

    def test_subscript_on_identifier(self):
        module, diag = parse(
            "function string F(vector w) { return behaviors[w]; }"
        )
        self.assertFalse(diag.has_errors())
        ret = module.items[0].body.statements[0]
        self.assertIsInstance(ret.value, ast.Subscript)
        self.assertIsInstance(ret.value.target, ast.Identifier)
        self.assertEqual(ret.value.target.name, "behaviors")

    def test_subscript_chained(self):
        module, diag = parse(
            "function void F() { var x = grid[1][2]; }"
        )
        self.assertFalse(diag.has_errors())
        init = module.items[0].body.statements[0].initializer
        self.assertIsInstance(init, ast.Subscript)
        self.assertIsInstance(init.target, ast.Subscript)

    def test_subscript_on_array_literal(self):
        module, diag = parse(
            "function void F() { var x = [a, b, c][0]; }"
        )
        self.assertFalse(diag.has_errors())
        init = module.items[0].body.statements[0].initializer
        self.assertIsInstance(init, ast.Subscript)
        self.assertIsInstance(init.target, ast.ArrayLiteral)

    def test_permutation_as_type(self):
        module, diag = parse(
            "function permutation F(permutation p) { return p; }"
        )
        self.assertFalse(diag.has_errors())
        fn = module.items[0]
        self.assertEqual(fn.return_type.name, "permutation")
        self.assertEqual(fn.params[0].type_ref.name, "permutation")

    def test_permutation_top_level_var(self):
        module, diag = parse(
            'permutation NOT_SMELL = permutation_key("NOT_SMELL");'
        )
        self.assertFalse(diag.has_errors())
        decl = module.items[0]
        self.assertIsInstance(decl, ast.VarDecl)
        self.assertEqual(decl.type_ref.name, "permutation")

    def test_map_literal_empty(self):
        module, diag = parse("function void F() { var m = {}; }")
        self.assertFalse(diag.has_errors())
        init = module.items[0].body.statements[0].initializer
        self.assertIsInstance(init, ast.MapLiteral)
        self.assertEqual(init.keys, [])
        self.assertEqual(init.values, [])

    def test_map_literal_single_entry(self):
        module, diag = parse(
            'function void F() { var m = {"only": 1}; }'
        )
        self.assertFalse(diag.has_errors())
        init = module.items[0].body.statements[0].initializer
        self.assertIsInstance(init, ast.MapLiteral)
        self.assertEqual(len(init.keys), 1)
        self.assertEqual(len(init.values), 1)
        self.assertIsInstance(init.keys[0], ast.StringLiteral)
        self.assertIsInstance(init.values[0], ast.IntLiteral)

    def test_map_literal_multi_entry(self):
        module, diag = parse(
            'function void F() { var m = {"a": 1, "b": 2, "c": 3}; }'
        )
        self.assertFalse(diag.has_errors())
        init = module.items[0].body.statements[0].initializer
        self.assertIsInstance(init, ast.MapLiteral)
        self.assertEqual(len(init.keys), 3)
        self.assertEqual(len(init.values), 3)

    def test_map_literal_vector_keys(self):
        # The permutation-conditional shape: map<vector, string>
        # with expression-valued keys.
        module, diag = parse(
            'map<vector, string> BEHAVIOR_OF = '
            '{proto_PH: "approach", proto_AH: "search"};'
        )
        self.assertFalse(diag.has_errors())
        decl = module.items[0]
        self.assertIsInstance(decl, ast.VarDecl)
        self.assertEqual(decl.type_ref.name, "map")
        self.assertEqual(len(decl.type_ref.type_args), 2)
        self.assertEqual(decl.type_ref.type_args[0].name, "vector")
        self.assertEqual(decl.type_ref.type_args[1].name, "string")
        self.assertIsInstance(decl.initializer, ast.MapLiteral)
        self.assertEqual(len(decl.initializer.keys), 2)
        self.assertIsInstance(decl.initializer.keys[0], ast.Identifier)

    def test_map_literal_as_call_argument(self):
        module, diag = parse(
            'function void F() { Register({"a": 1, "b": 2}); }'
        )
        self.assertFalse(diag.has_errors())
        call = module.items[0].body.statements[0].expr
        self.assertIsInstance(call, ast.Call)
        self.assertEqual(len(call.args), 1)
        self.assertIsInstance(call.args[0], ast.MapLiteral)

    def test_map_literal_subscript_chain(self):
        # {k: v}[k] — map literal immediately followed by a subscript.
        module, diag = parse(
            'function void F() { var x = {"a": 1}["a"]; }'
        )
        self.assertFalse(diag.has_errors())
        init = module.items[0].body.statements[0].initializer
        self.assertIsInstance(init, ast.Subscript)
        self.assertIsInstance(init.target, ast.MapLiteral)


class TestErrorRecovery(unittest.TestCase):
    def test_missing_semicolon(self):
        _, diag = parse("function void F() { var x = 1 return x; }")
        self.assertTrue(diag.has_errors())

    def test_unclosed_brace(self):
        _, diag = parse("function void F() { var x = 1;")
        self.assertTrue(diag.has_errors())

    def test_recovery_continues_to_next_function(self):
        # Error in first function should not prevent parsing the second.
        module, diag = parse(
            "function void F() { var x = 1 }\n"
            "function void G() { return; }"
        )
        self.assertTrue(diag.has_errors())
        self.assertGreaterEqual(len(module.items), 1)


if __name__ == "__main__":
    unittest.main()
