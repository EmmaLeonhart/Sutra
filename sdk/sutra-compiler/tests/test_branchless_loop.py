"""Tests for the branchless RNN-style loop(cond) lowering.

Sutra's design constraint: looping programs are RNNs — recurrent forward
passes through tensor ops, with NO host-side control flow inside the
loop primitive. The old `_VSA.loop()` had a host `for iters in range(N)`
plus three host `if` checks per iteration; this is the bug. The new
implementation:

- Runs T fixed steps unconditionally as tensor-op cell calls
- Uses a soft halt (sigmoid + monotone cumulative) to freeze state once
  convergence is reached
- Gates the value-bearing axes by the cumulative halt so a non-converging
  loop emits a zero-vector with AXIS_LOOP_DONE = halted < 1 marking
  the incomplete-output exception condition
- Returns iters_active (a tensor scalar accumulating (1 - halted) per
  step) instead of a Python int counter

Tests verify each of these properties.
"""
from __future__ import annotations

import math
import unittest

from sutra_compiler.codegen import translate_module as np_translate
from sutra_compiler.codegen_pytorch import translate_module as torch_translate
from sutra_compiler.lexer import Lexer
from sutra_compiler.parser import Parser


def _compile(translate_fn, src: str) -> tuple[str, dict]:
    """Return (emitted source, prelude namespace)."""
    lexer = Lexer(src, file="<test>")
    tokens = lexer.tokenize()
    parser = Parser(tokens, file="<test>", diagnostics=lexer.diagnostics)
    module = parser.parse_module()
    assert not lexer.diagnostics.has_errors(), list(lexer.diagnostics)
    py_src = translate_fn(module)
    head = py_src.split("def main(")[0]
    namespace = {}
    exec(head, namespace)
    return py_src, namespace


TRIVIAL_SRC = 'function vector main() { return basis_vector("x"); }\n'


class TestNoHostControlFlow(unittest.TestCase):
    """The emitted _VSA.loop method body must have no host-side
    iteration count and no host-side conditional comparing scores
    against the threshold. The whole point of this refactor.
    """

    @staticmethod
    def _strip_docstring_and_comments(src: str) -> str:
        """Return src with triple-quoted blocks and `#` comments stripped.

        We only care whether actual *code* contains forbidden patterns —
        docstrings and comments may mention the old design verbatim.
        """
        out = []
        i = 0
        in_docstring = False
        doc_quote = None
        while i < len(src):
            if not in_docstring:
                if src.startswith('"""', i):
                    in_docstring = True
                    doc_quote = '"""'
                    i += 3
                    continue
                if src.startswith("'''", i):
                    in_docstring = True
                    doc_quote = "'''"
                    i += 3
                    continue
                if src[i] == "#":
                    # skip to end of line
                    while i < len(src) and src[i] != "\n":
                        i += 1
                    continue
                out.append(src[i])
                i += 1
            else:
                if src.startswith(doc_quote, i):
                    in_docstring = False
                    doc_quote = None
                    i += 3
                    continue
                i += 1
        return "".join(out)

    def test_loop_emits_no_for_iters_in_range(self):
        py_src, _ = _compile(np_translate, TRIVIAL_SRC)
        loop_block = py_src.split("def loop(self,")[1].split("def ")[0]
        loop_code = self._strip_docstring_and_comments(loop_block)
        # The old impl had `for iters in range(1, max_iters + 1):` — that's
        # the host-side iteration count we're banishing. Our new impl uses
        # `for _t in range(max_iters):` which is meta-iteration over a
        # compile-time-fixed count. Specifically check for the OLD form.
        self.assertNotIn("for iters in range", loop_code)
        # No `while` inside the loop primitive.
        self.assertNotIn("while ", loop_code)

    def test_loop_emits_no_best_score_compare(self):
        py_src, _ = _compile(np_translate, TRIVIAL_SRC)
        loop_block = py_src.split("def loop(self,")[1].split("def ")[0]
        loop_code = self._strip_docstring_and_comments(loop_block)
        self.assertNotIn("best_score", loop_code)
        self.assertNotIn(">= threshold", loop_code)

    def test_torch_loop_emits_no_host_for(self):
        py_src, _ = _compile(torch_translate, TRIVIAL_SRC)
        loop_block = py_src.split("def loop(self,")[1].split("def ")[0]
        loop_code = self._strip_docstring_and_comments(loop_block)
        self.assertNotIn("for iters in range", loop_code)
        self.assertNotIn("best_score", loop_code)


