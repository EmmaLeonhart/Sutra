"""Audit REAL LEAK #3 regression guard — `await` is substrate-pure.

`await x` lowers (promise_desugar) to `Promise.await_value(x)` ->
`_VSA.await_value`. The prior runtime body was a host Python
`for _ in range(100): if self.isPending(p) <= 0.5: break` — a host
branch on a predicate (plus the host float()/max() inside that
isPending call). It is the exact reduction of the spec-2 while_loop
(promises.md Stage 2) in the current no-external-producer runtime,
so it was replaced by `return self.value(p)` (pure tensor ops).

These tests assert (a) the leak signature is gone from the emitted
runtime on BOTH backends and (b) the reduction preserves the
end-to-end async/await semantics of the corpus fixture.
"""
from __future__ import annotations

import os
import unittest

from sutra_compiler.codegen import translate_module as np_translate
from sutra_compiler.codegen_pytorch import translate_module as torch_translate
from sutra_compiler.lexer import Lexer
from sutra_compiler.parser import Parser

_FIXTURE = os.path.join(
    os.path.dirname(__file__), "corpus", "valid", "async_promise_runtime.su"
)


def _compile(translate_fn, src: str) -> str:
    lexer = Lexer(src, file="<test>")
    tokens = lexer.tokenize()
    parser = Parser(tokens, file="<test>", diagnostics=lexer.diagnostics)
    module = parser.parse_module()
    assert not lexer.diagnostics.has_errors(), list(lexer.diagnostics)
    return translate_fn(module)


def _run(translate_fn, src: str, fn: str):
    ns: dict = {}
    exec(_compile(translate_fn, src), ns)
    return ns[fn]()


class TestAwaitSubstratePure(unittest.TestCase):
    def setUp(self):
        with open(_FIXTURE, "r", encoding="utf-8") as f:
            self.src = f.read()

    def _check_no_leak(self, py: str) -> None:
        # `for _ in range(100)` and `if self.isPending` existed ONLY
        # in await_value's old host body anywhere in the emitted
        # runtime (the generic loop runtime uses `range(max_iters)`,
        # a different signature). So whole-file assertions are a
        # sound, non-fragile regression guard.
        self.assertNotIn("for _ in range(100)", py)
        self.assertNotIn("if self.isPending", py)
        self.assertIn("def await_value(self, p):", py)
        self.assertIn("return self.value(p)", py)

    def test_no_host_loop_or_branch_torch(self):
        self._check_no_leak(_compile(torch_translate, self.src))

    def test_no_host_loop_or_branch_numpy(self):
        self._check_no_leak(_compile(np_translate, self.src))

    def test_await_semantics_preserved_torch(self):
        # chained() does `await immediate(); await g(v1)`; main() sums
        # five promise-inspector bools to 3.0.
        self.assertAlmostEqual(
            float(_run(torch_translate, self.src, "main")), 3.0, places=3
        )

    def test_await_semantics_preserved_numpy(self):
        self.assertAlmostEqual(
            float(_run(np_translate, self.src, "main")), 3.0, places=3
        )


if __name__ == "__main__":
    unittest.main()
