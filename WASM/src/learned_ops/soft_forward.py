"""Grad-enabled, batched, causal softmax-attention forward over a constructed
transformer-vm `VanillaTransformer`.

The shipped inference forward (`generate_with_cache`) is `@torch.no_grad()` and
ends in `argmax` (hardmax). To *train* new operations into the analytic weights we
need a differentiable forward. This reproduces the same per-token math —
embedding + position encoding, per-layer `Q·K` attention (unscaled, exactly as the
reference `StandardKVCache`), ReGLU FFN, vocab head — but batched over the whole
sequence with a causal mask and a temperature knob `tau` on the attention scores.

- `tau = 1.0` reproduces the constructed model's exact execution (the constructed
  keys are scaled so softmax already behaves as argmax) — this is the E0 faithfulness
  contract.
- `tau < 1.0` softens attention so gradients flow for end-to-end training.
"""
import math

import torch
import torch.nn.functional as F


def forward_logits(model, idx, tau: float = 1.0):
    """Return vocab logits at every position. idx: long tensor [1, T] -> [1, T, vocab]."""
    seq = idx[0]
    T = int(seq.shape[0])
    dtype = model.tok.weight.dtype
    device = model.tok.weight.device

    # Token embedding + deterministic position encoding (cf. add_position_encoding).
    x = model.tok.weight[seq].clone()  # [T, d_model]
    pos = torch.arange(T, dtype=dtype, device=device)
    x[:, 0] = x[:, 0] + pos
    x[:, 1] = x[:, 1] + (1.0 / math.log(2) - 1.0 / torch.log(pos + 2.0))
    x[:, 2] = x[:, 2] + pos * pos

    n_heads = model.attn[0].num_heads
    causal = torch.tril(torch.ones(T, T, dtype=torch.bool, device=device))  # [T(query), S(key)]

    for attn, ff_in, ff_out in zip(model.attn, model.ff_in, model.ff_out, strict=True):
        q, k, v = (x @ attn.in_proj_weight.t()).chunk(3, dim=-1)  # each [T, d]
        d = q.shape[-1]
        hd = d // n_heads
        q = q.reshape(T, n_heads, hd)
        k = k.reshape(T, n_heads, hd)
        v = v.reshape(T, n_heads, hd)

        scores = torch.einsum("thi,shi->tsh", q, k) * tau  # [T, S, H]
        scores = scores.masked_fill(~causal.unsqueeze(-1), float("-inf"))
        weights = F.softmax(scores, dim=1)  # over keys S
        out = torch.einsum("tsh,shi->thi", weights, v).reshape(T, d)
        x = x + attn.out_proj(out)

        gate, val = ff_in(x).chunk(2, dim=-1)
        x = x + ff_out(F.relu(gate) * val)

    return model.head(x).unsqueeze(0)  # [1, T, vocab]
