"""Compare the attention-on-RAM variants side-by-side (Emma 2026-06-08:
"do all of them so we can compare them").

The codable attention-on-RAM parser has, across this track, four variants of
"reading a RAM tape with one attention head". This script runs them together and
reports measured numbers, organized on the axis Emma cares about: **evaluate a
given linear model vs. learn one from data** — both being "linear regression over
memory", one constructed, one trained.

Variants:
  1. sum_tape       (constructed) — q=ones; aggregate the tape.            [evaluate]
  2. dot_tape       (constructed) — q=coeffs; ŷ = w·x over the tape.       [evaluate]
  3. select_field   (constructed) — hardmax location read; out = tape[j].  [evaluate]
  4. soft linear read (trained)   — fit w by SGD to (X, X@c); recover c.   [learn]

The apples-to-apples comparison (the point): pick ONE coefficient vector `c` and
ONE set of tapes `X`. The constructed head EVALUATES ŷ = c·x exactly. The trained
head LEARNS w from (X, X@c) by SGD, then evaluating with the LEARNED w must agree
with the constructed evaluation — i.e. the two mechanisms converge to the SAME
linear-regression-over-memory operator, one given the coefficients, the other
recovering them.

Off any Sutra runtime hot path: constructed eval is torch analysis; the SGD fit is
compile-time training (the sanctioned building/fitting role). No claim is made here
about substrate execution — the substrate-run instances are the OCaml fixtures
(`attn_*`, finding 2026-06-08-attention-on-ram-substrate.md); this script is the
cross-variant comparison oracle.
"""

from __future__ import annotations

import pathlib
import sys

import torch

_HERE = pathlib.Path(__file__).resolve().parent
_REPO = _HERE.parents[1]
sys.path.insert(0, str(_HERE))
sys.path.insert(0, str(_REPO / "experiments" / "ntm_ram"))

import reference  # constructed parse tasks  # noqa: E402
import trainable_read as tr  # the substrate soft-linear-read + vsa  # noqa: E402

DTYPE = torch.float64


def fit_w(vsa, X: torch.Tensor, y: torch.Tensor, steps: int = 300):
    """Learn read coefficients w by SGD so the substrate soft-linear-read of each
    config's cells matches y. Returns (w_learned, loss0, lossN, grad0)."""
    M, N = X.shape
    dim = vsa.dim
    cells_all = torch.zeros(M, N, dim, dtype=vsa.dtype, device=vsa.device)
    for m in range(M):
        for i in range(N):
            cells_all[m, i] = vsa.make_real(float(X[m, i]))
    w = torch.zeros(N, dtype=vsa.dtype, device=vsa.device, requires_grad=True)
    opt = torch.optim.Adam([w], lr=0.1)

    def epoch_loss():
        preds = torch.stack([
            tr.read_value(vsa, tr.soft_linear_read(vsa, cells_all[m], w))
            for m in range(M)
        ])
        return ((preds - y) ** 2).mean()

    loss0 = float(epoch_loss().detach())
    grad0 = None
    for step in range(steps):
        opt.zero_grad()
        loss = epoch_loss()
        loss.backward()
        if step == 0:
            grad0 = float(w.grad.norm())
        opt.step()
    return w.detach(), loss0, float(epoch_loss().detach()), grad0


def run_comparison(verbose: bool = True) -> dict:
    torch.manual_seed(0)
    vsa = tr._vsa(runtime_dim=4)

    # ── The shared linear-regression-over-memory task ──
    c_true = torch.tensor([2.0, -1.0, 0.5, 3.0], dtype=DTYPE)
    X = torch.randn(24, 4, dtype=DTYPE, generator=torch.Generator().manual_seed(1))
    y = X @ c_true                                   # ground-truth targets

    # EVALUATE (constructed): the head with q = c_true evaluates ŷ = c·x exactly.
    eval_pred = torch.tensor([reference.dot_tape(X[m].tolist(), c_true.tolist())
                              for m in range(X.shape[0])], dtype=DTYPE)
    eval_err = float((eval_pred - y).abs().max())

    # LEARN (trained): recover w from (X, y) by SGD on the substrate soft read.
    w_learned, loss0, lossN, grad0 = fit_w(
        vsa, X.to(dtype=vsa.dtype, device=vsa.device),
        y.to(dtype=vsa.dtype, device=vsa.device))
    w_learned = w_learned.to(dtype=DTYPE, device="cpu")
    coeff_err = float((w_learned - c_true).norm())
    # Evaluate with the LEARNED w via the SAME constructed head -> must agree.
    learn_pred = torch.tensor([reference.dot_tape(X[m].tolist(), w_learned.tolist())
                               for m in range(X.shape[0])], dtype=DTYPE)
    learn_err = float((learn_pred - y).abs().max())
    agree = float((eval_pred - learn_pred).abs().max())

    res = {
        "constructed_tasks_ok": reference.run_test_set(verbose=False),
        "eval_max_err": eval_err,
        "learn_loss0": loss0,
        "learn_lossN": lossN,
        "learn_grad0": grad0,
        "learn_coeff_err": coeff_err,
        "learn_eval_max_err": learn_err,
        "eval_vs_learn_agreement": agree,
        "c_true": [round(float(v), 3) for v in c_true],
        "w_learned": [round(float(v), 3) for v in w_learned],
    }

    if verbose:
        print("attention-on-RAM variants — comparison (Emma: do all, compare)\n")
        print("CONSTRUCTED parse tasks (evaluate), substrate-run as attn_* fixtures:")
        for task, args, expected in reference.TEST_SET:
            got = reference._DISPATCH[task](*args)
            print(f"  {task:<13}{str(args):<28} = {got!r:<8} (expected {expected!r})")
        print()
        print("EVALUATE vs LEARN on ONE shared linear-regression-over-memory task:")
        print(f"  c_true                       = {res['c_true']}")
        print(f"  [evaluate] constructed q=c   -> max|y_hat - y|       = {eval_err:.2e}")
        print(f"  [learn]    SGD fit w         -> loss {loss0:.3f} -> {lossN:.2e}, "
              f"||grad||@0 = {grad0:.3f}")
        print(f"             recovered w       = {res['w_learned']}")
        print(f"             ||w - c||         = {coeff_err:.2e}")
        print(f"             max|y_hat(learned) - y| = {learn_err:.2e}")
        print(f"  AGREEMENT  max|y_hat_eval - y_hat_learn| = {agree:.2e}  "
              f"(both converge to the same operator)")
    return res


def main() -> int:
    r = run_comparison(verbose=True)
    ok = (r["constructed_tasks_ok"] and r["eval_max_err"] < 1e-9
          and r["learn_lossN"] < 1e-3 and r["learn_coeff_err"] < 1e-2
          and r["learn_grad0"] > 1e-3 and r["eval_vs_learn_agreement"] < 1e-2)
    print("\n" + ("PASS: evaluate (constructed, exact) and learn (SGD, recovers c) "
                   "realize the SAME linear regression over memory."
                   if ok else "FAIL: a variant did not meet its measured bar."))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