class TestSoftHaltFreeze(unittest.TestCase):
    """Once halted saturates at 1, state should stop changing.

    Build a setup where the rotation drives state toward the target
    quickly, then verify state at step T equals state at step T/2.
    """

    def setUp(self):
        _, self.ns = _compile(np_translate, TRIVIAL_SRC)
        self.vsa = self.ns["_VSA"]

    def test_state_freezes_after_convergence(self):
        import numpy as np
        # Construct a rotation whose iteration converges quickly to a
        # known target. Identity rotation + state=target: trivially
        # converged at step 0.
        target = self.vsa.make_real(1.0)
        target = target / np.linalg.norm(target)
        state_init = target.copy()
        identity = np.eye(self.vsa.dim, dtype=np.float64)
        protos = {"target": target}

        # Run with T=20.
        _, state_T20, iters_T20 = self.vsa.loop(
            state_init, identity, protos,
            target_name="target", threshold=0.5, max_iters=20, k=20.0,
        )
        # Run with T=10, same setup.
        _, state_T10, iters_T10 = self.vsa.loop(
            state_init, identity, protos,
            target_name="target", threshold=0.5, max_iters=10, k=20.0,
        )

        # State at T=10 should match state at T=20 within tight tolerance,
        # because halted saturates by ~step 1 (sim is exactly 1 from step 0)
        # so all steps after halt are frozen.
        diff = np.linalg.norm(state_T20 - state_T10)
        self.assertLess(diff, 1e-6, f"state changed past convergence: {diff}")


class TestOutputGatingOnNonConvergence(unittest.TestCase):
    """If the loop never converges within T steps, the output value axes
    should be scaled toward zero AND AXIS_LOOP_DONE should be < 1.

    This is the "incomplete output exception" channel: programs see a
    zero result they can detect rather than a misleading partial state.
    """

    def setUp(self):
        _, self.ns = _compile(np_translate, TRIVIAL_SRC)
        self.vsa = self.ns["_VSA"]

    def test_orthogonal_target_yields_low_halt_and_gated_output(self):
        import numpy as np
        # State = e_0, target = e_1 (orthogonal). Identity rotation
        # never moves state. cosine = 0 forever, sigmoid(20*(0-0.5)) ~ 5e-5.
        # halted stays near 0.
        state_init = np.zeros(self.vsa.dim, dtype=np.float64)
        state_init[0] = 1.0
        target = np.zeros(self.vsa.dim, dtype=np.float64)
        target[1] = 1.0
        identity = np.eye(self.vsa.dim, dtype=np.float64)
        protos = {"target": target}

        _, state_out, iters_active = self.vsa.loop(
            state_init, identity, protos,
            target_name="target", threshold=0.5, max_iters=10, k=20.0,
        )

        # halted ends up tiny (sigmoid(20 * -0.5) ~ 5e-5 per step,
        # accumulated for 10 steps ~ 5e-4). AXIS_LOOP_DONE reflects this.
        halt_done = state_out[self.vsa.semantic_dim + self.vsa.AXIS_LOOP_DONE]
        self.assertLess(halt_done, 0.5,
                        f"AXIS_LOOP_DONE should be low for non-convergence, got {halt_done}")

        # Value axes (everything except AXIS_LOOP_DONE) should be scaled
        # by halted, so total magnitude is small.
        # We zero out AXIS_LOOP_DONE before measuring magnitude:
        masked = state_out.copy()
        masked[self.vsa.semantic_dim + self.vsa.AXIS_LOOP_DONE] = 0.0
        gated_mag = np.linalg.norm(masked)
        self.assertLess(gated_mag, 0.1,
                        f"value axes should be near zero on non-convergence, got {gated_mag}")

        # iters_active should be near max_iters since cell stayed unsaturated.
        self.assertGreater(iters_active, 9.0,
                           f"iters_active should be near T=10 when not converging, got {iters_active}")


class TestConvergenceMarksDoneAxis(unittest.TestCase):
    """When the loop DOES converge, AXIS_LOOP_DONE should be near 1."""

    def setUp(self):
        _, self.ns = _compile(np_translate, TRIVIAL_SRC)
        self.vsa = self.ns["_VSA"]

    def test_converged_loop_marks_done(self):
        import numpy as np
        target = self.vsa.make_real(1.0)
        target = target / np.linalg.norm(target)
        state_init = target.copy()
        identity = np.eye(self.vsa.dim, dtype=np.float64)
        protos = {"target": target}

        _, state_out, _ = self.vsa.loop(
            state_init, identity, protos,
            target_name="target", threshold=0.5, max_iters=20, k=20.0,
        )

        halt_done = state_out[self.vsa.semantic_dim + self.vsa.AXIS_LOOP_DONE]
        self.assertGreater(halt_done, 0.99,
                           f"AXIS_LOOP_DONE should be near 1 for converged loop, got {halt_done}")


class TestPyTorchBackend(unittest.TestCase):
    """Spot-check that the torch backend has the same shape."""

    def test_torch_loop_compiles_and_runs(self):
        _, ns = _compile(torch_translate, TRIVIAL_SRC)
        vsa = ns["_VSA"]
        import torch as _torch
        target = vsa.make_real(1.0)
        target = target / _torch.linalg.norm(target)
        state_init = target.clone()
        identity = _torch.eye(vsa.dim, dtype=vsa.dtype, device=vsa.device)
        protos = {"target": target}

        _, state_out, _ = vsa.loop(
            state_init, identity, protos,
            target_name="target", threshold=0.5, max_iters=20, k=20.0,
        )

        halt_done = float(state_out[vsa.semantic_dim + vsa.AXIS_LOOP_DONE].item())
        self.assertGreater(halt_done, 0.99)


if __name__ == "__main__":
    unittest.main()
