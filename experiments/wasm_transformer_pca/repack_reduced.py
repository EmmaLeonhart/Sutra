"""Pruned-transformer: re-pack the reduced core into literally smaller tensors.

Steps 1-2 proved (by equivalence) that dropping the 2 zero attention sublayers
and the 91 fully-zero head-slots is output-preserving. This builds the concrete
reduced model: per layer, the attention in_proj keeps only the used heads' Q/K/V
rows and out_proj keeps only their columns; layers with 0 used heads have no
attention. The FFNs and embeddings are unchanged. Because the removed rows/cols
are exactly zero, the reduced model is output-IDENTICAL to the full one — checked
here token-for-token on random inputs. Reports the exact parameter reduction.

Clang-free (random-input equivalence; canonical 6-program oracle is the
committed-fixtures route). Compile/monitor analysis on constructed weights, off
any Sutra runtime path — allowed.
"""

from __future__ import annotations

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


def generate_full(model, idx, max_new_tokens=24):
    """Stock forward, StandardKVCache (pure torch)."""
    nH, nL = model.attn[0].num_heads, len(model.attn)
    cache = StandardKVCache(nL, nH)
    ids = idx[0].tolist()
    for pos in range(len(ids) + max_new_tokens):
        x = model.tok.weight[ids[pos]].clone()
        add_position_encoding(x, pos)
        for li, (attn, ff_in, ff_out) in enumerate(zip(model.attn, model.ff_in, model.ff_out, strict=True)):
            q, k, v = (attn.in_proj_weight @ x).chunk(3, dim=-1)
            out = cache.layer_step(li, k, q, v)
            x = x + attn.out_proj(out)
            gate, val = ff_in(x).chunk(2, dim=-1)
            x = x + ff_out(F.relu(gate) * val)
        if pos + 1 == len(ids):
            nid = model.head(x).argmax().item()
            ids.append(nid)
            if nid == model.stop_token_id:
                break
    return ids


def build_reduced(model):
    """Slice each layer's attention to its used heads (Q&K nonzero). Returns a list
    of per-layer dicts {inQ,inK,inV,outP,u} (u==0 => no attention)."""
    D = model.tok.weight.shape[1]
    H = model.attn[0].num_heads
    hd = D // H
    layers = []
    for li in range(len(model.attn)):
        W = model.attn[li].in_proj_weight.detach()
        op = model.attn[li].out_proj.weight.detach()
        Q, K, V = W[:D], W[D : 2 * D], W[2 * D :]
        used = [h for h in range(H)
                if Q[h * hd:(h + 1) * hd].abs().sum() > 0 and K[h * hd:(h + 1) * hd].abs().sum() > 0]
        if not used:
            layers.append({"u": 0})
            continue
        rows = torch.cat([torch.arange(h * hd, (h + 1) * hd) for h in used])
        layers.append({
            "u": len(used), "hd": hd,
            "inQ": Q[rows].clone(), "inK": K[rows].clone(), "inV": V[rows].clone(),
            "outP": op[:, rows].clone(),
        })
    return layers


def generate_reduced(model, red, idx, max_new_tokens=24):
    """Forward using the reduced per-layer attention (per-layer head count)."""
    nL = len(model.attn)
    hist_k = [[] for _ in range(nL)]
    hist_v = [[] for _ in range(nL)]
    ids = idx[0].tolist()
    for pos in range(len(ids) + max_new_tokens):
        x = model.tok.weight[ids[pos]].clone()
        add_position_encoding(x, pos)
        for li in range(nL):
            r = red[li]
            if r["u"] > 0:
                u, hd = r["u"], r["hd"]
                q = r["inQ"] @ x
                k = r["inK"] @ x
                v = r["inV"] @ x
                hist_k[li].append(k.clone())
                hist_v[li].append(v.clone())
                Km = torch.stack(hist_k[li]).reshape(-1, u, hd)
                Vm = torch.stack(hist_v[li]).reshape(-1, u, hd)
                Qr = q.reshape(u, hd)
                scores = torch.einsum("thi,hi->th", Km, Qr)
                w = F.softmax(scores, dim=0)
                out = torch.einsum("th,thi->hi", w, Vm).flatten()
                x = x + r["outP"] @ out
            gate, val = model.ff_in[li](x).chunk(2, dim=-1)
            x = x + model.ff_out[li](F.relu(gate) * val)
        if pos + 1 == len(ids):
            nid = model.head(x).argmax().item()
            ids.append(nid)
            if nid == model.stop_token_id:
                break
    return ids


def main() -> int:
    torch.manual_seed(0)
    model, all_tokens, *_ = build_model(plan_path=PLAN)
    vocab = len(all_tokens)
    D = model.tok.weight.shape[1]
    H = model.attn[0].num_heads
    nL = len(model.attn)
    red = build_reduced(model)
    used_per_layer = [r["u"] for r in red]
    print(f"d_model={D}, heads/layer={H}, layers={nL}")
    print(f"used heads per layer: {used_per_layer} (total {sum(used_per_layer)}/{H * nL})")

    # Parameter accounting (attention only; FFN + embeddings unchanged).
    hd = D // H
    full_attn = nL * (3 * D * D + D * D)  # in_proj (3D x D) + out_proj (D x D) per layer
    red_attn = sum((3 * (r["u"] * hd) * D + D * (r["u"] * hd)) for r in red if r["u"] > 0)
    print(f"attention params: full {full_attn} -> reduced {red_attn} "
          f"({100 * (full_attn - red_attn) / full_attn:.1f}% removed)")

    mism = 0
    for trial in range(8):
        L = int(torch.randint(3, 9, (1,)).item())
        prefix = torch.randint(0, vocab, (1, L), dtype=torch.long)
        a = generate_full(model, prefix)
        b = generate_reduced(model, red, prefix)
        same = a == b
        print(f"trial {trial}: L={L} full_len={len(a)} reduced_len={len(b)} match={same}")
        if not same:
            mism += 1
    if mism:
        print(f"FAIL: {mism}/8 trials diverged — the re-packed reduced model is NOT identical.")
        return 1
    print(f"PASS: the re-packed {sum(used_per_layer)}-head reduced model is output-IDENTICAL "
          f"to the full model on 8/8 random inputs ({100 * (full_attn - red_attn) / full_attn:.1f}% "
          f"of attention params removed).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
