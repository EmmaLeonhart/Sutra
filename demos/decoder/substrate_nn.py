"""Substrate neural-net building blocks for the learned decoder (D1+).

Compiles the trainable substrate layers (`dense.su`) and exposes them as differentiable torch
callables: a `dense`/`dense_tanh` layer whose weights are trained by a host optimizer via
autograd THROUGH the compiled substrate `matmul`. The forward pass is the substrate; the
optimizer is host-side (named so). The learned coordinate-MLP decoder (D3) stacks these.
"""
from __future__ import annotations

import pathlib
import sys

_DIR = pathlib.Path(__file__).resolve().parent
_REPO_ROOT = _DIR.parent.parent
_SUTRA_SDK = _REPO_ROOT / "sdk" / "sutra-compiler"
if str(_SUTRA_SDK) not in sys.path:
    sys.path.insert(0, str(_SUTRA_SDK))

_CACHE = {}


def compile_dense():
    """Compile dense.su once and cache it. Returns the compiled module (mod.dense,
    mod.dense_tanh, mod._VSA)."""
    if "dense" not in _CACHE:
        from sutra_compiler import compile_su
        _CACHE["dense"] = compile_su(_DIR / "dense.su",
                                     llm_model="unused-no-basis-vectors", runtime_dim=8,
                                     verbose=False)
    return _CACHE["dense"]


def dense_layers():
    """Return (dense, dense_cube, _VSA): the substrate Linear layer, its cubic-activated
    variant, and the runtime (for dtype/device). `dense(W, x, b) = matmul(W, x) + b` with the
    autograd graph intact, so `W,b` are trainable by a host optimizer. `dense_cube` applies an
    elementwise cubic (hadamard) nonlinearity — the substrate's tanh/sin are canonical-vector
    ops, not elementwise over activation buffers (D1 finding)."""
    mod = compile_dense()
    return mod.dense, mod.dense_cube, mod._VSA
