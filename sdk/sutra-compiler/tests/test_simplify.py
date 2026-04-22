"""Tests for the AST simplification pass.

Covers algebraic rewrites the pass applies before codegen: bundle
identity/flattening/zero-absorption, compose flattening, similarity-
of-self, displacement-of-self, unbind/bind inverses, and arithmetic
constant folding. Also covers the basis_vector string collection
pass the codegen uses for batched Ollama pre-fetching.
"""
from __future__ import annotations

import unittest

from sutra_compiler import ast_nodes as ast
from sutra_compiler.lexer import Lexer
from sutra_compiler.parser import Parser
from sutra_compiler.simplify import (
    simplify_module,
    collect_basis_vector_strings,
)


def _parse(src: str):
    lexer = Lexer(src, file="<test>")
    tokens = lexer.tokenize()
    parser = Parser(tokens, file="<test>", diagnostics=lexer.diagnostics)
    module = parser.parse_module()
    assert not lexer.diagnostics.has_errors(), list(lexer.diagnostics)
    return module


def _main_return_expr(module):
    """Return the expression in `return <expr>;` inside function main().

    Helper used by every test below — the simplifier acts on expressions,
    so the uniform shape is to stick the expression-under-test in the
    `return` of a function called `main`.
    """
    for item in module.items:
        if isinstance(item, ast.FunctionDecl) and item.name == "main":
            ret = item.body.statements[0]
            assert isinstance(ret, ast.ReturnStmt)
            return ret.value
    raise AssertionError("no main() found")


class TestBundleRewrites(unittest.TestCase):
    def test_bundle_of_one_elides(self):
        m = _parse(
            "vector a = basis_vector(\"a\");\n"
            "function vector main() { return bundle(a); }"
        )
        simplify_module(m)
        ret = _main_return_expr(m)
        self.assertIsInstance(ret, ast.Identifier)
        self.assertEqual(ret.name, "a")

    def test_bundle_flattens_nested(self):
        m = _parse(
            "vector a = basis_vector(\"a\");\n"
            "vector b = basis_vector(\"b\");\n"
            "vector c = basis_vector(\"c\");\n"
            "function vector main() { return bundle(bundle(a, b), c); }"
        )
        simplify_module(m)
        ret = _main_return_expr(m)
        self.assertIsInstance(ret, ast.Call)
        self.assertEqual(ret.callee.name, "bundle")
        self.assertEqual(len(ret.args), 3)
        self.assertEqual(ret.args[0].name, "a")
        self.assertEqual(ret.args[1].name, "b")
        self.assertEqual(ret.args[2].name, "c")

    def test_bundle_flattens_deeply(self):
        m = _parse(
            "vector a = basis_vector(\"a\");\n"
            "vector b = basis_vector(\"b\");\n"
            "vector c = basis_vector(\"c\");\n"
            "vector d = basis_vector(\"d\");\n"
            "function vector main() {"
            " return bundle(bundle(a, bundle(b, c)), d); }"
        )
        simplify_module(m)
        ret = _main_return_expr(m)
        # bundle(a, b, c, d) after full flattening.
        self.assertIsInstance(ret, ast.Call)
        self.assertEqual(ret.callee.name, "bundle")
        self.assertEqual([a.name for a in ret.args], ["a", "b", "c", "d"])

    def test_bundle_with_zero_drops_the_zero(self):
        m = _parse(
            "vector a = basis_vector(\"a\");\n"
            "vector b = basis_vector(\"b\");\n"
            "function vector main() { return bundle(a, displacement(b, b)); }"
        )
        simplify_module(m)
        ret = _main_return_expr(m)
        # displacement(b, b) → zero_vector(); bundle(a, zero) → a.
        self.assertIsInstance(ret, ast.Identifier)
        self.assertEqual(ret.name, "a")

    def test_all_zero_bundle_collapses_to_zero_vector(self):
        m = _parse(
            "vector a = basis_vector(\"a\");\n"
            "function vector main() {"
            " return bundle(displacement(a, a), displacement(a, a)); }"
        )
        simplify_module(m)
        ret = _main_return_expr(m)
        self.assertIsInstance(ret, ast.Call)
        self.assertEqual(ret.callee.name, "zero_vector")
        self.assertEqual(ret.args, [])


