"""Tests for the loop-call EXPRESSION form (2026-07-12, Stage 1).

`loop NAME(cond, state_expr)` in expression position evaluates to the
loop's FINAL state — the idiomatic surface named in
planning/sutra-spec/control-flow.md §"Call site syntax" and todo.md
§"Make loops idiomatic". It reuses the exact driver the by-reference
statement form emits (`_loop_NAME`), taking the state slot of its
`(state..., halted)` return tuple.

    int x = loop addNumber(x0 < 11, x0);   // init position
    return loop addNumber(x0 < 11, x0);    // return position

Stage 1 supports single-state loops only; a multi-state loop in
expression position raises a codegen diagnostic pointing at the
by-reference statement form.

Like test_loop_function_decl.py these bypass `translate_module`'s slow
simplify_egglog post-pass by driving the inliner + Codegen directly.

The expression form's value is a substrate number-vector (value on
AXIS_REAL), exactly as a plain non-slot `int x = 9 + 2` is — so we read
the scalar out with `_VSA._re(...)`, not `float(...)` (float only works
on the 0-d value the slot plane projects to).
"""
from __future__ import annotations

import unittest

import pytest

from sutra_compiler import ast_nodes
from sutra_compiler.codegen_base import CodegenNotSupported
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
    module = _parse(src)
    inline_stdlib_calls(module)
    cg = PyTorchCodegen()
    cg._prefetch_strings = []
    return cg.translate(module)


def _run_main_real(src: str) -> float:
    """Compile, exec, run main(), and read the real-axis scalar off the
    returned number-vector via the substrate `_re` projection."""
    py = _compile(src)
    ns: dict = {}
    exec(py, ns)
    main = ns.get("main")
    assert main is not None, "no `main` in emitted module"
    result = main()
    vsa = ns["_VSA"]
    return float(vsa._re(result))


def _run_main_string(src: str) -> str:
    """Compile, exec, run main(), and DECODE the returned String vector to
    a Python string via the substrate `string_to_python` boundary — the
    same decode the CLI terminal uses. Ground-truth comparison, not
    "it ran"."""
    py = _compile(src)
    ns: dict = {}
    exec(py, ns)
    main = ns.get("main")
    assert main is not None, "no `main` in emitted module"
    vsa = ns["_VSA"]
    return vsa.string_to_python(main())


# Single-state do_while, invoked in expression position (init).
EXPR_INIT = """
do_while addNumber(x < 11, int x) {
    pass x + 1;
}

function int main() {
    int x = loop addNumber(9 < 11, 9);
    return x;
}
"""

# Single-state do_while, invoked in return (tail) position.
EXPR_RETURN = """
do_while addNumber(x < 11, int x) {
    pass x + 1;
}

function int main() {
    return loop addNumber(9 < 11, 9);
}
"""


class TestParser(unittest.TestCase):
    """`loop NAME(...)` in expression position parses to a LoopCallExpr."""

    def test_init_position_parses_loop_call_expr(self):
        module = _parse(EXPR_INIT)
        main_decl = module.items[1]
        var_decl = main_decl.body.statements[0]
        self.assertIsInstance(var_decl, ast_nodes.VarDecl)
        self.assertIsInstance(var_decl.initializer, ast_nodes.LoopCallExpr)
        call = var_decl.initializer
        self.assertEqual(call.name, "addNumber")
        self.assertIsInstance(call.condition_arg, ast_nodes.BinaryOp)
        self.assertEqual(len(call.state_args), 1)
        self.assertIsInstance(call.state_args[0], ast_nodes.IntLiteral)

    def test_return_position_parses_loop_call_expr(self):
        module = _parse(EXPR_RETURN)
        main_decl = module.items[1]
        ret = main_decl.body.statements[0]
        self.assertIsInstance(ret, ast_nodes.ReturnStmt)
        self.assertIsInstance(ret.value, ast_nodes.LoopCallExpr)
        self.assertEqual(ret.value.name, "addNumber")

    def test_dotted_name_parses(self):
        # A class-bodied loop reference `loop Class.name(...)` keeps the
        # dotted name (codegen decides support; parser just records it).
        src = """
function int main() {
    int x = loop Counter.step(9 < 11, 9);
    return x;
}
"""
        module = _parse(src)
        call = module.items[0].body.statements[0].initializer
        self.assertIsInstance(call, ast_nodes.LoopCallExpr)
        self.assertEqual(call.name, "Counter.step")


