"""Test Sutra `bundle` on the real Shiu LIF whole-brain model.

Question: does driving two disjoint input patterns A and B
simultaneously produce a response approximately equal to the
normalized sum of A-alone and B-alone responses? If yes, bundle is
linear on real W at 100 ms and compiles trivially. If no, report
the non-linearity and document what an honest bundle operator must
look like.

Protocol:
  1. Drive A alone at 200 Hz for 100 ms, record spike-count vector out_A
  2. Drive B alone at 200 Hz for 100 ms, record spike-count vector out_B
  3. Drive A ∪ B simultaneously at 200 Hz for 100 ms, record out_AB
  4. Compute cos(out_AB, normalize(out_A + out_B))
  5. Compare to baseline: cos(out_A1, out_A2) from stability probe

Two seeds per condition to separate Poisson noise from non-linearity.
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
    print(f"weights loaded: {weights.shape}, nnz={weights._nnz()} ({perf_counter()-t0:.1f}s)")

    model = TorchModel(1, N_NEURONS, DT, MODEL_PARAMS, weights, device=device).to(device)

    rng = np.random.default_rng(42)
    A = rng.choice(N_NEURONS, size=N_INPUT, replace=False)
    B = rng.choice(N_NEURONS, size=N_INPUT, replace=False)
    while np.intersect1d(A, B).size > 0:
        B = rng.choice(N_NEURONS, size=N_INPUT, replace=False)
    AB = np.concatenate([A, B])
    assert AB.size == 2 * N_INPUT

    rA = build_rates(A)
    rB = build_rates(B)
    rAB = build_rates(AB)

    print(f"\ndriving {N_INPUT} + {N_INPUT} = {2*N_INPUT} neurons @ {DRIVE_RATE_HZ} Hz for {T_SIM_MS} ms")
    t = perf_counter()
    out_A1 = run_once(model, rA, 1000, device)
    out_A2 = run_once(model, rA, 1001, device)
    out_B1 = run_once(model, rB, 1002, device)
    out_B2 = run_once(model, rB, 1003, device)
    out_AB1 = run_once(model, rAB, 1004, device)
    out_AB2 = run_once(model, rAB, 1005, device)
    print(f"6 runs in {perf_counter()-t:.1f}s")

    def active(v): return int((v > 0).sum())
    print(f"\nactive neurons: A1={active(out_A1)} A2={active(out_A2)} "
          f"B1={active(out_B1)} B2={active(out_B2)} "
          f"AB1={active(out_AB1)} AB2={active(out_AB2)}")

    def norm(v):
        n = np.linalg.norm(v)
        return v / n if n > 0 else v

    predicted = norm(norm(out_A1) + norm(out_B1))

    print(f"\nSTABILITY (same-input Poisson-seed repeats):")
    print(f"  cos(A1, A2)   = {cos(out_A1, out_A2):.4f}")
    print(f"  cos(B1, B2)   = {cos(out_B1, out_B2):.4f}")
    print(f"  cos(AB1, AB2) = {cos(out_AB1, out_AB2):.4f}")
    print(f"\nDISTINCTNESS (disjoint inputs):")
    print(f"  cos(A1, B1)   = {cos(out_A1, out_B1):.4f}")
    print(f"\nBUNDLE LINEARITY (out_AB vs normalize(out_A + out_B)):")
    print(f"  cos(AB1, norm(A1+B1)) = {cos(out_AB1, predicted):.4f}")
    print(f"  cos(AB2, norm(A1+B1)) = {cos(out_AB2, predicted):.4f}")
    print(f"  cos(AB1, A1)          = {cos(out_AB1, out_A1):.4f}  "
          f"(should be near sqrt(2)/2 = 0.707 if linear + equal magnitude)")
    print(f"  cos(AB1, B1)          = {cos(out_AB1, out_B1):.4f}")


if __name__ == "__main__":
    main()