class TestComposeFlattening(unittest.TestCase):
    def test_compose_flattens_nested(self):
        m = _parse(
            "vector k1 = basis_vector(\"k1\");\n"
            "vector k2 = basis_vector(\"k2\");\n"
            "vector k3 = basis_vector(\"k3\");\n"
            "function vector main() { return compose(compose(k1, k2), k3); }"
        )
        simplify_module(m)
        ret = _main_return_expr(m)
        self.assertIsInstance(ret, ast.Call)
        self.assertEqual(ret.callee.name, "compose")
        self.assertEqual([a.name for a in ret.args], ["k1", "k2", "k3"])


class TestSimilarityOfSelf(unittest.TestCase):
    def test_similarity_of_same_identifier_collapses_to_one(self):
        m = _parse(
            "vector x = basis_vector(\"x\");\n"
            "function float main() { return similarity(x, x); }"
        )
        simplify_module(m)
        ret = _main_return_expr(m)
        self.assertIsInstance(ret, ast.FloatLiteral)
        self.assertEqual(ret.value, 1.0)

    def test_similarity_of_different_identifiers_does_not_simplify(self):
        m = _parse(
            "vector x = basis_vector(\"x\");\n"
            "vector y = basis_vector(\"y\");\n"
            "function float main() { return similarity(x, y); }"
        )
        simplify_module(m)
        ret = _main_return_expr(m)
        self.assertIsInstance(ret, ast.Call)
        self.assertEqual(ret.callee.name, "similarity")


class TestDisplacementOfSelf(unittest.TestCase):
    def test_displacement_of_same_identifier_is_zero(self):
        m = _parse(
            "vector x = basis_vector(\"x\");\n"
            "function vector main() { return displacement(x, x); }"
        )
        simplify_module(m)
        ret = _main_return_expr(m)
        self.assertIsInstance(ret, ast.Call)
        self.assertEqual(ret.callee.name, "zero_vector")
        self.assertEqual(ret.args, [])

    def test_displacement_of_different_identifiers_unchanged(self):
        m = _parse(
            "vector x = basis_vector(\"x\");\n"
            "vector y = basis_vector(\"y\");\n"
            "function vector main() { return displacement(x, y); }"
        )
        simplify_module(m)
        ret = _main_return_expr(m)
        self.assertIsInstance(ret, ast.Call)
        self.assertEqual(ret.callee.name, "displacement")


class TestBindUnbindInverse(unittest.TestCase):
    def test_unbind_cancels_inner_bind_with_same_role(self):
        m = _parse(
            "vector r = basis_vector(\"r\");\n"
            "vector x = basis_vector(\"x\");\n"
            "function vector main() { return unbind(r, bind(r, x)); }"
        )
        simplify_module(m)
        ret = _main_return_expr(m)
        self.assertIsInstance(ret, ast.Identifier)
        self.assertEqual(ret.name, "x")

    def test_bind_cancels_inner_unbind_with_same_role(self):
        m = _parse(
            "vector r = basis_vector(\"r\");\n"
            "vector x = basis_vector(\"x\");\n"
            "function vector main() { return bind(r, unbind(r, x)); }"
        )
        simplify_module(m)
        ret = _main_return_expr(m)
        self.assertIsInstance(ret, ast.Identifier)
        self.assertEqual(ret.name, "x")

    def test_mismatched_roles_do_not_cancel(self):
        m = _parse(
            "vector r1 = basis_vector(\"r1\");\n"
            "vector r2 = basis_vector(\"r2\");\n"
            "vector x = basis_vector(\"x\");\n"
            "function vector main() { return unbind(r1, bind(r2, x)); }"
        )
        simplify_module(m)
        ret = _main_return_expr(m)
        self.assertIsInstance(ret, ast.Call)
        self.assertEqual(ret.callee.name, "unbind")


