"""General mid-function `await` — end-to-end semantics guard.

Mid-function `await` lowers (promise_desugar Stage 1) by hoisting the
awaited promise into a temp, replacing `await x` with
`Promise.await_value(temp)`, and folding `Promise.propagate(temp, ...)`
over the returns. `Promise.propagate` is a substrate-pure tanh-polarized
blend on AXIS_PROMISE_REJECTED (codegen `def propagate`).

These tests assert, on BOTH backends:
  - the verification-target shape `vector v = await x; return g(v);`
    fulfils and the resolved value flows through `g` (value_is_cat ~1,
    value_is_dog low — signal separation);
  - a rejected awaited promise propagates rejection (does NOT silently
    fulfil) — both directly and through a 2-await chain.

The host `float(...)` reads here are at the TEST boundary only (the same
pattern as test_await_substrate_pure's `float(_run(...))`); no host
readout is added inside any compiled operation — that is guarded
separately by test_no_host_readout.py and test_await_substrate_pure.py.
"""
from __future__ import annotations

import os
import unittest

from sutra_compiler.codegen import translate_module as np_translate
from sutra_compiler.codegen_pytorch import translate_module as torch_translate
from sutra_compiler.lexer import Lexer
from sutra_compiler.parser import Parser

_FIXTURE = os.path.join(
    os.path.dirname(__file__), "corpus", "valid", "await_midfunction.su"
)


def _compile_ns(translate_fn, src: str) -> dict:
    lexer = Lexer(src, file="<test>")
    tokens = lexer.tokenize()
    parser = Parser(tokens, file="<test>", diagnostics=lexer.diagnostics)
    module = parser.parse_module()
    assert not lexer.diagnostics.has_errors(), list(lexer.diagnostics)
    ns: dict = {}
    exec(translate_fn(module), ns)
    return ns


class _MidAwaitMixin:
    translate_fn = None  # set by subclasses

    @classmethod
    def setUpClass(cls):
        with open(_FIXTURE, "r", encoding="utf-8") as f:
            cls.src = f.read()
        cls.ns = _compile_ns(cls.translate_fn, cls.src)
        cls.vsa = cls.ns["_VSA"]

    def _bool(self, fn: str) -> float:
        return float(self.ns[fn]())

    def _truth(self, fn: str) -> float:
        # `==` returns a fuzzy-truth vector with cosine on AXIS_TRUTH.
        v = self.ns[fn]()
        return float(v[self.vsa.semantic_dim + self.vsa.AXIS_TRUTH])

    # ---- the verification target ----
    def test_target_fulfils(self):
        self.assertAlmostEqual(self._bool("f_fulfilled"), 1.0, places=3)
        self.assertAlmostEqual(self._bool("f_rejected"), 0.0, places=3)

    def test_value_flows_through_g(self):
        # resolved value cosine-matches cat, and is separated from dog.
        cat = self._truth("value_is_cat")
        dog = self._truth("value_is_dog")
        self.assertGreater(cat, 0.99, f"value_is_cat cos={cat}")
        self.assertGreater(cat - dog, 0.2, f"gap cat-dog = {cat - dog}")

    # ---- rejection propagation ----
    def test_direct_rejection_propagates(self):
        self.assertAlmostEqual(self._bool("f_reject_fulfilled"), 0.0, places=3)
        self.assertAlmostEqual(self._bool("f_reject_rejected"), 1.0, places=3)

    def test_chain_fulfils(self):
        self.assertAlmostEqual(self._bool("chain_ok_fulfilled"), 1.0, places=3)

    def test_chain_midreject_propagates(self):
        # Second await rejects -> whole chain rejects, not fulfils.
        self.assertAlmostEqual(self._bool("chain_rm_fulfilled"), 0.0, places=3)
        self.assertAlmostEqual(self._bool("chain_rm_rejected"), 1.0, places=3)


class TestMidAwaitTorch(_MidAwaitMixin, unittest.TestCase):
    translate_fn = staticmethod(torch_translate)


class TestMidAwaitNumpy(_MidAwaitMixin, unittest.TestCase):
    translate_fn = staticmethod(np_translate)


if __name__ == "__main__":
    unittest.main()
