"""Tests for the stdlib inliner — step 2 of the function-expansion
pipeline.

The inliner rewrites every `Call(Identifier(name), args)` against
the stdlib symbol table. Bodies that are a single `return <expr>;`
get substituted inline; statement-bodied functions (defuzzy)
currently pass through unchanged and continue to hit their runtime
methods — statement inlining is a separate extension.

Tests strategy: compile .su source through the full pipeline and
assert on emitted Python. When a stdlib call is inlined, the
corresponding runtime-method call (`_VSA.logical_and`, etc.) should
NOT appear and the polynomial / rewritten form should.
"""
from __future__ import annotations

import unittest

from sutra_compiler import ast_nodes as ast
from sutra_compiler.codegen import translate_module
from sutra_compiler.inliner import inline_stdlib_calls
from sutra_compiler.lexer import Lexer
from sutra_compiler.parser import Parser
from sutra_compiler.stdlib_loader import load_stdlib


def _parse(src: str) -> ast.Module:
    lexer = Lexer(src, file="<test>")
    tokens = lexer.tokenize()
    parser = Parser(tokens, file="<test>", diagnostics=lexer.diagnostics)
    module = parser.parse_module()
    assert not lexer.diagnostics.has_errors(), list(lexer.diagnostics)
    return module


def _compile(src: str) -> str:
    """Full pipeline: parse → inline → simplify → codegen. Returns
    emitted Python source."""
    module = _parse(src)
    py = translate_module(module)
    # Verify it parses as Python too.
    compile(py, "<generated>", "exec")
    return py


class TestInlinerSingleReturn(unittest.TestCase):
    """Each of the 7 single-return stdlib functions should inline
    when called by name."""

    # Assertions check the AST of `f` after the inline pass, not
    # substrings in emitted Python — the runtime prelude contains
    # `def le(self, a, b): return self.lt(a, b)` etc. which would
    # give false positives on any `substring in py` check.

    def _inline(self, src: str) -> ast.Expr:
        """Parse, inline, return the return-expr of the first
        function declaration in the module."""
        module = _parse(src)
        inline_stdlib_calls(module)
        fn = next(it for it in module.items if isinstance(it, ast.FunctionDecl))
        ret = fn.body.statements[0]
        assert isinstance(ret, ast.ReturnStmt)
        return ret.value

    def test_logical_not_inlines_to_subtract(self):
        expr = self._inline(
            "function fuzzy f(fuzzy v) {\n"
            "  return logical_not(v);\n"
            "}\n"
        )
        # logical_not body: `0 - v` → BinaryOp(op='-', left=0, right=v)
        self.assertIsInstance(expr, ast.BinaryOp)
        self.assertEqual(expr.op, "-")
        self.assertIsInstance(expr.left, ast.IntLiteral)
        self.assertEqual(expr.left.value, 0)
        self.assertIsInstance(expr.right, ast.Identifier)
        self.assertEqual(expr.right.name, "v")

    def test_logical_and_inlines_to_polynomial(self):
        expr = self._inline(
            "function fuzzy f(fuzzy a, fuzzy b) {\n"
            "  return logical_and(a, b);\n"
            "}\n"
        )
        # logical_and body: `(a + b + a*b - a*a - b*b + a*a*b*b) * 0.5`
        # Top-level form is a multiply by 0.5.
        self.assertIsInstance(expr, ast.BinaryOp)
        self.assertEqual(expr.op, "*")
        self.assertIsInstance(expr.right, ast.FloatLiteral)
        self.assertAlmostEqual(expr.right.value, 0.5)
        # The entire polynomial must reference both params `a` and `b`
        # by the substituted names (here also `a` and `b` since the
        # user function used the same names — substitution is by AST).
        text = _repr_expr_tree(expr)
        self.assertIn("a", text)
        self.assertIn("b", text)

    def test_logical_and_substitutes_different_arg_names(self):
        # User passes `x, y`; the polynomial body uses `a, b` in the
        # stdlib definition. After inlining the body should reference
        # `x` and `y`, not `a` or `b`.
        expr = self._inline(
            "function fuzzy f(fuzzy x, fuzzy y) {\n"
            "  return logical_and(x, y);\n"
            "}\n"
        )
        text = _repr_expr_tree(expr)
        self.assertIn("x", text)
        self.assertIn("y", text)
        # `a` and `b` are the param names in the stdlib body; they
        # must NOT appear in the inlined form as Identifier names.
        self.assertNotIn("Identifier(name='a'", text)
        self.assertNotIn("Identifier(name='b'", text)

    def test_neq_inlines_through_to_polynomial(self):
        expr = self._inline(
            "vector cat = \"cat\";\n"
            "vector dog = \"dog\";\n"
            "function fuzzy f() {\n"
            "  return neq(cat, dog);\n"
            "}\n"
        )
        # neq body: `!(a == b)`. `!` is a stdlib-lowered UnaryOp so it
        # rewrites to Call(logical_not, ...) which inlines to `0 - _`.
        # Final shape: BinaryOp('-', IntLiteral(0), <== expr>).
        self.assertIsInstance(expr, ast.BinaryOp)
        self.assertEqual(expr.op, "-")
        self.assertIsInstance(expr.left, ast.IntLiteral)
        self.assertEqual(expr.left.value, 0)
        # No stdlib call-by-name survives.
        self.assertNotIn("neq", _collect_call_names(expr))
        self.assertNotIn("logical_not", _collect_call_names(expr))

    def test_lt_inlines_to_swapped_gt(self):
        expr = self._inline(
            "function fuzzy f(complex a, complex b) {\n"
            "  return lt(a, b);\n"
            "}\n"
        )
        # lt body: `b > a` → BinaryOp(op='>', left=b, right=a)
        self.assertIsInstance(expr, ast.BinaryOp)
        self.assertEqual(expr.op, ">")
        self.assertIsInstance(expr.left, ast.Identifier)
        self.assertEqual(expr.left.name, "b")
        self.assertIsInstance(expr.right, ast.Identifier)
        self.assertEqual(expr.right.name, "a")


