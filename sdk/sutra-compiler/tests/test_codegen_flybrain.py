"""Tests for the AST → FlyBrainVSA translator.

The golden test is that `fly-brain/permutation_conditional.ak` round-trips
cleanly through the translator and produces syntactically valid Python
whose structure matches the hand-written `permutation_conditional.py`.
Unsupported constructs must raise `CodegenNotSupported` with a source
span, not silently emit wrong code.
"""

from __future__ import annotations

import os
import unittest

from sutra_compiler.codegen_flybrain import (
    CodegenNotSupported,
    translate_module,
)
from sutra_compiler.lexer import Lexer
from sutra_compiler.parser import Parser


def _parse(src: str, file: str = "<test>"):
    lexer = Lexer(src, file=file)
    tokens = lexer.tokenize()
    parser = Parser(tokens, file=file, diagnostics=lexer.diagnostics)
    module = parser.parse_module()
    assert not lexer.diagnostics.has_errors(), list(lexer.diagnostics)
    return module


REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
FLY_BRAIN_AK = os.path.join(REPO_ROOT, "fly-brain", "permutation_conditional.ak")


class TestPermutationConditional(unittest.TestCase):
    """Golden: the fly-brain example compiles to valid Python."""

    def setUp(self) -> None:
        with open(FLY_BRAIN_AK, encoding="utf-8") as f:
            self.source = f.read()
        self.module = _parse(self.source, file=FLY_BRAIN_AK)
        self.py_src = translate_module(self.module)

    def test_emits_syntactically_valid_python(self) -> None:
        # If the emitted string is not valid Python this raises SyntaxError.
        compile(self.py_src, "<generated>", "exec")

    def test_emits_fixed_frame_runtime(self) -> None:
        self.assertIn("_FixedFrameFlyBrainVSA", self.py_src)
        self.assertIn("_VSA = _FixedFrameFlyBrainVSA", self.py_src)

    def test_emits_helpers(self) -> None:
        self.assertIn("def _argmax_cosine(", self.py_src)
        self.assertIn("def _vector_map_lookup(", self.py_src)

    def test_emits_basis_vectors_and_permutation_keys(self) -> None:
        self.assertIn("smell_present = _VSA.embed('smell')", self.py_src)
        self.assertIn("hunger_hungry = _VSA.embed('hunger')", self.py_src)
        self.assertIn(
            "NOT_SMELL = _VSA.make_permutation_key('NOT_SMELL')", self.py_src
        )
        self.assertIn(
            "NOT_HUNGER = _VSA.make_permutation_key('NOT_HUNGER')", self.py_src
        )

    def test_emits_prototype_table_via_snap_bind(self) -> None:
        # Each prototype is snap(bind(state_a, state_b)).
        for proto in ("proto_PH", "proto_PF", "proto_AH", "proto_AF"):
            self.assertIn(f"{proto} = _VSA.snap(_VSA.bind(", self.py_src)

    def test_vector_keyed_map_becomes_list_of_pairs(self) -> None:
        # `map<vector, string>` must NOT become a Python dict — numpy
        # arrays are unhashable. The list-of-pairs form goes through
        # the identity-first helper at lookup.
        self.assertIn("BEHAVIOR_OF = [(proto_PH, 'approach')", self.py_src)
        self.assertNotIn(
            "BEHAVIOR_OF = {proto_PH:", self.py_src,
            "vector-keyed map must not emit as a Python dict",
        )

    def test_subscript_on_vector_map_uses_helper(self) -> None:
        self.assertIn("_vector_map_lookup(BEHAVIOR_OF, winner)", self.py_src)

    def test_decide_function_shape(self) -> None:
        self.assertIn("def decide(smell, hunger, px, py):", self.py_src)
        self.assertIn("query = _VSA.bind(smell, hunger)", self.py_src)
        self.assertIn("query = _VSA.permute(px, query)", self.py_src)
        self.assertIn("brain_query = _VSA.snap(query)", self.py_src)
        self.assertIn(
            "winner = _argmax_cosine(brain_query, "
            "[proto_PH, proto_PF, proto_AH, proto_AF])",
            self.py_src,
        )

    def test_program_variants_share_decide(self) -> None:
        # The whole point of the demo: A/B/C/D differ only in which
        # permutation keys go into `decide`, not in having their own
        # if-tree. The generated Python should reflect that.
        self.assertIn("def program_A(smell, hunger):", self.py_src)
        self.assertIn("return decide(smell, hunger, I, I)", self.py_src)
        self.assertIn(
            "return decide(smell, hunger, NOT_SMELL, I)", self.py_src
        )
        self.assertIn(
            "return decide(smell, hunger, I, NOT_HUNGER)", self.py_src
        )
        self.assertIn(
            "return decide(smell, hunger, NOT_SMELL, NOT_HUNGER)", self.py_src
        )

    def test_identity_permutation_emits_numpy_ones(self) -> None:
        self.assertIn("I = _np.ones(_VSA.dim)", self.py_src)


class TestUnsupportedConstructs(unittest.TestCase):
    """Loops, if-statements, and operator decls must fail loudly."""

    def _assert_rejects(self, src: str, substring: str) -> None:
        module = _parse(src)
        with self.assertRaises(CodegenNotSupported) as cm:
            translate_module(module)
        self.assertIn(substring, str(cm.exception))

    def test_while_loop_rejected(self) -> None:
        self._assert_rejects(
            "function void tick() { while (true) { return; } }",
            "loops are intentionally unsupported",
        )

    def test_for_loop_rejected(self) -> None:
        self._assert_rejects(
            "function void tick() { for (;;) { return; } }",
            "loops are intentionally unsupported",
        )

    def test_if_statement_rejected(self) -> None:
        self._assert_rejects(
            "function void tick() { if (true) { return; } }",
            "if/else is not supported",
        )

    def test_source_level_negation_rejected(self) -> None:
        # We want `!` to compile to permute(NOT_X, .), which needs a
        # transformation pass we haven't written. For now, fail loud.
        self._assert_rejects(
            "function bool f() { return !true; }",
            "source-level `!` is not yet lowered",
        )


class TestBuiltinArityChecks(unittest.TestCase):
    def test_bind_wrong_arity(self) -> None:
        module = _parse('vector v = bind(basis_vector("a"));')
        with self.assertRaises(CodegenNotSupported) as cm:
            translate_module(module)
        self.assertIn("builtin `bind` expects 2", str(cm.exception))

    def test_identity_permutation_no_args(self) -> None:
        module = _parse("permutation p = identity_permutation();")
        py_src = translate_module(module)
        self.assertIn("p = _np.ones(_VSA.dim)", py_src)


if __name__ == "__main__":
    unittest.main()
