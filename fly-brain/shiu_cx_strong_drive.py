"""Last-ditch CX probe: does STRONGER drive + LONGER window engage EPG recurrence on real W?

Prior test (shiu_cx_bump_position.py, 200 Hz, 100 ms): 47/47 single-EPG
drives produced zero recurrent EPG spikes. This version escalates on
both axes to see if the ring-attractor recurrence activates at all on
real Shiu W, even in regimes outside normal biological range.

Two variants run per drive:
  (a) 500 Hz drive, 500 ms window  — 5x higher drive, 5x longer
  (b) drive 5 adjacent EPGs simultaneously at 500 Hz for 500 ms — a
      localized bump, closer to biologically plausible initial condition

If (a) and (b) both give zero recurrent EPG spikes, the paper's
rotation claim is unambiguously not salvageable on this substrate at
the sub-circuit level. If (b) shows recurrent activity, the ring
engages with multi-neuron drive and we have a narrower but honest claim.
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

N_NEURONS = 138639


def get_epg_indices():
    ct = pd.read_csv(CELL_TYPES_PATH)
    epg_ids = set(ct[ct["primary_type"] == "EPG"]["root_id"].astype(str))
    comp = pd.read_csv(COMP_PATH, index_col=0)
    shiu_ids = comp.index.astype(str)
    return np.array([i for i, fid in enumerate(shiu_ids) if fid in epg_ids])


def build_rates(driven_indices, rate_hz):
    rates = torch.zeros(1, N_NEURONS, dtype=torch.float32)
    rates[0, driven_indices] = rate_hz
    return rates


def run_once(model, rates, seed, device, num_steps):
    torch.manual_seed(seed)
    gen = torch.Generator(device=device).manual_seed(seed)
    conductance, delay_buffer, spikes, v, refrac = model.state_init()
    rates_d = rates.to(device)
    counts = torch.zeros(1, N_NEURONS, dtype=torch.float32, device=device)
    for _ in range(num_steps):
        conductance, delay_buffer, spikes, v, refrac = model(
            rates_d, conductance, delay_buffer, spikes, v, refrac, generator=gen,
        )
        counts += spikes
    return counts[0].detach().cpu().numpy()


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

    # ------------------------------------------------------------
    # Variant A: single-EPG drive, 500 Hz, 500 ms. 10 samples.
    # ------------------------------------------------------------
    print(f"\n=== Variant A: single-EPG drive, 500 Hz, 500 ms (10 samples) ===")
    rate_A, tms_A = 500.0, 500.0
    steps_A = int(tms_A / DT)
    samples = np.linspace(0, E - 1, 10, dtype=int)
    t = perf_counter()
    max_recurrent_A = []
    total_recurrent_A = []
    for k in samples:
        out = run_once(model, build_rates([epg_idx[k]], rate_A), seed=10000 + int(k),
                       device=device, num_steps=steps_A)
        epg_out = out[epg_idx].copy()
        direct = epg_out[k]
        epg_out[k] = 0  # mask driven neuron
        max_rec = float(epg_out.max())
        tot_rec = float(epg_out.sum())
        max_recurrent_A.append(max_rec)
        total_recurrent_A.append(tot_rec)
        print(f"  drive EPG {int(k):2d}: direct={direct:.0f}, max-recurrent={max_rec:.0f}, "
              f"total-recurrent={tot_rec:.0f}, active-other-EPGs={int((epg_out>0).sum())}")
    print(f"  {len(samples)} drives in {perf_counter()-t:.1f}s")
    print(f"  summary: mean total-recurrent = {np.mean(total_recurrent_A):.1f}, "
          f"max total-recurrent = {np.max(total_recurrent_A):.0f}")

    # ------------------------------------------------------------
    # Variant B: 5 adjacent EPGs (indices k..k+4), 500 Hz, 500 ms.
    # ------------------------------------------------------------
    print(f"\n=== Variant B: 5 adjacent EPGs, 500 Hz, 500 ms (5 samples) ===")
    rate_B, tms_B = 500.0, 500.0
    steps_B = int(tms_B / DT)
    t = perf_counter()
    max_recurrent_B = []
    for k in [0, 10, 20, 30, 40]:
        drive_pos = np.arange(k, min(k + 5, E))
        drive_neurons = epg_idx[drive_pos]
        out = run_once(model, build_rates(drive_neurons, rate_B), seed=20000 + k,
                       device=device, num_steps=steps_B)
        epg_out = out[epg_idx].copy()
        # mask direct drives
        mask = np.ones(E, dtype=bool)
        mask[drive_pos] = False
        recurrent = epg_out[mask]
        direct_sum = epg_out[~mask].sum()
        max_rec = float(recurrent.max()) if recurrent.size > 0 else 0.0
        tot_rec = float(recurrent.sum())
        max_recurrent_B.append(max_rec)
        n_rec_active = int((recurrent > 0).sum())
        print(f"  drive EPGs {drive_pos.tolist()}: direct-sum={direct_sum:.0f}, "
              f"max-recurrent={max_rec:.0f}, total-recurrent={tot_rec:.0f}, "
              f"active-other-EPGs={n_rec_active}/{recurrent.size}")
    print(f"  {5} drives in {perf_counter()-t:.1f}s")

    # ------------------------------------------------------------
    # Verdict
    # ------------------------------------------------------------
    print(f"\n=== VERDICT ===")
    a_fires = any(r > 0 for r in max_recurrent_A)
    b_fires = any(r > 0 for r in max_recurrent_B)
    print(f"  Variant A (single-EPG @ 500Hz 500ms): "
          f"{'RECURRENT FIRING DETECTED' if a_fires else 'no recurrent firing'}")
    print(f"  Variant B (5-EPG cluster @ 500Hz 500ms): "
          f"{'RECURRENT FIRING DETECTED' if b_fires else 'no recurrent firing'}")


if __name__ == "__main__":
    main()
