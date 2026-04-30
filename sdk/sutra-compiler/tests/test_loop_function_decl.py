"""Tests for the function-declaration loop form (Emma 2026-04-30).

Loops are first-class declared functions whose recurrent state is the
named state parameters. Body uses `pass` for tail-recursive yield.
Call site uses `loop NAME(args)`. See
planning/open-questions/loop-function-declarations.md.

These tests exercise:
1. Parsing — new syntax produces the right AST nodes.
2. Codegen — emitted Python contains the expected loop function +
   call shape.
3. End-to-end execution — number-adder converges to the right value
   (do_while), starting-condition-false skips body (while_loop),
   iterator keyword and tick count (iterative_loop).
4. The body actually runs each tick (the bug the prior body-discard
   designs hid).

Note: tests bypass `translate_module`'s simplify_egglog post-pass by
using the inliner + Codegen directly, since simplify_egglog has a
slow import that can take 20+ minutes on Windows.
"""
from __future__ import annotations

import unittest

import pytest

from sutra_compiler import ast_nodes
from sutra_compiler.codegen_pytorch import PyTorchCodegen
from sutra_compiler.inliner import inline_stdlib_calls
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
    """Return emitted Python source via inliner + PyTorchCodegen
    (bypassing simplify_egglog post-pass so tests don't hang on its
    import). PyTorch is Sutra's canonical compile target — see
    CLAUDE.md and the queue-item-6 numpy-backend retirement work
    (2026-04-30).
    """
    module = _parse(src)
    inline_stdlib_calls(module)
    cg = PyTorchCodegen()
    cg._prefetch_strings = []
    return cg.translate(module)


def _run_main(src: str):
    """Compile, exec, and return main()'s value."""
    py = _compile(src)
    ns: dict = {}
    exec(py, ns)
    main = ns.get("main")
    assert main is not None, "no `main` in emitted module"
    return main()


SIMPLE_DO_WHILE_ADDER = """
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
        module = _parse(SIMPLE_DO_WHILE_ADDER)
        loop_decl = module.items[0]
        self.assertIsInstance(loop_decl, ast_nodes.LoopFunctionDecl)
        self.assertEqual(loop_decl.kind, "do_while")
        self.assertEqual(loop_decl.name, "addNumber")
        self.assertIsInstance(loop_decl.condition, ast_nodes.BinaryOp)
        self.assertEqual(len(loop_decl.state_params), 1)
        self.assertEqual(loop_decl.state_params[0].name, "x")
        self.assertIsInstance(loop_decl.body.statements[0], ast_nodes.PassStmt)

    def test_parses_loop_call_stmt(self):
        module = _parse(SIMPLE_DO_WHILE_ADDER)
        main_decl = module.items[1]
        loop_call = main_decl.body.statements[1]
        self.assertIsInstance(loop_call, ast_nodes.LoopCallStmt)
        self.assertEqual(loop_call.name, "addNumber")
        self.assertEqual(loop_call.state_arg_names, ["x"])

    def test_replace_keyword_in_pass(self):
        src = """
do_while foo(c > 0, int x, int y) {
    pass replace, y + 1;
}
"""
        module = _parse(src)
        loop_decl = module.items[0]
        pass_stmt = loop_decl.body.statements[0]
        self.assertEqual(len(pass_stmt.values), 2)
        self.assertIsInstance(pass_stmt.values[0], ast_nodes.ReplaceMarker)
        self.assertIsInstance(pass_stmt.values[1], ast_nodes.BinaryOp)


class TestCodegenShape(unittest.TestCase):
    """The emitted Python contains the expected substrate-pure shape."""

    def test_emits_loop_function_with_soft_halt(self):
        py = _compile(SIMPLE_DO_WHILE_ADDER)
        self.assertIn("def _loop_addNumber(_init_x):", py)
        self.assertIn("for _t in range(50):", py)
        self.assertIn("_pre_x = x", py)
        # Substrate-pure halt accumulator (queue item 4 fix, 2026-04-30):
        # uses _VSA.saturate_unit instead of Python's min().
        self.assertIn("_halt_cum = _VSA.saturate_unit(_halt_cum + _halt_term)", py)
        self.assertIn("x = (1.0 - _halt_cum) * x + _halt_cum * _pre_x", py)


class TestDoWhile(unittest.TestCase):
    """do_while: body always runs at least once, then condition checked."""

    def test_basic_increment_to_threshold(self):
        # start=9, x<11: body runs; x=10; check 10<11 true; body; x=11;
        # check 11<11 false; halt. Final x=11.
        result = _run_main(SIMPLE_DO_WHILE_ADDER)
        self.assertAlmostEqual(float(result), 11.0, places=2)

    def test_starting_at_threshold_runs_body_once(self):
        # do_while runs body unconditionally before first check, so even
        # if starting value already fails the condition, body runs once.
        # start=11, x<11: preamble runs body; x=12; check 12<11 false; halt.
        # Final x=12 (NOT 11 — that would be while_loop semantics).
        src = SIMPLE_DO_WHILE_ADDER.replace("int x = 9", "int x = 11")
        result = _run_main(src)
        self.assertAlmostEqual(float(result), 12.0, places=2)

    def test_starting_well_past_threshold(self):
        # start=15, x<11: preamble x=16; check 16<11 false; halt. Final 16.
        src = SIMPLE_DO_WHILE_ADDER.replace("int x = 9", "int x = 15")
        result = _run_main(src)
        self.assertAlmostEqual(float(result), 16.0, places=2)


class TestWhileLoop(unittest.TestCase):
    """while_loop: body skipped (effect reverted) if condition false at start."""

    WHILE_SRC = """
