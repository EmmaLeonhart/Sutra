"""Test Sutra `rotate` / iterative dynamics on the real Shiu LIF model.

The paper's rotation claim is: state_{n+1} = R @ state_n applied
iteratively produces a trajectory of distinguishable states that the
brain uses for counting. This has to date been run on polar-decomp Q,
which is the rejected attractor per CLAUDE.md. Here we test the real
substrate-native version: iterate the Shiu LIF dynamical map f:
state_{n+1} = f(state_n), where f encodes (drive the top-K neurons
of state_n at 200 Hz for 100 ms, read out spike-count vector as the
next state).

This is NOT identically W @ state, because f includes alpha synapses,
membrane dynamics, and thresholding. But it IS the honest
substrate-native question: does the real network dynamics produce
a structured trajectory we can use for computation, or does it
collapse to a fixed point?

Protocol:
  1. Start from a random 50-neuron drive pattern v_0
  2. Drive 100 ms, read out_0
  3. Pick top-K active neurons of out_0 as the next drive set
  4. Repeat for N steps
  5. Measure cos(out_i, out_j) over all i, j — look for diagonal
     structure (trajectory) vs. all-high (fixed point) vs. all-low
     (divergence)

K (top-K) = 50 to match the input patterns used in probe/bundle/snap.
"""
from __future__ import annotations

import sys
from pathlib import Path
from time import perf_counter

import numpy as np
import torch

SHIU_REPO = Path(r"C:/Users/Immanuelle/shiu-fly-brain")
sys.path.insert(0, str(SHIU_REPO / "code"))

from run_pytorch import MODEL_PARAMS, DT, TorchModel, get_weights  # noqa: E402

CONN_PATH = SHIU_REPO / "data" / "2025_Connectivity_783.parquet"
COMP_PATH = SHIU_REPO / "data" / "2025_Completeness_783.csv"
WT_DIR = SHIU_REPO / "data"

T_SIM_MS = 100.0
NUM_STEPS = int(T_SIM_MS / DT)
N_INPUT = 50
TOP_K = 50
N_ITER = 10
N_NEURONS = 138639
DRIVE_RATE_HZ = 200.0


def build_rates(driven_indices: np.ndarray) -> torch.Tensor:
    rates = torch.zeros(1, N_NEURONS, dtype=torch.float32)
    rates[0, driven_indices] = DRIVE_RATE_HZ
    return rates


def run_once(model, rates, seed, device):
    torch.manual_seed(seed)
    gen = torch.Generator(device=device).manual_seed(seed)
    conductance, delay_buffer, spikes, v, refrac = model.state_init()
    rates_d = rates.to(device)
    counts = torch.zeros(1, N_NEURONS, dtype=torch.float32, device=device)
    for _ in range(NUM_STEPS):
        conductance, delay_buffer, spikes, v, refrac = model(
            rates_d, conductance, delay_buffer, spikes, v, refrac, generator=gen,
        )
        counts += spikes
    return counts[0].detach().cpu().numpy()


def cos(a, b):
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    return 0.0 if (na == 0 or nb == 0) else float(np.dot(a, b) / (na * nb))


def main():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"device: {device}")

    t0 = perf_counter()
    weights = get_weights(CONN_PATH, COMP_PATH, WT_DIR, csr=True).to(device)
    print(f"weights: {weights.shape}, nnz={weights._nnz()} ({perf_counter()-t0:.1f}s)")

    model = TorchModel(1, N_NEURONS, DT, MODEL_PARAMS, weights, device=device).to(device)

    rng = np.random.default_rng(42)
    v0 = rng.choice(N_NEURONS, size=N_INPUT, replace=False)

    print(f"\niterating Shiu dynamical map f: state_n -> state_n+1")
    print(f"  drive {N_INPUT} neurons @ {DRIVE_RATE_HZ} Hz for {T_SIM_MS} ms")
    print(f"  top-K = {TOP_K} active neurons become next drive set")
    print(f"  N_ITER = {N_ITER}")

    trajectory = []
    driven_sets = [v0]

    t = perf_counter()
    for i in range(N_ITER):
        drive = driven_sets[-1]
        out = run_once(model, build_rates(drive), seed=7000 + i, device=device)
        trajectory.append(out)
        active = int((out > 0).sum())
        top_k_idx = np.argsort(out)[-TOP_K:]
        if i + 1 < N_ITER:
            driven_sets.append(top_k_idx)
        print(f"  step {i:2d}: drive={len(drive):3d} neurons, "
              f"active={active:5d}, top-{TOP_K} sum-spikes={out[top_k_idx].sum():.0f}")
    print(f"  {N_ITER} steps in {perf_counter()-t:.1f}s")

    print(f"\nCOSINE MATRIX (trajectory self-similarity):")
    M = np.zeros((N_ITER, N_ITER))
    for i in range(N_ITER):
        for j in range(N_ITER):
            M[i, j] = cos(trajectory[i], trajectory[j])

    header = "       " + "  ".join(f"  i={j}" for j in range(N_ITER))
    print(header)
    for i in range(N_ITER):
        row = "  ".join(f"{M[i, j]:.3f}" for j in range(N_ITER))
        print(f"  i={i}:  {row}")

    print(f"\nDIAGONAL STRUCTURE:")
    offdiag_1 = np.mean([M[i, i+1] for i in range(N_ITER-1)])
    offdiag_2 = np.mean([M[i, i+2] for i in range(N_ITER-2)])
    farthest = M[0, N_ITER-1]
    print(f"  mean cos(step_i, step_i+1)   = {offdiag_1:.4f}  (consecutive)")
    print(f"  mean cos(step_i, step_i+2)   = {offdiag_2:.4f}  (skip-1)")
    print(f"  cos(step_0, step_{N_ITER-1})              = {farthest:.4f}  (endpoints)")

    distinct_pairs = int(np.sum(M < 0.5) - N_ITER)  # off-diag
    print(f"  off-diagonal pairs with cos<0.5: {distinct_pairs}/{N_ITER*(N_ITER-1)}")


if __name__ == "__main__":
    main()