class TestCodegenShape(unittest.TestCase):
    """The call site reuses the driver and takes the state slot `[0]`."""

    def test_callsite_indexes_state_slot(self):
        py = _compile(EXPR_INIT)
        # Non-foreach: cond evaluated for side-effect parity, then the
        # driver's first return (the state) is the expression value.
        self.assertIn("_loop_addNumber(9)[0]", py)
        # The driver itself is still emitted exactly once.
        self.assertIn("def _loop_addNumber(_init_x):", py)


class TestEndToEnd(unittest.TestCase):
    """The expression form computes the same final state the statement
    form writes back by reference."""

    def test_init_position_converges(self):
        self.assertAlmostEqual(_run_main_real(EXPR_INIT), 11.0, places=2)

    def test_return_position_converges(self):
        self.assertAlmostEqual(_run_main_real(EXPR_RETURN), 11.0, places=2)

    def test_while_loop_expression_form(self):
        src = """
while_loop addNumber(x < 11, int x) {
    pass x + 1;
}

function int main() {
    return loop addNumber(9 < 11, 9);
}
"""
        self.assertAlmostEqual(_run_main_real(src), 11.0, places=2)

    def test_while_loop_condition_false_at_start(self):
        # while_loop with cond false at start reverts the body effect, so
        # the final state equals the initial state.
        src = """
while_loop addNumber(x < 11, int x) {
    pass x + 1;
}

function int main() {
    return loop addNumber(15 < 11, 15);
}
"""
        self.assertAlmostEqual(_run_main_real(src), 15.0, places=2)

    def test_iterative_loop_expression_form(self):
        # iterator is 1-indexed: 1+2+3+4+5 = 15 accumulated from 0.
        src = """
iterative_loop sumN(5, int total) {
    pass total + iterator;
}

function int main() {
    return loop sumN(5, 0);
}
"""
        self.assertAlmostEqual(_run_main_real(src), 15.0, places=2)

    def test_foreach_loop_expression_form(self):
        # foreach over an array literal: sum 1..5 = 15.
        src = """
foreach_loop sumArr(arr, int total) {
    pass total + element;
}

function int main() {
    return loop sumArr([1, 2, 3, 4, 5], 0);
}
"""
        self.assertAlmostEqual(_run_main_real(src), 15.0, places=2)

    def test_vector_string_state_carries_through_expression_form(self):
        # THE key property (finding 2026-07-12): the expression form
        # threads state straight through the driver, so String/vector loop
        # state survives tick-to-tick. (Historically this bypassed the old
        # scalar slot plane that crushed such state — SUT0206, retired once
        # the unified d-dim slot store made the by-reference form carry
        # vectors too.) Ground-truth decode, not "it ran": 3 iterations
        # each append "x" → "xxx".
        src = """
iterative_loop build(3, String acc) {
    pass string_concat(acc, make_string("x"));
}

function string main() {
    return loop build(3, make_string(""));
}
"""
        self.assertEqual(_run_main_string(src), "xxx")

    def test_state_arg_is_an_expression(self):
        # The state arg is a full expression, not a slot-var name — the
        # whole point of the expression form. Start from 4 + 5 = 9.
        src = """
do_while addNumber(x < 11, int x) {
    pass x + 1;
}

function int main() {
    return loop addNumber(9 < 11, 4 + 5);
}
"""
        self.assertAlmostEqual(_run_main_real(src), 11.0, places=2)


class TestStatementFormUnchanged(unittest.TestCase):
    """The by-reference statement form is untouched by the new surface."""

    def test_by_reference_adder_still_works(self):
        src = """
do_while addNumber(x < 11, int x) {
    pass x + 1;
}

function int main() {
    slot int x = 9;
    loop addNumber(x < 11, x);
    return x;
}
"""
        py = _compile(src)
        # Statement form still slot-loads init + writes back by reference.
        self.assertIn("_loop_addNumber(_VSA.slot_load(_slot_state, 0))", py)
        ns: dict = {}
        exec(py, ns)
        # `_re` boundary (rung 3 B1b): the slot-backed int return is a 0-d
        # tensor today, a number-vector after the representation flip.
        self.assertAlmostEqual(float(ns["_VSA"]._re(ns["main"]())), 11.0,
                               places=2)


