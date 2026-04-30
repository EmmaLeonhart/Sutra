"""Tests for the function-declaration loop form (Emma 2026-04-30).

Loops are first-class declared functions whose recurrent state is the
named state parameters. Body uses `pass` for tail-recursive yield.
Call site uses `loop NAME(args)`. See
planning/open-questions/loop-function-declarations.md.

These tests verify:
1. Parsing — new syntax produces the right AST nodes.
2. Codegen — emitted Python contains the expected loop function +
   call shape.
3. End-to-end execution — the number-adder converges to the right
   value (start=9 → end=11).
4. The body actually runs each tick (the bug the prior body-discard
   designs hid).
"""
from __future__ import annotations

import unittest

import pytest

from sutra_compiler import ast_nodes
from sutra_compiler.codegen import translate_module as np_translate
from sutra_compiler.lexer import Lexer
from sutra_compiler.parser import Parser


def _parse(src: str):
    lexer = Lexer(src, file="<test>")
    tokens = lexer.tokenize()
    parser = Parser(tokens, file="<test>", diagnostics=lexer.diagnostics)
    module = parser.parse_module()
    errors = list(lexer.diagnostics.errors)
    assert not errors, [str(e) for e in errors]
    return module


def _compile(src: str) -> str:
    """Return emitted Python source from the numpy backend."""
    return np_translate(_parse(src))


def _exec_prelude_and_call_main(py_src: str):
    """Exec the emitted module up through main() and return main()'s result."""
    namespace: dict = {}
    exec(py_src, namespace)
    main = namespace.get("main")
    assert main is not None, "no `main` in emitted module"
    return main()


SIMPLE_ADDER = """
do_while addNumber(x < 11, int x) {
    pass x + 1;
}

function int main() {
    slot int x = 9;
    loop addNumber(x < 11, x);
    return x;
}
"""


class TestParser(unittest.TestCase):
    """The parser produces the right AST nodes for the new syntax."""

    def test_parses_loop_function_decl(self):
        module = _parse(SIMPLE_ADDER)
        decls = module.items
        # First decl: LoopFunctionDecl.
        self.assertIsInstance(decls[0], ast_nodes.LoopFunctionDecl)
        loop_decl = decls[0]
        self.assertEqual(loop_decl.kind, "do_while")
        self.assertEqual(loop_decl.name, "addNumber")
        # Condition: a binary op (`x < 11`).
        self.assertIsInstance(loop_decl.condition, ast_nodes.BinaryOp)
        # State params: one int x.
        self.assertEqual(len(loop_decl.state_params), 1)
        self.assertEqual(loop_decl.state_params[0].name, "x")
        # Body has one PassStmt.
        self.assertEqual(len(loop_decl.body.statements), 1)
        self.assertIsInstance(loop_decl.body.statements[0], ast_nodes.PassStmt)

    def test_parses_loop_call_stmt(self):
        module = _parse(SIMPLE_ADDER)
        main_decl = module.items[1]
        # main's body has slot decl, loop call, return.
        loop_call = main_decl.body.statements[1]
        self.assertIsInstance(loop_call, ast_nodes.LoopCallStmt)
        self.assertEqual(loop_call.name, "addNumber")
        self.assertEqual(loop_call.state_arg_names, ["x"])

    def test_replace_keyword_in_pass(self):
        src = """
do_while foo(c > 0, int x, int y) {
    pass replace, y + 1;
}

function int main() {
    slot int a = 5;
    slot int b = 0;
    loop foo(a > 0, a, b);
    return b;
}
"""
        module = _parse(src)
        loop_decl = module.items[0]
        pass_stmt = loop_decl.body.statements[0]
        self.assertIsInstance(pass_stmt, ast_nodes.PassStmt)
        self.assertEqual(len(pass_stmt.values), 2)
        # First value is `replace`, second is `y + 1`.
        self.assertIsInstance(pass_stmt.values[0], ast_nodes.ReplaceMarker)
        self.assertIsInstance(pass_stmt.values[1], ast_nodes.BinaryOp)


class TestCodegen(unittest.TestCase):
    """The emitted Python has the right shape."""

    def test_emits_loop_function(self):
        py = _compile(SIMPLE_ADDER)
        # Loop function appears as `def _loop_addNumber(...)`.
        self.assertIn("def _loop_addNumber(_init_x):", py)
        # State init from arg.
        self.assertIn("x = _init_x", py)
        # T-step soft-halt loop.
        self.assertIn("for _t in range(50):", py)
        # Snapshot for soft mux.
        self.assertIn("_pre_x = x", py)
        # Condition eval.
        self.assertIn("_keep = 1.0 if bool(", py)
        # Halt accumulation.
        self.assertIn("_halt_cum = min(_halt_cum + _halt_term, 1.0)", py)
        # Soft mux.
        self.assertIn("x = (1.0 - _halt_cum) * x + _halt_cum * _pre_x", py)

    def test_emits_loop_call(self):
        py = _compile(SIMPLE_ADDER)
        # Call to _loop_addNumber with slot_load init.
        self.assertIn("_loop_addNumber(_VSA.slot_load(_slot_state,", py)
        # Writeback via slot_store.
        self.assertIn("_VSA.slot_store(_slot_state,", py)


class TestEndToEnd(unittest.TestCase):
    """The number-adder actually computes 11 starting from 9."""

    def test_number_adder_converges(self):
        py = _compile(SIMPLE_ADDER)
        result = _exec_prelude_and_call_main(py)
        # Soft-mux means result might be a float close to 11, not exactly 11.
        # Tolerance accounts for the soft halt's last partial step.
        self.assertAlmostEqual(float(result), 11.0, places=2,
                               msg=f"expected ~11, got {result}")


class TestPassValidation(unittest.TestCase):
    """`pass` outside a loop body, or with wrong arg count, errors clearly."""

    def test_pass_outside_loop_body_errors(self):
        src = """
function int main() {
    pass 1;
    return 0;
}
"""
        from sutra_compiler.codegen_base import CodegenNotSupported
        with pytest.raises(CodegenNotSupported) as exc_info:
            _compile(src)
        self.assertIn("pass", str(exc_info.value))
        self.assertIn("loop function body", str(exc_info.value))


if __name__ == "__main__":
    unittest.main()
