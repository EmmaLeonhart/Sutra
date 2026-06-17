# Decoder weight→code: emit a trained substrate decoder as Sutra (2026-06-17)

**Context.** The learned decoder (D1–D8) trains its weights by autograd through the compiled
substrate forward. D11 asks: can a *trained* decoder be turned back into Sutra **code** — "every
op trainable" meeting "compile the weights to code"?

**What already exists.** `experiments/weight_to_code_corpus.py` + `experiments/w2c_seq2seq/`
build a weight↔code corpus and a seq2seq *decompiler* (weights→`.su` source). Two reusable
substrate facts from that work:
- A `.su` program can take a `matrix` parameter and run `Tensor.MatrixMul(M, x)` on the
  substrate (the trainable component).
- Weights are **file-backed** (CSV via `load_matrix`) — the established weight↔code separation:
  the `.su` is the *code* (structure), the CSV matrices are the *weights*.

**What D11 built (verified).** `demos/decoder/emit_decoder.py` emits a trained decoder's FORWARD
as a standalone `.su` over `matrix` weight params: `layer_cube`/`layer_lin` =
`Tensor.MatrixMul(W,x)+b` (+ hadamard cubic for hidden layers — the substrate's tanh/sin are
canonical-only, D1 finding), composed into a `decoder(W0,b0,…,x)`. `test_emit_decoder.py` trains
a small `[F,16,16,1]` decoder, emits + compiles the `.su`, runs it with the trained weights, and
confirms it reproduces the host forward to **< 1e-4** (max abs diff) — i.e. the trained decoder
is now standalone Sutra **code** plus weight tensors. The *code* (`decoder_emitted.su`) is fixed
by the architecture; only the weights change per trained model.

**Boundary / honesty.** The emitted `.su` is the forward; the weights are supplied at call
(torch tensors here, file-backable as CSVs via the corpus's `load_matrix`). The Fourier
input-encoding is still host-built input geometry (as in D2). So "weight→code" here = the
forward emitted as Sutra + the trained weights as data — not a single self-contained literal.

**Follow-ons (spec).**
1. **Bake weights to CSV + `load_matrix`** so the emitted `.su` loads its own weights (a fully
   standalone program), matching the corpus's file-backed pattern end-to-end.
2. **Emit the Fourier encoding** as substrate ops (polynomial sin-approx via hadamard) so even
   the input geometry is in-program — removes the host-encoding boundary.
3. **Feed the decompiler.** A trained decoder (weights + emitted code + IO) is a high-value
   weight↔code corpus triple; wire decoder emissions into `weight_to_code_corpus.py`.
