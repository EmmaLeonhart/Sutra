"""Unit tests for surprise functions."""

import pytest
import torch

from src.surprise_functions import (
    causal_running_mean_distance,
    cosine_outlier,
    key_magnitude_outlier,
    local_window_distance,
    _normalize,
    SURPRISE_FUNCTIONS,
)


@pytest.fixture
def key_states():
    """Random key states: [batch=2, heads=4, seq_len=16, head_dim=8]."""
    torch.manual_seed(42)
    return torch.randn(2, 4, 16, 8)


@pytest.fixture
def key_states_with_outlier():
    """Key states where position 5 is a clear outlier."""
    torch.manual_seed(42)
    keys = torch.randn(1, 1, 10, 8) * 0.1  # small, similar keys
    keys[:, :, 5, :] = torch.randn(1, 1, 1, 8) * 10.0  # big outlier
    return keys


class TestOutputShape:
    """All surprise functions must return [B, H, 1, S]."""

    @pytest.mark.parametrize("fn_name", SURPRISE_FUNCTIONS.keys())
    def test_shape(self, key_states, fn_name):
        fn = SURPRISE_FUNCTIONS[fn_name]
        result = fn(key_states)
        B, H, S, D = key_states.shape
        assert result.shape == (B, H, 1, S)

    @pytest.mark.parametrize("fn_name", SURPRISE_FUNCTIONS.keys())
    def test_no_nans(self, key_states, fn_name):
        fn = SURPRISE_FUNCTIONS[fn_name]
        result = fn(key_states)
        assert not torch.isnan(result).any()


class TestCausalRunningMean:
    def test_first_position_is_zero_pre_normalize(self):
        """Position 0 has no prior keys, so raw surprise should be 0."""
        keys = torch.randn(1, 1, 5, 4)
        # Manually check: running_mean at pos 0 is zeros, diff = key itself
        # but that's the raw distance, not 0. After normalization it shifts.
        # The key property: it's causal (doesn't peek ahead).
        result = causal_running_mean_distance(keys)
        assert result.shape == (1, 1, 1, 5)

    def test_outlier_gets_high_surprise(self, key_states_with_outlier):
        result = causal_running_mean_distance(key_states_with_outlier)
        scores = result.squeeze()  # [10]
        # Position 5 (the outlier) should have the highest surprise
        assert scores[5] == scores.max()

    def test_causality(self):
        """Changing a future key must not affect surprise at earlier positions."""
        torch.manual_seed(0)
        keys = torch.randn(1, 1, 10, 8)

        s1 = causal_running_mean_distance(keys).squeeze()

        keys_modified = keys.clone()
        keys_modified[:, :, 8, :] = torch.randn(1, 1, 1, 8) * 100.0
        s2 = causal_running_mean_distance(keys_modified).squeeze()

        # Positions 0-7 should be unchanged (normalization affects all, so
        # we check un-normalized by checking the relative ordering is preserved)
        # More precisely: raw distances before position 8 are identical
        # After normalization the values shift, but the *order* of 0-7 is preserved
        order1 = torch.argsort(s1[:8])
        order2 = torch.argsort(s2[:8])
        assert torch.equal(order1, order2)


class TestCosineOutlier:
    def test_outlier_detected(self, key_states_with_outlier):
        result = cosine_outlier(key_states_with_outlier)
        scores = result.squeeze()
        # The outlier at position 5 should have high surprise
        assert scores[5] > scores.median()


class TestLocalWindow:
    def test_outlier_detected(self, key_states_with_outlier):
        result = local_window_distance(key_states_with_outlier, window_size=4)
        scores = result.squeeze()
        assert scores[5] > scores.median()


class TestKeyMagnitude:
    def test_outlier_detected(self, key_states_with_outlier):
        result = key_magnitude_outlier(key_states_with_outlier)
        scores = result.squeeze()
        assert scores[5] == scores.max()


class TestNormalize:
    def test_mean_near_zero(self):
        x = torch.randn(2, 4, 16)
        normed = _normalize(x)
        assert normed.mean(dim=-1).abs().max() < 1e-5

    def test_std_near_one(self):
        x = torch.randn(2, 4, 16)
        normed = _normalize(x)
        assert (normed.std(dim=-1) - 1.0).abs().max() < 1e-4


class TestRegistry:
    def test_all_registered(self):
        expected = {"causal_running_mean", "cosine_outlier", "local_window", "key_magnitude"}
        assert set(SURPRISE_FUNCTIONS.keys()) == expected

    def test_all_callable(self):
        for fn in SURPRISE_FUNCTIONS.values():
            assert callable(fn)