def _collect_call_names(expr) -> set:
    """Return the set of identifier-names used as Call callees
    anywhere in the given expression tree."""
    import dataclasses
    names: set = set()

    def walk(node):
        if node is None:
            return
        if isinstance(node, ast.Call) and isinstance(node.callee, ast.Identifier):
            names.add(node.callee.name)
        if dataclasses.is_dataclass(node):
            for field in dataclasses.fields(node):
                child = getattr(node, field.name, None)
                if isinstance(child, list):
                    for c in child:
                        walk(c)
                else:
                    walk(child)

    walk(expr)
    return names


def _repr_expr_tree(expr) -> str:
    """Cheap AST stringifier for test assertions. Walks the expr
    and returns a flat representation including every Identifier."""
    import dataclasses

    def walk(node, parts):
        if node is None:
            return
        if isinstance(node, ast.Identifier):
            parts.append(f"Identifier(name={node.name!r})")
            return
        if dataclasses.is_dataclass(node):
            for field in dataclasses.fields(node):
                child = getattr(node, field.name, None)
                if isinstance(child, list):
                    for c in child:
                        walk(c, parts)
                else:
                    walk(child, parts)

    parts = []
    walk(expr, parts)
    return " ".join(parts)


class TestInlinerStatementBodiedPassesThrough(unittest.TestCase):
    """defuzzy is statement-bodied (contains a loop). The inliner
    today skips it — call-by-name stays a Call, and codegen handles
    it as any other user call. The `defuzzy(v)` keyword form (which
    parses to DefuzzyExpr, not Call) is unaffected."""

    def test_defuzzy_keyword_form_expands_inline(self):
        # `defuzzy(v)` at expression position parses as DefuzzyExpr.
        # Codegen's _defuzzy_expr_src now expands it inline to ten
        # nested _VSA.eq calls wrapping the truth-axis projection
        # (instead of the single _VSA.defuzzify runtime call it used
        # to emit). _VSA.defuzzify is dead and removable.
        src = (
            "function bool f(fuzzy v) {\n"
            "  return defuzzy(v);\n"
            "}\n"
        )
        py = _compile(src)
        # Ten nested _VSA.eq calls + a truth-projector + _as_any_vector.
        # Count `_VSA.eq(` occurrences — need at least 10.
        self.assertGreaterEqual(py.count("_VSA.eq("), 10)
        self.assertIn("_VSA._truth_projector()", py)
        self.assertNotIn("_VSA.defuzzify", py)


class TestInlinerNested(unittest.TestCase):
    """Calls within calls: inner inlines first (post-order)."""

    def test_nested_inline(self):
        module = _parse(
            "function fuzzy f(fuzzy a, fuzzy b) {\n"
            "  return logical_or(logical_not(a), b);\n"
            "}\n"
        )
        inline_stdlib_calls(module)
        fn = module.items[0]
        ret = fn.body.statements[0]
        # No Call(Identifier('logical_or')) or Call(Identifier('logical_not'))
        # anywhere in the resulting tree.
        calls_by_name = _collect_call_names(ret.value)
        self.assertNotIn("logical_or", calls_by_name)
        self.assertNotIn("logical_not", calls_by_name)


