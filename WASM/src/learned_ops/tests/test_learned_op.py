"""Contract tests for the op-local exactness metric and the E1 success gate."""
import torch
import torch.nn as nn

from learned_ops.learned_op import (
    bits_of,
    byte_from_bits,
    encode_inputs,
    exact_match_fraction,
    all_byte_pairs,
)


def test_bits_roundtrip():
    a, _ = all_byte_pairs()
    assert torch.equal(byte_from_bits(bits_of(a)), a)


class _ExactAnd(nn.Module):
    """Reference: emits the true AND bits as saturated logits (a&b, bit 0 = LSB)."""

    def forward(self, x):
        a = (x[:, 0] * 255).round().long()
        b = (x[:, 1] * 255).round().long()
        return (bits_of(a & b) * 2 - 1) * 1e3  # +big for bit=1, -big for bit=0


class _AlwaysZero(nn.Module):
    def forward(self, x):
        return torch.full((x.shape[0], 8), -1e3, dtype=torch.float64)


def test_metric_is_one_for_reference_exact_and():
    assert exact_match_fraction(_ExactAnd()) == 1.0


def test_metric_below_one_for_trivial_module():
    # AND is 0 for most pairs but not all; an always-zero op cannot be perfect.
    assert exact_match_fraction(_AlwaysZero()) < 1.0
