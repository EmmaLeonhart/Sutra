"""Unit tests for experiment configuration functions."""

import pytest
import torch
from transformers import GPT2Config, GPT2LMHeadModel

from src.inquisitive_gpt2 import InquisitiveGPT2, _replace_attention
from experiments.e2_split import configure_split
from experiments.e3_random import make_configure_random
from experiments.e4_doubled import configure_alternating


@pytest.fixture
def wrapper():
    """Create a small InquisitiveGPT2 wrapper for testing."""
    config = GPT2Config(
        n_embd=64, n_head=4, n_layer=6, n_positions=128,
        vocab_size=1000, attn_implementation="eager",
    )
    model = GPT2LMHeadModel(config)
    model = _replace_attention(model)
    model.eval()

    w = InquisitiveGPT2.__new__(InquisitiveGPT2)
    w.model = model
    w.device = "cpu"
    return w


class TestE2Split:
    def test_split_assigns_opposite_signs(self, wrapper):
        configure_split(wrapper, 0.5)
        alphas = wrapper.get_alphas()
        # 6 layers: first 3 positive, last 3 negative
        assert all(a == 0.5 for a in alphas[:3])
        assert all(a == -0.5 for a in alphas[3:])

    def test_split_zero_alpha(self, wrapper):
        configure_split(wrapper, 0.0)
        assert all(a == 0.0 for a in wrapper.get_alphas())

    def test_split_negative_alpha(self, wrapper):
        configure_split(wrapper, -0.5)
        alphas = wrapper.get_alphas()
        # First half gets the passed alpha (-0.5), second half gets -(-0.5)=+0.5
        assert all(a == -0.5 for a in alphas[:3])
        assert all(a == 0.5 for a in alphas[3:])


class TestE3Random:
    def test_random_assigns_different_values(self, wrapper):
        configure_fn = make_configure_random(seed=42)
        configure_fn(wrapper, 1.0)
        alphas = wrapper.get_alphas()
        # With 6 layers and scale=1.0, very unlikely all are the same
        assert len(set(alphas)) > 1

    def test_random_within_bounds(self, wrapper):
        configure_fn = make_configure_random(seed=42)
        configure_fn(wrapper, 0.5)
        for a in wrapper.get_alphas():
            assert -0.5 <= a <= 0.5

    def test_random_reproducible(self, wrapper):
        configure_fn = make_configure_random(seed=123)
        configure_fn(wrapper, 0.5)
        alphas1 = wrapper.get_alphas()

        configure_fn(wrapper, 0.5)
        alphas2 = wrapper.get_alphas()

        assert alphas1 == alphas2


class TestE4Alternating:
    def test_alternating_pattern(self, wrapper):
        configure_alternating(wrapper, 0.5)
        alphas = wrapper.get_alphas()
        for i, a in enumerate(alphas):
            expected = 0.5 if i % 2 == 0 else -0.5
            assert a == expected, f"Layer {i}: expected {expected}, got {a}"

    def test_alternating_zero(self, wrapper):
        configure_alternating(wrapper, 0.0)
        assert all(a == 0.0 for a in wrapper.get_alphas())
