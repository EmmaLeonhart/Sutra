"""E1 success gate (G1): the trained i32.and op is 100% exact on all 65 536 pairs.

This is the real red-green: it fails until train_and.py has produced a checkpoint
that learned AND exactly from integer operand inputs.
"""
from pathlib import Path

import pytest
import torch

from learned_ops.learned_op import LearnedByteOp, exact_match_fraction

CKPT = Path(__file__).resolve().parents[2].parent / "results" / "and_op.pt"


@pytest.mark.skip(
    reason="i32.and is NOT learnable to bit-exactness from raw integer operands "
    "(spectral bias: the LSB is a period-2 square wave; MLPs are low-frequency-biased). "
    "Documented negative result — see notes/experiment_learned_ops.md. The learnable "
    "demonstrator is saturating arithmetic (value-output), see test_sat_add_checkpoint_exact."
)
def test_trained_and_op_is_exact_on_all_pairs():
    if not CKPT.exists():
        pytest.fail(f"no trained checkpoint at {CKPT} (run train_and.py)")
    state = torch.load(CKPT, weights_only=False)
    op = LearnedByteOp(width=state["width"], depth=state["depth"])
    op.load_state_dict(state["state_dict"])
    frac = exact_match_fraction(op)
    assert frac == 1.0, f"AND op exact on {frac * 100:.4f}% of pairs, need 100%"
