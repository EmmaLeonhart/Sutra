"""D9 — headless demo of the preference-steered generative decoder.

End-to-end pipeline, all on the Sutra substrate render: (1) train a latent-conditioned decoder
on two blob-position targets so the latent controls the generated blob (auto-decoder); (2)
freeze it and steer the latent by a synthetic owner preference (`LatentSteer`); (3) show the
generated frame move with the preference. Run-verifiable (no display); the tkinter window
(`latent_window.py`) is a thin wrapper over the same controller.

    python demos/decoder/latent_demo.py            # train + steer right, print the trajectory
"""
from __future__ import annotations

import importlib.util
import pathlib

import numpy as np

_DIR = pathlib.Path(__file__).resolve().parent


def _load(name, filename):
    spec = importlib.util.spec_from_file_location(name, _DIR / filename)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _centroid_x(img):
    w = np.clip(img, 0.0, None)
    lin = np.linspace(-1, 1, img.shape[1])
    xx = np.tile(lin, (img.shape[0], 1))
    return float((w * xx).sum() / (w.sum() + 1e-9))


def train_generator(size=20, num_freqs=4, latent_dim=4, steps=1000, seed=0):
    """Auto-decoder on two blob-position targets → (substrate_nn, params, z_mid). The latent
    controls the generated blob's x; weights are returned ready to freeze for steering."""
    import torch
    nn = _load("substrate_nn", "substrate_nn.py")
    _d, _c, vsa = nn.dense_layers()
    dt, dev = vsa.dtype, vsa.device

    def blob(cx):
        lin = torch.linspace(-1, 1, size, dtype=dt, device=dev)
        yy, xx = torch.meshgrid(lin, lin, indexing="ij")
        t = torch.exp(-10.0 * ((xx - cx) ** 2 + yy ** 2))
        return (t / t.max()).detach()

    torch.manual_seed(seed)
    params = nn.init_mlp([nn.latent_input_dim(num_freqs, latent_dim), 64, 64, 1], dt, dev, seed=seed)
    zA = torch.empty(latent_dim, dtype=dt, device=dev).normal_(0, 0.5).requires_grad_(True)
    zB = torch.empty(latent_dim, dtype=dt, device=dev).normal_(0, 0.5).requires_grad_(True)
    nn.fit_autodecoder(params, [zA, zB], [blob(-0.4), blob(0.4)], size, num_freqs=num_freqs, steps=steps)
    return nn, params, (0.5 * (zA + zB)).detach(), (size, num_freqs)


def steer_session(prefer="right", rounds=40, seed=0, size=20, num_freqs=4):
    """Train the generator, then steer its latent by `prefer`. Returns (start_cx, final_cx,
    start_img, final_img) — the generated blob's centroid before/after and the frames."""
    nn, params, z_mid, (size, nf) = train_generator(size=size, num_freqs=num_freqs, seed=seed)
    ls = _load("latent_steer", "latent_steer.py")
    st = ls.LatentSteer(params, z_mid, size=size, num_freqs=nf, seed=seed)
    start_img = st.current_image()
    for _ in range(rounds):
        cur, var = st.propose()
        var_more_right = _centroid_x(var) > _centroid_x(cur)
        st.choose(prefer_variant=(var_more_right if prefer == "right" else not var_more_right))
    final_img = st.current_image()
    return _centroid_x(start_img), _centroid_x(final_img), start_img, final_img


def main():
    print("Training the latent-conditioned generator (substrate decoder) ...")
    s, f, _si, _fi = steer_session(prefer="right")
    print(f"Steered the latent by 'prefer rightward': generated blob centroid_x {s:+.3f} -> {f:+.3f}")
    print("The substrate render generated the frame; the reward head + Adam (over the latent) are host-side.")


if __name__ == "__main__":
    main()
