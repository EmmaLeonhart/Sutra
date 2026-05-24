"""Formal-verification artifact: §3.3 termination obligation for soft-halt loops.

`planning/sutra-spec/formal-verification.md` § Pillar 3: each loop is a bounded
recurrence whose halt cell decides termination; the obligation is that the halt
signal is MONOTONE within BOUNDED steps.

Structurally the emitted loop guarantees both (codegen_pytorch.py):
  - BOUNDED: `for _t in range(max_iters)` — a fixed step count, no unbounded
    `while`; iters_active can never exceed max_iters.
  - MONOTONE halt: `halted = min(halted + halt, 1)` with `halt = sigmoid(...) >= 0`
    — non-decreasing, capped at 1; once it saturates, `state = (1-halted)*cand +
    halted*state` freezes the state.

This test discharges the obligation OBSERVABLY on the torch substrate (the
canonical compile target):
  - a non-converging loop runs to the bound and stops (iters_active <= max_iters,
    no hang) — termination is bounded;
  - a converging loop FREEZES, so running more unroll steps yields the same state
    (the monotone cumulative halt, once saturated, holds) — termination is real.

Referenced by `paper/formal-verification/paper.md` §3.3.
"""
from __future__ import annotations

import pytest

torch = pytest.importorskip(
    "torch", reason="the soft-halt loop runs on the torch substrate"
)

from sutra_compiler.codegen_pytorch import translate_module as torch_translate
from sutra_compiler.lexer import Lexer
from sutra_compiler.parser import Parser

# A trivial program just to obtain a torch _VSA with the `loop` runtime.
TRIVIAL = 'function vector main() { return basis_vector("x"); }\n'


def _vsa():
    lexer = Lexer(TRIVIAL, file="<fv-term>")
    toks = lexer.tokenize()
    module = Parser(
        toks, file="<fv-term>", diagnostics=lexer.diagnostics
    ).parse_module()
    assert not lexer.diagnostics.has_errors(), list(lexer.diagnostics)
    py = torch_translate(module, llm_model="nomic-embed-text", runtime_dim=768)
    ns: dict = {}
    exec(compile(py, "<fv-term>", "exec"), ns)
    return ns["_VSA"]


def test_fv_loop_terminates_bounded_with_monotone_halt() -> None:
    vsa = _vsa()
    dim, dt, dev = vsa.dim, vsa.dtype, vsa.device
    ident = torch.eye(dim, dtype=dt, device=dev)

    # Converging: state == target under identity rotation -> sim=1, halt
    # saturates almost immediately. Run at two unroll depths.
    target = vsa.make_real(1.0)
    target = target / (torch.linalg.norm(target) + 1e-12)
    protos = {"target": target}
    _, s_t20, it_t20 = vsa.loop(
        target.clone(), ident, protos,
        target_name="target", threshold=0.5, max_iters=20, k=20.0,
    )
    _, s_t10, it_t10 = vsa.loop(
        target.clone(), ident, protos,
        target_name="target", threshold=0.5, max_iters=10, k=20.0,
    )
    frozen_diff = float(torch.linalg.norm(s_t20 - s_t10))

    # Non-converging: orthogonal state/target under identity -> sim=0 forever,
    # halt stays ~0, loop runs to the bound and stops.
    s0 = torch.zeros(dim, dtype=dt, device=dev)
    s0[0] = 1.0
    tgt = torch.zeros(dim, dtype=dt, device=dev)
    tgt[1] = 1.0
    _, _s_nc, it_nc = vsa.loop(
        s0, ident, {"target": tgt},
        target_name="target", threshold=0.5, max_iters=10, k=20.0,
    )

    print(
        f"[fv-term] converged frozen-diff(T20,T10)={frozen_diff:.2e} "
        f"it20={float(it_t20):.3f}; non-converging iters={float(it_nc):.3f}/10"
    )

    # MONOTONE halt holds -> a converged loop is frozen; extra unroll steps
    # do not change the result.
    assert frozen_diff < 1e-5, (
        f"converged loop not frozen across unroll depth (monotone halt would "
        f"hold it): diff={frozen_diff:.3e}"
    )
    # BOUNDED -> iters_active can never exceed max_iters (no unbounded run).
    assert float(it_t20) <= 20.0 + 1e-6, f"iters_active exceeded T=20: {float(it_t20)}"
    assert float(it_t10) <= 10.0 + 1e-6, f"iters_active exceeded T=10: {float(it_t10)}"
    assert float(it_nc) <= 10.0 + 1e-6, (
        f"non-converging iters_active exceeded the bound (unbounded!): {float(it_nc)}"
    )
    # A non-converging loop still terminates by running to the bound.
    assert float(it_nc) > 1.0, (
        f"non-converging loop should run multiple bounded steps, got {float(it_nc)}"
    )
