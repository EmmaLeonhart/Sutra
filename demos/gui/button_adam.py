"""B3 — ButtonAdam: dual-reward steering of the substrate button (owner preference + CTR).

The trainable-button controller. It steers the DIFFERENTIABLE substrate button render (B1)
to maximize a blend of two rewards:

    R(θ, copy) = α · owner_pref(frame) + (1 − α) · CTR(frame, copy)

  * owner_pref — a small differentiable reward head (pooled-linear over the RGB frame),
    trained online from the owner's pairwise warmer/colder choices (Bradley-Terry), exactly
    like the hero steering demo. This is "what the website owner wants".
  * CTR — the simulated audience (B2), a deterministic differentiable click-probability over
    the frame + the discrete copy choice. This is "what gets the biggest CTR".

`α ∈ [0,1]` is the tradeoff knob: 1 = pure owner taste, 0 = pure clicks. Adam ascends R
through the substrate render for the continuous θ (colours, size, position); the discrete
copy is chosen by argmax of R over the preset set each round. The render is the substrate;
the reward head, the audience, and Adam are host-side and named so. Real clicks (B4) would
replace the simulated audience with a learned CTR head on logged clicks; the loop is the
same shape.
"""
from __future__ import annotations

import importlib.util
import pathlib

_DIR = pathlib.Path(__file__).resolve().parent

# Continuous θ axes (name, centre, half-range) → healthy box [centre−hr, centre+hr]. The
# size box keeps the button covering the centre but never the corners (so the audience's
# centre-vs-corner contrast stays well defined); the page stays light; the fill spans the
# full colour cube (incl. pure blue for owner taste and warm red for CTR).
BUTTON_AXES = (
    ("cx",    0.0,  0.4),
    ("cy",    0.0,  0.4),
    ("inv_w", 2.1,  0.9),     # half-width  ∈ ~[0.33, 0.83]
    ("inv_h", 4.25, 1.75),    # half-height ∈ ~[0.17, 0.40]
    ("pr",    0.9,  0.1),     # page colour ∈ [0.8, 1.0] (light)
    ("pg",    0.9,  0.1),
    ("pb",    0.9,  0.1),
    ("fr",    0.5,  0.5),     # fill colour ∈ [0.0, 1.0]
    ("fg",    0.5,  0.5),
    ("fb",    0.5,  0.5),
)


def _load(name, filename):
    spec = importlib.util.spec_from_file_location(name, _DIR / filename)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class OwnerRewardModel:
    """A tiny differentiable reward head R(frame) → scalar logit over an RGB button frame: a
    `pool`×`pool` per-channel average-pool then a learnable linear layer. Small enough to
    learn online from single pairwise comparisons, rich enough to capture a colour/spatial
    taste ('I like a blue button')."""

    def __init__(self, pool: int = 4, dtype=None, device=None):
        import torch
        self.pool = pool
        self.head = torch.nn.Linear(3 * pool * pool, 1)
        torch.nn.init.zeros_(self.head.weight)
        torch.nn.init.zeros_(self.head.bias)
        if dtype is not None or device is not None:
            self.head = self.head.to(dtype=dtype, device=device)

    def parameters(self):
        return self.head.parameters()

    def features(self, img):
        import torch.nn.functional as F
        x = img.permute(2, 0, 1)[None]                       # (1,3,H,W)
        return F.adaptive_avg_pool2d(x, (self.pool, self.pool)).reshape(-1)

    def __call__(self, img):
        return self.head(self.features(img)).reshape(())


