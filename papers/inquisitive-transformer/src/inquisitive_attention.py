"""Inquisitive Attention: GPT-2 attention with a perceptiveness parameter.

Drop-in replacement for GPT2Attention that adds:
    scores_modified = scores + alpha * S(K)

where alpha controls sensitivity to surprising/out-of-place keys and S(K)
is a pluggable surprise function.
"""

import math

import torch
import torch.nn as nn
import torch.nn.functional as F
from transformers.models.gpt2.modeling_gpt2 import GPT2Attention

from .surprise_functions import causal_running_mean_distance, SURPRISE_FUNCTIONS


class InquisitiveAttention(GPT2Attention):
    """GPT-2 attention modified with an additive surprise bias.

    At alpha=0 this is identical to standard GPT-2 attention. Positive alpha
    amplifies attention to surprising keys; negative alpha suppresses them.
    """

    def __init__(self, config, layer_idx=None):
        super().__init__(config, layer_idx=layer_idx)
        self.alpha = 0.0
        self._surprise_fn = causal_running_mean_distance

    def set_surprise_function(self, name: str) -> None:
        """Set the surprise function by name."""
        if name not in SURPRISE_FUNCTIONS:
            raise ValueError(f"Unknown surprise function '{name}'. "
                             f"Available: {list(SURPRISE_FUNCTIONS.keys())}")
        self._surprise_fn = SURPRISE_FUNCTIONS[name]

    def forward(
        self,
        hidden_states,
        past_key_values=None,
        attention_mask=None,
        encoder_hidden_states=None,
        encoder_attention_mask=None,
        output_attentions=False,
        **kwargs,
    ):
        # If alpha is zero, skip surprise computation entirely
        if self.alpha == 0.0:
            return super().forward(
                hidden_states,
                past_key_values=past_key_values,
                attention_mask=attention_mask,
                encoder_hidden_states=encoder_hidden_states,
                encoder_attention_mask=encoder_attention_mask,
                output_attentions=output_attentions,
                **kwargs,
            )

        # --- Manual eager attention with surprise injection ---
        # Project Q, K, V
        query_states, key_states, value_states = self.c_attn(hidden_states).split(
            self.split_size, dim=2
        )

        shape_q = (*query_states.shape[:-1], -1, self.head_dim)
        shape_kv = (*key_states.shape[:-1], -1, self.head_dim)

        query_states = query_states.view(shape_q).transpose(1, 2)
        key_states = key_states.view(shape_kv).transpose(1, 2)
        value_states = value_states.view(shape_kv).transpose(1, 2)

        # Handle KV cache
        if past_key_values is not None:
            key_states, value_states = past_key_values.update(
                key_states, value_states, self.layer_idx
            )

        # Compute attention scores (matching eager_attention_forward scaling)
        attn_weights = torch.matmul(query_states, key_states.transpose(-1, -2))

        if self.scale_attn_weights:
            attn_weights = attn_weights / torch.full(
                [], value_states.size(-1) ** 0.5,
                dtype=attn_weights.dtype, device=attn_weights.device,
            )
        if self.scale_attn_by_inverse_layer_idx:
            attn_weights = attn_weights / float(self.layer_idx + 1)

        # === INQUISITIVE MODIFICATION ===
        surprise = self._surprise_fn(key_states)  # [B, H, 1, S_k]
        attn_weights = attn_weights + self.alpha * surprise
        # === END MODIFICATION ===

        # Causal mask
        if attention_mask is not None:
            attn_weights = attn_weights + attention_mask

        attn_weights = F.softmax(attn_weights, dim=-1, dtype=torch.float32).to(
            query_states.dtype
        )
        attn_weights = self.attn_dropout(attn_weights)

        attn_output = torch.matmul(attn_weights, value_states)

        # Merge heads: [B, H, S, D] -> [B, S, E]
        attn_output = attn_output.transpose(1, 2)
        attn_output = attn_output.reshape(*attn_output.shape[:-2], -1).contiguous()

        # Output projection
        attn_output = self.c_proj(attn_output)
        attn_output = self.resid_dropout(attn_output)

        outputs_attn_weights = attn_weights if output_attentions else None
        return attn_output, outputs_attn_weights
