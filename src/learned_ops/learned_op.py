"""Op-local learning of a byte operation from INTEGER operand inputs.

E1 target: `i32.and`. The trainable block sees only the two operand byte *values*
(0-255, normalized) — no bit decomposition handed to it — and must discover the
bitwise function. Output is 8 per-bit logits (bit 0 = LSB); the result byte is the
thresholded bits. Success = 100% exact over all 65 536 byte pairs (G1).
"""
import torch
import torch.nn as nn

N_BITS = 8


def all_byte_pairs():
    """Every (a, b) in [0,255]^2. Returns int tensors a, b each [65536]."""
    a = torch.arange(256).repeat_interleave(256)
    b = torch.arange(256).repeat(256)
    return a, b


def bits_of(x):
    """int tensor [N] -> float bits [N, 8], bit 0 = LSB."""
    shifts = torch.arange(N_BITS)
    return ((x.unsqueeze(-1) >> shifts) & 1).to(torch.float64)


def byte_from_bits(bits):
    """{0,1} bits [N, 8] (bit 0 = LSB) -> int byte [N]."""
    shifts = torch.arange(N_BITS, device=bits.device)
    return (bits.long() << shifts).sum(-1)


def encode_inputs(a, b):
    """Integer operand bytes -> model input features: just the two values in [0,1]."""
    return torch.stack([a.to(torch.float64), b.to(torch.float64)], dim=-1) / 255.0


def target_and(a, b):
    return a & b


def target_sat_add_u(a, b):
    """Unsigned 8-bit saturating add: min(a+b, 255). Piecewise-linear (one kink)."""
    return torch.clamp(a + b, max=255)


def target_sat_sub_u(a, b):
    """Unsigned 8-bit saturating subtract: max(a-b, 0)."""
    return torch.clamp(a - b, min=0)


# Registry of learnable byte ops (target functions over int tensors in [0,255]).
TARGETS = {
    "and": target_and,
    "sat_add_u": target_sat_add_u,
    "sat_sub_u": target_sat_sub_u,
}


def exact_match_fraction(op, target_fn=target_and):
    """Fraction of all 65 536 byte pairs where the op's output == target_fn.

    Dispatches on output width: 8 -> thresholded bits (bitwise ops);
    1 -> rounded byte value (arithmetic ops, the scaffold's native representation).
    """
    a, b = all_byte_pairs()
    x = encode_inputs(a, b)
    op.eval()
    with torch.no_grad():
        out = op(x)
        if out.shape[-1] == 1:
            pred = out.squeeze(-1).round().clamp(0, 255).long()
        else:
            pred = byte_from_bits((out > 0).to(torch.float64))
    return (pred == target_fn(a, b)).to(torch.float64).mean().item()


class LearnedByteOp(nn.Module):
    """ReGLU/ReLU MLP: 2 integer operands (normalized) -> 8 result-bit logits.

    Uses the same gated nonlinearity family as the scaffold's FFN (ReGLU = relu(b)*a),
    so a trained instance is crystallizable into the analytic DSL later.
    """

    def __init__(self, width=1024, depth=3, out_dim=N_BITS):
        super().__init__()
        self.out_dim = out_dim
        dims = [2] + [width] * depth
        self.hidden = nn.ModuleList(
            nn.Linear(dims[i], dims[i + 1]) for i in range(depth)
        )
        self.out = nn.Linear(width, out_dim)
        self.to(torch.float64)

    def forward(self, x):
        for lin in self.hidden:
            x = torch.relu(lin(x))
        return self.out(x)
