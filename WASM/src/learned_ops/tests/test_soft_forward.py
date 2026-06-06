"""E0: the grad-enabled softmax forward must reproduce the constructed model's
exact argmax execution.

If a differentiable, batched, causal softmax-attention forward over the loaded
analytic weights predicts the SAME next token at every generated position as the
model's own (hull-cache, argmax) generation, then it is a faithful stand-in we can
backprop through. That faithfulness is the whole foundation of the experiment.
"""
import torch
from transformer_vm.attention.standard_cache import StandardKVCache

from learned_ops.soft_forward import forward_logits


def test_soft_forward_reproduces_argmax_execution_on_hello(built_model, load_program_idx):
    model, _all_tokens, tok_to_idx = built_model
    prefix = load_program_idx("hello", tok_to_idx)

    # Ground truth: the model's own exact execution via the reference O(n) softmax
    # cache (pure torch; avoids the hull_ext C++ extension, which needs python3-dev).
    gen = model.generate_with_cache(
        torch.tensor([prefix], dtype=torch.long), cache_class=StandardKVCache
    )[0].tolist()
    assert len(gen) > len(prefix), "model did not generate beyond the prefix"

    # The differentiable forward, teacher-forced on that exact sequence.
    logits = forward_logits(model, torch.tensor([gen], dtype=torch.long))
    pred = logits[0].argmax(dim=-1)

    start = len(prefix) - 1  # first position that predicts a generated token
    mism = [
        (p, gen[p + 1], int(pred[p]))
        for p in range(start, len(gen) - 1)
        if int(pred[p]) != gen[p + 1]
    ]
    assert not mism, (
        f"{len(mism)}/{len(gen) - 1 - start} generated positions mismatch; "
        f"first 3 (pos, expected, got): {mism[:3]}"
    )