class TestInlinerArityMismatchPreserved(unittest.TestCase):
    """If the arity doesn't match, we leave the call alone and let
    the validator (or a later pass) diagnose."""

    def test_wrong_arity_not_inlined(self):
        # logical_and takes 2 args. Calling it with 1 produces AST
        # the inliner should leave untouched.
        module = _parse(
            "function fuzzy f(fuzzy a) {\n"
            "  return logical_and(a);\n"
            "}\n"
        )
        inline_stdlib_calls(module)
        # The return expr should still be a Call to logical_and.
        fn = module.items[0]
        assert isinstance(fn, ast.FunctionDecl)
        ret = fn.body.statements[0]
        assert isinstance(ret, ast.ReturnStmt)
        self.assertIsInstance(ret.value, ast.Call)
        self.assertEqual(ret.value.callee.name, "logical_and")


class TestInlinerPreservesNonStdlibCalls(unittest.TestCase):
    """User-defined functions and runtime builtins that aren't in the
    stdlib table should pass through untouched."""

    def test_user_function_call_unchanged(self):
        module = _parse(
            "function fuzzy helper(fuzzy v) {\n"
            "  return v;\n"
            "}\n"
            "function fuzzy f(fuzzy v) {\n"
            "  return helper(v);\n"
            "}\n"
        )
        inline_stdlib_calls(module)
        fn = module.items[1]
        ret = fn.body.statements[0]
        # helper is user-defined, not stdlib; the call must remain.
        self.assertIn("helper", _collect_call_names(ret.value))


class TestInlinerIdempotent(unittest.TestCase):
    """Running the inliner twice produces the same result. Useful
    because downstream passes (simplify) might create new Calls that
    the inliner could consume on a second pass — idempotence gives us
    headroom to iterate without infinite loops."""

    def test_double_pass_matches_single(self):
        src = (
            "function fuzzy f(fuzzy a, fuzzy b) {\n"
            "  return logical_and(a, b);\n"
            "}\n"
        )
        m1 = _parse(src)
        m2 = _parse(src)
        inline_stdlib_calls(m1)
        inline_stdlib_calls(m2)
        inline_stdlib_calls(m2)  # twice
        # Codegen both; they must match.
        py1 = translate_module(m1)
        py2 = translate_module(m2)
        self.assertEqual(py1, py2)


class TestOperatorLowering(unittest.TestCase):
    """Step 2.6 — operators with stdlib bodies (&&, ||, !, !=, <, <=,
    >=) lower to Call nodes targeting their stdlib functions, then
    the inliner expands them. Operators without stdlib bodies (==, >,
    +, -, *, /) stay as operators."""

    def test_and_operator_lowers_and_inlines(self):
        module = _parse(
            "function fuzzy f(fuzzy a, fuzzy b) {\n"
            "  return a && b;\n"
            "}\n"
        )
        inline_stdlib_calls(module)
        fn = module.items[0]
        expr = fn.body.statements[0].value
        # After inline: (a + b + ... ) * 0.5 — top is BinaryOp('*')
        # with the 0.5 literal as the right operand.
        self.assertIsInstance(expr, ast.BinaryOp)
        self.assertEqual(expr.op, "*")

    def test_not_operator_lowers_and_inlines(self):
        module = _parse(
            "function fuzzy f(fuzzy v) {\n"
            "  return !v;\n"
            "}\n"
        )
        inline_stdlib_calls(module)
        fn = module.items[0]
        expr = fn.body.statements[0].value
        # After inline: 0 - v → BinaryOp('-')
        self.assertIsInstance(expr, ast.BinaryOp)
        self.assertEqual(expr.op, "-")

    def test_lt_operator_lowers_to_swapped_gt(self):
        module = _parse(
            "function fuzzy f(complex a, complex b) {\n"
            "  return a < b;\n"
            "}\n"
        )
        inline_stdlib_calls(module)
        fn = module.items[0]
        expr = fn.body.statements[0].value
        # lt body: b > a
        self.assertIsInstance(expr, ast.BinaryOp)
        self.assertEqual(expr.op, ">")
        self.assertIsInstance(expr.left, ast.Identifier)
        self.assertEqual(expr.left.name, "b")

    def test_eq_operator_preserved(self):
        """eq has no stdlib body (blocked on intrinsics), so `a == b`
        stays as BinaryOp('==') and compiles through _VSA.eq."""
        module = _parse(
            "function fuzzy f(vector a, vector b) {\n"
            "  return a == b;\n"
            "}\n"
        )
        inline_stdlib_calls(module)
        fn = module.items[0]
        expr = fn.body.statements[0].value
        self.assertIsInstance(expr, ast.BinaryOp)
        self.assertEqual(expr.op, "==")

    def test_gt_operator_preserved(self):
        """Same story — gt body is blocked."""
        module = _parse(
            "function fuzzy f(int a, int b) {\n"
            "  return a > b;\n"
            "}\n"
        )
        inline_stdlib_calls(module)
        fn = module.items[0]
        expr = fn.body.statements[0].value
        self.assertIsInstance(expr, ast.BinaryOp)
        self.assertEqual(expr.op, ">")

    def test_arithmetic_operators_preserved(self):
        """+, -, *, / are primitive tensor arithmetic, not stdlib."""
        module = _parse(
            "function fuzzy f(fuzzy a, fuzzy b) {\n"
            "  return a + b;\n"
            "}\n"
        )
        inline_stdlib_calls(module)
        fn = module.items[0]
        expr = fn.body.statements[0].value
        self.assertIsInstance(expr, ast.BinaryOp)
        self.assertEqual(expr.op, "+")

    def test_nested_operators_lower(self):
        """!(a && b) lowers to logical_not(logical_and(a, b)) and both
        inline — the outer !() and inner && both expand."""
        module = _parse(
            "function fuzzy f(fuzzy a, fuzzy b) {\n"
            "  return !(a && b);\n"
            "}\n"
        )
        inline_stdlib_calls(module)
        fn = module.items[0]
        expr = fn.body.statements[0].value
        # No Call-by-name to logical_and or logical_not should survive.
        calls = _collect_call_names(expr)
        self.assertNotIn("logical_and", calls)
        self.assertNotIn("logical_not", calls)


