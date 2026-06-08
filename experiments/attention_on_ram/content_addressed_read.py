"""Content-based soft addressing vs. hard/inert addressing — the NTM/DNC hard part.

Emma's point (2026-06-08): editing RAM "normally" (indexed read, a hard argmax
location read, or a FIXED per-position weighted sum) is easy, but none of those
address memory BY CONTENT, and their addressing is either non-differentiable (argmax)
or not query-conditioned (fixed coefficients). The hard, load-bearing thing in an
NTM/DNC is content-based SOFT addressing:

    scores_i = q . M_i            # compare a query against each memory row's CONTENT
    w        = softmax(beta*scores)   # soft, differentiable addressing
    read     = sum_i w_i * v_i        # soft read

The gradient flows back through `w` into `q`, so the system can LEARN WHERE TO LOOK.
This is the difference between "theoretically differentiable but never improves" and
"a logical differentiable-ness that actually does stuff".

This script makes that difference MEASURABLE on a "learn to address by content" task:
a query `q` must learn to attend to the memory row whose value is the target. We train
`q` two ways and compare:

  (A) SOFT read (softmax addressing) — gradient flows through the addressing; `q` should
      move to the target row and the read should converge to the target value.
  (B) HARD read (argmax addressing)  — d(read)/dq = 0 almost everywhere; `q` gets no
      gradient, never moves, never learns. The "theoretically differentiable but inert"
      case. (We still build the loss; the point is that it cannot improve.)

This is a TRAINING experiment (the sanctioned compile-time fit role); the forward read
is plain torch. The substrate question (can softmax run as a Sutra op, exp-based) is the
design doc's open O1 and is noted, not claimed here.
"""

from __future__ import annotations

import torch

DTYPE = torch.float64


def make_memory(N: int = 8, d: int = 16, seed: int = 0):
    g = torch.Generator().manual_seed(seed)
    K = torch.randn(N, d, dtype=DTYPE, generator=g)      # memory keys (content)
    vals = torch.arange(1.0, N + 1.0, dtype=DTYPE)        # memory values (scalars)
    return K, vals


def soft_read(q, K, vals, beta: float):
    scores = K @ q                       # content match: query vs each row
    w = torch.softmax(beta * scores, dim=0)
    return w @ vals, w


def hard_read(q, K, vals):
    scores = K @ q
    w = torch.zeros_like(scores)
    w[int(torch.argmax(scores))] = 1.0   # argmax: NOT differentiable in q
    return w @ vals, w


def train_query(mode: str, K, vals, target_row: int, beta: float = 4.0,
                steps: int = 400, seed: int = 1):
    d = K.shape[1]
    g = torch.Generator().manual_seed(seed)
    q = torch.randn(d, dtype=DTYPE, generator=g, requires_grad=True)
    target = vals[target_row]
    opt = torch.optim.Adam([q], lr=0.2)
    grad0 = None
    loss0 = None
    for step in range(steps):
        opt.zero_grad()
        if mode == "soft":
            read, _w = soft_read(q, K, vals, beta)
        else:
            read, _w = hard_read(q, K, vals)
        loss = (read - target) ** 2
        # The hard (argmax) read detaches q from the graph: `loss` has no grad_fn,
        # so there is literally no gradient to backprop — the inert case made
        # concrete. We record grad0=0 and skip the (impossible) update.
        if loss.requires_grad:
            loss.backward()
            gnorm = float(q.grad.norm()) if q.grad is not None else 0.0
            opt.step()
        else:
            gnorm = 0.0
        if step == 0:
            grad0, loss0 = gnorm, float(loss.detach())
    # Final measurement (use the SOFT weights to read the attention even for the hard
    # run, so we can see where q ended up pointing; the read used in training is mode's).
    with torch.no_grad():
        read_final = (soft_read(q, K, vals, beta)[0] if mode == "soft"
                      else hard_read(q, K, vals)[0])
        _, w_soft = soft_read(q, K, vals, beta)
        weight_on_target = float(w_soft[target_row])
        lossN = float((read_final - target) ** 2)
    return {
        "mode": mode, "grad0": grad0, "loss0": loss0, "lossN": lossN,
        "read_final": float(read_final), "target": float(target),
        "weight_on_target": weight_on_target,
    }


def run(verbose: bool = True) -> dict:
    K, vals = make_memory()
    target_row = 3                       # value 4.0 is the retrieval target
    soft = train_query("soft", K, vals, target_row)
    hard = train_query("hard", K, vals, target_row)
    if verbose:
        print("content-based addressing: learn a query to retrieve value "
              f"{soft['target']} (row {target_row}) by CONTENT\n")
        for r in (soft, hard):
            print(f"  [{r['mode']:>4}] loss {r['loss0']:.3f} -> {r['lossN']:.3e}  "
                  f"||grad||@0 = {r['grad0']:.3e}  read -> {r['read_final']:.4f}  "
                  f"weight_on_target = {r['weight_on_target']:.4f}")
        print("\n  SOFT learns content-based retrieval (gradient flows through the "
              "softmax addressing into q).")
        print("  HARD cannot learn (argmax addressing gives q ~zero gradient) — "
              "'theoretically differentiable but inert'.")
    return {"soft": soft, "hard": hard, "target_row": target_row}


def main() -> int:
    r = run(verbose=True)
    soft, hard = r["soft"], r["hard"]
    # The discriminator, asserted: soft learns (low final loss, attends to target,
    # gradients flow); hard does NOT (negligible gradient, does not reach the target).
    soft_ok = (soft["lossN"] < 1e-2 and soft["weight_on_target"] > 0.9
               and soft["grad0"] > 1e-3)
    hard_inert = hard["grad0"] < 1e-9          # argmax: ~zero gradient to q
    hard_failed = hard["lossN"] > soft["lossN"]  # and it does not reach the target
    ok = soft_ok and hard_inert and hard_failed
    print("\n" + ("PASS: content-based SOFT addressing learns where to look; HARD "
                  "addressing is differentiable-on-paper but inert (zero gradient)."
                  if ok else "RESULT did not match the expected soft-learns/hard-inert "
                  "pattern — inspect the numbers above."))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
