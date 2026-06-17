"""D11 — emit a trained decoder as Sutra CODE (weight→code).

The learned decoder (D1–D8) trains its weights by autograd through the compiled substrate
forward. This module emits that forward as a STANDALONE Sutra (`.su`) program over `matrix`
weight parameters + `Tensor.MatrixMul` + `hadamard` (the cubic activation), connecting the
trained decoder to Sutra's weight↔code infrastructure (`experiments/weight_to_code_corpus.py`:
file-backed matrices, `Tensor.MatrixMul`). The *code* is the emitted `.su` (architecture); the
*weights* are the trained matrices/biases (torch tensors, file-backable as CSVs). Running the
emitted program with the trained weights reproduces the decoder — "every op trainable" meets
"compile the weights to code."

This is the atomic, verified step: emit the forward, confirm it equals the trained decoder's
host forward. Folding weights into CSVs (the corpus's `load_matrix`) and emitting the
Fourier-encoding too are the documented follow-ons (see planning/findings).
"""
from __future__ import annotations

import pathlib

_DIR = pathlib.Path(__file__).resolve().parent

_HELPERS = """\
// Emitted by emit_decoder.py (learned-decoder D11, weight->code). The decoder FORWARD as a
// standalone Sutra program over `matrix` weight params; the trained weights are supplied at
// call (file-backable as CSVs, the weight_to_code_corpus pattern). Activation = cubic via
// hadamard (the substrate's tanh/sin are canonical-only — D1 finding).
function vector layer_cube(matrix W, vector x, vector b) {
    vector h = Tensor.MatrixMul(W, x) + b;
    return hadamard(hadamard(h, h), h);
}
function vector layer_lin(matrix W, vector x, vector b) {
    return Tensor.MatrixMul(W, x) + b;
}
"""


def decoder_su_source(n_weight_layers: int) -> str:
    """Emit the `.su` source for a decoder with `n_weight_layers` Linear layers (the first
    n-1 cubic-activated, the last linear). Params: W0,b0,…,W{n-1},b{n-1}, then the input x."""
    if n_weight_layers < 1:
        raise ValueError("need at least one weight layer")
    params = ", ".join(f"matrix W{i}, vector b{i}" for i in range(n_weight_layers)) + ", vector x"
    expr = "x"
    for i in range(n_weight_layers - 1):
        expr = f"layer_cube(W{i}, {expr}, b{i})"
    last = n_weight_layers - 1
    expr = f"layer_lin(W{last}, {expr}, b{last})"
    return (
        _HELPERS
        + f"\nfunction vector decoder({params}) {{\n    return {expr};\n}}\n"
        + '\nfunction vector main() { return tanh(make_real(1.0)); }\n'
    )


def write_decoder_su(n_weight_layers: int, path: pathlib.Path | None = None) -> pathlib.Path:
    """Write the emitted decoder `.su` and return its path."""
    path = path or (_DIR / "decoder_emitted.su")
    path.write_text(decoder_su_source(n_weight_layers), encoding="utf-8")
    return path


def compile_decoder_su(path: pathlib.Path):
    """Compile an emitted decoder `.su` → its `decoder` function + the _VSA runtime."""
    import sys
    sdk = _DIR.parent.parent / "sdk" / "sutra-compiler"
    if str(sdk) not in sys.path:
        sys.path.insert(0, str(sdk))
    from sutra_compiler import compile_su
    mod = compile_su(path, llm_model="unused-no-basis-vectors", runtime_dim=8, verbose=False)
    return mod.decoder


def run_emitted(decoder_fn, params, X):
    """Run the emitted decoder with trained `params` ([(W,b),…]) on input `X` (in, N) →
    (out, N). Flattens params into the decoder's positional matrix/bias args."""
    args = []
    for W, b in params:
        args.append(W)
        args.append(b)
    args.append(X)
    return decoder_fn(*args)
