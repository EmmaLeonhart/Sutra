"""E1 (retargeted): the learned unsigned saturating-add op is 100% exact.

Saturating add is value-natured (piecewise-linear: min(a+b,255) = a+b - relu(a+b-255)),
so it is learnable to bit-exactness where bitwise AND is not (spectral bias). This is
the constructed+trained thesis on a genuinely new, scaffold-natural instruction.
"""
from pathlib import Path

import pytest
import torch

from learned_ops.learned_op import LearnedByteOp, exact_match_fraction, TARGETS

CKPT = Path(__file__).resolve().parents[2].parent / "results" / "sat_add_u_op.pt"


def test_trained_sat_add_u_op_is_exact_on_all_pairs():
    if not CKPT.exists():
        pytest.fail(f"no trained checkpoint at {CKPT} (run train_and.py --op sat_add_u)")
    state = torch.load(CKPT, weights_only=False)
    op = LearnedByteOp(width=state["width"], depth=state["depth"], out_dim=state["out_dim"])
    op.load_state_dict(state["state_dict"])
    frac = exact_match_fraction(op, TARGETS[state["op"]])
    assert frac == 1.0, f"sat_add_u op exact on {frac * 100:.4f}% of pairs, need 100%"
