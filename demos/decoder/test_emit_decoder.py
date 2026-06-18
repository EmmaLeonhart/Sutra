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


def test_baked_su_is_standalone_and_reproduces_trained_decoder(tmp_path):
    """Bake the trained weights to CSV + emit a STANDALONE .su that loads its own weights; run
    it with NO host weight tensors (only the input) and confirm it reproduces the trained
    decoder forward — the trained decoder as fully self-contained Sutra code + data."""
    import torch
    pytest.importorskip("torch")
    nn = _load("substrate_nn", "substrate_nn.py")
    emit = _load("emit_decoder", "emit_decoder.py")
    _d, _c, vsa = nn.dense_layers()
    dt, dev = vsa.dtype, vsa.device

    nf = 3
    params = nn.init_mlp([nn.decoder_input_dim(nf), 16, 16, 1], dt, dev, seed=0)
    size = 12
    lin = torch.linspace(-1, 1, size, dtype=dt, device=dev)
    yy, xx = torch.meshgrid(lin, lin, indexing="ij")
    target = torch.exp(-6.0 * (xx ** 2 + yy ** 2)).detach()
    nn.fit_decoder(params, target, size, num_freqs=nf, steps=50, lr=0.01)

    su_path = emit.bake_decoder(params, tmp_path)          # writes CSVs + decoder_baked.su
    baked_fn = emit.compile_baked(su_path)

    coords = nn.coord_grid(size, dt, dev)
    X = nn.fourier_features(coords, nf).to(dt).T.contiguous()
    baked = baked_fn(X)                                    # NO weights passed — loaded from CSV
    baked = baked.real if baked.is_complex() else baked
    host = nn.mlp_forward(params, X)

    max_abs = float((baked - host).abs().max().detach())
    assert max_abs < 1e-4, f"standalone baked decoder != trained host forward: {max_abs:.2e}"
    src = su_path.read_text(encoding="utf-8")
    assert src.count("load_matrix(") == 2 * len(params), "not every weight is file-backed"


def test_decoder_su_source_shapes_to_layer_count():
    emit = _load("emit_decoder", "emit_decoder.py")
    src = emit.decoder_su_source(3)
    assert "function vector decoder(matrix W0" in src and "matrix W2" in src
    assert "Tensor.MatrixMul" in src and "hadamard" in src
    # last layer linear (no cube wrapping the final MatrixMul)
    assert "layer_lin(W2" in src


def test_baked_decoder_runs_the_fourier_encoding_on_the_substrate(tmp_path):
    """w2c follow-on #2 (unblocked by sin_buf): bake a decoder so the emitted standalone `.su`
    takes RAW (x,y) coordinates and runs the Fourier ENCODING on the substrate (sin_buf/cos_buf)
    as well as the decode — a fully self-contained coords→pixels Sutra program.

    Faithfulness reference = the SAME substrate computation via the python callables
    (`fourier_features_substrate` + `mlp_forward`): the baked `.su` must reproduce THAT to <1e-4,
    proving the W0-column-fold + CSV-weight bake is exact. (Against the exact-`torch.sin` host
    render the gap is larger — ~0.05 — because `sin_buf` is a table readout whose ~8e-5 error is
    amplified by the two cubic layers; that is a documented property of the encoding, separately
    tested in test_encoding.py, NOT a bake defect. The bake's job is to reproduce the substrate
    computation faithfully, which it does.)"""
    import torch
    pytest.importorskip("torch")
    nn = _load("substrate_nn", "substrate_nn.py")
    emit = _load("emit_decoder", "emit_decoder.py")
    _d, _c, vsa = nn.dense_layers()
    dt, dev = vsa.dtype, vsa.device

    nf = 4
    params = nn.init_mlp([nn.decoder_input_dim(nf), 16, 16, 1], dt, dev, seed=0)
    size = 12
    lin = torch.linspace(-1, 1, size, dtype=dt, device=dev)
    yy, xx = torch.meshgrid(lin, lin, indexing="ij")
    target = torch.exp(-6.0 * (xx ** 2 + yy ** 2)).detach()
    nn.fit_decoder(params, target, size, num_freqs=nf, steps=50, lr=0.01)

    su_path = emit.bake_decoder_with_encoding(params, nf, tmp_path, coord_dim=2, name="dec_enc")
    fn = emit.compile_baked(su_path, name="dec_enc")

    coords = nn.coord_grid(size, dt, dev)                         # (N², 2)
    baked = fn(coords.T.contiguous()).reshape(size, size)         # RAW coords in; NO host encoding
    baked = baked.real if baked.is_complex() else baked

    # reference: identical substrate computation (substrate encoding + decode) via python
    sub_feats = nn.fourier_features_substrate(coords, nf).to(dt)
    ref = nn.mlp_forward(params, sub_feats.T.contiguous()).reshape(size, size)

    max_abs = float((baked.detach() - ref.detach()).abs().max())
    assert max_abs < 1e-4, f"baked coords->pixels .su != substrate-encoding reference: {max_abs:.2e}"

    # the emitted .su really runs sin/cos on the substrate and loads only its own weights.
    src = su_path.read_text(encoding="utf-8")
    assert "sin_buf(" in src and "cos_buf(" in src, "encoding not emitted as substrate sin_buf/cos_buf"
    assert "function matrix dec_enc(matrix coords)" in src, "baked fn does not take raw coords"
    assert "load_matrix(" in src, "weights not file-backed"
