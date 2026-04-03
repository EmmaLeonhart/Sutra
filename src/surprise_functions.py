"""Surprisingness functions S(K) for the Inquisitive Transformer.

Each function takes key states and returns a per-position surprise score
that can be added to attention logits before softmax.

All functions return shape [batch, num_heads, 1, seq_len] so they broadcast
directly against attention scores of shape [batch, num_heads, seq_len_q, seq_len_k].
"""

import torch
import torch.nn.functional as F


def causal_running_mean_distance(key_states: torch.Tensor) -> torch.Tensor:
    """Surprise = distance of each key from the running mean of prior keys.

    This is the primary candidate: causal, O(n), no learned parameters,
    and directly interpretable as "how far is this key from what came before."

    Args:
        key_states: [batch, num_heads, seq_len, head_dim]

    Returns:
        surprise: [batch, num_heads, 1, seq_len]
    """
    batch, heads, seq_len, dim = key_states.shape

    # Cumulative sum for efficient running mean
    cumsum = torch.cumsum(key_states, dim=2)  # [B, H, S, D]
    counts = torch.arange(1, seq_len + 1, device=key_states.device, dtype=key_states.dtype)
    counts = counts.view(1, 1, -1, 1)

    # Running mean shifted by 1 position (causal: only prior keys)
    running_mean = torch.zeros_like(key_states)
    if seq_len > 1:
        running_mean[:, :, 1:, :] = cumsum[:, :, :-1, :] / counts[:, :, :-1, :]

    # L2 distance from running mean
    diff = key_states - running_mean
    surprise = torch.norm(diff, dim=-1)  # [B, H, S]

    # Normalize: zero mean, unit variance per (batch, head)
    surprise = _normalize(surprise)

    return surprise.unsqueeze(2)  # [B, H, 1, S]


def cosine_outlier(key_states: torch.Tensor) -> torch.Tensor:
    """Surprise = angular distance of each key from the causal running mean.

    Scale-invariant alternative: uses cosine distance instead of L2.

    Args:
        key_states: [batch, num_heads, seq_len, head_dim]

    Returns:
        surprise: [batch, num_heads, 1, seq_len]
    """
    batch, heads, seq_len, dim = key_states.shape

    cumsum = torch.cumsum(key_states, dim=2)
    counts = torch.arange(1, seq_len + 1, device=key_states.device, dtype=key_states.dtype)
    counts = counts.view(1, 1, -1, 1)

    running_mean = torch.zeros_like(key_states)
    if seq_len > 1:
        running_mean[:, :, 1:, :] = cumsum[:, :, :-1, :] / counts[:, :, :-1, :]

    # Cosine distance: 1 - cos(key, running_mean)
    cos_sim = F.cosine_similarity(key_states, running_mean, dim=-1)  # [B, H, S]
    surprise = 1.0 - cos_sim

    surprise = _normalize(surprise)
    return surprise.unsqueeze(2)


def local_window_distance(key_states: torch.Tensor, window_size: int = 8) -> torch.Tensor:
    """Surprise = distance of each key from the mean of a local causal window.

    Captures local context deviations rather than global running statistics.

    Args:
        key_states: [batch, num_heads, seq_len, head_dim]
        window_size: number of prior keys to include in the local mean

    Returns:
        surprise: [batch, num_heads, 1, seq_len]
    """
    batch, heads, seq_len, dim = key_states.shape

    surprise = torch.zeros(batch, heads, seq_len, device=key_states.device, dtype=key_states.dtype)

    # Cumulative sum for efficient windowed mean
    cumsum = torch.cumsum(key_states, dim=2)  # [B, H, S, D]

    for i in range(1, seq_len):
        start = max(0, i - window_size)
        if start == 0:
            window_sum = cumsum[:, :, i - 1, :]
        else:
            window_sum = cumsum[:, :, i - 1, :] - cumsum[:, :, start - 1, :]
        window_count = i - start
        local_mean = window_sum / window_count
        diff = key_states[:, :, i, :] - local_mean
        surprise[:, :, i] = torch.norm(diff, dim=-1)

    surprise = _normalize(surprise)
    return surprise.unsqueeze(2)


def key_magnitude_outlier(key_states: torch.Tensor) -> torch.Tensor:
    """Surprise = how much each key's magnitude deviates from the mean magnitude.

    Simplest method. Non-causal (uses full-sequence statistics).

    Args:
        key_states: [batch, num_heads, seq_len, head_dim]

    Returns:
        surprise: [batch, num_heads, 1, seq_len]
    """
    magnitudes = torch.norm(key_states, dim=-1)  # [B, H, S]
    mean_mag = magnitudes.mean(dim=-1, keepdim=True)
    surprise = (magnitudes - mean_mag).abs()

    surprise = _normalize(surprise)
    return surprise.unsqueeze(2)


def _normalize(surprise: torch.Tensor) -> torch.Tensor:
    """Zero-mean, unit-variance normalization along the sequence dimension.

    Args:
        surprise: [batch, num_heads, seq_len]

    Returns:
        normalized: same shape, mean ~0 and std ~1 per (batch, head)
    """
    mean = surprise.mean(dim=-1, keepdim=True)
    std = surprise.std(dim=-1, keepdim=True)
    return (surprise - mean) / (std + 1e-8)


# Registry for easy access by name
SURPRISE_FUNCTIONS = {
    "causal_running_mean": causal_running_mean_distance,
    "cosine_outlier": cosine_outlier,
    "local_window": local_window_distance,
    "key_magnitude": key_magnitude_outlier,
}