class TestZeroAbsorptionInAddition(unittest.TestCase):
    def test_x_plus_zero_vector_drops_zero(self):
        m = _parse(
            "vector a = basis_vector(\"a\");\n"
            "function vector main() { return a + displacement(a, a); }"
        )
        simplify_module(m)
        ret = _main_return_expr(m)
        self.assertIsInstance(ret, ast.Identifier)
        self.assertEqual(ret.name, "a")

    def test_zero_vector_plus_x_drops_zero(self):
        m = _parse(
            "vector a = basis_vector(\"a\");\n"
            "function vector main() { return displacement(a, a) + a; }"
        )
        simplify_module(m)
        ret = _main_return_expr(m)
        self.assertIsInstance(ret, ast.Identifier)
        self.assertEqual(ret.name, "a")

    def test_x_minus_zero_vector_drops_zero(self):
        m = _parse(
            "vector a = basis_vector(\"a\");\n"
            "function vector main() { return a - displacement(a, a); }"
        )
        simplify_module(m)
        ret = _main_return_expr(m)
        self.assertIsInstance(ret, ast.Identifier)
        self.assertEqual(ret.name, "a")


class TestArithmeticConstantFolding(unittest.TestCase):
    def test_plus_zero_drops(self):
        m = _parse("function int main() { return 5 + 0; }")
        simplify_module(m)
        ret = _main_return_expr(m)
        self.assertIsInstance(ret, ast.IntLiteral)
        self.assertEqual(ret.value, 5)

    def test_zero_plus_drops(self):
        m = _parse("function int main() { return 0 + 5; }")
        simplify_module(m)
        ret = _main_return_expr(m)
        self.assertIsInstance(ret, ast.IntLiteral)
        self.assertEqual(ret.value, 5)

    def test_times_one_drops(self):
        m = _parse("function int main() { return 7 * 1; }")
        simplify_module(m)
        ret = _main_return_expr(m)
        self.assertIsInstance(ret, ast.IntLiteral)
        self.assertEqual(ret.value, 7)

    def test_times_zero_is_zero(self):
        m = _parse("function float main() { return 7 * 0; }")
        simplify_module(m)
        ret = _main_return_expr(m)
        self.assertIsInstance(ret, ast.FloatLiteral)
        self.assertEqual(ret.value, 0.0)

    def test_divide_by_one_drops(self):
        m = _parse("function int main() { return 7 / 1; }")
        simplify_module(m)
        ret = _main_return_expr(m)
        self.assertIsInstance(ret, ast.IntLiteral)
        self.assertEqual(ret.value, 7)


class TestZeroVectorAbsorptionInBindUnbind(unittest.TestCase):
    def test_bind_of_zero_absorbs(self):
        # bind(role, zero_vector()) → zero_vector(). Q @ 0 = 0 for any
        # orthogonal Q, so the result is zero regardless of role.
        m = _parse(
            "vector r = basis_vector(\"r\");\n"
            "function vector main() { return bind(r, zero_vector()); }"
        )
        simplify_module(m)
        ret = _main_return_expr(m)
        self.assertIsInstance(ret, ast.Call)
        self.assertEqual(ret.callee.name, "zero_vector")
        self.assertEqual(len(ret.args), 0)

    def test_unbind_of_zero_absorbs(self):
        # unbind(role, zero_vector()) → zero_vector(). Q^T @ 0 = 0.
        m = _parse(
            "vector r = basis_vector(\"r\");\n"
            "function vector main() { return unbind(r, zero_vector()); }"
        )
        simplify_module(m)
        ret = _main_return_expr(m)
        self.assertIsInstance(ret, ast.Call)
        self.assertEqual(ret.callee.name, "zero_vector")

    def test_bind_of_nonzero_filler_unchanged(self):
        m = _parse(
            "vector r = basis_vector(\"r\");\n"
            "vector f = basis_vector(\"f\");\n"
            "function vector main() { return bind(r, f); }"
        )
        simplify_module(m)
        ret = _main_return_expr(m)
        self.assertIsInstance(ret, ast.Call)
        self.assertEqual(ret.callee.name, "bind")


