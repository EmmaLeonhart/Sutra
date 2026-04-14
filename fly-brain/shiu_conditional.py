"""Fuzzy-weighted-superposition conditional branching on the Shiu LIF model.

Ports the hemibrain-MB conditional (`fuzzy_conditional.py`, 560/560 at n=35)
to the real 138,639-neuron Shiu substrate with real FlyWire v783 W.

Algorithm (per planning/sutra-spec/03-control-flow.md):
  result = sum_i w_i * behavior_vec[program_map[prototype_i]]
  where w_i = relu(cos(query_spike_vec, prototype_spike_vec_i)) normalized

Substrate realization on Shiu:
  1. Pick 4 disjoint 40-neuron "input" populations for the 4 joint
     prototypes (PH, PF, AH, AF) — smell ∈ {vinegar, clean_air} ×
     hunger ∈ {hungry, fed}. Drive each at 200 Hz for 100 ms, record
     138,639-D spike-count vector. These are the compiled prototypes.
  2. Pick 4 disjoint 40-neuron "behavior" populations for the 4
     outputs (approach, ignore, search, idle). Drive each alone and
     record spike-count vectors — the behavior codebook.
  3. For each (smell, hunger) scenario × program:
     a. Drive the matching input population → get query_vec.
     b. Compute w_i = max(0, cos(query_vec, proto_i)), normalize to
        sum to 1.
     c. Drive all 4 behavior populations simultaneously at rates
        w_i * base_rate, where the mapping from prototype-index to
        behavior-index is the program's prototype-to-behavior table.
        This is fuzzy-weighted superposition *as substrate drive*.
     d. Record result_vec, argmax cos against behavior codebook.
     e. Correct if argmax == program_map[true_proto].

Every VSA op — the bundle-as-drive, the snap-as-spike-count, the
cosine, the weighted superposition — runs on Shiu. The host does
scalar arithmetic on the scores (the "scaffolding" allowed by
planning/sutra-spec/02-operations.md) and the final argmax readout.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from time import perf_counter

import numpy as np
import pandas as pd
import torch

SHIU_REPO = Path(r"C:/Users/Immanuelle/shiu-fly-brain")
sys.path.insert(0, str(SHIU_REPO / "code"))

from run_pytorch import MODEL_PARAMS, DT, TorchModel, get_weights  # noqa: E402

CONN_PATH = SHIU_REPO / "data" / "2025_Connectivity_783.parquet"
COMP_PATH = SHIU_REPO / "data" / "2025_Completeness_783.csv"
WT_DIR = SHIU_REPO / "data"

N_NEURONS = 138639
POP_SIZE = 40
DRIVE_RATE_HZ = 200.0
T_SIM_MS = 100.0
NUM_STEPS = int(T_SIM_MS / DT)

PROTOTYPES = ["PH", "PF", "AH", "AF"]  # (present/absent) × (hungry/fed)
BEHAVIORS = ["approach", "ignore", "search", "idle"]

# Scenario ground truth: (smell, hunger) → prototype name
SCENARIOS = {
    ("vinegar", "hungry"): "PH",
    ("vinegar", "fed"): "PF",
    ("clean_air", "hungry"): "AH",
    ("clean_air", "fed"): "AF",
}

# Four programs — each is a prototype-to-behavior map
PROGRAMS = {
    "A": {"PH": "approach", "PF": "ignore", "AH": "search", "AF": "idle"},
    "B": {"PH": "search", "PF": "idle", "AH": "approach", "AF": "ignore"},
    "C": {"PH": "ignore", "PF": "approach", "AH": "idle", "AF": "search"},
    "D": {"PH": "idle", "PF": "search", "AH": "ignore", "AF": "approach"},
}


def build_rates(driven_populations, rates_hz):
    """driven_populations: list of np.ndarray[int] neuron indices.
    rates_hz: list of float, same length. Rates sum into shared dims."""
    rates = torch.zeros(1, N_NEURONS, dtype=torch.float32)
    for pop, r in zip(driven_populations, rates_hz):
        rates[0, pop] += r
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


def pick_populations(rng, n_pops, pop_size, used=None):
    """Return n_pops disjoint random populations of pop_size neurons."""
    pool = np.arange(N_NEURONS)
    if used is not None:
        pool = np.setdiff1d(pool, used, assume_unique=False)
    chosen = rng.choice(pool, size=n_pops * pop_size, replace=False)
    return [chosen[i * pop_size:(i + 1) * pop_size] for i in range(n_pops)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-runs", type=int, default=3)
    args = ap.parse_args()

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"device: {device}")

    t0 = perf_counter()
    weights = get_weights(CONN_PATH, COMP_PATH, WT_DIR, csr=True).to(device)
    print(f"weights: {weights.shape}, nnz={weights._nnz()} ({perf_counter()-t0:.1f}s)")
    model = TorchModel(1, N_NEURONS, DT, MODEL_PARAMS, weights, device=device).to(device)

    # Per-seed totals
    seed_results = []
    prog_correct = {p: 0 for p in PROGRAMS}
    prog_total = {p: 0 for p in PROGRAMS}

    for run_idx in range(args.n_runs):
        seed_base = 30000 + run_idx * 1000
        rng = np.random.default_rng(seed_base)
        print(f"\n=== run {run_idx+1}/{args.n_runs} (seed base {seed_base}) ===")

        # Pick 4 disjoint input pops (for prototypes) and 4 disjoint
        # behavior pops, non-overlapping with each other.
        proto_pops = pick_populations(rng, 4, POP_SIZE)
        used = np.concatenate(proto_pops)
        behavior_pops = pick_populations(rng, 4, POP_SIZE, used=used)
        proto_pop_map = dict(zip(PROTOTYPES, proto_pops))
        behavior_pop_map = dict(zip(BEHAVIORS, behavior_pops))

        # Compile prototype codebook: drive each input pop, record spike vec.
        proto_vecs = {}
        t = perf_counter()
        for i, name in enumerate(PROTOTYPES):
            out = run_once(
                model,
                build_rates([proto_pop_map[name]], [DRIVE_RATE_HZ]),
                seed=seed_base + 1 + i, device=device,
            )
            proto_vecs[name] = out
        # Behavior codebook: drive each behavior pop, record spike vec.
        behavior_vecs = {}
        for i, name in enumerate(BEHAVIORS):
            out = run_once(
                model,
                build_rates([behavior_pop_map[name]], [DRIVE_RATE_HZ]),
                seed=seed_base + 100 + i, device=device,
            )
            behavior_vecs[name] = out
        print(f"  compiled 4 proto + 4 behavior codebooks in {perf_counter()-t:.1f}s")

        # Sanity: off-diagonal cos between different prototype vecs.
        off = [cos(proto_vecs[a], proto_vecs[b])
               for a in PROTOTYPES for b in PROTOTYPES if a != b]
        print(f"  proto codebook: off-diag cos mean {np.mean(off):.3f}, max {np.max(off):.3f}")

        # For each (scenario × program): query -> weights -> weighted behavior drive -> argmax
        correct_this_run = 0
        total_this_run = 0
        t = perf_counter()
        for (smell, hunger), true_proto in SCENARIOS.items():
            # Query: drive the matching input pop (fresh seed).
            query_seed = seed_base + 200 + hash((smell, hunger)) % 100
            query_vec = run_once(
                model,
                build_rates([proto_pop_map[true_proto]], [DRIVE_RATE_HZ]),
                seed=query_seed, device=device,
            )
            # Weights over prototypes (clip negatives, normalize).
            raw = np.array([cos(query_vec, proto_vecs[p]) for p in PROTOTYPES])
            w = np.clip(raw, 0.0, None)
            s = w.sum()
            if s > 0:
                w = w / s
            for prog_name, prog_map in PROGRAMS.items():
                # Weighted behavior drive: each behavior pop driven at
                # w_i * DRIVE_RATE_HZ where i is the prototype that
                # maps to that behavior under this program.
                drive_pops, drive_rates = [], []
                for i, p in enumerate(PROTOTYPES):
                    b = prog_map[p]
                    drive_pops.append(behavior_pop_map[b])
                    drive_rates.append(float(w[i]) * DRIVE_RATE_HZ)
                result_vec = run_once(
                    model,
                    build_rates(drive_pops, drive_rates),
                    seed=seed_base + 300 + hash((smell, hunger, prog_name)) % 1000,
                    device=device,
                )
                scores = np.array([cos(result_vec, behavior_vecs[b])
                                   for b in BEHAVIORS])
                pred = BEHAVIORS[int(np.argmax(scores))]
                truth = prog_map[true_proto]
                ok = pred == truth
                correct_this_run += int(ok)
                total_this_run += 1
                prog_correct[prog_name] += int(ok)
                prog_total[prog_name] += 1
        print(f"  16 scenarios in {perf_counter()-t:.1f}s; "
              f"correct {correct_this_run}/{total_this_run}")
        seed_results.append((correct_this_run, total_this_run))

    # Aggregate
    total_correct = sum(c for c, _ in seed_results)
    total_scen = sum(t for _, t in seed_results)
    print(f"\n=== AGGREGATE (n={args.n_runs}) ===")
    print(f"  overall: {total_correct}/{total_scen} "
          f"({100.0*total_correct/max(total_scen,1):.1f}%)")
    accs = [c/max(t,1) for c, t in seed_results]
    print(f"  per-run acc: mean {np.mean(accs):.3f}, std {np.std(accs):.3f}")
    print("  per-program:")
    for p in PROGRAMS:
        c, t = prog_correct[p], prog_total[p]
        print(f"    {p}: {c}/{t} ({100.0*c/max(t,1):.1f}%)")


if __name__ == "__main__":
    main()