class ButtonAdam:
    """Dual-reward (owner preference + CTR) Adam steering controller for the substrate
    button. Interactive flow mirrors the hero demo:

        cur, var = ctl.propose()          # two button frames: current and a variant
        ctl.choose(prefer_variant=True)   # the OWNER prefers the variant (False = current)

    Each `choose` trains the owner head on the pairwise choice, takes a few Adam steps
    ascending the blended reward R through the substrate render, then picks the best preset
    copy by argmax of R. CTR comes from the simulated audience (B2)."""

    def __init__(self, size: int = 48, seed: int = 0, alpha: float = 0.5,
                 lr_theta: float = 0.05, lr_reward: float = 0.3,
                 theta_steps: int = 2, explore: float = 0.12, pool: int = 4,
                 live_ctr: bool = False):
        import torch
        torch.manual_seed(seed)
        self.wf = _load("gui_whole_frame", "whole_frame.py")
        _, vsa = self.wf._compile_button()
        self.dt, self.dev = vsa.dtype, vsa.device
        self.size = int(size)
        self.theta_steps = int(theta_steps)
        self.explore = float(explore)
        self.alpha = float(alpha)
        self.axes = BUTTON_AXES
        self.theta = {name: torch.nn.Parameter(
            torch.tensor(center, dtype=self.dt, device=self.dev))
            for name, center, _hr in self.axes}
        self._bounds = {name: (center - hr, center + hr) for name, center, hr in self.axes}
        _sample = self._render().detach()
        self.img_dt, self.img_dev = _sample.dtype, _sample.device
        self.owner = OwnerRewardModel(pool, dtype=self.img_dt, device=self.img_dev)
        aud = _load("gui_button_audience", "button_audience.py")
        self.audience = aud.SimulatedAudience()
        self.n_copy = len(aud.PRESET_COPY)
        self.copy = 1                                    # start neutral ("Get started")
        self.theta_opt = torch.optim.Adam(list(self.theta.values()), lr=lr_theta)
        self.owner_opt = torch.optim.Adam(list(self.owner.parameters()), lr=lr_reward)
        # Live mode: the CTR term in the reward is a LEARNED head trained from real click
        # preferences (record_click), not the simulated audience. Default off (B3 behaviour).
        self.live_ctr = bool(live_ctr)
        if self.live_ctr:
            self.ctr_head = OwnerRewardModel(pool, dtype=self.img_dt, device=self.img_dev)
            self.ctr_opt = torch.optim.Adam(list(self.ctr_head.parameters()), lr=lr_reward)
        self._gen = torch.Generator(device=self.img_dev).manual_seed(seed + 1)
        self._pending = None

    # --- render (clamped to the displayed [0,1]; differentiable for the policy step) ---
    def _render(self, theta=None):
        th = self.theta if theta is None else theta
        return self.wf.render_button_torch(self.size, th).clamp(0.0, 1.0)

    def current_image(self):
        return self._render().detach().to("cpu").numpy()

    def current_theta(self) -> dict:
        return {k: float(v.detach()) for k, v in self.theta.items()}

    def current_copy(self) -> int:
        return int(self.copy)

    def _ctr_term(self, frame, copy):
        """The CTR reward term: the LEARNED click head in live mode, else the simulated
        audience (B2). Both differentiable in the frame."""
        if self.live_ctr:
            return self.ctr_head(frame)
        return self.audience.ctr(frame, copy)

    def _reward(self, frame, copy):
        return self.alpha * self.owner(frame) + (1.0 - self.alpha) * self._ctr_term(frame, copy)

    def record_click(self, prefer_variant: bool) -> float:
        """Live mode: train the learned CTR head on a click preference (the visitor clicked the
        preferred button) via Bradley-Terry. Does NOT consume the pending pair or step the
        policy — `choose` does the policy step (on the blended reward, which now includes the
        freshly-trained ctr_head). Returns the BT loss."""
        import torch
        import torch.nn.functional as F
        if not self.live_ctr:
            raise RuntimeError("record_click requires live_ctr=True")
        if self._pending is None:
            raise RuntimeError("record_click() called before propose()")
        cur_img, var_img = self._pending
        better, worse = (var_img, cur_img) if prefer_variant else (cur_img, var_img)
        self.ctr_opt.zero_grad()
        bt = -F.logsigmoid(self.ctr_head(better) - self.ctr_head(worse))
        bt.backward()
        self.ctr_opt.step()
        return float(bt.detach())

    def ctr_now(self) -> float:
        import torch
        with torch.no_grad():
            return float(self.audience.ctr(self._render(), self.copy).detach())

    def _clamp_theta(self):
        import torch
        with torch.no_grad():
            for name, p in self.theta.items():
                lo, hi = self._bounds[name]
                p.clamp_(lo, hi)

    # --- interactive pairwise step ---
    def propose(self):
        """Render the current θ and a perturbed variant θ′; return `(current, variant)` numpy
        frames for the owner to compare; stash the (detached) renders for `choose`."""
        import torch
        with torch.no_grad():
            saved = {k: v.clone() for k, v in self.theta.items()}
            for name, p in self.theta.items():
                lo, hi = self._bounds[name]
                p.add_(self.explore * torch.randn((), generator=self._gen,
                                                  dtype=self.dt, device=self.img_dev))
                p.clamp_(lo, hi)
            var_theta = {k: float(v.detach()) for k, v in self.theta.items()}
            var_img = self._render().detach()
            var_np = var_img.to("cpu").numpy()
            for k, p in self.theta.items():
                p.copy_(saved[k])
            cur_theta = {k: float(v.detach()) for k, v in self.theta.items()}
            cur_img = self._render().detach()
            cur_np = cur_img.to("cpu").numpy()
        self._pending = (cur_img, var_img)
        self._pending_thetas = (cur_theta, var_theta)
        return cur_np, var_np

    def pending_thetas(self):
        """The (current θ, variant θ) dicts from the last `propose()` — what a live HTML
        button styles its current / proposed pair from (B4). None before the first propose."""
        return getattr(self, "_pending_thetas", None)

    def choose(self, prefer_variant: bool) -> float:
        """Record the owner's pairwise preference, train the owner head (Bradley-Terry), take
        the blended-reward Adam policy steps through the substrate render, then pick the best
        preset copy by argmax of the blended reward. Returns the owner-head BT loss."""
        import torch
        import torch.nn.functional as F
        if self._pending is None:
            raise RuntimeError("choose() called before propose()")
        cur_img, var_img = self._pending
        better, worse = (var_img, cur_img) if prefer_variant else (cur_img, var_img)

        # 1) OWNER UPDATE — Bradley-Terry on the owner's preference pair.
        self.owner_opt.zero_grad()
        bt = -F.logsigmoid(self.owner(better) - self.owner(worse))
        bt.backward()
        self.owner_opt.step()

        # 2) POLICY UPDATE — Adam ascends the BLENDED reward THROUGH the substrate render.
        for _ in range(self.theta_steps):
            self.theta_opt.zero_grad()
            self.owner_opt.zero_grad()
            loss = -self._reward(self._render(), self.copy)
            loss.backward()
            self.theta_opt.step()
            self._clamp_theta()

        # 3) DISCRETE COPY — argmax of the blended reward over the preset set. Only in sim
        # mode: the simulated audience scores copy (copy_weight), so the argmax has signal. In
        # live mode the learned head reads only the frame (copy is not rendered), so there is
        # no copy signal — copy stays put (copy-from-clicks would need a separate discrete
        # bandit over click stats; noted follow-on).
        if not self.live_ctr:
            with torch.no_grad():
                frame = self._render()
                rewards = [float(self._reward(frame, c).detach()) for c in range(self.n_copy)]
                self.copy = int(max(range(self.n_copy), key=lambda c: rewards[c]))
        self._pending = None
        return float(bt.detach())