class TestMultiStateDiagnostic(unittest.TestCase):
    """Stage 1 rejects multi-state loops in expression position with a
    diagnostic that points at the by-reference statement form."""

    def test_multi_state_loop_expression_form_errors(self):
        src = """
while_loop step((n > 0) && (n != 1), int acc, int n) {
    acc = acc + n;
    pass acc, n - 1;
}

function int main() {
    int r = loop step(3 > 0, 0);
    return r;
}
"""
        with pytest.raises(CodegenNotSupported) as exc_info:
            _compile(src)
        msg = str(exc_info.value)
        self.assertIn("single-state", msg)
        # Steers to BOTH the tuple-destructure form (shipped rung 2) and
        # the by-reference statement form.
        self.assertIn("(a, b) = loop", msg)
        self.assertIn("statement form", msg)


class TestMultiStateDestructure(unittest.TestCase):
    """Rung 2: `(a, b, ...) = loop NAME(cond, s0, s1, ...);` binds a
    multi-state loop's final states to newly-declared locals — the
    multi-state counterpart of the single-state expression form."""

    STEP = """
while_loop step((n > 0) && (n != 1), int acc, int n) {
    acc = acc + n;
    pass acc, n - 1;
}
"""

    def test_parses_to_destructure_stmt(self):
        src = self.STEP + """
function int main() {
    (a, b) = loop step((3 > 0) && (3 != 1), 0, 3);
    return a;
}
"""
        module = _parse(src)
        main_decl = module.items[1]
        stmt = main_decl.body.statements[0]
        self.assertIsInstance(stmt, ast_nodes.LoopDestructureStmt)
        self.assertEqual(stmt.names, ["a", "b"])
        self.assertIsInstance(stmt.call, ast_nodes.LoopCallExpr)
        self.assertEqual(stmt.call.name, "step")

    def test_binds_both_states(self):
        # acc accumulates 3 then 2 (n: 3->2->1, halts at n==1); a=5, b=1.
        base = self.STEP + """
function int main() {
    (a, b) = loop step((3 > 0) && (3 != 1), 0, 3);
    return %s;
}
"""
        self.assertAlmostEqual(_run_main_real(base % "a"), 5.0, places=2)
        self.assertAlmostEqual(_run_main_real(base % "b"), 1.0, places=2)

    def test_destructured_names_are_referenceable(self):
        # The bound names are real locals — used in later arithmetic.
        src = self.STEP + """
function int main() {
    (a, b) = loop step((3 > 0) && (3 != 1), 0, 3);
    return a + b;
}
"""
        self.assertAlmostEqual(_run_main_real(src), 6.0, places=2)

    def test_arity_mismatch_errors(self):
        src = self.STEP + """
function int main() {
    (a, b, c) = loop step((3 > 0) && (3 != 1), 0, 3);
    return a;
}
"""
        with pytest.raises(CodegenNotSupported) as exc:
            _compile(src)
        msg = str(exc)
        self.assertIn("2 state parameter", msg)
        self.assertIn("binds 3", msg)

    def test_non_loop_rhs_is_a_parse_error(self):
        # Sutra has no general tuples — a `(a, b) =` target is only valid
        # for a loop call.
        src = """
function int main() {
    (a, b) = 5 + 3;
    return a;
}
"""
        lexer = Lexer(src, file="<test>")
        parser = Parser(lexer.tokenize(), file="<test>",
                        diagnostics=lexer.diagnostics)
        parser.parse_module()
        errors = [d.format() for d in lexer.diagnostics.errors]
        self.assertTrue(errors, "expected a parse error for non-loop RHS")
        self.assertTrue(any("loop call" in e for e in errors), errors)


