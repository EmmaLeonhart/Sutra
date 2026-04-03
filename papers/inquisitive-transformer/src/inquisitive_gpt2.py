"""GPT-2 wrapper with inquisitive attention.

Loads a pretrained GPT-2 model and replaces its attention layers with
InquisitiveAttention, providing a unified interface to control the
perceptiveness parameter alpha.
"""

from __future__ import annotations

import torch
from transformers import GPT2LMHeadModel, GPT2Tokenizer

from .inquisitive_attention import InquisitiveAttention


def _replace_attention(model: GPT2LMHeadModel) -> GPT2LMHeadModel:
    """Replace all GPT2Attention modules with InquisitiveAttention in-place."""
    for i, block in enumerate(model.transformer.h):
        old_attn = block.attn
        new_attn = InquisitiveAttention(model.config, layer_idx=i)
        # Copy pretrained weights
        new_attn.load_state_dict(old_attn.state_dict(), strict=False)
        block.attn = new_attn
    return model


class InquisitiveGPT2:
    """GPT-2 with per-layer or global perceptiveness control.

    Usage:
        model = InquisitiveGPT2.from_pretrained("gpt2")
        model.set_alpha(0.5)
        output = model.generate("The anthropologist noticed", max_new_tokens=50)
    """

    def __init__(self, model: GPT2LMHeadModel, tokenizer: GPT2Tokenizer):
        self.model = model
        self.tokenizer = tokenizer
        self.device = next(model.parameters()).device

    @classmethod
    def from_pretrained(cls, model_name: str = "gpt2", device: str | None = None) -> "InquisitiveGPT2":
        """Load a pretrained GPT-2 and swap in inquisitive attention."""
        if device is None:
            device = "cuda" if torch.cuda.is_available() else "cpu"

        tokenizer = GPT2Tokenizer.from_pretrained(model_name)
        tokenizer.pad_token = tokenizer.eos_token

        model = GPT2LMHeadModel.from_pretrained(model_name)
        model = _replace_attention(model)
        model = model.to(device)
        model.eval()

        return cls(model, tokenizer)

    def set_alpha(self, alpha: float, layers: list[int] | None = None) -> None:
        """Set perceptiveness parameter.

        Args:
            alpha: Value in [-1, 1]. 0 = standard attention.
            layers: If specified, only set alpha on these layer indices.
        """
        for i, block in enumerate(self.model.transformer.h):
            if layers is not None and i not in layers:
                continue
            block.attn.alpha = alpha

    def set_surprise_function(self, name: str, layers: list[int] | None = None) -> None:
        """Set which surprise function to use.

        Args:
            name: One of the registered surprise function names.
            layers: If specified, only set on these layer indices.
        """
        for i, block in enumerate(self.model.transformer.h):
            if layers is not None and i not in layers:
                continue
            block.attn.set_surprise_function(name)

    def get_alphas(self) -> list[float]:
        """Return current alpha value for each layer."""
        return [block.attn.alpha for block in self.model.transformer.h]

    @torch.no_grad()
    def generate(self, prompt: str, max_new_tokens: int = 50, temperature: float = 1.0,
                 **kwargs) -> str:
        """Generate text from a prompt."""
        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.device)
        output_ids = self.model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            temperature=temperature,
            do_sample=temperature > 0,
            pad_token_id=self.tokenizer.eos_token_id,
            **kwargs,
        )
        return self.tokenizer.decode(output_ids[0], skip_special_tokens=True)

    @torch.no_grad()
    def perplexity(self, text: str) -> float:
        """Compute perplexity of a text string."""
        inputs = self.tokenizer(text, return_tensors="pt").to(self.device)
        input_ids = inputs["input_ids"]
        outputs = self.model(**inputs, labels=input_ids)
        return torch.exp(outputs.loss).item()
