"""Crystallized (exact, minimal) forms of learned byte ops.

A learned op is a wide MLP that fits the target to 100%. Crystallization identifies
the exact closed form it represents and re-expresses it minimally using the scaffold's
own DSL primitives, so the op becomes a permanent, deterministic, bit-exact
instruction — indistinguishable from a hand-built one, but discovered by gradient.

Unsigned saturating add: min(a+b, 255) = a + b - relu(a+b - 255). The `relu(...)` is a
single ReGLU neuron in the scaffold's FFN (reglu(one, a+b-255) = relu(a+b-255)).
"""
import torch
import torch.nn as nn


class CrystallizedSatAddU(nn.Module):
    """Exact unsigned saturating add as one ReGLU neuron: a + b - relu(a+b-255).

    Input is the same normalized encoding the learned op uses (x = [a/255, b/255]);
    output is the byte value, shape [..., 1].
    """

    def forward(self, x):
        a = x[..., 0] * 255.0
        b = x[..., 1] * 255.0
        s = a + b
        out = s - torch.relu(s - 255.0)  # = min(a + b, 255)
        return out.unsqueeze(-1)
