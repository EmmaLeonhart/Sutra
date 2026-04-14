"""Tests for the AST → FlyBrainVSA translator.

The golden test is that `fly-brain/fuzzy_conditional.su` round-trips
cleanly through the translator and produces syntactically valid Python
matching the fuzzy-weighted-superposition shape from spec
`03-control-flow.md`. The prior `permutation_conditional.su` target was
retired — its `sign_flip(NOT_X, X)` semantic-NOT codegen was
category-error (see CLAUDE.md "NO MATH SHORTCUTS") and the file is
deleted. Unsupported constructs must raise `CodegenNotSupported` with
a source span, not silently emit wrong code.
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
FUZZY_CONDITIONAL = os.path.join(
    REPO_ROOT, "fly-brain", "fuzzy_conditional.su"
)


class TestFuzzyConditional(unittest.TestCase):
    """Golden: the fly-brain fuzzy conditional compiles to valid Python."""

    def setUp(self) -> None:
        with open(FUZZY_CONDITIONAL, encoding="utf-8") as f:
            self.source = f.read()
        self.module = _parse(self.source, file=FUZZY_CONDITIONAL)
        self.py_src = translate_module(self.module)

    def test_emits_syntactically_valid_python(self) -> None:
        compile(self.py_src, "<generated>", "exec")

    def test_emits_fixed_frame_runtime(self) -> None:
        self.assertIn("_FixedFrameFlyBrainVSA", self.py_src)
        self.assertIn("_VSA = _FixedFrameFlyBrainVSA", self.py_src)

    def test_emits_helpers(self) -> None:
        self.assertIn("def _argmax_cosine(", self.py_src)
        self.assertIn("def _vector_map_lookup(", self.py_src)

    def test_emits_basis_vectors(self) -> None:
        # Fuzzy-conditional does not use permutation keys — the whole
        # point of the spec-aligned rewrite is that there is no
        # sign-flip-as-semantic-NOT. Assert on the two axis basis
        # vectors instead.
        self.assertIn(
            "smell_present = _VSA.embed('smell_present')", self.py_src
        )
        self.assertIn(
            "hunger_hungry = _VSA.embed('hunger_hungry')", self.py_src
        )
        self.assertNotIn("make_sign_flip_key", self.py_src)

    def test_emits_prototype_table_via_snap_bind(self) -> None:
        for proto in ("proto_PH", "proto_PF", "proto_AH", "proto_AF"):
            self.assertIn(f"{proto} = _VSA.snap(_VSA.bind(", self.py_src)

    def test_vector_keyed_map_becomes_list_of_pairs(self) -> None:
        # `map<vector, string>` must NOT become a Python dict — numpy
        # arrays are unhashable. The list-of-pairs form goes through
        # the identity-first helper at lookup.
        self.assertIn(
            "BEHAVIOR_NAME = [(b_approach, 'approach')", self.py_src
        )
        self.assertNotIn(
            "BEHAVIOR_NAME = {b_approach:", self.py_src,
            "vector-keyed map must not emit as a Python dict",
        )

    def test_subscript_on_vector_map_uses_helper(self) -> None:
        self.assertIn(
            "_vector_map_lookup(BEHAVIOR_NAME, winner)", self.py_src
        )

    def test_fuzzy_decide_signature(self) -> None:
        # Canonical weighted-superposition decide signature: query +
        # one behavior vector per prototype.
        self.assertIn(
            "def fuzzy_decide(smell, hunger, beh_PH, beh_PF, "
            "beh_AH, beh_AF)",
            self.py_src,
        )
        self.assertIn("brain_query = _VSA.snap(query)", self.py_src)
        self.assertIn(
            "winner = _argmax_cosine(result, "
            "[b_approach, b_ignore, b_search, b_idle])",
            self.py_src,
        )

    def test_program_variants_share_fuzzy_decide(self) -> None:
        # A/B/C/D differ only in the behavior-vector 4-tuple they pass
        # to fuzzy_decide — the decision pipeline itself is shared.
        for variant in ("program_A", "program_B", "program_C", "program_D"):
            self.assertIn(f"def {variant}(smell, hunger)", self.py_src)
            self.assertIn("return fuzzy_decide(smell, hunger,", self.py_src)


class TestUnsupportedConstructs(unittest.TestCase):
    """Source-level negation and top-level if-statements must fail loudly."""

    def _assert_rejects(self, src: str, substring: str) -> None:
        module = _parse(src)
        with self.assertRaises(CodegenNotSupported) as cm:
            translate_module(module)
        self.assertIn(substring, str(cm.exception))

    def test_if_statement_rejected(self) -> None:
        self._assert_rejects(
            "function void tick() { if (true) { return; } }",
            "if/else is not supported",
        )

    def test_source_level_negation_rejected(self) -> None:
        # Source `!` has no spec-aligned lowering — the deprecated
        # `permute(NOT_X, .)` path was the category error that motivated
        # the fuzzy_conditional rewrite. Fail loud.
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
