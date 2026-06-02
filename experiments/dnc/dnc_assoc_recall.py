"""DNC↔code isomorphism — first experiment (content-addressing only).

planning/sutra-spec/ram-pointers.md is the discrete cousin;
planning/exploratory/differentiable-neural-computer.md § "The point" is
the design. This tests the load-bearing hypothesis: does a TRAINED soft
content-addressing policy DEFUZZ into a clean discrete op — an associative
lookup `value = M[argmax_cosine(query)]` — i.e. does the learned soft
addressing read off as written code at the β→∞ limit?

HONEST SCOPE: this is a host-PyTorch research prototype. It is NOT a
substrate-pure Sutra DNC — the point is to test whether the β-defuzz
bridge yields a clean discrete addressing at all before building the
substrate version. The ops used (cosine, softmax, matmul) are the same
family as Sutra's substrate ops; the defuzzed op maps to the ram-op
`M[argmax_cosine(key)]`.

Task: associative recall. Each example has N fresh random (key, value)
pairs in memory; a query = one stored key + noise; the target is that
key's value. A trainable linear controller maps query → read key; the
soft read is `softmax(β·cosine(read_key, M_keys)) · M_values`. "Attention"
here is the weighting VECTOR w (N-dim), not a matrix (Emma 2026-06-02).

Defuzz test: after training at a gentle β, raise β (sharpen) and measure
whether argmax(w) lands on the right row and how peaked w is — that is the
soft→discrete (→code) recovery.

Run: python experiments/dnc/dnc_assoc_recall.py
"""
from __future__ import annotations

import io
import sys

import torch
import torch.nn as nn
import torch.nn.functional as F

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

torch.manual_seed(0)

D = 16          # vector width
N = 8           # memory rows / pairs per example
NOISE = 0.3     # query = stored key + NOISE * unit-noise  (forces learning)
BETA_TRAIN = 5.0
BETA_DEFUZZ = 50.0
STEPS = 3000
BATCH = 64
LR = 1e-2


def _unit(x, dim=-1):
    return x / (x.norm(dim=dim, keepdim=True) + 1e-8)


def make_batch(batch=BATCH):
    # Fresh random (key, value) memory per example so the controller must
    # learn the general query->address map, not memorise specific pairs.
    keys = _unit(torch.randn(batch, N, D))
    values = torch.randn(batch, N, D)
    q_idx = torch.randint(0, N, (batch,))
    chosen = keys[torch.arange(batch), q_idx]           # (batch, D)
    query = _unit(chosen + NOISE * torch.randn(batch, D))
    target = values[torch.arange(batch), q_idx]         # (batch, D)
    return keys, values, query, q_idx, target


def soft_read(W, keys, values, query, beta):
    read_key = _unit(query @ W.t())                      # controller: linear map
    cos = torch.einsum("bd,bnd->bn", read_key, _unit(keys))  # cosine vs each row
    w = F.softmax(beta * cos, dim=-1)                    # the weighting VECTOR
    recalled = torch.einsum("bn,bnd->bd", w, values)     # w · M_values
    return recalled, w


def main():
    W = nn.Parameter(torch.eye(D) + 0.01 * torch.randn(D, D))
    opt = torch.optim.Adam([W], lr=LR)

    for step in range(STEPS):
        keys, values, query, q_idx, target = make_batch()
        recalled, _ = soft_read(W, keys, values, query, BETA_TRAIN)
        loss = F.mse_loss(recalled, target)
        opt.zero_grad(); loss.backward(); opt.step()

    # Evaluation on fresh data.
    with torch.no_grad():
        keys, values, query, q_idx, target = make_batch(4000)
        idx = torch.arange(4000)
        # (1) trained soft read (gentle beta)
        rec_soft, _ = soft_read(W, keys, values, query, BETA_TRAIN)
        cos_soft = F.cosine_similarity(rec_soft, target).mean().item()
        # (2) DEFUZZED soft read (sharp beta) — the soft->discrete limit
        rec_dz, w_dz = soft_read(W, keys, values, query, BETA_DEFUZZ)
        peak = w_dz.max(dim=-1).values.mean().item()
        # (3) the EXPLICIT discrete ram-op  M[argmax_cosine(read_key)]
        read_key = _unit(query @ W.t())
        cos_rows = torch.einsum("bd,bnd->bn", read_key, _unit(keys))
        hard_row = cos_rows.argmax(dim=-1)
        rec_hard = values[idx, hard_row]                 # M_values[argmax_cosine]
        # ISOMORPHISM metric: does the defuzzed soft read EQUAL the discrete op?
        soft_hard_agree = F.cosine_similarity(rec_dz, rec_hard).mean().item()
        same_row = (w_dz.argmax(dim=-1) == hard_row).float().mean().item()
        # TASK metric (separate): recall accuracy of the lookup under noise.
        recall_acc = (hard_row == q_idx).float().mean().item()
        rand_cos = F.cosine_similarity(values[idx, torch.randint(0, N, (4000,))],
                                       target).mean().item()

    print(f"config: D={D} N={N} noise={NOISE} beta_train={BETA_TRAIN} "
          f"beta_defuzz={BETA_DEFUZZ} steps={STEPS}")
    print(f"trained soft read (β={BETA_TRAIN:.0f}): recalled·target cos = {cos_soft:.3f}")
    print()
    print("ISOMORPHISM (does the defuzzed soft read == the discrete ram-op?):")
    print(f"  defuzz cleanliness (mean peak weight) : {peak:.3f}  (1.0 = one-hot)")
    print(f"  defuzzed-soft row == argmax_cosine row: {same_row*100:.1f}%")
    print(f"  defuzzed-soft read · hard-op read cos : {soft_hard_agree:.3f}  (1.0 = identical)")
    print()
    print("TASK (separate — accuracy of the lookup itself under query noise):")
    print(f"  M[argmax_cosine(query)] == true row   : {recall_acc*100:.1f}%   "
          f"(random {100/N:.1f}%)")
    print(f"  (the discrete op and the soft read score the SAME here — the")
    print(f"   misses are noisy-nearest-neighbour, intrinsic to the lookup.)")
    print()
    iso = peak > 0.95 and soft_hard_agree > 0.97 and same_row > 0.99
    if iso:
        print("RESULT: the trained soft content read DEFUZZES to — and is")
        print("numerically identical to — the discrete op  value =")
        print("M[argmax_cosine(read_key)]. First measured evidence of the")
        print("DNC↔code isomorphism: a learned soft read reads off as the")
        print("associative-lookup ram-op. (Recall < 100% is the lookup's own")
        print("accuracy under noise, not a defuzz-fidelity gap.)")
    else:
        print("RESULT: the defuzzed soft read does NOT match the discrete op")
        print("(blurry weighting or argmax disagreement). Finding: needs")
        print("β-anneal / regulariser (open Q 7). Reported as-is, not hidden.")
    return 0 if iso else 1


if __name__ == "__main__":
    sys.exit(main())