class TestFusionConstantFolding(unittest.TestCase):
    """Step 6 — the fusion pass, first slice. When stdlib-inlined
    bodies have literal arguments, the resulting polynomial collapses
    to a single compile-time constant; the emitted runtime sees one
    `make_truth(...)` call instead of a chain of arithmetic ops."""

    def test_logical_and_literal_args_folds_to_constant(self):
        src = (
            "function fuzzy main() {\n"
            "  fuzzy x = logical_and(0.7, 0.3);\n"
            "  return x;\n"
            "}\n"
        )
        py = _compile(src)
        # After inline + full constant fold, the body should contain
        # exactly one make_truth call wrapping a folded literal.
        # 0.7 * 0.3 = 0.21, the polynomial evaluates to 0.33705 (×0.5
        # applied as part of the spec form). Emitted form inside main:
        #   x = _VSA.make_truth(0.33705)
        self.assertIn("_VSA.make_truth(0.33705)", py)

    def test_logical_and_symbolic_args_stay_polynomial(self):
        # No fold when args are variables — the polynomial stays
        # as arithmetic ops (fusion at matrix level is future work).
        src = (
            "function fuzzy f(fuzzy a, fuzzy b) {\n"
            "  return logical_and(a, b);\n"
            "}\n"
        )
        py = _compile(src)
        self.assertIn("0.5", py)   # the `* 0.5` tail from the polynomial
        self.assertIn("a", py)
        self.assertIn("b", py)

    def test_not_not_folds_to_noop_on_literal(self):
        # !!0.5 → 0 - (0 - 0.5) → 0.5. Full arithmetic fold.
        src = (
            "function fuzzy main() {\n"
            "  fuzzy x = !!0.5;\n"
            "  return x;\n"
            "}\n"
        )
        py = _compile(src)
        self.assertIn("_VSA.make_truth(0.5)", py)


class TestIntrinsicCodegen(unittest.TestCase):
    """Step 5 — `intrinsic function ... ;` declarations in stdlib
    route user calls to the runtime class via `_VSA.<name>(...)`.
    The inliner leaves intrinsic calls alone (empty body), and
    codegen emits the runtime dispatch."""

    def test_intrinsic_call_routes_to_vsa_method(self):
        # `similarity` is declared as `intrinsic function scalar
        # similarity(vector a, vector b);` in similarity.su. Calling
        # it by name from user code should compile to _VSA.similarity.
        src = (
            "vector cat = \"cat\";\n"
            "vector dog = \"dog\";\n"
            "function scalar f() {\n"
            "  return similarity(cat, dog);\n"
            "}\n"
        )
        py = _compile(src)
        # One occurrence for the user function body (the runtime
        # prelude has `def similarity(self, ...)` which is different).
        self.assertIn("_VSA.similarity(cat, dog)", py)


class TestInlinerUsesRealStdlib(unittest.TestCase):
    """Sanity: the inliner does load the real stdlib by default."""

    def test_default_uses_real_stdlib(self):
        from sutra_compiler.inliner import _stdlib_table
        table = _stdlib_table()
        # Must include the 7 single-return functions + defuzzy.
        for name in ("defuzzy", "logical_not", "logical_and",
                     "logical_or", "neq", "lt", "ge", "le"):
            self.assertIn(name, table)


if __name__ == "__main__":
    unittest.main()