class TestExpressionFormDiagnostics(unittest.TestCase):
    """The remaining Stage-1 rejection branches produce actionable
    diagnostics (verified live: SUT-style span-carrying messages, no raw
    Python traceback). These lock in error paths that were otherwise
    untested — a future refactor that silently broke one would be caught
    here."""

    ADDER = """
do_while addNumber(x < 11, int x) {
    pass x + 1;
}
"""

    def test_too_few_state_args(self):
        src = self.ADDER + """
function int main() {
    int x = loop addNumber(9 < 11);
    return x;
}
"""
        with pytest.raises(CodegenNotSupported) as exc:
            _compile(src)
        msg = str(exc)
        self.assertIn("1 state argument", msg)
        self.assertIn("got 0", msg)

    def test_too_many_state_args(self):
        src = self.ADDER + """
function int main() {
    int x = loop addNumber(9 < 11, 9, 9);
    return x;
}
"""
        with pytest.raises(CodegenNotSupported) as exc:
            _compile(src)
        msg = str(exc)
        self.assertIn("1 state argument", msg)
        self.assertIn("got 2", msg)

    def test_undeclared_loop(self):
        src = """
function int main() {
    int x = loop nope(9 < 11, 9);
    return x;
}
"""
        with pytest.raises(CodegenNotSupported) as exc:
            _compile(src)
        msg = str(exc)
        self.assertIn("not declared", msg)
        self.assertIn("nope", msg)

    def test_non_static_class_loop(self):
        # A non-static class loop threads `this` (returned first) and
        # rebinds the caller instance — no meaning as a pure value, so the
        # expression form is rejected pointing at the statement form.
        src = """
class Counter extends vector {
    do_while step(x < 5, int x) {
        pass x + 1;
    }
}

function int main() {
    Counter c = (Counter) zero_vector();
    int r = loop Counter.step(c, 0);
    return r;
}
"""
        with pytest.raises(CodegenNotSupported) as exc:
            _compile(src)
        msg = str(exc)
        self.assertIn("non-static class loop", msg)
        self.assertIn("statement form", msg)




class TestStringCharAtNumberVectorIndex(unittest.TestCase):
    """Reach-audit fix (2026-07-13): `string_char_at` with a NUMBER-VECTOR
    index — the form a loop-threaded state param produces (`i - 1` is a
    num_sub number-vector). The old `_st(i)` boundary passed the d-dim
    index through unprojected, making the gather return a d-wide garbage
    "codepoint" that poisoned every downstream string op. `_scalar(i)`
    projects it to the real-axis 0-d value.

    End-to-end: reverse a string char-by-char through a mixed
    String+scalar multi-state loop — the reach probe that decoded as
    'c' + 98 fill chars before the fix.
    """

    def test_reverse_string_via_loop(self):
        src = """
while_loop rev(i > 0, String out, String s, int i) {
    pass string_concat(out, make_char(string_char_at(s, i - 1))), replace, i - 1;
}

function string main() {
    (out, s2, i) = loop rev((3 > 0), make_string(""), make_string("abc"), 3);
    return out;
}
"""
        self.assertEqual(_run_main_string(src), "cba")


if __name__ == "__main__":
    unittest.main()


class TestIntIntrinsicEqualityRouting(unittest.TestCase):
    """Reach-audit fix (2026-07-13): `==` where one operand is a call to an
    int-returning intrinsic (string_char_at) must route to num_eq, not the
    general vector eq (whose cosine reads ANY two numbers as equal —
    measured eq(98, 97) → true). The Call branch in
    _infer_cast_operand_type consults declared return types.

    Note the SIGNED truth semantics: `(number)(cond)` is +1/-1 (the
    fizzbuzz score algebra depends on it), so a 0/1 counter maps via
    (s + 1) / 2."""

    def test_count_matching_chars_via_codepoint_eq(self):
        src = """
while_loop count(i < 3, int n, String s, int i) {
    pass n + ((number)(string_char_at(s, i) == 97) + 1) / 2, replace, i + 1;
}

function int main() {
    (n, s2, i) = loop count((0 < 3), 0, make_string("aba"), 0);
    return n;
}
"""
        # 'aba': codepoints 97, 98, 97 -> exactly two match 97.
        self.assertAlmostEqual(_run_main_real(src), 2.0, places=2)
