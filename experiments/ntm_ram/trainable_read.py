"""Trainable NTM read head — a SOFT LINEAR READ over memory cell contents.

Emma's design choice (AskUserQuestion 2026-06-07): the trainable NTM's "linear
regression over memory" is a **differentiable read = a linear-weighted sum over
memory cell CONTENTS**, layered on top of the hard pointer. Read becomes
differentiable; write + address stay hard (round-to-nearest discrete I/O, per
ram-pointers.md). This gives the controller a gradient path through reads while
memory stays EXTERNAL (orchestrator-fetched), NOT fused into the graph.

What this is (and is NOT):
  - The memory CELLS are the contents the orchestrator brought in from external RAM
    (here: number-vectors in VRAM). RAM is NOT fused into a step graph; these are
    just the fetched contents the read regresses over.
  - The READ is `read = sum_i w_i * value(cell_i)`, a linear regression over the
    cell contents, with TRAINABLE coefficients `w`. `value(cell_i)` is extracted by
    the substrate real-axis projector (`_real_projector()` — a matmul, no host
    readout). The read output is a number-VECTOR (real axis = the regression value).
  - Differentiable in `w` (and in the contents) -> trainable by SGD. The address
    (which cells) is NOT in the grad graph (hard pointer, separate).

The measured experiment (a real training result, not a claim): a fixed unknown true
coefficient vector `c`; M memory configurations `X` (each row = the N stored values
of one config); targets `y = X @ c`. Train `w` by SGD so the substrate read matches
`y`. We measure: loss -> ~0, and `w -> c` (recovered coefficients). This is the
NTM read head being TRAINED to do linear regression over memory — the trainable
seed's first concrete training demonstration.

Substrate honesty: the READ forward uses the substrate real projector (a tensor
matmul). SGD (loss/backward/step) is host-side TRAINING — the sanctioned compile-
time role (building/fitting), not a runtime hot-path op. Ollama-free (make_real
cells, tiny dim). Self-asserting.
"""

from __future__ import annotations

import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str((REPO / "sdk" / "sutra-compiler").resolve()))

import torch  # noqa: E402

from sutra_compiler.lexer import Lexer  # noqa: E402
from sutra_compiler.parser import Parser  # noqa: E402
from sutra_compiler.codegen_pytorch import translate_module  # noqa: E402


def _vsa(runtime_dim: int = 4):
    src = 'function string main(){ return "ok"; }'
    lx = Lexer(src, file="<read>")
    ast = Parser(lx.tokenize(), file="<read>", diagnostics=lx.diagnostics).parse_module()
    assert not lx.diagnostics.has_errors(), list(lx.diagnostics)
    ns: dict = {}
    exec(translate_module(ast, llm_model="none", runtime_dim=runtime_dim), ns)
    return ns["_VSA"]


def soft_linear_read(vsa, cells, w):
    """The differentiable read: read = sum_i w_i * value(cell_i), returned as a
    number-VECTOR (real axis = the regression output). `cells` is (N, dim) memory
    contents (orchestrator-fetched); `w` is (N,) trainable coefficients. Uses the
    substrate real-axis projector (matmul) — no host readout in the forward.
    """
    P = vsa._real_projector()                 # (dim, dim) substrate projector
    projected = cells @ P.T                    # (N, dim): only real axis kept
    # Weighted sum over cells (the linear regression over contents).
    read_vec = w @ projected                   # (dim,): real axis = sum_i w_i * v_i
    return read_vec


def read_value(vsa, read_vec):
    """Read the regression output off the read vector's real axis. This is the
    terminal/monitoring boundary (host), used for the loss target comparison and
    for reporting — not inside the substrate forward."""
    return read_vec[vsa.semantic_dim + vsa.AXIS_REAL]


def main() -> int:
    torch.manual_seed(0)
    vsa = _vsa(runtime_dim=4)
    dim = vsa.dim
    N = 4          # memory cells
    M = 24         # training configurations (M >= N -> well-posed regression)

    # True (unknown) coefficients the read must learn.
    c_true = torch.tensor([2.0, -1.0, 0.5, 3.0], dtype=vsa.dtype, device=vsa.device)
    # M memory configs: each row = the N stored values of one config.
    X = torch.randn(M, N, dtype=vsa.dtype, device=vsa.device)
    y = X @ c_true                              # targets = linear fn of memory

    # Encode each config's values as N number-vector CELLS (orchestrator-fetched
    # external-RAM contents brought into VRAM).
    cells_all = torch.zeros(M, N, dim, dtype=vsa.dtype, device=vsa.device)
    ridx = vsa.semantic_dim + vsa.AXIS_REAL
    for m in range(M):
        for i in range(N):
            cells_all[m, i] = vsa.make_real(float(X[m, i]))

    # Trainable read coefficients.
    w = torch.zeros(N, dtype=vsa.dtype, device=vsa.device, requires_grad=True)
    opt = torch.optim.Adam([w], lr=0.1)

    def epoch_loss():
        preds = torch.stack([
            read_value(vsa, soft_linear_read(vsa, cells_all[m], w)) for m in range(M)
        ])
        return ((preds - y) ** 2).mean()

    loss0 = float(epoch_loss().detach())
    init_grad_norm = None
    for step in range(300):
        opt.zero_grad()
        loss = epoch_loss()
        loss.backward()
        if step == 0:
            # Gradient-flow evidence, measured BEFORE convergence (at the optimum
            # the gradient goes to ~0, which would be misleading). A clearly
            # positive gradient on the FIRST step shows the read is differentiable
            # and the loss backprops into the read coefficients.
            init_grad_norm = float(w.grad.norm())
        opt.step()
    lossN = float(epoch_loss().detach())
    coeff_err = float((w.detach() - c_true).norm())

    print("soft linear read over memory contents -- trained:")
    print(f"  initial loss = {loss0:.4f}  ->  final loss = {lossN:.6f}")
    print(f"  recovered w  = {[round(float(v), 3) for v in w.detach()]}")
    print(f"  true c       = {[round(float(v), 3) for v in c_true]}")
    print(f"  ||w - c||    = {coeff_err:.4f}")
    print(f"  gradient flows: ||grad|| at step 0 = {init_grad_norm:.4f} (>0)")

    ok = (lossN < 1e-3 and coeff_err < 1e-2 and init_grad_norm > 1e-3
          and lossN < loss0)
    if not ok:
        print("FAIL: trainable soft-linear-read did not converge / no gradient")
        return 1
    print("PASS: a DIFFERENTIABLE soft linear read over external memory cell contents "
          "was TRAINED (SGD) to do linear regression over memory -- loss -> ~0, "
          "coefficients recovered, gradients flow (||grad||>0 at step 0). Read "
          "differentiable; write/address stay hard; RAM external. The trainable-NTM "
          "read head, measured.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
