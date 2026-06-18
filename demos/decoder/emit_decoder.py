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


# --- D12: bake the trained weights to CSV → a FULLY STANDALONE emitted .su ---
#
# The emitted program declares all its weights via `load_matrix("…csv")` (the
# weight_to_code_corpus file-backed-weight pattern), so it needs no host-supplied tensors —
# just the input. All-`matrix` typed (bias as (out,1), broadcast-added; cubic via hadamard).

_BAKED_HELPERS = """\
// Emitted by emit_decoder.bake_decoder (learned-decoder D12, weight->code, STANDALONE). The
// decoder loads its OWN trained weights from CSV via load_matrix — code + data, no host tensors.
function matrix lc(matrix W, matrix x, matrix b) {
    matrix h = Tensor.MatrixMul(W, x) + b;
    return hadamard(hadamard(h, h), h);
}
function matrix ll(matrix W, matrix x, matrix b) {
    return Tensor.MatrixMul(W, x) + b;
}
"""


def _write_csv(path, M):
    """Write a 2-D tensor to CSV (one row per line, comma-separated repr-floats)."""
    rows = M.detach().cpu().reshape(M.shape[0], -1).tolist()
    path.write_text("\n".join(",".join(repr(float(v)) for v in row) for row in rows) + "\n",
                    encoding="utf-8")


def bake_decoder(params, out_dir, name: str = "decoder_baked"):
    """Bake trained `params` ([(W (out,in), b (out,1)), …]) to CSVs + emit a STANDALONE `.su`
    that `load_matrix`'s its own weights and takes only the (batched) input `matrix x` (in, N).
    Returns the emitted `.su` path. The forward = the same cubic/linear layers as the trained
    decoder, so running it reproduces the decoder with no host weight tensors."""
    import pathlib
    out_dir = pathlib.Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    n = len(params)
    decls = []
    for i, (W, b) in enumerate(params):
        wp, bp = out_dir / f"{name}_W{i}.csv", out_dir / f"{name}_b{i}.csv"
        _write_csv(wp, W)
        _write_csv(bp, b.reshape(b.shape[0], 1))
        decls.append(f'    matrix W{i} = load_matrix("{str(wp).replace(chr(92), "/")}");')
        decls.append(f'    matrix b{i} = load_matrix("{str(bp).replace(chr(92), "/")}");')
    expr = "x"
    for i in range(n - 1):
        expr = f"lc(W{i}, {expr}, b{i})"
    expr = f"ll(W{n - 1}, {expr}, b{n - 1})"
    src = (_BAKED_HELPERS
           + f"\nfunction matrix {name}(matrix x) {{\n"
           + "\n".join(decls)
           + f"\n    return {expr};\n}}\n"
           + 'function string main() { return "ok"; }\n')
    su_path = out_dir / f"{name}.su"
    su_path.write_text(src, encoding="utf-8")
    return su_path


def compile_baked(su_path, name: str = "decoder_baked"):
    """Compile a baked standalone decoder `.su` → its forward function (loads its own weights)."""
    import sys
    sdk = _DIR.parent.parent / "sdk" / "sutra-compiler"
    if str(sdk) not in sys.path:
        sys.path.insert(0, str(sdk))
    from sutra_compiler import compile_su
    mod = compile_su(su_path, llm_model="unused-no-basis-vectors", runtime_dim=8, verbose=False)
    return getattr(mod, name)


# --- emit the Fourier ENCODING on-substrate too (w2c finding follow-on #2, unblocked by sin_buf) ---
#
# `bake_decoder` above bakes the decoder FORWARD but still expects the host to Fourier-encode the
# coordinates first. Follow-on #2 of planning/findings/2026-06-17-decoder-weight-to-code.md was
# BLOCKED on an elementwise-buffer transcendental; `sin_buf`/`cos_buf` (2026-06-17) unblocked it.
# `bake_decoder_with_encoding` emits a FULLY self-contained `name(matrix coords)` — raw (x,y)
# coordinates in, image out, the Fourier encoding AND the decode both on the substrate.
#
# No concat primitive is needed. The host encoding is `feats = [coords, sin(f0·c), cos(f0·c), …]`
# (row-blocks of `coord_dim` rows each) and the first layer computes `W0 @ feats`. Since
# `W0 @ row_stack(blocks) = Σ_j W0[:, cols_j] @ block_j`, we split the trained `W0` (H×F) BY
# COLUMNS into per-block matrices (H×coord_dim) at bake time and emit a SUM of
# `Tensor.MatrixMul(W0_blk, <block>)` terms, where `<block>` is `coords`, `sin_buf(f_k·coords)`,
# or `cos_buf(f_k·coords)` — mathematically identical, all existing substrate ops + the new
# primitive. The frequencies f_k = 2^k·π are compile-time constants (scalar·buffer scales
# elementwise on the substrate, verified).

