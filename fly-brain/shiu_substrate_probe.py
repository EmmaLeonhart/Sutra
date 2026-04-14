"""First Sutra operation on the real Shiu LIF model (eonsystemspbc/fly-brain).

This is not a paper number — it is the substrate-level probe we need
BEFORE any Sutra op can claim to run on real FlyWire W. Question:
given the full 138k-neuron LIF model with real W, does activating
input pattern A twice produce similar output patterns (stability),
and does activating A vs B produce distinguishable patterns
(distinctness)? Both are prerequisites for bundle/bind/snap on this
substrate.

We record the per-neuron spike count vector as the "output state,"
compute cosine between output states, and report:
  cos(A1, A2)  -- same input, different seeds  -> should be ~1
  cos(A,  B)   -- different inputs              -> should be < 1
  cos(B1, B2)  -- same input, different seeds  -> should be ~1

Nothing here uses polar-decomp Q. The W that drives dynamics is the
real FlyWire v783 connectivity loaded by run_pytorch.get_weights.

Usage:
    python fly-brain/shiu_substrate_probe.py

Expects eonsystemspbc/fly-brain checked out at C:/Users/Immanuelle/shiu-fly-brain/
with `brain-fly` conda env (python 3.10 + brian2cuda + torch-cu126).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from time import perf_counter

import numpy as np
import torch

SHIU_REPO = Path(r"C:/Users/Immanuelle/shiu-fly-brain")
sys.path.insert(0, str(SHIU_REPO / "code"))

from run_pytorch import (  # noqa: E402
    MODEL_PARAMS,
    DT,
    TorchModel,
    get_weights,
)

CONN_PATH = SHIU_REPO / "data" / "2025_Connectivity_783.parquet"
COMP_PATH = SHIU_REPO / "data" / "2025_Completeness_783.csv"
WT_DIR = SHIU_REPO / "data"

T_SIM_MS = 100.0
NUM_STEPS = int(T_SIM_MS / DT)
N_INPUT = 50               # neurons to activate per pattern
N_NEURONS = 138639
BASE_RATE_HZ = 0
DRIVE_RATE_HZ = 200.0


def build_rates(driven_indices: np.ndarray) -> torch.Tensor:
    rates = torch.zeros(1, N_NEURONS, dtype=torch.float32)
    rates[0, driven_indices] = DRIVE_RATE_HZ
    return rates


def run_once(model: TorchModel, rates: torch.Tensor, seed: int,
             device: str) -> np.ndarray:
    torch.manual_seed(seed)
    generator = torch.Generator(device=device).manual_seed(seed)
    state = model.state_init()
    conductance, delay_buffer, spikes, v, refrac = state
    rates_d = rates.to(device)
    spike_counts = torch.zeros(1, N_NEURONS, dtype=torch.float32, device=device)
    for _ in range(NUM_STEPS):
        conductance, delay_buffer, spikes, v, refrac = model(
            rates_d, conductance, delay_buffer, spikes, v, refrac,
            generator=generator,
        )
        spike_counts += spikes
    return spike_counts[0].detach().cpu().numpy()


def cos(a: np.ndarray, b: np.ndarray) -> float:
    na = np.linalg.norm(a)
    nb = np.linalg.norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def main() -> None:
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"device: {device}")
    if device == "cuda":
        print(f"gpu: {torch.cuda.get_device_name(0)}")

    t0 = perf_counter()
    weights = get_weights(CONN_PATH, COMP_PATH, WT_DIR, csr=True)
    weights = weights.to(device)
    print(f"weights loaded: {weights.shape}, nnz={weights._nnz() if hasattr(weights, '_nnz') else 'csr'} "
          f"({perf_counter() - t0:.1f}s)")

    model = TorchModel(
        batch=1, size=N_NEURONS, dt=DT, params=MODEL_PARAMS,
        weights=weights, device=device,
    ).to(device)

    rng = np.random.default_rng(42)
    pattern_A = rng.choice(N_NEURONS, size=N_INPUT, replace=False)
    pattern_B = rng.choice(N_NEURONS, size=N_INPUT, replace=False)
    while np.intersect1d(pattern_A, pattern_B).size > 0:
        pattern_B = rng.choice(N_NEURONS, size=N_INPUT, replace=False)

    rates_A = build_rates(pattern_A)
    rates_B = build_rates(pattern_B)

    print(f"\nactivating {N_INPUT} input neurons @ {DRIVE_RATE_HZ} Hz for {T_SIM_MS} ms")

    t = perf_counter()
    out_A1 = run_once(model, rates_A, seed=1000, device=device)
    out_A2 = run_once(model, rates_A, seed=1001, device=device)
    out_B1 = run_once(model, rates_B, seed=1002, device=device)
    out_B2 = run_once(model, rates_B, seed=1003, device=device)
    print(f"4 runs in {perf_counter() - t:.1f}s")

    def active(v: np.ndarray) -> int:
        return int((v > 0).sum())

    print(f"\nper-run active-neuron counts:")
    print(f"  A1={active(out_A1):6d}  A2={active(out_A2):6d}  "
          f"B1={active(out_B1):6d}  B2={active(out_B2):6d}")

    print(f"\ncosine similarities on full {N_NEURONS}-D spike-count vector:")
    print(f"  stability  cos(A1, A2) = {cos(out_A1, out_A2):.4f}")
    print(f"  stability  cos(B1, B2) = {cos(out_B1, out_B2):.4f}")
    print(f"  distinct   cos(A1, B1) = {cos(out_A1, out_B1):.4f}")
    print(f"  distinct   cos(A1, B2) = {cos(out_A1, out_B2):.4f}")
    print(f"  distinct   cos(A2, B1) = {cos(out_A2, out_B1):.4f}")
    print(f"  distinct   cos(A2, B2) = {cos(out_A2, out_B2):.4f}")


if __name__ == "__main__":
    main()
