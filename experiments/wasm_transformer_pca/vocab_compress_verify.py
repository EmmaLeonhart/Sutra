"""Pruned-transformer step 3: compress the token/head embedding, find the minimal
rank that stays output-preserving.

PCA said the 915x38 token and head (readout) embeddings carry ~99% energy in ~3
of 38 dimensions. Unlike steps 1-2 (weights exactly zero -> lossless), this is
LOSSY: a rank-k truncation perturbs the input vectors and the logits, so the
question is the SMALLEST k for which the rank-k model still produces identical
output. This measures that k by SVD-truncating tok.weight and head.weight to
each rank and checking generation equivalence to the full model.

CAVEAT (honest): equivalence is checked on RANDOM token inputs, which do not
exercise the same paths as the 6 reference programs. So the minimal k found here
is a LOWER BOUND on what the real programs need; the canonical sign-off is the
committed-fixtures 6-program oracle (Emma 2026-06-06; needs clang, in progress).
Compile/monitor analysis on constructed weights, off any Sutra runtime path.
"""

from __future__ import annotations

import copy
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str((REPO / "WASM" / "replication_target" / "transformer-vm").resolve()))

import torch  # noqa: E402
import torch.nn.functional as F  # noqa: E402

from transformer_vm.model.weights import build_model  # noqa: E402
from transformer_vm.model.transformer import add_position_encoding  # noqa: E402
from transformer_vm.attention import StandardKVCache  # noqa: E402

PLAN = str((REPO / "experiments" / "wasm_transformer_pca" / "plan.yaml").resolve())


def generate(model, idx, max_new_tokens=24, cache_class=StandardKVCache):
    n_heads = model.attn[0].num_heads
    n_layers = len(model.attn)
    cache = cache_class(n_layers, n_heads)
    if hasattr(model, "head_tiebreak") and hasattr(cache, "set_tiebreak"):
        for li in range(n_layers):
            for h in range(n_heads):
                if model.head_tiebreak[li][h]:
                    cache.set_tiebreak(li, h, True)
    idx_list = idx[0].tolist()
    for pos in range(len(idx_list) + max_new_tokens):
        x = model.tok.weight[idx_list[pos]].clone()
        add_position_encoding(x, pos)
        for li, (attn, ff_in, ff_out) in enumerate(
            zip(model.attn, model.ff_in, model.ff_out, strict=True)
        ):
            q, k, v = (attn.in_proj_weight @ x).chunk(3, dim=-1)
            out = cache.layer_step(li, k, q, v)
            x = x + attn.out_proj(out)
            gate, val = ff_in(x).chunk(2, dim=-1)
            x = x + ff_out(F.relu(gate) * val)
        if pos + 1 == len(idx_list):
            nid = model.head(x).argmax().item()
            idx_list.append(nid)
            if nid == model.stop_token_id:
                break
    return idx_list


def rank_k(W, k):
    """Best rank-k approximation of W via SVD truncation."""
    U, S, Vh = torch.linalg.svd(W, full_matrices=False)
    return (U[:, :k] * S[:k]) @ Vh[:k]


def energy_table(W, name):
    S = torch.linalg.svdvals(W)
    e = (S ** 2).cumsum(0) / (S ** 2).sum()
    for k in (1, 2, 3, 4, 5):
        print(f"  {name} rank {k}: cumulative energy {100 * e[k - 1].item():.2f}%")


def main() -> int:
    torch.manual_seed(0)
    model, all_tokens, *_ = build_model(plan_path=PLAN)
    vocab = len(all_tokens)
    D = model.tok.weight.shape[1]
    print(f"vocab={vocab}, d_model={D}")
    print("token embedding energy:")
    energy_table(model.tok.weight.detach(), "tok")
    print("head (readout) energy:")
    energy_table(model.head.weight.detach(), "head")

    prefixes = [torch.randint(0, vocab, (1, int(torch.randint(3, 9, (1,)).item())),
                              dtype=torch.long) for _ in range(8)]
    full_out = [generate(model, p) for p in prefixes]

    min_k = None
    for k in range(1, D + 1):
        m = copy.deepcopy(model)
        m.tok.weight.data = rank_k(model.tok.weight.detach(), k)
        m.head.weight.data = rank_k(model.head.weight.detach(), k)
        ok = all(generate(m, p) == full_out[i] for i, p in enumerate(prefixes))
        print(f"rank {k:2d}: output-equivalent on 8/8 random inputs = {ok}")
        if ok and min_k is None:
            min_k = k
        if min_k is not None and k >= min_k + 2:
            break  # report a couple past the threshold, then stop

    if min_k is None:
        print("RESULT: no rank < full preserved output on random inputs (no clean low-rank cut).")
        return 0
    S = torch.linalg.svdvals(model.tok.weight.detach())
    etok = 100 * ((S[:min_k] ** 2).sum() / (S ** 2).sum()).item()
    print(f"RESULT: minimal output-preserving rank on random inputs = {min_k} "
          f"(tok energy at k={min_k}: {etok:.2f}%). "
          f"Embedding params if factored: {vocab * min_k + min_k * D} vs {vocab * D} "
          f"(per matrix). CAVEAT: random-input lower bound; 6-program oracle is canonical.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
