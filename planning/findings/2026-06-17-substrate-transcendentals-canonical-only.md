# Substrate transcendentals are canonical-vector ops, not elementwise on field buffers (2026-06-17)

**Negative result, found twice while building the learned decoder.**

The substrate's transcendental / complex-exponential machinery — `tanh`, `sin`, `cexp` (and the
`realExp`/`imaginaryExp`/`complex_mul` they lower to) — operates on the **canonical d-dim
complex-vector representation** (the fuzzy-logic value form), NOT elementwise over an arbitrary
length-N *field buffer*.

Evidence:
- **D1 (decoder dense layer):** `tanh(matmul(W, x))` on a length-H activation buffer raised a
  dim-mismatch in `_canon` (it tried to coerce the H-vector to the canonical dim).
- **On-substrate Fourier encoding probe (this finding):** `cos(θ) = realvec(cexp(1.0i·θ))` over
  a length-5 buffer raised `RuntimeError: size of tensor a (108) must match b (5)` inside
  `complex_mul` — `cexp` evaluated against the canonical dim (108), not the 5-element buffer.

The only ops that ARE elementwise over field buffers are `hadamard`, `+`, `-` (and `matmul`/
`Tensor.MatrixMul` for the linear part). That is why the learned decoder:
- uses a **hadamard polynomial (cubic)** as its nonlinearity (D1), not `tanh`/`sin`; and
- gets its periodic/high-frequency expressivity from a **host-built Fourier-feature encoding**
  of the coordinates (D2) — host input geometry, the same boundary as the X/Y grid.

## Consequence for "on-substrate Fourier encoding" (decoder follow-on)

Computing `sin/cos` of a coordinate *buffer* on the substrate was **not directly available** at
the time of this finding. Two paths were noted, both with real costs:
1. **Polynomial (hadamard) approximation of sin/cos.** Works only over a small argument range —
   a Taylor/Chebyshev cos over `[−πf, πf]` is fine for the lowest frequency but diverges badly
   for the high-frequency bands (`f = 2^(L−1)`, range ≈ ±25 for L=4). So a polynomial encoding
   could cover low frequencies only — strictly weaker than the host Fourier features.
2. **A new substrate primitive: elementwise transcendentals on field buffers** (`sin_buf`,
   `cos_buf`, or an elementwise `cexp`). The clean fix; also unblocks SIREN-style sin-activations.

## ✅ RESOLVED 2026-06-17 — path 2 shipped (`sin_buf`/`cos_buf`)

Emma: "Make the compiler primitive." Path 2 is built. `sin_buf`/`cos_buf` are elementwise
transcendentals over a length-N field buffer in `codegen_pytorch.py` (registered as builtins in
`codegen_base.py`), using the **same substrate-pure table readout the scalar trig already uses**
— wrap each element to `(−π, π]` then a triangular soft-index crosstalk matmul against the cached
sin/cos table — but **broadcast over the N elements** (the exact `(N, T)` weight-matrix pattern
`sawtooth_mod` already ships). One fused tensor op, autograd-preserving, **periodic by
construction** so it does NOT diverge at the high-frequency bands (the failure mode path 1 had):
measured accurate to ~8e-5 vs `math.sin/cos` at arguments 0.5 … 100.0, and `d/dx sin_buf ≈ cos`
to 5e-3 (so SIREN-style sin-activations are now expressible). Tests: `sdk/sutra-compiler/tests/
test_buffer_transcendentals.py` (5).

The decoder's on-substrate Fourier encoding is now wired: `fourier_features_substrate` in
`demos/decoder/substrate_nn.py` runs the sin/cos on the substrate via `sin_buf`/`cos_buf` (the
`f·coords` scaling is an affine input transform, the `cat` is layout). It reproduces the host
`fourier_features` to max |Δ| 6.9e-5, and a decoder built on it fits the wave target. Tests:
`demos/decoder/test_encoding.py` (3 new). The decoder forward (matmul + hadamard cubic) was
always on the substrate; now the *input transcendental* is too — the only host-Python part of
the encoding that genuinely had to leave the substrate. The host `fourier_features` is retained
as the reference the substrate version is measured against.
