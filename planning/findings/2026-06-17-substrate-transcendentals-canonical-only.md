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

Computing `sin/cos` of a coordinate *buffer* on the substrate is **not directly available**.
Two paths, both with real costs:
1. **Polynomial (hadamard) approximation of sin/cos.** Works only over a small argument range —
   a Taylor/Chebyshev cos over `[−πf, πf]` is fine for the lowest frequency but diverges badly
   for the high-frequency bands (`f = 2^(L−1)`, range ≈ ±25 for L=4). So a polynomial encoding
   could cover low frequencies only — strictly weaker than the host Fourier features.
2. **A new substrate primitive: elementwise transcendentals on field buffers** (`sin_buf`,
   `cos_buf`, or an elementwise `cexp`). This is the clean fix and would also unblock SIREN-style
   sin-activations, but it's a compiler/runtime addition (`codegen_pytorch.py`), not a decoder
   change — out of scope for the decoder track; queue it Sutra-side if wanted.

**Decision:** leave the Fourier encoding host-side (honestly labeled as input geometry, like the
coordinate grid) until a real elementwise-buffer transcendental primitive exists. Do NOT ship a
polynomial "on-substrate encoding" that silently degrades the high-frequency bands — that would
fake substrate-purity at the cost of the decoder's expressivity. The decoder forward (matmul +
hadamard cubic) is and stays on the substrate; this is about the *input encoding* only.
