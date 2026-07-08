"""Cast lowering: `(Type) expr` conversion casts + `unsafeCast<Type>` relabels.

Design per `planning/sutra-spec/types.md` § "Casting — relabeling, not
transformation": the default cast is a NO-OP relabel (the vector crosses
unchanged); the one genuine axis-MOVE pair is numeric↔truth, because a number
carries its value on AXIS_REAL and a fuzzy/bool/trit carries it on AXIS_TRUTH —
a pure relabel would strand the value on the wrong axis and every downstream
read would see 0 (neutral). Text casts are rejected at codegen: number→string
needs the (unbuilt) substrate formatter; string→vector is the spec's
"embedding cast", whose implementation is `embed()` at the entry boundary.

`unsafeCast<T>(x)` is ALWAYS the pure relabel — it changes the static type and
never the value (the grep-able escape hatch).
"""
from __future__ import annotations

import unittest

from sutra_compiler.lexer import Lexer
from sutra_compiler.parser import Parser
from sutra_compiler.codegen_base import CodegenNotSupported
from sutra_compiler.codegen_pytorch import translate_module


def _compile(src: str, dim: int = 16):
    lx = Lexer(src, file="<t>")
    ast = Parser(lx.tokenize(), file="<t>", diagnostics=lx.diagnostics).parse_module()
    assert not lx.diagnostics.has_errors(), list(lx.diagnostics)
    ns: dict = {}
    exec(translate_module(ast, llm_model="none", runtime_dim=dim), ns)
    return ns


def _run(src: str, dim: int = 16):
    ns = _compile(src, dim)
    return ns["main"](), ns["_VSA"]


def _axis(r, v, axis: int) -> float:
    if not hasattr(r, "numel"):
        # A literal that never crossed a substrate op stays a host
        # number until the entry boundary lifts it (same as `return 5`
        # without any cast) — its value IS its reading on any axis.
        return float(r)
    if r.numel() == 1:
        return float(r)
    return float(r[v.semantic_dim + axis])


class TestNumericTruthMove(unittest.TestCase):
    """numeric↔truth is the one genuine axis-move pair."""

    def test_number_literal_to_fuzzy(self):
        r, v = _run("function fuzzy main(){ fuzzy f = (fuzzy) 0.7; return f; }")
        self.assertAlmostEqual(_axis(r, v, v.AXIS_TRUTH), 0.7, places=5)
        # the value MOVED, not copied: real axis is zero after the cast
        self.assertAlmostEqual(_axis(r, v, v.AXIS_REAL), 0.0, places=5)

    def test_number_var_to_fuzzy(self):
        r, v = _run(
            "function fuzzy main(){ number x = 0.5; fuzzy f = (fuzzy) x; return f; }")
        self.assertAlmostEqual(_axis(r, v, v.AXIS_TRUTH), 0.5, places=5)

    def test_int_literal_to_bool(self):
        r, v = _run("function bool main(){ bool b = (bool) 1; return b; }")
        self.assertAlmostEqual(_axis(r, v, v.AXIS_TRUTH), 1.0, places=5)

    def test_bool_to_number(self):
        r, v = _run(
            "function number main(){ bool b = true; number n = (number) b; return n; }")
        self.assertAlmostEqual(_axis(r, v, v.AXIS_REAL), 1.0, places=5)

    def test_fuzzy_var_to_number(self):
        r, v = _run(
            "function number main(){ fuzzy f = 0.3; number n = (number) f; return n; }")
        self.assertAlmostEqual(_axis(r, v, v.AXIS_REAL), 0.3, places=5)

    def test_roundtrip_number_fuzzy_number(self):
        r, v = _run(
            "function number main(){ fuzzy f = (fuzzy) 0.4; "
            "number n = (number) f; return n; }")
        self.assertAlmostEqual(_axis(r, v, v.AXIS_REAL), 0.4, places=5)


