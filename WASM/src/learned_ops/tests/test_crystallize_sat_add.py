"""E2: crystallize the learned sat_add into an exact minimal DSL construction.

The learned wide MLP fit sat_add to 100%. Crystallization identifies the exact
closed form it represents — min(a+b,255) = a + b - relu(a+b-255), a single ReGLU
neuron — re-expresses it minimally, and verifies (a) it is exact and (b) the learned
net agrees with it on every pair (learned == crystallized). The result is a
permanent, deterministic, exact instruction (learn -> understand -> re-compile).
"""
from pathlib import Path

import pytest
import torch

from learned_ops.crystallize import CrystallizedSatAddU
from learned_ops.learned_op import (
    LearnedByteOp,
    TARGETS,
    all_byte_pairs,
    encode_inputs,
    exact_match_fraction,
)

CKPT = Path(__file__).resolve().parents[2].parent / "results" / "sat_add_u_op.pt"


def test_crystallized_sat_add_is_exact():
    assert exact_match_fraction(CrystallizedSatAddU(), TARGETS["sat_add_u"]) == 1.0


def test_learned_equals_crystallized_on_all_pairs():
    if not CKPT.exists():
        pytest.fail(f"no trained checkpoint at {CKPT} (run train_and.py --op sat_add_u)")
    state = torch.load(CKPT, weights_only=False)
    learned = LearnedByteOp(width=state["width"], depth=state["depth"], out_dim=state["out_dim"])
    learned.load_state_dict(state["state_dict"])
    cryst = CrystallizedSatAddU()

    a, b = all_byte_pairs()
    x = encode_inputs(a, b)
    learned.eval()
    with torch.no_grad():
        lp = learned(x).squeeze(-1).round().clamp(0, 255).long()
        cp = cryst(x).squeeze(-1).round().clamp(0, 255).long()
    assert torch.equal(lp, cp), f"{int((lp != cp).sum())} pairs disagree"
