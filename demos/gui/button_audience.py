"""B2 — a SIMULATED audience / CTR model for the trainable-button demo.

`SimulatedAudience.ctr(frame, copy)` maps a rendered button frame (and a discrete copy
choice) to a click probability in [0,1]. It is the synthetic click signal that drives the
training/CI loop (B3) — explicitly *simulated*, NOT real traffic (real clicks arrive only in
the live browser, B4). It is:

  * DETERMINISTIC — a fixed formula, no randomness, so tests are reproducible.
  * DIFFERENTIABLE in the frame — built from torch slicing/means/sigmoid, so B3's Adam can
    ascend CTR THROUGH the differentiable substrate render to θ.

The model is a small, interpretable stand-in for what makes a real button get clicked:

  * SALIENCE — the button stands out from the page (colour contrast between the button
    centre and the page corners). A button that blends into the page gets few clicks.
  * WARM CALL-TO-ACTION colour — warm (red-leaning) CTAs tend to convert better than cold.
  * PUNCHY COPY — action-oriented preset copy ("Buy now") beats passive ("Learn more").

These are deliberately monotonic and few; size/shape preferences are a future refinement
(noted, not modelled here — no overclaim).
"""
from __future__ import annotations

# Preset copy choices (the discrete "copy" axis) and their click weights — punchier copy
# earns a higher weight. Index-aligned with the controller's discrete copy choice (B3).
PRESET_COPY = ["Buy now", "Get started", "Learn more"]
COPY_CLICK_WEIGHT = [0.9, 0.7, 0.4]


class SimulatedAudience:
    """A fixed differentiable click-probability model over a rendered button frame.

    ctr(frame, copy) = σ( w_contrast·contrast + w_warmth·warmth + w_copy·copy_weight − bias ),
    where `contrast` is the mean absolute colour difference between the button centre and the
    page corners, `warmth` is the centre's red-minus-blue (≥0), and `copy_weight` is the
    preset's click weight. The weights are chosen so CTR spans a useful range and salience
    dominates."""

    def __init__(self, w_contrast: float = 4.0, w_warmth: float = 1.5,
                 w_copy: float = 2.0, bias: float = 2.5):
        self.w_contrast = float(w_contrast)
        self.w_warmth = float(w_warmth)
        self.w_copy = float(w_copy)
        self.bias = float(bias)

    @staticmethod
    def _centre_and_corners(frame):
        """Mean colour of the central region (the button) and of the four corner patches
        (the page), both (3,) tensors. Differentiable (slicing + mean)."""
        h, w = frame.shape[0], frame.shape[1]
        centre = frame[h // 3:2 * h // 3, w // 3:2 * w // 3, :].reshape(-1, 3).mean(dim=0)
        k = max(2, h // 6)
        import torch
        corners = torch.cat([
            frame[:k, :k, :].reshape(-1, 3),
            frame[:k, w - k:, :].reshape(-1, 3),
            frame[h - k:, :k, :].reshape(-1, 3),
            frame[h - k:, w - k:, :].reshape(-1, 3),
        ], dim=0).mean(dim=0)
        return centre, corners

    def ctr(self, frame, copy: int = 0):
        """Click probability in [0,1] for `frame` showing preset `copy`. Differentiable in
        `frame`; `copy` selects a (constant) copy weight."""
        import torch
        centre, corners = self._centre_and_corners(frame)
        contrast = (centre - corners).abs().mean()
        warmth = torch.relu(centre[0] - centre[2])
        copy_weight = COPY_CLICK_WEIGHT[int(copy)]
        logit = (self.w_contrast * contrast
                 + self.w_warmth * warmth
                 + self.w_copy * copy_weight
                 - self.bias)
        return torch.sigmoid(logit)
