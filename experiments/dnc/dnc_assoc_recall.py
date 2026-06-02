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

SEEDS = [0, 1, 2, 3, 4]   # sweep to confirm the result isn't a single-seed fluke

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


def run(seed):
    """Train + evaluate once for a given seed. Returns the metrics dict."""
    torch.manual_seed(seed)
    W = nn.Parameter(torch.eye(D) + 0.01 * torch.randn(D, D))
    opt = torch.optim.Adam([W], lr=LR)

    for _ in range(STEPS):
        keys, values, query, q_idx, target = make_batch()
        recalled, _ = soft_read(W, keys, values, query, BETA_TRAIN)
        loss = F.mse_loss(recalled, target)
        opt.zero_grad(); loss.backward(); opt.step()

    with torch.no_grad():
        keys, values, query, q_idx, target = make_batch(4000)
        idx = torch.arange(4000)
        rec_soft, _ = soft_read(W, keys, values, query, BETA_TRAIN)
        cos_soft = F.cosine_similarity(rec_soft, target).mean().item()
        # DEFUZZED soft read (sharp beta) — the soft->discrete limit
        rec_dz, w_dz = soft_read(W, keys, values, query, BETA_DEFUZZ)
        peak = w_dz.max(dim=-1).values.mean().item()
        # the EXPLICIT discrete ram-op  M[argmax_cosine(read_key)]
        read_key = _unit(query @ W.t())
        hard_row = torch.einsum("bd,bnd->bn", read_key, _unit(keys)).argmax(dim=-1)
        rec_hard = values[idx, hard_row]
        # ISOMORPHISM: does the defuzzed soft read EQUAL the discrete op?
        agree = F.cosine_similarity(rec_dz, rec_hard).mean().item()
        same_row = (w_dz.argmax(dim=-1) == hard_row).float().mean().item()
        recall_acc = (hard_row == q_idx).float().mean().item()   # TASK metric
    return dict(cos_soft=cos_soft, peak=peak, agree=agree,
                same_row=same_row, recall=recall_acc)


def main():
    print(f"config: D={D} N={N} noise={NOISE} beta_train={BETA_TRAIN} "
          f"beta_defuzz={BETA_DEFUZZ} steps={STEPS}  seeds={SEEDS}")
    print()
    print("seed |  soft_cos  peak   same_row  agree   recall")
    rows = []
    for s in SEEDS:
        m = run(s)
        rows.append(m)
        print(f"  {s}  |   {m['cos_soft']:.3f}   {m['peak']:.3f}  "
              f"{m['same_row']*100:5.1f}%   {m['agree']:.3f}  {m['recall']*100:5.1f}%")

    def agg(k):
        vals = [r[k] for r in rows]
        return min(vals), sum(vals) / len(vals), max(vals)

    pk, sr, ag = agg("peak"), agg("same_row"), agg("agree")
    print()
    print(f"ISOMORPHISM across {len(SEEDS)} seeds (min / mean / max):")
    print(f"  defuzz cleanliness (peak weight)      : {pk[0]:.3f} / {pk[1]:.3f} / {pk[2]:.3f}")
    print(f"  defuzzed-soft row == argmax_cosine row: {sr[0]*100:.1f}% / {sr[1]*100:.1f}% / {sr[2]*100:.1f}%")
    print(f"  defuzzed-soft read · hard-op read cos : {ag[0]:.3f} / {ag[1]:.3f} / {ag[2]:.3f}")
    print(f"  (task recall is the lookup's accuracy under noise — separate.)")
    print()
    # Verdict on the WORST seed (no cherry-picking).
    iso = pk[0] > 0.95 and ag[0] > 0.97 and sr[0] > 0.99
    if iso:
        print("RESULT (all seeds): the trained soft content read DEFUZZES to —")
        print("and is numerically identical to — the discrete op  value =")
        print("M[argmax_cosine(read_key)]. Robust evidence of the DNC↔code")
        print("isomorphism for content read. (Recall<100% is the lookup's own")
        print("accuracy under noise, not a defuzz-fidelity gap.)")
    else:
        print("RESULT: at least one seed does NOT defuzz cleanly to the discrete")
        print("op. Finding: content-read isomorphism is seed-sensitive here —")
        print("needs β-anneal / regulariser (open Q 7). Reported as-is.")
    return 0 if iso else 1


if __name__ == "__main__":
    sys.exit(main())
