"""D11 — the emitted decoder Sutra program reproduces the trained decoder (weight→code).

Trains a small substrate decoder, EMITS its forward as a standalone `.su` (matrix params +
Tensor.MatrixMul + hadamard cubic), compiles it, runs it with the trained weights, and checks
it matches the host decoder forward to float tolerance — i.e. the trained decoder is now
standalone Sutra CODE (+ weight tensors, file-backable as CSVs). Connects the learned decoder
to Sutra's weight↔code infrastructure.
"""
from __future__ import annotations

import importlib.util
import pathlib

import pytest

_DIR = pathlib.Path(__file__).resolve().parent


def _load(name, filename):
    spec = importlib.util.spec_from_file_location(name, _DIR / filename)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_emitted_su_compiles_and_matches_trained_decoder():
    import torch
    pytest.importorskip("torch")
    nn = _load("substrate_nn", "substrate_nn.py")
    emit = _load("emit_decoder", "emit_decoder.py")
    _d, _c, vsa = nn.dense_layers()
    dt, dev = vsa.dtype, vsa.device

    # A small trained decoder: [F, 16, 16, 1] = 3 weight layers (2 cubic + 1 linear).
    nf = 3
    fin = nn.decoder_input_dim(nf)
    sizes = [fin, 16, 16, 1]
    params = nn.init_mlp(sizes, dt, dev, seed=0)
    # (a few steps so weights are non-trivial; exact reconstruction quality is D4's job)
    size = 12
    lin = torch.linspace(-1, 1, size, dtype=dt, device=dev)
    yy, xx = torch.meshgrid(lin, lin, indexing="ij")
    target = torch.exp(-6.0 * (xx ** 2 + yy ** 2)).detach()
    nn.fit_decoder(params, target, size, num_freqs=nf, steps=50, lr=0.01)

    # Emit the forward as a standalone .su and compile it.
    n_layers = len(sizes) - 1
    su_path = emit.write_decoder_su(n_layers)
    decoder_fn = emit.compile_decoder_su(su_path)

    # Run the emitted program vs the host forward on the same Fourier-encoded grid.
    coords = nn.coord_grid(size, dt, dev)
    X = nn.fourier_features(coords, nf).to(dt).T.contiguous()        # (F, N²)
    emitted = emit.run_emitted(decoder_fn, params, X)
    emitted = emitted.real if emitted.is_complex() else emitted
    host = nn.mlp_forward(params, X)

    max_abs = float((emitted - host).abs().max().detach())
    assert max_abs < 1e-4, f"emitted .su decoder != trained host forward: max abs diff {max_abs:.2e}"


def test_decoder_su_source_shapes_to_layer_count():
    emit = _load("emit_decoder", "emit_decoder.py")
    src = emit.decoder_su_source(3)
    assert "function vector decoder(matrix W0" in src and "matrix W2" in src
    assert "Tensor.MatrixMul" in src and "hadamard" in src
    # last layer linear (no cube wrapping the final MatrixMul)
    assert "layer_lin(W2" in src
