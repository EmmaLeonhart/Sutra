"""Unit tests for the implicit-loop variable-capture analysis
(`sutra_compiler.loop_capture.captured_state`).

This is the first, isolated unit of the implicit `loop(x){body}`
desugar (queue.md item 0). Pure AST analysis — no codegen, no
control-flow regression surface.
"""
from __future__ import annotations

import dataclasses
import unittest

from sutra_compiler import ast_nodes as ast
from sutra_compiler.lexer import Lexer
from sutra_compiler.loop_capture import captured_state, free_identifiers
from sutra_compiler.parser import Parser


def _first_loop_body(src: str) -> ast.Block:
    lexer = Lexer(src, file="<test>")
    tokens = lexer.tokenize()
    parser = Parser(tokens, file="<test>", diagnostics=lexer.diagnostics)
    module = parser.parse_module()
    assert not lexer.diagnostics.has_errors(), list(lexer.diagnostics)

    found: list[ast.LoopStmt] = []

    def _walk(node: object) -> None:
        if isinstance(node, ast.LoopStmt):
            found.append(node)
        if not dataclasses.is_dataclass(node):
            return
        for f in dataclasses.fields(node):
            v = getattr(node, f.name, None)
            if dataclasses.is_dataclass(v):
                _walk(v)
            elif isinstance(v, (list, tuple)):
                for item in v:
                    if dataclasses.is_dataclass(item):
                        _walk(item)

    _walk(module)
    assert found, "no LoopStmt parsed from source"
    return found[0].body


class TestCapturedState(unittest.TestCase):
    def test_single_mutated_var(self):
        # `i` is declared outside the loop -> threaded state.
        # `iterator` is only read -> not state. `x` is the bound,
        # not in the body at all.
        src = (
            "function int main() {\n"
            "  int i = 0;\n"
            "  int iterator = 1;\n"
            "  int x = 5;\n"
            "  loop(x) { i += iterator; }\n"
            "  return i;\n"
            "}\n"
        )
        self.assertEqual(captured_state(_first_loop_body(src)), ["i"])

    def test_multi_var_order_preserved(self):
        # Emma's exact multi-var example. First-mutation order.
        src = (
            "function int main() {\n"
            "  int n1 = 0;\n"
            "  int n2 = 0;\n"
            "  int x = 5;\n"
            "  loop(x) { n1 = n1 + 1; n2 = n2 + 2; }\n"
            "  return n1 + n2;\n"
            "}\n"
        )
        self.assertEqual(captured_state(_first_loop_body(src)), ["n1", "n2"])

    def test_body_local_decl_excluded(self):
        # `tmp` is declared inside the body -> per-iteration local,
        # NOT recurrent state, even though it is mutated.
        src = (
            "function int main() {\n"
            "  int n1 = 0;\n"
            "  int x = 5;\n"
            "  loop(x) { int tmp = 0; tmp += 1; n1 = n1 + tmp; }\n"
            "  return n1;\n"
            "}\n"
        )
        self.assertEqual(captured_state(_first_loop_body(src)), ["n1"])

    def test_postfix_increment_is_mutation(self):
        src = (
            "function int main() {\n"
            "  int i = 0;\n"
            "  int x = 5;\n"
            "  loop(x) { i++; }\n"
            "  return i;\n"
            "}\n"
        )
        self.assertEqual(captured_state(_first_loop_body(src)), ["i"])

    def test_mutation_inside_nested_if(self):
        src = (
            "function int main() {\n"
            "  int n1 = 0;\n"
            "  int n2 = 0;\n"
            "  int x = 5;\n"
            "  loop(x) { if (n1 > 0) { n2 = n2 + 1; } }\n"
            "  return n2;\n"
            "}\n"
        )
        self.assertEqual(captured_state(_first_loop_body(src)), ["n2"])

    def test_first_mutation_order_not_alphabetical(self):
        src = (
            "function int main() {\n"
            "  int a = 0;\n"
            "  int b = 0;\n"
            "  int x = 5;\n"
            "  loop(x) { b = b + 1; a = a + 1; }\n"
            "  return a + b;\n"
            "}\n"
        )
        self.assertEqual(captured_state(_first_loop_body(src)), ["b", "a"])

    def test_pure_no_ast_mutation(self):
        src = (
            "function int main() {\n"
            "  int i = 0;\n"
            "  int x = 5;\n"
            "  loop(x) { i = i + 1; }\n"
            "  return i;\n"
            "}\n"
        )
        body = _first_loop_body(src)
        before = len(body.statements)
        captured_state(body)
        captured_state(body)  # idempotent
        self.assertEqual(len(body.statements), before)
        self.assertEqual(captured_state(body), ["i"])


def _first_loop_condition(src: str):
    lexer = Lexer(src, file="<test>")
    tokens = lexer.tokenize()
    parser = Parser(tokens, file="<test>", diagnostics=lexer.diagnostics)
    module = parser.parse_module()
    assert not lexer.diagnostics.has_errors(), list(lexer.diagnostics)
    found: list[ast.LoopStmt] = []

    def _walk(node: object) -> None:
        if isinstance(node, ast.LoopStmt):
            found.append(node)
        if not dataclasses.is_dataclass(node):
            return
        for f in dataclasses.fields(node):
            v = getattr(node, f.name, None)
            if dataclasses.is_dataclass(v):
                _walk(v)
            elif isinstance(v, (list, tuple)):
                for item in v:
                    if dataclasses.is_dataclass(item):
                        _walk(item)

    _walk(module)
    assert found, "no LoopStmt parsed"
    return found[0].condition


class TestFreeIdentifiers(unittest.TestCase):
    def test_bare_bound_var(self):
        src = (
            "function int main() {\n"
            "  int i = 0; int x = 5;\n"
            "  loop(x) { i = i + 1; }\n"
            "  return i;\n}\n"
        )
        self.assertEqual(free_identifiers(_first_loop_condition(src)), ["x"])

    def test_relational_bound_literal_excluded(self):
        src = (
            "function int main() {\n"
            "  int n = 0;\n"
            "  loop(n < 11) { n = n + 1; }\n"
            "  return n;\n}\n"
        )
        # `11` is a literal -> not an identifier; `n` is referenced.
        self.assertEqual(free_identifiers(_first_loop_condition(src)), ["n"])

    def test_two_bound_vars_order(self):
        src = (
            "function int main() {\n"
            "  int n = 0; int limit = 9; int base = 1;\n"
            "  loop(n < limit + base) { n = n + 1; }\n"
            "  return n;\n}\n"
        )
        self.assertEqual(
            free_identifiers(_first_loop_condition(src)),
            ["n", "limit", "base"],
        )

    def test_call_callee_excluded_args_kept(self):
        src = (
            "function int main() {\n"
            "  int n = 0; int cap = 3;\n"
            "  loop(n < Math.abs(cap)) { n = n + 1; }\n"
            "  return n;\n}\n"
        )
        # Math.abs callee is not a slottable value var; `cap` is.
        got = free_identifiers(_first_loop_condition(src))
        self.assertIn("n", got)
        self.assertIn("cap", got)
        self.assertNotIn("abs", got)


if __name__ == "__main__":
    unittest.main()
