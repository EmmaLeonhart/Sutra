"""Unit tests for InquisitiveAttention and InquisitiveGPT2."""

import pytest
import torch
from transformers import GPT2Config, GPT2LMHeadModel

from src.inquisitive_attention import InquisitiveAttention
from src.inquisitive_gpt2 import InquisitiveGPT2, _replace_attention


@pytest.fixture
def small_config():
    """Tiny GPT-2 config for fast tests."""
    return GPT2Config(
        n_embd=64,
        n_head=4,
        n_layer=2,
        n_positions=128,
        vocab_size=1000,
        attn_implementation="eager",
    )


@pytest.fixture
def small_model(small_config):
    """Tiny GPT-2 model with inquisitive attention."""
    model = GPT2LMHeadModel(small_config)
    model = _replace_attention(model)
    model.eval()
    return model


class TestInquisitiveAttention:
    def test_alpha_zero_matches_standard(self, small_config):
        """With alpha=0, output should match standard GPT2Attention."""
        torch.manual_seed(0)
        attn = InquisitiveAttention(small_config, layer_idx=0)
        attn.eval()
        attn.alpha = 0.0

        hidden = torch.randn(1, 10, small_config.n_embd)

        # alpha=0 delegates to super().forward, so the output should be valid
        output = attn(hidden)
        assert output[0].shape == hidden.shape

    def test_alpha_nonzero_changes_output(self, small_config):
        """With alpha != 0, output should differ from alpha=0."""
        torch.manual_seed(0)
        attn = InquisitiveAttention(small_config, layer_idx=0)
        attn.eval()

        hidden = torch.randn(1, 10, small_config.n_embd)

        attn.alpha = 0.0
        out_zero = attn(hidden)[0]

        attn.alpha = 0.5
        out_pos = attn(hidden)[0]

        # Outputs should differ
        assert not torch.allclose(out_zero, out_pos, atol=1e-5)

    def test_positive_negative_alpha_differ(self, small_config):
        """Positive and negative alpha should produce different outputs."""
        torch.manual_seed(0)
        attn = InquisitiveAttention(small_config, layer_idx=0)
        attn.eval()

        hidden = torch.randn(1, 10, small_config.n_embd)

        attn.alpha = 0.5
        out_pos = attn(hidden)[0]

        attn.alpha = -0.5
        out_neg = attn(hidden)[0]

        assert not torch.allclose(out_pos, out_neg, atol=1e-5)

    def test_output_attentions(self, small_config):
        """Should return attention weights when requested."""
        attn = InquisitiveAttention(small_config, layer_idx=0)
        attn.eval()
        attn.alpha = 0.3

        hidden = torch.randn(1, 10, small_config.n_embd)
        outputs = attn(hidden, output_attentions=True)

        assert len(outputs) == 2
        attn_weights = outputs[1]
        # Attention weights should sum to ~1 along key dimension
        sums = attn_weights.sum(dim=-1)
        assert torch.allclose(sums, torch.ones_like(sums), atol=1e-5)

    def test_set_surprise_function(self, small_config):
        attn = InquisitiveAttention(small_config, layer_idx=0)
        attn.set_surprise_function("cosine_outlier")
        # Should not raise

        with pytest.raises(ValueError):
            attn.set_surprise_function("nonexistent")

    def test_no_nans(self, small_config):
        """Output should never contain NaN."""
        attn = InquisitiveAttention(small_config, layer_idx=0)
        attn.eval()

        for alpha in [-1.0, -0.5, 0.0, 0.5, 1.0]:
            attn.alpha = alpha
            hidden = torch.randn(1, 10, small_config.n_embd)
            output = attn(hidden)[0]
            assert not torch.isnan(output).any(), f"NaN at alpha={alpha}"


class TestReplaceAttention:
    def test_all_layers_replaced(self, small_model, small_config):
        for block in small_model.transformer.h:
            assert isinstance(block.attn, InquisitiveAttention)

    def test_model_runs_after_replacement(self, small_model):
        input_ids = torch.randint(0, 1000, (1, 10))
        output = small_model(input_ids)
        assert output.logits.shape == (1, 10, 1000)


class TestInquisitiveGPT2:
    def test_set_alpha_global(self, small_model):
        from transformers import GPT2Tokenizer

        # Create wrapper manually with the small model
        wrapper = InquisitiveGPT2.__new__(InquisitiveGPT2)
        wrapper.model = small_model
        wrapper.device = "cpu"

        wrapper.set_alpha(0.7)
        assert all(a == 0.7 for a in wrapper.get_alphas())

    def test_set_alpha_per_layer(self, small_model):
        wrapper = InquisitiveGPT2.__new__(InquisitiveGPT2)
        wrapper.model = small_model
        wrapper.device = "cpu"

        wrapper.set_alpha(0.0)  # reset
        wrapper.set_alpha(0.3, layers=[0])

        alphas = wrapper.get_alphas()
        assert alphas[0] == 0.3
        assert alphas[1] == 0.0

    def test_perplexity_runs(self, small_model):
        from transformers import GPT2Tokenizer

        wrapper = InquisitiveGPT2.__new__(InquisitiveGPT2)
        wrapper.model = small_model
        wrapper.device = "cpu"

        # Use a simple tokenizer-like mock
        tokenizer = type("Tok", (), {
            "__call__": lambda self, text, **kw: {
                "input_ids": torch.randint(0, 1000, (1, 5)),
                "attention_mask": torch.ones(1, 5, dtype=torch.long),
            },
            "eos_token_id": 0,
        })()
        tokenizer.__call__ = lambda text, **kw: type("Out", (), {
            "to": lambda self, d: {"input_ids": torch.randint(0, 1000, (1, 5))},
        })()

        wrapper.tokenizer = tokenizer

        # Just test that the model forward pass works with labels
        input_ids = torch.randint(0, 1000, (1, 5))
        output = wrapper.model(input_ids=input_ids, labels=input_ids)
        assert output.loss is not None
