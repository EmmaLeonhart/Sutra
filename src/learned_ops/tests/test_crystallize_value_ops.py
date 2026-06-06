"""E2b: every value-op crystallizes to an exact closed form, and the learned net
equals that crystallized form on all 65 536 pairs (learn -> understand -> re-compile,
for all four arithmetic ops, not just sat_add)."""
from pathlib import Path

import pytest
import torch

from learned_ops.crystallize import CRYSTALLIZED
from learned_ops.learned_op import LearnedByteOp, TARGETS, all_byte_pairs, encode_inputs, exact_match_fraction

RESULTS = Path(__file__).resolve().parents[2].parent / "results"
OPS = ["sat_add_u", "sat_sub_u", "min_u", "max_u"]


@pytest.mark.parametrize("op", OPS)
def test_crystallized_form_is_exact(op):
    assert exact_match_fraction(CRYSTALLIZED[op](), TARGETS[op]) == 1.0


@pytest.mark.parametrize("op", OPS)
def test_learned_equals_crystallized(op):
    ckpt = RESULTS / f"{op}_op.pt"
    if not ckpt.exists():
        pytest.skip(f"no checkpoint for {op}")
    state = torch.load(ckpt, weights_only=False)
    learned = LearnedByteOp(width=state["width"], depth=state["depth"], out_dim=state["out_dim"])
    learned.load_state_dict(state["state_dict"])
    cryst = CRYSTALLIZED[op]()
    a, b = all_byte_pairs()
    x = encode_inputs(a, b)
    learned.eval()
    with torch.no_grad():
        lp = learned(x).squeeze(-1).round().clamp(0, 255).long()
        cp = cryst(x).squeeze(-1).round().clamp(0, 255).long()
    assert torch.equal(lp, cp), f"{op}: {int((lp != cp).sum())} pairs disagree"
