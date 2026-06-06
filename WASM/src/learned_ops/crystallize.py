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


def _ab(x):
    """Recover the integer operand values from the normalized encoding [a/255, b/255]."""
    return x[..., 0] * 255.0, x[..., 1] * 255.0


class CrystallizedSatAddU(nn.Module):
    """min(a+b, 255) = a + b - relu(a+b-255). One ReGLU neuron."""

    def forward(self, x):
        a, b = _ab(x)
        return (a + b - torch.relu(a + b - 255.0)).unsqueeze(-1)


class CrystallizedSatSubU(nn.Module):
    """max(a-b, 0) = relu(a-b). One ReGLU neuron."""

    def forward(self, x):
        a, b = _ab(x)
        return torch.relu(a - b).unsqueeze(-1)


class CrystallizedMinU(nn.Module):
    """min(a, b) = a - relu(a-b). One ReGLU neuron."""

    def forward(self, x):
        a, b = _ab(x)
        return (a - torch.relu(a - b)).unsqueeze(-1)


class CrystallizedMaxU(nn.Module):
    """max(a, b) = a + relu(b-a). One ReGLU neuron."""

    def forward(self, x):
        a, b = _ab(x)
        return (a + torch.relu(b - a)).unsqueeze(-1)


# op name -> exact crystallized module (the closed form each learned op reduces to).
CRYSTALLIZED = {
    "sat_add_u": CrystallizedSatAddU,
    "sat_sub_u": CrystallizedSatSubU,
    "min_u": CrystallizedMinU,
    "max_u": CrystallizedMaxU,
}
