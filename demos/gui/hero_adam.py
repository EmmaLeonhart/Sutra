"""Adam steering of the substrate-rendered hero via an ONLINE LEARNED REWARD MODEL
(GUI rebuild R2 + R3 — replaces the host-side black-box SPSA of hero_spsa.py).

This is the real-time-RL demo Sutra is meant to show off: a pixel image generated
ENTIRELY by the Sutra substrate (`frame_hero.su` via `whole_frame.render_hero_torch`),
steered by a person's WARMER / COLDER preferences, where the learning is GRADIENT-BASED
and flows THROUGH the differentiable substrate render — not a zeroth-order black box.

The loop is online RLHF with **pairwise preferences** (the Bradley-Terry formulation
real reward models use — contrastive by construction, so it is stable in any preference
direction, unlike single-frame thumbs up/down):

  1. **Propose.** Render the current θ and a slightly perturbed variant θ′ — two frames.
  2. **Prefer.** The person says which they like better (WARMER = prefer the variant,
     COLDER = prefer the current). One Bradley-Terry step trains a small differentiable
     reward head R(image): `loss = −log σ(R(preferred) − R(rejected))`.
  3. **Policy.** A few Adam steps ASCEND R(render(θ)) — backprop through the reward head
     AND the compiled Sutra render (R1 proved θ.grad flows through the substrate) — then
     clamp θ into the render's healthy box. The image morphs toward what the person likes.

The substrate is the renderer; the reward head and the optimizers are host-side (named so,
per the integrity rails). Every gradient here is real autograd through the substrate render.
"""
from __future__ import annotations

import pathlib

_DIR = pathlib.Path(__file__).resolve().parent

# θ axes the mono differentiable render (`render_hero_torch` → frame_hero.su `hero`)
# actually consumes, with the healthy render box (center, half_range) → [c−h, c+h].
# Color tints (cr/cg/cb) act only on the RGB render, so they are not axes of the mono demo.
HERO_ADAM_AXES = (
    ("cx",     0.0, 0.8),    # glow centre x   ∈ [-0.8, 0.8]
    ("cy",     0.0, 0.8),    # glow centre y   ∈ [-0.8, 0.8]
    ("invs",   1.3, 1.2),    # glow spread     ∈ [ 0.1, 2.5]
    ("bright", 1.0, 0.8),    # glow brightness ∈ [ 0.2, 1.8]
    ("radius", 0.5, 0.4),    # ring radius     ∈ [ 0.1, 0.9]
    ("accent", 0.3, 0.3),    # ring brightness ∈ [ 0.0, 0.6]
    ("bg",     0.1, 0.3),    # background      ∈ [-0.2, 0.4]
)

# Per-channel colour tints — the COLOUR axes of the RGB render (`color=True`). Each tint
# multiplies its own channel on the substrate (R←cr, G←cg, B←cb), so the box bottoms at 0
# (channel off) and tops near 2× the warm-white default. Only used in colour mode.
HERO_ADAM_COLOR_AXES = (
    ("cr", 1.0,  1.0),       # red   tint ∈ [0.0, 2.0]
    ("cg", 0.85, 0.85),      # green tint ∈ [0.0, 1.7]
    ("cb", 0.6,  0.6),       # blue  tint ∈ [0.0, 1.2]
)


