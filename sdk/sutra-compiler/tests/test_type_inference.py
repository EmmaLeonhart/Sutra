"""Expression type inference (v0.2 H1, the T1/T2 rungs) — the substrate for the
REPL return-type inference and the wrong-arg-type diagnostic.

Inference is deliberately CONSERVATIVE: it returns a concrete type only for the
constructs it can decide precisely (unambiguous literals, `embed(...)`, casts,
parenthesised exprs, annotated locals/params, and calls with a known return type)
and None everywhere else. None is always the safe answer — every downstream
diagnostic acts only on a definitively-inferred type.
"""
from __future__ import annotations

import unittest

from sutra_compiler import ast_nodes as ast
from sutra_compiler.lexer import Lexer
from sutra_compiler.parser import Parser
from sutra_compiler.symbol_table import (
    build_symbol_table,
    extern_signatures,
    infer_type,
    local_type_env,
)


def _module(src: str):
    lx = Lexer(src, file="<test>")
    return Parser(lx.tokenize(), file="<test>", diagnostics=lx.diagnostics).parse_module()


def _return_expr(src_expr: str):
    """Parse `return <expr>;` inside a function and hand back the expr node."""
    m = _module(f"function vector g() {{ return {src_expr}; }}")
    for stmt in m.items[0].body.statements:
        if type(stmt).__name__ == "ReturnStmt":
            return stmt.value, build_symbol_table(m), m.items[0]
    raise AssertionError("no return statement parsed")


class TestSignatureCollection(unittest.TestCase):
    def test_user_function_return_and_param_types(self):
        st = build_symbol_table(
            _module("function number f(vector a, string b) { return 0; }")
        )
        self.assertEqual(st.functions["f"].return_type, "number")
        self.assertEqual(st.functions["f"].param_types, ["vector", "string"])

    def test_extern_similarity_and_embed_are_typed(self):
        sig = extern_signatures()
        self.assertEqual(sig.get("similarity"), ("number", ["vector", "vector"]))
        self.assertEqual(sig.get("embed"), ("vector", ["string"]))

    def test_untyped_builtins_have_no_signature(self):
        # bind/bundle/argmax_cosine are raw BUILTINS with no stdlib type decl.
        sig = extern_signatures()
        for name in ("bind", "bundle", "argmax_cosine"):
            self.assertIsNone(sig.get(name), name)

    def test_call_return_type_and_param_types(self):
        st = build_symbol_table(_module("function fuzzy f(vector a) { return 0; }"))
        self.assertEqual(st.call_return_type("f"), "fuzzy")          # user
        self.assertEqual(st.call_return_type("similarity"), "number")  # extern
        self.assertIsNone(st.call_return_type("bundle"))              # untyped
        self.assertEqual(st.param_types_of("similarity"), ["vector", "vector"])
        self.assertIsNone(st.param_types_of("bundle"))


class TestInferType(unittest.TestCase):
    def test_literals(self):
        cases = {'"hi"': "string", "'c'": "char", "true": "bool",
                 "42": "int", "3.14": "number"}
        for src, expected in cases.items():
            expr, st, _ = _return_expr(src)
            self.assertEqual(infer_type(expr, st), expected, src)

    def test_embed_is_vector(self):
        expr, st, _ = _return_expr('embed("cat")')
        self.assertEqual(infer_type(expr, st), "vector")

    def test_cast_is_target_type(self):
        expr, st, _ = _return_expr('(vector) embed("cat")')
        self.assertEqual(infer_type(expr, st), "vector")

    def test_call_returns_callee_return_type(self):
        m = _module("function number f(vector a, vector b) { return similarity(a, b); }")
        st = build_symbol_table(m)
        ret = next(s for s in m.items[0].body.statements
                   if type(s).__name__ == "ReturnStmt")
        self.assertEqual(infer_type(ret.value, st, local_type_env(m.items[0])), "number")

    def test_identifier_uses_local_type_env(self):
        m = _module("function vector f(string name) { return embed(name); }")
        env = local_type_env(m.items[0])
        self.assertEqual(env.get("name"), "string")
        ident = ast.Identifier(span=None, name="name")
        self.assertEqual(infer_type(ident, build_symbol_table(m), env), "string")

    def test_unknown_constructs_return_none(self):
        # operators / array literals / un-annotated names are left unknown.
        for src in ("a + b", "[embed(\"x\")]", "unknownvar"):
            expr, st, _ = _return_expr(src)
            self.assertIsNone(infer_type(expr, st), src)


if __name__ == "__main__":
    unittest.main()
