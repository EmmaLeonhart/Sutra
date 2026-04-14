"""Does real W preserve EPG bump-position info in the Shiu LIF model?

The prior iterative rotate tests collapsed (both whole-brain and
CX-restricted) because direct Poisson drive masks the recurrent signal.
This test sidesteps iteration and asks the cleaner question:

  Do different drive positions on the EPG ring produce distinguishable
  EPG response patterns at 100 ms?

If yes, the ring structure is carrying positional information — the
real-W substrate for bump-based rotation is intact, and the problem
is only the iteration protocol. If no, real W does not preserve
EPG positional info even at the sub-circuit level, and the paper's
rotation claim is dead.

Protocol:
  1. For each of the 47 EPGs, drive JUST THAT ONE EPG for 100 ms
  2. Read the 47-D EPG-only spike-count vector (excluding the driven
     neuron to isolate recurrent response)
  3. Build a 47x47 cosine matrix over these responses
  4. A ring-attractor signature: cosine matrix has band structure
     (near-diagonal entries high, distant entries low)
  5. A washed-out signature: all entries ~1.0 or all ~0.0
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


def get_epg_indices():
    ct = pd.read_csv(CELL_TYPES_PATH)
    epg_ids = set(ct[ct["primary_type"] == "EPG"]["root_id"].astype(str))
    comp = pd.read_csv(COMP_PATH, index_col=0)
    shiu_ids = comp.index.astype(str)
    return np.array([i for i, fid in enumerate(shiu_ids) if fid in epg_ids])


def build_rates(driven_indices) -> torch.Tensor:
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
    E = len(epg_idx)
    print(f"EPG neurons: {E}")

    t0 = perf_counter()
    weights = get_weights(CONN_PATH, COMP_PATH, WT_DIR, csr=True).to(device)
    print(f"weights: {weights.shape}, nnz={weights._nnz()} ({perf_counter()-t0:.1f}s)")
    model = TorchModel(1, N_NEURONS, DT, MODEL_PARAMS, weights, device=device).to(device)

    print(f"\ndriving EACH EPG in isolation (200Hz, 100ms); recording 47-D EPG response")
    responses_with_drive = np.zeros((E, E), dtype=np.float32)
    t = perf_counter()
    for k in range(E):
        out = run_once(model, build_rates([epg_idx[k]]), seed=9000 + k, device=device)
        responses_with_drive[k] = out[epg_idx]
        if k % 10 == 0:
            print(f"  drive EPG {k:2d}: active EPGs = {int((responses_with_drive[k]>0).sum())}, "
                  f"driven-neuron spikes = {responses_with_drive[k][k]:.0f}, "
                  f"max-recurrent spikes = {max(x for j, x in enumerate(responses_with_drive[k]) if j != k):.0f}")
    print(f"  {E} drives in {perf_counter()-t:.1f}s")

    # Isolate recurrent response: zero out the driven-neuron entry
    recurrent = responses_with_drive.copy()
    for k in range(E):
        recurrent[k, k] = 0.0

    # Cosine on recurrent-only responses
    print(f"\nrecurrent-only EPG response: spike counts excluding the driven neuron")
    total_rec = recurrent.sum(axis=1)
    print(f"  mean recurrent spikes per drive: {total_rec.mean():.1f} "
          f"(min {total_rec.min():.0f}, max {total_rec.max():.0f})")
    print(f"  drives with zero recurrent response: {int((total_rec == 0).sum())}/{E}")

    # Full cosine matrix
    M = np.zeros((E, E), dtype=np.float32)
    for i in range(E):
        for j in range(E):
            M[i, j] = cos(recurrent[i], recurrent[j])

    mask = ~np.eye(E, dtype=bool)
    print(f"\nCOSINE MATRIX over recurrent-only responses ({E}x{E}):")
    print(f"  mean off-diagonal cos       = {M[mask].mean():.4f}")
    print(f"  min  off-diagonal cos       = {M[mask].min():.4f}")
    print(f"  max  off-diagonal cos       = {M[mask].max():.4f}")
    print(f"  fraction off-diagonal < 0.5 = {(M[mask] < 0.5).mean():.3f}")
    print(f"  fraction off-diagonal < 0.1 = {(M[mask] < 0.1).mean():.3f}")

    # Per-drive: which EPGs light up most?
    print(f"\nSAMPLE ROWS (top-5 non-driven EPG responders per driven EPG):")
    for k in [0, 10, 20, 30, 40, 46]:
        row = recurrent[k]
        top5 = np.argsort(row)[-5:][::-1]
        print(f"  drive EPG {k:2d}: top recurrent responders = "
              + ", ".join(f"EPG{i}({row[i]:.0f})" for i in top5))

    # How many distinct response patterns do we actually have?
    # Count unique drives by thresholded argmax
    argmaxes = np.array([int(np.argmax(recurrent[k])) if recurrent[k].sum() > 0 else -1
                         for k in range(E)])
    unique = len(set(argmaxes[argmaxes >= 0].tolist()))
    print(f"\nargmax responder diversity: {unique} distinct EPGs are top-responder "
          f"across {E} drives")


if __name__ == "__main__":
    main()
