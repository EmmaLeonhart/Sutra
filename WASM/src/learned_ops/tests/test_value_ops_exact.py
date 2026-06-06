"""E4 gate: every value-output arithmetic op learns to 100% exact.

These ops (saturating add/sub, min, max) are piecewise-linear and value-natured —
the scaffold's native byte representation — so SGD reaches bit-exactness, unlike
bitwise AND (high-frequency, spectral bias). Skips an op whose checkpoint hasn't
been trained yet (run train_and.py --op <op>).
"""
from pathlib import Path

import pytest
import torch

from learned_ops.learned_op import LearnedByteOp, exact_match_fraction, TARGETS

RESULTS = Path(__file__).resolve().parents[2].parent / "results"
VALUE_OPS = ["sat_add_u", "sat_sub_u", "min_u", "max_u"]


@pytest.mark.parametrize("op", VALUE_OPS)
def test_value_op_is_exact(op):
    ckpt = RESULTS / f"{op}_op.pt"
    if not ckpt.exists():
        pytest.skip(f"no checkpoint for {op} (run train_and.py --op {op})")
    state = torch.load(ckpt, weights_only=False)
    module = LearnedByteOp(width=state["width"], depth=state["depth"], out_dim=state["out_dim"])
    module.load_state_dict(state["state_dict"])
    frac = exact_match_fraction(module, TARGETS[op])
    assert frac == 1.0, f"{op} exact on {frac * 100:.4f}% of pairs, need 100%"