def _load_whole_frame():
    import importlib.util
    spec = importlib.util.spec_from_file_location("gui_whole_frame", _DIR / "whole_frame.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class HeroRewardModel:
    """A tiny differentiable reward head R(image) → scalar logit. Features are a fixed
    `pool`×`pool` average-pool of the frame (interpretable spatial cells), then a learnable
    linear layer — small enough to learn online from single comparisons, rich enough to
    capture spatial/brightness preferences ('I like a bright top-left')."""

    def __init__(self, pool: int = 4, channels: int = 1, dtype=None, device=None):
        import torch
        self.pool = pool
        self.channels = int(channels)
        self.head = torch.nn.Linear(self.channels * pool * pool, 1)
        torch.nn.init.zeros_(self.head.weight)
        torch.nn.init.zeros_(self.head.bias)
        if dtype is not None or device is not None:
            self.head = self.head.to(dtype=dtype, device=device)

    def parameters(self):
        return self.head.parameters()

    def features(self, img):
        import torch.nn.functional as F
        if img.dim() == 3 and img.shape[-1] == 3:            # (H,W,3) colour frame
            x = img.permute(2, 0, 1)[None]                   # (1,3,H,W)
        else:
            x = img[None, None]                              # (1,1,H,W) mono frame
        return F.adaptive_avg_pool2d(x, (self.pool, self.pool)).reshape(-1)

    def __call__(self, img):
        return self.head(self.features(img)).reshape(())


class HeroAdam:
    """Online-RLHF (pairwise) Adam steering controller. Interactive flow:

        cur_np, var_np = ctl.propose()   # two frames to show: current and a variant
        ctl.choose(prefer_variant=True)  # WARMER: like the variant more  (COLDER: False)

    or the one-call convenience `ctl.press(+1)` / `ctl.press(-1)`. The live window paints
    the pair and maps the buttons; tests drive it with a synthetic rater."""

    def __init__(self, size: int = 48, seed: int = 0,
                 lr_theta: float = 0.06, lr_reward: float = 0.3,
                 theta_steps: int = 2, explore: float = 0.15, pool: int = 4,
                 color: bool = False):
        import torch
        torch.manual_seed(seed)
        self.wf = _load_whole_frame()
        _, vsa = self.wf._compile_hero()
        self.dt, self.dev = vsa.dtype, vsa.device
        self.size = int(size)
        self.theta_steps = int(theta_steps)
        self.explore = float(explore)
        # Colour mode adds the per-channel tints (cr/cg/cb) as steerable axes and renders
        # the differentiable 3-channel frame; mono mode keeps the original 7 axes.
        self.color = bool(color)
        self.axes = HERO_ADAM_AXES + (HERO_ADAM_COLOR_AXES if self.color else ())
        self.theta = {name: torch.nn.Parameter(
            torch.tensor(center, dtype=self.dt, device=self.dev))
            for name, center, _hr in self.axes}
        self._bounds = {name: (center - hr, center + hr)
                        for name, center, hr in self.axes}
        _sample = self._render().detach()
        self.img_dt, self.img_dev = _sample.dtype, _sample.device
        self.reward = HeroRewardModel(pool, channels=(3 if self.color else 1),
                                      dtype=self.img_dt, device=self.img_dev)
        self.theta_opt = torch.optim.Adam(list(self.theta.values()), lr=lr_theta)
        self.reward_opt = torch.optim.Adam(list(self.reward.parameters()), lr=lr_reward)
        self._gen = torch.Generator(device=self.img_dev).manual_seed(seed + 1)
        self._pending = None     # (img_current, img_variant) detached, from propose()

    # --- render (clamped to the displayed [0,1]; differentiable for the policy step) ---
    def _render(self, theta=None):
        # Clamp to the displayed range — the reward head and the rater react to what is
        # SHOWN, not the raw field (whose ring/bg terms can run outside [0,1]). The clamp
        # is differentiable (grad passes through in-range pixels), so Adam still steers.
        th = self.theta if theta is None else theta
        if self.color:
            return self.wf.render_hero_rgb_torch(self.size, th).clamp(0.0, 1.0)
        return self.wf.render_hero_torch(self.size, th).clamp(0.0, 1.0)

    def current_image(self):
        return self._render().detach().to("cpu").numpy()

    def current_theta(self) -> dict:
        return {k: float(v.detach()) for k, v in self.theta.items()}

    def _clamp_theta(self):
        import torch
        with torch.no_grad():
            for name, p in self.theta.items():
                lo, hi = self._bounds[name]
                p.clamp_(lo, hi)

    # --- the pairwise online-RLHF step, split for interactive scoring ---
    def propose(self):
        """Render the current θ and a perturbed variant θ′ (θ + small exploration noise,
        clamped into the box). Returns `(current_img, variant_img)` numpy frames to show;
        stashes the two (detached) renders for `choose`."""
        import torch
        with torch.no_grad():
            saved = {k: v.clone() for k, v in self.theta.items()}
            for name, p in self.theta.items():
                lo, hi = self._bounds[name]
                p.add_(self.explore * torch.randn((), generator=self._gen,
                                                  dtype=self.dt, device=self.img_dev))
                p.clamp_(lo, hi)
            var_img = self._render().detach()
            var_np = var_img.to("cpu").numpy()
            for k, p in self.theta.items():
                p.copy_(saved[k])
            cur_img = self._render().detach()
            cur_np = cur_img.to("cpu").numpy()
        self._pending = (cur_img, var_img)
        return cur_np, var_np

    def choose(self, prefer_variant: bool) -> float:
        """Record the pairwise preference for the last `propose()` pair and take the
        learning + policy steps. Returns the Bradley-Terry reward loss (host-side scalar)."""
        import torch
        import torch.nn.functional as F
        if self._pending is None:
            raise RuntimeError("choose() called before propose()")
        cur_img, var_img = self._pending
        better, worse = (var_img, cur_img) if prefer_variant else (cur_img, var_img)

        # 1) REWARD UPDATE — Bradley-Terry on the preference pair.
        self.reward_opt.zero_grad()
        bt = -F.logsigmoid(self.reward(better) - self.reward(worse))
        bt.backward()
        self.reward_opt.step()

        # 2) POLICY UPDATE — Adam ascends R(render(θ)) THROUGH the substrate render.
        for _ in range(self.theta_steps):
            self.theta_opt.zero_grad()
            self.reward_opt.zero_grad()        # keep reward grads from accumulating
            loss_t = -self.reward(self._render())
            loss_t.backward()
            self.theta_opt.step()
            self._clamp_theta()
        self._pending = None
        return float(bt.detach())

    def press(self, sign: int) -> float:
        """Convenience: `propose()` (if needed) then `choose`. `sign` > 0 = WARMER (prefer
        the variant), < 0 = COLDER (prefer the current)."""
        if self._pending is None:
            self.propose()
        return self.choose(prefer_variant=(sign > 0))
