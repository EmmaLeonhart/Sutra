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
1. **Bake weights to CSV + `load_matrix`** — ✅ DONE (D12): `bake_decoder` emits a fully
   standalone `.su` that loads its own weights; verified to reproduce the trained forward.
2. **Emit the Fourier encoding** as substrate ops — ✅ **DONE 2026-06-17** (was blocked on a
   substrate primitive; `sin_buf`/`cos_buf` shipped and unblocked it —
   `2026-06-17-substrate-transcendentals-canonical-only.md`).
   `emit_decoder.bake_decoder_with_encoding` emits a FULLY self-contained `.su`
   `dec_enc(matrix coords)` — raw (x,y) coordinates in, image out, the Fourier ENCODING
   (`sin_buf`/`cos_buf`) AND the decode both on the substrate, weights from CSV. **No concat
   primitive was needed:** since `W0 @ row_stack(blocks) = Σ_j W0[:, cols_j] @ block_j`, the
   trained `W0` is split BY COLUMNS at bake time into the coords block + per-frequency sin/cos
   blocks, and the first-layer pre-activation is emitted as a SUM of
   `Tensor.MatrixMul(W0_block, sin_buf/cos_buf(f_k·coords))` — mathematically identical, using
   only existing ops (`Tensor.MatrixMul`, `+`, scalar·buffer scaling — verified elementwise) plus
   the new primitive. Verified (`test_emit_decoder.py`): the baked coords→pixels `.su` reproduces
   the SAME substrate computation (`fourier_features_substrate` + `mlp_forward`) to **4.6e-5**.
   (Against the exact-`torch.sin` host render the gap is ~0.05 — the `sin_buf` table readout's
   ~8e-5 error amplified through the two cubic layers, a documented property of the encoding, not
   a bake defect. The bake reproduces the substrate computation faithfully, which is its job.)
3. **Feed the decompiler.** A trained decoder (weights + emitted code + IO) is a high-value
   weight↔code corpus triple; wire decoder emissions into `weight_to_code_corpus.py`.