_ENC_HELPERS = """\
// Emitted by emit_decoder.bake_decoder_with_encoding (w2c follow-on #2, STANDALONE + on-substrate
// Fourier encoding). Raw coordinates in, image out: the Fourier encoding (sin_buf/cos_buf) AND the
// decode (Tensor.MatrixMul + hadamard cubic) both run on the substrate; weights load from CSV.
function matrix lc(matrix W, matrix x, matrix b) {
    matrix h = Tensor.MatrixMul(W, x) + b;
    return hadamard(hadamard(h, h), h);
}
function matrix ll(matrix W, matrix x, matrix b) {
    return Tensor.MatrixMul(W, x) + b;
}
"""


def bake_decoder_with_encoding(params, num_freqs, out_dir, coord_dim: int = 2,
                               name: str = "decoder_enc"):
    """Bake a trained decoder (whose first layer consumes `fourier_features(coords, num_freqs)`)
    to a STANDALONE `.su` `name(matrix coords)` that runs the Fourier ENCODING on the substrate
    too (via `sin_buf`/`cos_buf`), not just the decode. `params` = [(W0,b0),…] with W0 of shape
    (H, coord_dim·(1+2·num_freqs)) — the host-encoded input dim. Returns the `.su` path.

    W0 is split by columns into the coords block + per-frequency sin/cos blocks (each H×coord_dim,
    matching the `fourier_features` row layout [coords, sin(f0·c), cos(f0·c), sin(f1·c), …]); the
    first-layer pre-activation is emitted as the SUM of `Tensor.MatrixMul(block, enc_block)` + b0,
    enc_block ∈ {coords, sin_buf(f_k·coords), cos_buf(f_k·coords)}. Remaining layers are the same
    cubic/linear stack as `bake_decoder`."""
    import math
    import pathlib
    out_dir = pathlib.Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    n = len(params)
    W0, b0 = params[0]
    F = W0.shape[1]
    expected = coord_dim * (1 + 2 * num_freqs)
    if F != expected:
        raise ValueError(f"W0 in-dim {F} != coord_dim·(1+2·num_freqs) = {expected}")

    decls = []
    # --- first-layer column blocks (the encoding fold) ---
    # block order matches fourier_features: [coords, sin(f0), cos(f0), sin(f1), cos(f1), …]
    blocks = []                                  # (decl_var, su_expr_for_enc_block)
    col = 0
    # coords block
    wc = out_dir / f"{name}_W0_coords.csv"
    _write_csv(wc, W0[:, col:col + coord_dim])
    decls.append(f'    matrix W0c = load_matrix("{str(wc).replace(chr(92), "/")}");')
    blocks.append(("W0c", "coords"))
    col += coord_dim
    for k in range(num_freqs):
        f = float(2 ** k) * math.pi
        for trig in ("sin", "cos"):
            wk = out_dir / f"{name}_W0_{trig}{k}.csv"
            _write_csv(wk, W0[:, col:col + coord_dim])
            var = f"W0{trig}{k}"
            decls.append(f'    matrix {var} = load_matrix("{str(wk).replace(chr(92), "/")}");')
            blocks.append((var, f"{trig}_buf({f!r} * coords)"))
            col += coord_dim
    # b0
    b0p = out_dir / f"{name}_b0.csv"
    _write_csv(b0p, b0.reshape(b0.shape[0], 1))
    decls.append(f'    matrix b0 = load_matrix("{str(b0p).replace(chr(92), "/")}");')
    # remaining layers (1..n-1), same as bake_decoder
    for i in range(1, n):
        W, b = params[i]
        wp, bp = out_dir / f"{name}_W{i}.csv", out_dir / f"{name}_b{i}.csv"
        _write_csv(wp, W)
        _write_csv(bp, b.reshape(b.shape[0], 1))
        decls.append(f'    matrix W{i} = load_matrix("{str(wp).replace(chr(92), "/")}");')
        decls.append(f'    matrix b{i} = load_matrix("{str(bp).replace(chr(92), "/")}");')

    # first-layer pre-activation = Σ MatrixMul(block, enc_block) + b0; bind it so the cubic
    # doesn't re-emit (and re-compute) the whole sum three times.
    sum_terms = " + ".join(f"Tensor.MatrixMul({var}, {enc})" for var, enc in blocks)
    body = [f"    matrix h0pre = ({sum_terms}) + b0;"]
    if n > 1:
        expr = "hadamard(hadamard(h0pre, h0pre), h0pre)"        # layer 0 is hidden → cubic
        for i in range(1, n - 1):
            expr = f"lc(W{i}, {expr}, b{i})"
        expr = f"ll(W{n - 1}, {expr}, b{n - 1})"
    else:
        expr = "h0pre"                                          # single linear layer

    src = (_ENC_HELPERS
           + f"\nfunction matrix {name}(matrix coords) {{\n"
           + "\n".join(decls) + "\n"
           + "\n".join(body)
           + f"\n    return {expr};\n}}\n"
           + 'function string main() { return "ok"; }\n')
    su_path = out_dir / f"{name}.su"
    su_path.write_text(src, encoding="utf-8")
    return su_path
