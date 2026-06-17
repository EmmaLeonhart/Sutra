"""D8 — steer a trained generative decoder's LATENT by preference.

The convergence of the two tracks: the learned latent-conditioned decoder (D7) + the
ButtonAdam-style preference loop. The decoder weights are FROZEN; the steered parameter is the
latent `z`. Each round proposes the current generated frame and a perturbed-latent variant; a
person's (here synthetic) pairwise preference trains a small reward head, and Adam ascends that
reward by moving `z` THROUGH the differentiable substrate decoder render — so a person's
preferences drive WHAT THE GENERATIVE DECODER PRODUCES.

The decoder render is the substrate (matmul + hadamard cubic); the reward head and Adam are
host-side and named — the same split as the hero/button steering, now over a learned generator.
"""
from __future__ import annotations

import importlib.util
import pathlib

_DIR = pathlib.Path(__file__).resolve().parent


def _nn():
    spec = importlib.util.spec_from_file_location("substrate_nn", _DIR / "substrate_nn.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class _RewardHead:
    """A tiny differentiable reward R(frame) → scalar: pool×pool average-pool of the frame then
    a learnable linear layer (the HeroRewardModel/OwnerRewardModel pattern, mono frame)."""

    def __init__(self, pool=4, dtype=None, device=None):
        import torch
        self.pool = pool
        self.head = torch.nn.Linear(pool * pool, 1)
        torch.nn.init.zeros_(self.head.weight)
        torch.nn.init.zeros_(self.head.bias)
        if dtype is not None or device is not None:
            self.head = self.head.to(dtype=dtype, device=device)

    def parameters(self):
        return self.head.parameters()

    def __call__(self, img):
        import torch.nn.functional as F
        x = img[None, None]
        feats = F.adaptive_avg_pool2d(x, (self.pool, self.pool)).reshape(-1)
        return self.head(feats).reshape(())


class LatentSteer:
    """Steer a trained generative decoder's latent `z` by pairwise preference. `params` are the
    FROZEN decoder weights; `z0` the starting latent. `propose()` returns (current, variant)
    frames; `choose(prefer_variant)` trains the reward head on the pair and Adam-steps `z`
    up the reward, through the substrate decoder render."""

    def __init__(self, params, z0, size=20, num_freqs=4, lr_z=0.05, lr_reward=0.3,
                 z_steps=3, explore=0.4, pool=4, seed=0):
        import torch
        self.nn = _nn()
        self.size, self.nf = int(size), int(num_freqs)
        self.z_steps, self.explore = int(z_steps), float(explore)
        # Freeze the decoder weights; only the latent is trainable.
        self.params = [(W.detach(), b.detach()) for W, b in params]
        self.dt, self.dev = self.params[0][0].dtype, self.params[0][0].device
        self.z = z0.detach().clone().to(self.dt).requires_grad_(True)
        _sample = self._render().detach()
        self.reward = _RewardHead(pool, dtype=_sample.dtype, device=_sample.device)
        self.z_opt = torch.optim.Adam([self.z], lr=lr_z)
        self.reward_opt = torch.optim.Adam(list(self.reward.parameters()), lr=lr_reward)
        self._gen = torch.Generator(device=self.dev).manual_seed(seed + 1)
        self._pending = None

    def _render(self, z=None):
        z = self.z if z is None else z
        return self.nn.render_decoder_latent_torch(self.params, z, self.size, self.nf).clamp(0.0, 1.0)

    def current_image(self):
        return self._render().detach().to("cpu").numpy()

    def current_z(self):
        return self.z.detach().to("cpu").numpy()

    def propose(self):
        import torch
        with torch.no_grad():
            saved = self.z.clone()
            self.z.add_(self.explore * torch.randn(self.z.shape, generator=self._gen,
                                                   dtype=self.dt, device=self.dev))
            var = self._render().detach()
            self.z.copy_(saved)
            cur = self._render().detach()
        self._pending = (cur, var)
        return cur.to("cpu").numpy(), var.to("cpu").numpy()

    def choose(self, prefer_variant: bool) -> float:
        """Train the reward head on the pairwise choice (Bradley-Terry), then ascend the reward
        by moving the latent through the substrate decoder render."""
        import torch
        import torch.nn.functional as F
        if self._pending is None:
            raise RuntimeError("choose() before propose()")
        cur, var = self._pending
        better, worse = (var, cur) if prefer_variant else (cur, var)
        self.reward_opt.zero_grad()
        bt = -F.logsigmoid(self.reward(better) - self.reward(worse))
        bt.backward()
        self.reward_opt.step()
        for _ in range(self.z_steps):
            self.z_opt.zero_grad()
            self.reward_opt.zero_grad()
            loss = -self.reward(self._render())
            loss.backward()
            self.z_opt.step()
        self._pending = None
        return float(bt.detach())
