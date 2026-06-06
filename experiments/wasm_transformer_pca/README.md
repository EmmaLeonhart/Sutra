# PCA / SVD of the analytic WASM transformer

`pca.py` builds the analytic `transformer-vm` (from the cached `plan.yaml` MILP
schedule — no solver re-run) and SVD-analyzes every weight matrix to find the
genuine low-dimensional structure for the reduced-attention DNC work.

Run: `python experiments/wasm_transformer_pca/pca.py`
(needs `pulp`, `highspy`, `pyyaml`, `torch`, `numpy`; the `transformer-vm`
submodule must be initialized — see `.gitmodules`.)

Result + interpretation: `planning/findings/2026-06-06-pca-wasm-transformer.md`.
Headline: magnitude-PCA is the wrong lens (weights span ~1e30+ dynamic range —
hardmax/address switches; importance ≠ norm). Concretely reducible: 2/7 attention
layers are all-zero; the 915-vocab embedding is ~3-d. The attention core must be
reduced from the computation graph, not SVD.