while_loop addNumber(x < 11, int x) {
    pass x + 1;
}

function int main() {
    slot int x = 9;
    loop addNumber(x < 11, x);
    return x;
}
"""

    def test_basic_increment(self):
        result = _run_main(self.WHILE_SRC)
        self.assertAlmostEqual(float(result), 11.0, places=2)

    def test_starting_at_threshold_does_not_run(self):
        # while_loop: cond false at start → body's effect reverted by
        # soft mux → final value unchanged from start.
        src = self.WHILE_SRC.replace("int x = 9", "int x = 11")
        result = _run_main(src)
        self.assertAlmostEqual(float(result), 11.0, places=2)

    def test_starting_well_past_threshold_does_not_run(self):
        src = self.WHILE_SRC.replace("int x = 9", "int x = 15")
        result = _run_main(src)
        self.assertAlmostEqual(float(result), 15.0, places=2)


class TestIterativeLoop(unittest.TestCase):
    """iterative_loop: runs body N times; iterator keyword for tick number."""

    SUM_N = """
iterative_loop sumN(5, int total) {
    pass total + iterator;
}

function int main() {
    slot int total = 0;
    loop sumN(5, total);
    return total;
}
"""

    def test_iterator_keyword_sums_correctly(self):
        # iterator is 1-indexed: 1, 2, 3, 4, 5.
        # total starts at 0; after each tick: 0+1=1, 1+2=3, 3+3=6, 6+4=10, 10+5=15.
        result = _run_main(self.SUM_N)
        self.assertAlmostEqual(float(result), 15.0, places=2)

    def test_zero_iterations(self):
        # iterator <= 0 → halt immediately. Body's effect reverted.
        src = self.SUM_N.replace("sumN(5,", "sumN(0,")
        result = _run_main(src)
        # Result should still be 0 (initial value) since no body completes.
        self.assertAlmostEqual(float(result), 0.0, places=2)


class TestPassValidation(unittest.TestCase):
    """`pass` outside a loop body errors clearly."""

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


class TestForeachLoop(unittest.TestCase):
    """foreach_loop: walks elements of a binding-array; binds `element`
    each tick to the current array value."""

    SUM_ARR = """
foreach_loop sumArr(arr, int total) {
    pass total + element;
}

function int main() {
    slot int total = 0;
    loop sumArr([1, 2, 3, 4, 5], total);
    return total;
}
"""

    def test_sum_basic(self):
        # 1+2+3+4+5 = 15
        result = _run_main(self.SUM_ARR)
        self.assertAlmostEqual(float(result), 15.0, places=2)

    def test_sum_single_element(self):
        src = self.SUM_ARR.replace("[1, 2, 3, 4, 5]", "[7]")
        result = _run_main(src)
        self.assertAlmostEqual(float(result), 7.0, places=2)

    def test_sum_ten_elements(self):
        # 1+2+...+10 = 55
        src = self.SUM_ARR.replace(
            "[1, 2, 3, 4, 5]",
            "[1, 2, 3, 4, 5, 6, 7, 8, 9, 10]",
        )
        result = _run_main(src)
        self.assertAlmostEqual(float(result), 55.0, places=2)

    def test_element_outside_foreach_errors(self):
        # `element` is contextual; only valid inside foreach_loop body.
        src = """
function int main() {
    return element;
}
"""
        from sutra_compiler.codegen_base import CodegenNotSupported
        with pytest.raises(CodegenNotSupported) as exc_info:
            _compile(src)
        self.assertIn("element", str(exc_info.value))
        self.assertIn("foreach_loop", str(exc_info.value))


class TestProgramHaltPropagation(unittest.TestCase):
    """Program-level halt propagation (Emma 2026-04-30): a loop that
    runs out of T-step budget without converging emits halt_cum≈0,
    which multiplies through to wipe the function's output. Loops that
    do converge leave halt_cum≈1.0 and the output is preserved."""

    def test_converged_loop_preserves_output(self):
        # Sanity check: existing converging case still returns the
        # same value after halt-multiply (1.0 * 11 == 11).
        result = _run_main(SIMPLE_DO_WHILE_ADDER)
        self.assertAlmostEqual(float(result), 11.0, places=2)

    def test_unconverged_loop_wipes_output(self):
        # iterative_loop with count=1000 and T=50: the cond
        # (_iterator <= 1000) stays true for all 50 ticks, so
        # halt_cum never increments above 0. Output gets multiplied
        # by ~0 → wiped.
        src = """
iterative_loop runForever(1000, int total) {
    pass total + 1;
}

function int main() {
    slot int total = 0;
    loop runForever(1000, total);
    return total;
}
"""
        result = _run_main(src)
        # Wiped output: total accumulates internally but the halt-mux
        # plus _program_halt multiply zero it out at return.
        self.assertAlmostEqual(float(result), 0.0, places=2)

    def test_emitted_program_halt_accumulator(self):
        # The codegen emits the _program_halt accumulator and the
        # multiply on return. Sanity-check the shape.
        py = _compile(SIMPLE_DO_WHILE_ADDER)
        self.assertIn("_program_halt = 1.0", py)
        self.assertIn("_program_halt = _program_halt * _loopret_halt", py)
        self.assertIn("* _program_halt", py)


if __name__ == "__main__":
    unittest.main()
