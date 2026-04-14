"""Test rotate restricted to the CX EPG ring attractor on real Shiu W.

The generic 50-random-neuron rotate test (shiu_rotate_test.py) collapsed
to a fixed-point attractor. This script tests the biologically-motivated
alternative: restrict drive and readout to the 47 EPG neurons (FlyWire
primary_type == "EPG") that form the central-complex ring attractor
(Kim 2017, Turner-Evans 2020, Kakaria & de Bivort 2017). EPG neurons
are organized in a ring topology and implement a moving bump of
activity that encodes heading direction.

Protocol:
  1. Initialize with a localized EPG drive (5 adjacent EPGs, not all 47)
  2. Drive at 200 Hz for 100 ms
  3. Read out spike counts, restrict to EPG indices (47-D state)
  4. Pick top-K active EPGs as the next drive set
  5. Iterate 10 steps; measure cos(state_i, state_j) over EPG-only
     spike vectors

If CX-restricted iteration preserves distinctness (cosine matrix has
structure, not uniform 0.97), the paper's rotation claim can narrow
to "runs on the CX sub-circuit, biologically grounded in Kim 2017."
If it also collapses, the paper must drop the rotation claim entirely.
"""
from __future__ import annotations

import sys
from pathlib import Path
from time import perf_counter

import numpy as np
import pandas as pd
import torch

SHIU_REPO = Path(r"C:/Users/Immanuelle/shiu-fly-brain")
FLYBRAIN_DIR = Path(r"C:/Users/Immanuelle/flybrain")
sys.path.insert(0, str(SHIU_REPO / "code"))

from run_pytorch import MODEL_PARAMS, DT, TorchModel, get_weights  # noqa: E402

CONN_PATH = SHIU_REPO / "data" / "2025_Connectivity_783.parquet"
COMP_PATH = SHIU_REPO / "data" / "2025_Completeness_783.csv"
CELL_TYPES_PATH = FLYBRAIN_DIR / "consolidated_cell_types.csv.gz"
WT_DIR = SHIU_REPO / "data"

T_SIM_MS = 100.0
NUM_STEPS = int(T_SIM_MS / DT)
N_NEURONS = 138639
DRIVE_RATE_HZ = 200.0
N_INIT_DRIVE = 5
TOP_K_EPG = 5
N_ITER = 10


def get_epg_indices():
    ct = pd.read_csv(CELL_TYPES_PATH)
    epg_ids = set(ct[ct["primary_type"] == "EPG"]["root_id"].astype(str))
    comp = pd.read_csv(COMP_PATH, index_col=0)
    shiu_ids = comp.index.astype(str)
    return np.array([i for i, fid in enumerate(shiu_ids) if fid in epg_ids])


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

    epg_idx = get_epg_indices()
    print(f"EPG neurons (FlyWire primary_type=EPG in Shiu model): {len(epg_idx)}")

    t0 = perf_counter()
    weights = get_weights(CONN_PATH, COMP_PATH, WT_DIR, csr=True).to(device)
    print(f"weights: {weights.shape}, nnz={weights._nnz()} ({perf_counter()-t0:.1f}s)")

    model = TorchModel(1, N_NEURONS, DT, MODEL_PARAMS, weights, device=device).to(device)

    rng = np.random.default_rng(42)
    init_positions = rng.choice(len(epg_idx), size=N_INIT_DRIVE, replace=False)
    init_drive = epg_idx[init_positions]
    print(f"\ninit drive: EPG positions {sorted(init_positions.tolist())} "
          f"(neuron idx {sorted(init_drive.tolist())})")
    print(f"iterating {N_ITER} steps; drive = top-{TOP_K_EPG} active EPGs from prev step")

    trajectory_epg = []
    driven_sets = [init_drive]

    t = perf_counter()
    for i in range(N_ITER):
        drive = driven_sets[-1]
        out = run_once(model, build_rates(drive), seed=8000 + i, device=device)
        state_epg = out[epg_idx]
        trajectory_epg.append(state_epg)
        active_epg = int((state_epg > 0).sum())
        top_k_local = np.argsort(state_epg)[-TOP_K_EPG:]
        next_drive = epg_idx[top_k_local]
        if i + 1 < N_ITER:
            driven_sets.append(next_drive)
        print(f"  step {i:2d}: drive EPG positions {sorted(np.where(np.isin(epg_idx, drive))[0].tolist())}, "
              f"active EPGs = {active_epg}/{len(epg_idx)}, "
              f"top{TOP_K_EPG} sum = {state_epg[top_k_local].sum():.0f}")
    print(f"  {N_ITER} steps in {perf_counter()-t:.1f}s")

    print(f"\nCOSINE MATRIX on EPG-only state ({len(epg_idx)}-D):")
    M = np.zeros((N_ITER, N_ITER))
    for i in range(N_ITER):
        for j in range(N_ITER):
            M[i, j] = cos(trajectory_epg[i], trajectory_epg[j])

    print("       " + "   ".join(f"i={j}" for j in range(N_ITER)))
    for i in range(N_ITER):
        row = "  ".join(f"{M[i, j]:.3f}" for j in range(N_ITER))
        print(f"  i={i}: {row}")

    offdiag_1 = np.mean([M[i, i + 1] for i in range(N_ITER - 1)])
    offdiag_2 = np.mean([M[i, i + 2] for i in range(N_ITER - 2)])
    farthest = M[0, N_ITER - 1]
    mask = ~np.eye(N_ITER, dtype=bool)
    print(f"\n  mean cos(step_i, step_i+1) = {offdiag_1:.4f}")
    print(f"  mean cos(step_i, step_i+2) = {offdiag_2:.4f}")
    print(f"  cos(step_0, step_{N_ITER-1})            = {farthest:.4f}")
    print(f"  min off-diagonal cos       = {M[mask].min():.4f}")
    print(f"  max off-diagonal cos       = {M[mask].max():.4f}")
    print(f"  mean off-diagonal cos      = {M[mask].mean():.4f}")

    # Also show the top-EPG position per step as a crude "bump tracker"
    print(f"\nBUMP TRACKER: argmax EPG index per step (heading proxy):")
    for i in range(N_ITER):
        bump = int(np.argmax(trajectory_epg[i]))
        print(f"  step {i:2d}: EPG-pos {bump:2d}  (spike count {trajectory_epg[i][bump]:.0f})")


if __name__ == "__main__":
    main()
