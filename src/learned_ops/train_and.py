"""E1: train i32.and op-local from INTEGER operand inputs to 100% exact.

The op sees only the two operand byte values (normalized) and must discover bitwise
AND. Output = 8 per-bit logits. The hard bit is the LSB: bit0(a&b) = [a odd]&[b odd],
a high-frequency square wave needing many ReLU thresholds — so we use ample width and
**hard-example focusing** (upweight currently-misclassified pairs) to drive the final
errors to exactly zero.

Saves results/and_op.pt = {state_dict (float64), width, depth, exact}.

Run: uv run python src/learned_ops/train_and.py [--width 768] [--epochs 4000]
"""
import argparse
from pathlib import Path

import torch
import torch.nn as nn

from learned_ops.learned_op import (
    TARGETS,
    LearnedByteOp,
    all_byte_pairs,
    bits_of,
    byte_from_bits,
    encode_inputs,
)

RESULTS = Path(__file__).resolve().parents[2] / "results"  # repo_root/results


# Output representation per op: bitwise ops need per-bit output; arithmetic ops are
# value-natured (the scaffold's native byte representation) and learn the value.
MODES = {"and": "bits", "sat_add_u": "value", "sat_sub_u": "value"}


def exact_and_errors(op, x, target_byte):
    """Return (exact_fraction, boolean mask [N] of misclassified pairs)."""
    op.eval()
    with torch.no_grad():
        out = op(x)
        if out.shape[-1] == 1:
            pred = out.squeeze(-1).round().clamp(0, 255).long()
        else:
            pred = byte_from_bits((out > 0).to(x.dtype))
    wrong = pred != target_byte
    return 1.0 - wrong.to(torch.float64).mean().item(), wrong


def train(op="and", width=768, depth=3, epochs=4000, lr=2e-3, batch=8192, seed=0, dtype=torch.float32):
    torch.manual_seed(seed)
    target_fn = TARGETS[op]
    mode = MODES[op]
    a, b = all_byte_pairs()
    x = encode_inputs(a, b).to(dtype)
    target_byte = target_fn(a, b)
    n = x.shape[0]

    if mode == "value":
        out_dim = 1
        y = target_byte.to(dtype)  # regress the byte value
    else:
        out_dim = bits_of(target_byte).shape[-1]
        y = bits_of(target_byte).to(dtype)

    model_op = LearnedByteOp(width=width, depth=depth, out_dim=out_dim).to(dtype)
    op_module = model_op  # alias used below; keep variable name `op` for the op string
    opt = torch.optim.Adam(model_op.parameters(), lr=lr)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=epochs)
    bce = nn.BCEWithLogitsLoss(reduction="none")
    mse = nn.MSELoss(reduction="none")

    weight = torch.ones(n, dtype=dtype)  # per-sample focus weight
    best_exact, best_state = 0.0, None

    for ep in range(epochs):
        op_module.train()
        perm = torch.randperm(n)
        for i in range(0, n, batch):
            idx = perm[i : i + batch]
            opt.zero_grad()
            out = op_module(x[idx])
            if mode == "value":
                per = mse(out.squeeze(-1), y[idx])
            else:
                per = bce(out, y[idx]).mean(dim=1)
            loss = (per * weight[idx]).mean()
            loss.backward()
            opt.step()
        sched.step()

        if ep % 25 == 0 or ep == epochs - 1:
            exact, wrong = exact_and_errors(op_module, x, target_byte)
            n_wrong = int(wrong.sum())
            if exact > best_exact:
                best_exact = exact
                best_state = {k: v.detach().clone() for k, v in op_module.state_dict().items()}
            print(f"epoch {ep:5d}  exact={exact * 100:8.4f}%  wrong={n_wrong:6d}  lr={sched.get_last_lr()[0]:.2e}", flush=True)
            if exact >= 1.0:
                break
            # Hard-example focusing once we're close: upweight the stragglers.
            if exact > 0.97 and n_wrong > 0:
                weight[wrong] = torch.clamp(weight[wrong] * 1.5, max=1e4)

    # Final exactness in float64 (the regime the scaffold runs in).
    final = LearnedByteOp(width=width, depth=depth, out_dim=out_dim)  # float64
    state = best_state if (best_state and best_exact >= exact) else op_module.state_dict()
    final.load_state_dict({k: v.to(torch.float64) for k, v in state.items()})
    exact64, wrong64 = exact_and_errors(final, encode_inputs(*all_byte_pairs()), target_byte)

    RESULTS.mkdir(exist_ok=True)
    out_path = RESULTS / f"{op}_op.pt"
    torch.save(
        {"op": op, "mode": mode, "out_dim": out_dim,
         "state_dict": {k: v.to(torch.float64) for k, v in final.state_dict().items()},
         "width": width, "depth": depth, "exact": exact64},
        out_path,
    )
    print(f"SAVED {out_path}  exact(float64)={exact64 * 100:.6f}%  wrong={int(wrong64.sum())}", flush=True)
    return exact64


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--op", default="and", choices=sorted(TARGETS), help="op to learn")
    ap.add_argument("--width", type=int, default=768)
    ap.add_argument("--depth", type=int, default=3)
    ap.add_argument("--epochs", type=int, default=4000)
    ap.add_argument("--lr", type=float, default=2e-3)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    exact = train(op=args.op, width=args.width, depth=args.depth, epochs=args.epochs, lr=args.lr, seed=args.seed)
    print("RESULT_EXACT", exact)


if __name__ == "__main__":
    main()
