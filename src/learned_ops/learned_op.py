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


def exact_match_fraction(op, target_fn=lambda a, b: a & b):
    """Fraction of all 65 536 byte pairs where thresholded op output == target_fn."""
    a, b = all_byte_pairs()
    x = encode_inputs(a, b)
    op.eval()
    with torch.no_grad():
        pred_bits = (op(x) > 0).to(torch.float64)
    pred = byte_from_bits(pred_bits)
    target = target_fn(a, b)
    return (pred == target).to(torch.float64).mean().item()


class LearnedByteOp(nn.Module):
    """ReGLU/ReLU MLP: 2 integer operands (normalized) -> 8 result-bit logits.

    Uses the same gated nonlinearity family as the scaffold's FFN (ReGLU = relu(b)*a),
    so a trained instance is crystallizable into the analytic DSL later.
    """

    def __init__(self, width=1024, depth=3):
        super().__init__()
        dims = [2] + [width] * depth
        self.hidden = nn.ModuleList(
            nn.Linear(dims[i], dims[i + 1]) for i in range(depth)
        )
        self.out = nn.Linear(width, N_BITS)
        self.to(torch.float64)

    def forward(self, x):
        for lin in self.hidden:
            x = torch.relu(lin(x))
        return self.out(x)
