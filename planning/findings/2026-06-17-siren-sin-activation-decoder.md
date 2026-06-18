# SIREN sin-activation decoder on the substrate — runs, but does NOT beat cubic+Fourier (2026-06-17)

**Mixed / negative-leaning result.** The `sin_buf` compiler primitive (shipped same day) makes a
SIREN-style sin-activation decoder *expressible on the substrate* for the first time. It runs and
trains; it does **not** outperform the existing hadamard-cubic + Fourier-feature decoder, and on
the reproducible CPU target it underperforms. Recorded so a future session does not "upgrade" the
decoder to SIREN expecting a win.

## What was built

- `dense.su::dense_sin(W,x,b) = sin_buf(matmul(W,x)+b)` — a compiled substrate SIREN layer (the sin
  runs on the substrate via the new `sin_buf` primitive; the D1 finding had blocked this).
- `substrate_nn.py::siren_forward` (stacks `dense_sin` + a linear readout) and `init_siren` (the
  principled SIREN init, Sitzmann et al. 2020 §3.2: ω0-scaled first layer, √(6/n) hidden bound).
- It is **differentiable end-to-end** — gradients flow through `dense_sin`/`sin_buf` to the weights
  (`test_siren.py`), so the SIREN trains on the substrate by host Adam, the proven decoder pattern.

## Measured (PSNR, dB) — SIREN vs cubic+Fourier, same targets, same fitting budget

| Target            | SIREN (CPU) | cubic+FF (CPU) | SIREN (CUDA) | cubic+FF (CUDA) |
|-------------------|:-----------:|:--------------:|:------------:|:---------------:|
| 1-D wave sin(3πx) |   44.7      |   **50.1**     |   **49.0**   |     35.2        |
| 2-D checkerboard  |   12.1      |   **30.6**     |     36.1     |   **63.9**      |

(SIREN: raw coords in, [·,32,32,1]/[·,96,96,1], ω0=30, 800/1000 Adam steps. cubic+FF: Fourier
features in (nf=4/6), same widths, lr 1e-2. Repro: the throwaway `_siren_measure.py` shape, CUDA
disabled for the CPU column.)

## Reading of the result

1. **The primitive is validated.** SIREN sin-activations now run on the substrate and train — the
   thing `sin_buf` was built to unblock. That part is a clean success.
2. **SIREN does not win.** On **CPU** (the CI / reproducible target) cubic+Fourier beats SIREN on
   **both** targets, decisively on the 2-D checker (30.6 vs 12.1 dB — SIREN essentially failed to
   fit it at these hyperparameters). On CUDA the comparison is mixed (SIREN wins the smooth wave,
   cubic+FF wins the checker by a wide margin).
3. **The head-to-head is hardware-sensitive and therefore NOT a robust claim.** The wave result
   *reverses* between CPU and CUDA (cubic 50 / SIREN 45 on CPU; SIREN 49 / cubic 35 on CUDA). This
   is why `test_siren.py` deliberately ships **no** "SIREN beats cubic" assertion — only the
   robust facts (runs NaN-free, fits the wave >35 dB, differentiable). Asserting a winner would
   encode a non-reproducible claim (integrity rule: measurements, not targets).
4. **Likely cause** of SIREN's CPU underperformance is the well-known SIREN sensitivity to ω0 / lr
   / depth. It was deliberately **not** tuned until it won — tuning hyperparameters to manufacture
   a favorable comparison would be doctoring the result.
5. **Cost caveat.** `sin_buf`'s readout is an `(N, 4096)` triangular soft-index matmul per call, so
   a SIREN forward (sin on every hidden layer) is markedly more expensive on CPU than the cubic
   activation (a couple of hadamards) — the CPU measurement was very slow. For the table-readout
   precision that buys periodicity, this is the cost.

## Decision (integrity rule 4: negative result → mark it, do not wire downstream)

The cubic-hadamard + Fourier-feature decoder **remains the default / recommended** decoder
(`mlp_forward` + `fourier_features`). SIREN (`siren_forward`) stays in the tree as a working,
tested, substrate-pure *alternative* and as the validation of `sin_buf` — but it is **not** wired
in as a replacement and should not be adopted as one without a measured, reproducible win on the
actual target of interest. The on-substrate Fourier *encoding* (`fourier_features_substrate`,
which also uses `sin_buf`) is the genuinely useful payoff of the primitive and stands on its own.