class TestComposeWithIdentity(unittest.TestCase):
    def test_compose_with_leading_identity_drops(self):
        # compose(identity_permutation(), x) → x.
        m = _parse(
            "vector x = basis_vector(\"x\");\n"
            "function vector main() { return compose(identity_permutation(), x); }"
        )
        simplify_module(m)
        ret = _main_return_expr(m)
        self.assertIsInstance(ret, ast.Identifier)
        self.assertEqual(ret.name, "x")

    def test_compose_with_trailing_identity_drops(self):
        # compose(x, identity_permutation()) → x.
        m = _parse(
            "vector x = basis_vector(\"x\");\n"
            "function vector main() { return compose(x, identity_permutation()); }"
        )
        simplify_module(m)
        ret = _main_return_expr(m)
        self.assertIsInstance(ret, ast.Identifier)
        self.assertEqual(ret.name, "x")

    def test_compose_all_identities_collapse_to_identity(self):
        m = _parse(
            "function vector main() { "
            "return compose(identity_permutation(), identity_permutation()); }"
        )
        simplify_module(m)
        ret = _main_return_expr(m)
        self.assertIsInstance(ret, ast.Call)
        self.assertEqual(ret.callee.name, "identity_permutation")

    def test_compose_two_non_identity_unchanged(self):
        m = _parse(
            "vector x = basis_vector(\"x\");\n"
            "vector y = basis_vector(\"y\");\n"
            "function vector main() { return compose(x, y); }"
        )
        simplify_module(m)
        ret = _main_return_expr(m)
        self.assertIsInstance(ret, ast.Call)
        self.assertEqual(ret.callee.name, "compose")
        self.assertEqual(len(ret.args), 2)


class TestArgmaxCosineSingleCandidate(unittest.TestCase):
    def test_single_candidate_argmax_is_the_candidate(self):
        # argmax_cosine(v, [x]) → x. Only one option, no choice to make.
        m = _parse(
            "vector v = basis_vector(\"v\");\n"
            "vector x = basis_vector(\"x\");\n"
            "function vector main() { return argmax_cosine(v, [x]); }"
        )
        simplify_module(m)
        ret = _main_return_expr(m)
        self.assertIsInstance(ret, ast.Identifier)
        self.assertEqual(ret.name, "x")

    def test_multiple_candidate_argmax_unchanged(self):
        m = _parse(
            "vector v = basis_vector(\"v\");\n"
            "vector x = basis_vector(\"x\");\n"
            "vector y = basis_vector(\"y\");\n"
            "function vector main() { return argmax_cosine(v, [x, y]); }"
        )
        simplify_module(m)
        ret = _main_return_expr(m)
        self.assertIsInstance(ret, ast.Call)
        self.assertEqual(ret.callee.name, "argmax_cosine")


class TestSubscriptOfArrayLiteral(unittest.TestCase):
    def test_positive_index_picks_element(self):
        m = _parse(
            "vector a = basis_vector(\"a\");\n"
            "vector b = basis_vector(\"b\");\n"
            "vector c = basis_vector(\"c\");\n"
            "function vector main() { return [a, b, c][1]; }"
        )
        simplify_module(m)
        ret = _main_return_expr(m)
        self.assertIsInstance(ret, ast.Identifier)
        self.assertEqual(ret.name, "b")

    def test_zero_index_picks_first(self):
        m = _parse(
            "vector a = basis_vector(\"a\");\n"
            "vector b = basis_vector(\"b\");\n"
            "function vector main() { return [a, b][0]; }"
        )
        simplify_module(m)
        ret = _main_return_expr(m)
        self.assertIsInstance(ret, ast.Identifier)
        self.assertEqual(ret.name, "a")

    def test_out_of_range_unchanged(self):
        # Out-of-range indices are left unsimplified so the runtime
        # IndexError surfaces as a real diagnostic. The rewrite would
        # otherwise mask a real bug in the program.
        m = _parse(
            "vector a = basis_vector(\"a\");\n"
            "function vector main() { return [a][5]; }"
        )
        simplify_module(m)
        ret = _main_return_expr(m)
        self.assertIsInstance(ret, ast.Subscript)


class TestBasisVectorCollection(unittest.TestCase):
    def test_collects_in_source_order(self):
        m = _parse(
            "vector a = basis_vector(\"hello\");\n"
            "vector b = basis_vector(\"world\");\n"
            "function vector main() { return bundle(a, b); }"
        )
        simplify_module(m)
        strings = collect_basis_vector_strings(m)
        self.assertEqual(strings, ["hello", "world"])

    def test_dedupes_duplicates(self):
        m = _parse(
            "vector a = basis_vector(\"hello\");\n"
            "vector b = basis_vector(\"hello\");\n"
            "function vector main() { return bundle(a, b); }"
        )
        simplify_module(m)
        strings = collect_basis_vector_strings(m)
        self.assertEqual(strings, ["hello"])


if __name__ == "__main__":
    unittest.main()