class TestNoOpRelabels(unittest.TestCase):
    """Everything within {number, complex, vector} relabels without moving axes."""

    def test_same_family_int_number(self):
        r, v = _run("function number main(){ number n = (number) 5; return n; }")
        self.assertAlmostEqual(_axis(r, v, v.AXIS_REAL), 5.0, places=5)

    def test_number_to_vector_and_back(self):
        r, v = _run(
            "function number main(){ vector w = (vector) 2.0; "
            "number n = (number) w; return n; }")
        self.assertAlmostEqual(_axis(r, v, v.AXIS_REAL), 2.0, places=5)

    def test_comparison_result_vector_to_fuzzy_is_noop(self):
        # A comparison already carries its value on AXIS_TRUTH; the
        # vector→truth cast must NOT axis-move (that would zero it).
        r, v = _run(
            "function fuzzy main(){ vector w = 3 < 5; "
            "fuzzy f = (fuzzy) w; return f; }")
        self.assertGreater(_axis(r, v, v.AXIS_TRUTH), 0.5)

    def test_complex_to_number_relabel(self):
        # number ops project AXIS_REAL themselves; the relabel is free.
        r, v = _run(
            "function number main(){ complex z = 3.0 + 2.0i; "
            "number n = (number) z; return n + 1; }")
        self.assertAlmostEqual(_axis(r, v, v.AXIS_REAL), 4.0, places=4)


class TestUnsafeCastIsPureRelabel(unittest.TestCase):
    def test_unsafecast_number_passthrough(self):
        r, v = _run(
            "function number main(){ number n = unsafeCast<number>(5); return n; }")
        self.assertAlmostEqual(_axis(r, v, v.AXIS_REAL), 5.0, places=5)

    def test_unsafecast_does_not_axis_move(self):
        # THE semantic difference from (fuzzy): for a substrate
        # number-vector (make_real pins one; plain literal arithmetic
        # constant-folds to a host number in preeval) the value stays on
        # AXIS_REAL, so the truth reading is 0 (neutral). Documented
        # reinterpret behaviour, not a bug.
        r, v = _run(
            "function fuzzy main(){ number x = make_real(0.7); "
            "fuzzy f = unsafeCast<fuzzy>(x); return f; }")
        self.assertAlmostEqual(_axis(r, v, v.AXIS_TRUTH), 0.0, places=5)
        self.assertAlmostEqual(_axis(r, v, v.AXIS_REAL), 0.7, places=5)

    def test_conversion_cast_of_arithmetic_result_moves(self):
        # The (fuzzy) counterpart of the reinterpret test above: the
        # BinaryOp infers as number, so the conversion cast axis-moves.
        r, v = _run(
            "function fuzzy main(){ fuzzy f = (fuzzy) (0.35 + 0.35); return f; }")
        self.assertAlmostEqual(_axis(r, v, v.AXIS_TRUTH), 0.7, places=5)


class TestRejectedCasts(unittest.TestCase):
    def _reject(self, src: str, needle: str):
        with self.assertRaises(CodegenNotSupported) as cm:
            _compile(src)
        self.assertIn(needle, str(cm.exception))

    def test_number_to_string_rejected(self):
        self._reject(
            "function string main(){ string s = (string) 5; return s; }",
            "make_string")

    def test_string_to_vector_rejected(self):
        self._reject(
            "function vector main(){ string s = \"hi\"; "
            "vector w = (vector) s; return w; }",
            "embed")

    def test_string_to_number_rejected(self):
        self._reject(
            "function number main(){ string s = \"hi\"; "
            "number n = (number) s; return n; }",
            "string")

    def test_unknown_source_to_truth_rejected(self):
        # A source whose static type can't be inferred cannot pick
        # between relabel and axis-move when the target is truth/number.
        self._reject(
            "function fuzzy main(){ fuzzy f = (fuzzy) similarity(\"a\", \"b\"); "
            "return f; }",
            "static type")


class TestCorpusCastFixtureRuns(unittest.TestCase):
    def test_double_cast_roundtrip_in_one_expr(self):
        r, v = _run(
            "function number main(){ number n = (number) ((fuzzy) 0.9); return n; }")
        self.assertAlmostEqual(_axis(r, v, v.AXIS_REAL), 0.9, places=5)


if __name__ == "__main__":
    unittest.main()
