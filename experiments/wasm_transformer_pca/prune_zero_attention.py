"""Cheap-win reduction step 1: drop the two ALL-ZERO attention sublayers.

Emma greenlit "Full pruned core + verify" (2026-06-06). This is the first,
provably-lossless reduction the PCA diagnosed: the attention sublayers of
transformer layers 5 and 6 of Percepta's `transformer-vm` are entirely zero
(PCA: attn.5/attn.6 in_proj + out_proj are rank 0, dyn-range 0). A zero
attention block computes `x = x + out_proj(attn(...)) = x + 0`, i.e. an identity
pass-through, so removing it cannot change any output. NOTE: layers 5/6 keep
NON-zero FFNs (ff_in.5/ff_out.5 are full-rank), so we drop only the ATTENTION
sublayers, not whole layers.

This is compile/monitor analysis on the constructed weights (numpy/torch off any
Sutra runtime hot path) — allowed. It does NOT need clang: it verifies
output-preservation numerically on random token inputs, independent of the
6-WASM-program byte-for-byte oracle (which IS blocked locally on clang/uv —
needs WSL to compile the C programs to wasm to generate model inputs + refs).

Verifies two things, with measurements:
  (1) attn[5] and attn[6] weights are EXACTLY zero (max |w| == 0).
  (2) full model output == attention-pruned model output, token-for-token, on
      random inputs (because the dropped sublayers contribute exactly zero).
Reports the parameter reduction. Exits non-zero on any failure.
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

ZERO_ATTN_LAYERS = (5, 6)


def generate(model, idx, skip_attn=frozenset(), max_new_tokens=24, cache_class=StandardKVCache):
    """Mirror VanillaTransformer.generate_with_cache, but skip the attention
    sublayer (q/k/v compute + cache step + out_proj add) for layers in
    `skip_attn`. With skip_attn=={} this is the stock forward. Keeps the FFN."""
    n_heads = model.attn[0].num_heads
    n_layers = len(model.attn)
    cache = cache_class(n_layers, n_heads)
    if hasattr(model, "head_tiebreak") and hasattr(cache, "set_tiebreak"):
        for layer_idx in range(n_layers):
            for h in range(n_heads):
                if model.head_tiebreak[layer_idx][h]:
                    cache.set_tiebreak(layer_idx, h, True)
    idx_list = idx[0].tolist()
    for pos in range(len(idx_list) + max_new_tokens):
        x = model.tok.weight[idx_list[pos]].clone()
        add_position_encoding(x, pos)
        for layer_idx, (attn, ff_in, ff_out) in enumerate(
            zip(model.attn, model.ff_in, model.ff_out, strict=True)
        ):
            if layer_idx not in skip_attn:
                q, k, v = (attn.in_proj_weight @ x).chunk(3, dim=-1)
                out = cache.layer_step(layer_idx, k, q, v)
                x = x + attn.out_proj(out)
            gate, val = ff_in(x).chunk(2, dim=-1)
            x = x + ff_out(F.relu(gate) * val)
        if pos + 1 == len(idx_list):
            next_id = model.head(x).argmax().item()
            idx_list.append(next_id)
            if next_id == model.stop_token_id:
                break
    return idx_list


def main() -> int:
    torch.manual_seed(0)
    model, all_tokens, tok_to_idx, _ = build_model(plan_path=None)
    vocab = len(all_tokens)
    n_layers = len(model.attn)
    print(f"model: vocab={vocab}, n_layers={n_layers}, n_heads={model.attn[0].num_heads}")

    # (1) the two attention sublayers are EXACTLY zero.
    ok = True
    attn_params_dropped = 0
    for li in ZERO_ATTN_LAYERS:
        ip = model.attn[li].in_proj_weight.detach()
        op = model.attn[li].out_proj.weight.detach()
        ip_max = ip.abs().max().item()
        op_max = op.abs().max().item()
        print(f"attn[{li}]: max|in_proj|={ip_max:.3e}  max|out_proj|={op_max:.3e}")
        if ip_max != 0.0 or op_max != 0.0:
            ok = False
            print(f"  !! attn[{li}] is NOT exactly zero — removal is not lossless")
        attn_params_dropped += ip.numel() + op.numel()
    if not ok:
        print("FAIL: a target attention sublayer is non-zero")
        return 1

    total_params = sum(p.numel() for p in model.parameters())
    print(
        f"attention params dropped: {attn_params_dropped} / {total_params} "
        f"({100.0 * attn_params_dropped / total_params:.1f}%)"
    )

    # (2) output-preservation on random inputs: full vs attention-pruned.
    mismatches = 0
    for trial in range(5):
        L = int(torch.randint(3, 9, (1,)).item())
        prefix = torch.randint(0, vocab, (1, L), dtype=torch.long)
        full = generate(model, prefix, skip_attn=frozenset())
        pruned = generate(model, prefix, skip_attn=frozenset(ZERO_ATTN_LAYERS))
        same = full == pruned
        print(f"trial {trial}: L={L} full_len={len(full)} pruned_len={len(pruned)} match={same}")
        if not same:
            mismatches += 1
    if mismatches:
        print(f"FAIL: {mismatches}/5 random-input trials diverged after pruning")
        return 1

    print("PASS: attn[5],attn[6] are exactly zero; pruning them is output-preserving "
          "on all 5 random-input trials (token-for-token).")
    print("NOTE: byte-for-byte verification on the 6 WASM programs is blocked locally "
          "(needs clang/uv via WSL to compile C->wasm->tokens + reference traces).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
