# thrml API study (Sutra→thrml compilation-target, step 0)

**Date:** 2026-06-13
**Status:** step 0 (vendor + study + run) DONE. This is a factual API record — it
does NOT design the Sutra→thrml mapping (that is step 1, Emma-driven; direction
already set: vectors → spin-node graph, ops → factor interactions).

## What was done

- Vendored Extropic's **thrml** as a git submodule at `external/thrml`, pinned to
  `db629a0` (`db629a053d4519b9b07eb2ee81ef0585246e128a`).
- Installed it editable (`pip install -e external/thrml`) → pulled **JAX 0.10.1 +
  jaxlib + equinox 0.13.8 + jaxtyping**. JAX runs on **CPU on this Windows
  machine** (no WSL needed; `jax.default_backend() == "cpu"`).
- **Ran the README minimal example** (5-spin Ising chain, two-colour block Gibbs):
  `sample_states` returned `(1000, 5)` bool samples (spins as 0/1), mean ≈ 0.51 —
  a valid near-symmetric sample for a zero-bias ferromagnetic chain. The toolchain
  works end-to-end. (Measured, not "it imported".)

## Public API surface (what a `codegen_thrml` backend would target)

Top-level `thrml`:
- **Nodes** (`pgm.py`): `AbstractNode`, **`SpinNode`** (±1, sampled as bool 0/1),
  **`CategoricalNode`** (k-state). Nodes are identity objects; the graph is built
  by referencing them.
- **Blocks** (`block_management.py`): **`Block`** (a set of nodes sampled together
  — block Gibbs needs each block internally conditionally independent), `BlockSpec`,
  and `block_state_to_global` / `from_global_state` / `get_node_locations` /
  `make_empty_block_state` (the compact "global" state packing the README mentions).
- **Factors** (`factor.py`): `AbstractFactor`, **`WeightedFactor`**,
  `FactorSamplingProgram`. A factor is an energy term over a node tuple.
- **Interactions** (`interaction.py`): **`InteractionGroup`** — batched same-shape
  factors (the array-level-parallelism mechanism).
- **Sampling** (`block_sampling.py`): **`SamplingSchedule`**(`n_warmup`,
  `n_samples`, `steps_per_sample`), **`BlockSamplingProgram`**, `BlockGibbsSpec`,
  **`sample_states`**, `sample_blocks`, `sample_single_block`,
  `sample_with_observation`.
- **Conditionals** (`conditional_samplers.py`): `AbstractConditionalSampler`,
  **`BernoulliConditional`** (spin), **`SoftmaxConditional`** (categorical) — the
  per-node conditional a Gibbs step draws from.
- **Observers** (`observers.py`): `StateObserver`, `MomentAccumulatorObserver`.

`thrml.models`:
- **EBM** (`ebm.py`): `AbstractEBM`, `FactorizedEBM`, `EBMFactor`,
  `AbstractFactorizedEBM` — an energy-based model AS a set of factors.
- **Discrete** (`discrete_ebm.py`): `DiscreteEBMFactor`, **`SpinEBMFactor`**,
  `CategoricalEBMFactor`, `Square{Discrete,Categorical}EBMFactor`,
  `SpinGibbsConditional`, `CategoricalGibbsConditional`.
- **Ising** (`ising.py`): **`IsingEBM`**(`nodes, edges, biases, weights, beta`),
  **`IsingSamplingProgram`**(`model, free_blocks, clamped_blocks`),
  **`hinton_init`**, `estimate_moments`, `estimate_kl_grad`, `IsingTrainingSpec`
  (so an Ising model is **trainable** via KL-gradient moment matching).

Minimal program shape (verified): build `SpinNode`s → `IsingEBM(nodes, edges,
biases, weights, beta)` → partition into conditionally-independent `free_blocks`
→ `IsingSamplingProgram` → `hinton_init` → `SamplingSchedule` → `sample_states`.

## Facts that bear on step 1 (the Emma-driven mapping) — NOT decisions

The mapping direction is set (vectors → spin-node graph; bind/bundle/similarity →
factor interactions). The open specifics step 1 must settle WITH Emma — recorded
here so they are not silently invented:

1. **Spins are discrete (±1).** Sutra's substrate is dense real/complex vector
   components. The load-bearing question is how a continuous vector component
   encodes into spin/categorical nodes (bit-planes? one categorical node per
   component? a population of spins per axis?). This is the quantization choice
   the whole backend rests on.
2. **Energy, not deterministic op.** A factor defines an energy; the "result" is
   recovered by *sampling* (block Gibbs to a mode / by moments), not a forward
   matmul. So bind/bundle/similarity must each be expressed as an energy whose
   samples reproduce the Sutra op's output — with measured signal-separation.
3. **Block structure is a correctness constraint.** Each `Block` must be
   internally conditionally independent; the factor graph topology dictates the
   colouring. Op encodings must keep a valid block partition.
4. **Trainable.** `IsingTrainingSpec` + `estimate_kl_grad` mean the backend could
   be fit (KL moment-matching), which lines up with the constrain-train arc.

## Dependency note

JAX/equinox are a **backend-only** dependency — NOT added to Sutra's core
requirements (that would force JAX on every user). When `codegen_thrml` lands it
goes in an optional extra (e.g. `pip install sutra[thrml]`), isolated from the
canonical PyTorch target.
