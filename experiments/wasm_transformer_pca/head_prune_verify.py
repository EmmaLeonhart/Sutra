"""Pruned-transformer step 2: prune to the 42/133 attending head-slots, verify.

A head "attends" iff its Q AND K in_proj rows are non-zero (attention_usage.py:
42/133, per-layer 7,5,11,11,8,0,0). But an IDLE head (Q,K zero) is not
automatically free: its scores are zero -> softmax is uniform -> it outputs
mean(V) over positions, which `out_proj` then adds to the residual. So an idle
head is only removable if its contribution is actually zero. The decisive test:
zero the out_proj COLUMNS of every non-attending head (which removes exactly its
additive contribution, regardless of V) and check the model's generation is
unchanged. If identical, a model keeping only the 42 heads is output-preserving.

This measures the real structure first (per head: |Q|,|K|,|V| rows, |out_proj
cols|), classifies heads, then runs the equivalence check on random inputs.
Clang-free (random-input equivalence; the canonical 6-program byte-for-byte
oracle is the committed-fixtures route, Emma 2026-06-06). Compile/monitor
analysis on constructed weights, off any Sutra runtime path -- allowed.
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
    """Stock VanillaTransformer.generate_with_cache, StandardKVCache (no C++ ext)."""
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


def main() -> int:
    torch.manual_seed(0)
    model, all_tokens, *_ = build_model(plan_path=PLAN)
    vocab = len(all_tokens)
    D = model.attn[0].embed_dim
    H = model.attn[0].num_heads
    hd = D // H
    n_layers = len(model.attn)
    print(f"d_model={D}, heads/layer={H} (dim {hd}), layers={n_layers}")

    # Per-head structure + classification.
    used, idle_zero, idle_nonzero = [], [], []
    for li in range(n_layers):
        W = model.attn[li].in_proj_weight.detach()
        op = model.attn[li].out_proj.weight.detach()       # (D, D); head h -> cols h*hd:(h+1)*hd
        Q, K, V = W[:D], W[D : 2 * D], W[2 * D :]
        for h in range(H):
            qn = Q[h * hd : (h + 1) * hd].abs().sum().item()
            kn = K[h * hd : (h + 1) * hd].abs().sum().item()
            vn = V[h * hd : (h + 1) * hd].abs().sum().item()
            on = op[:, h * hd : (h + 1) * hd].abs().sum().item()
            attends = qn > 0 and kn > 0
            if attends:
                used.append((li, h))
            elif vn == 0.0 and on == 0.0:
                idle_zero.append((li, h))
            else:
                idle_nonzero.append((li, h, vn, on))
    print(f"attending (Q&K nonzero): {len(used)}/{H * n_layers}")
    print(f"idle & fully zero (V and out_proj cols zero): {len(idle_zero)}")
    print(f"idle but NONZERO V or out_proj cols: {len(idle_nonzero)}")
    for (li, h, vn, on) in idle_nonzero[:12]:
        print(f"  layer {li} head {h}: |V rows|={vn:.3e} |out cols|={on:.3e}")

    # Build a pruned copy: zero the out_proj COLUMNS of every non-attending head.
    used_set = set(used)
    pruned = copy.deepcopy(model)
    zeroed = 0
    for li in range(n_layers):
        op = pruned.attn[li].out_proj.weight  # (D, D)
        for h in range(H):
            if (li, h) not in used_set:
                op.data[:, h * hd : (h + 1) * hd] = 0.0
                zeroed += 1
    print(f"zeroed out_proj columns for {zeroed} non-attending head-slots "
          f"(keeping {len(used)})")

    # Equivalence on random inputs.
    mism = 0
    for trial in range(5):
        L = int(torch.randint(3, 9, (1,)).item())
        prefix = torch.randint(0, vocab, (1, L), dtype=torch.long)
        full = generate(model, prefix)
        pr = generate(pruned, prefix)
        same = full == pr
        print(f"trial {trial}: L={L} full_len={len(full)} pruned_len={len(pr)} match={same}")
        if not same:
            mism += 1

    if idle_nonzero:
        print(f"RESULT: {len(idle_nonzero)} 'idle' heads have nonzero V/out_proj — they "
              f"contribute mean(V) to the residual; the 42-count UNDERSTATES output-load-bearing heads.")
    if mism:
        print(f"FAIL: {mism}/5 trials diverged — pruning to the 42 attending heads is NOT "
              f"output-preserving (some non-attending heads contribute).")
        return 1
    print(f"PASS: zeroing all {zeroed} non-attending head contributions is output-preserving "
          f"on 5/5 random-input trials — the 42 attending heads suffice.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
