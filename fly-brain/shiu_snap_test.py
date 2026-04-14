"""Test Sutra `snap` / cleanup on the real Shiu LIF whole-brain model.

Question: given a codebook of K prototype responses (one per input
pattern), can we recover the correct prototype from a noisy query
response? A "noisy query" here is an independent Poisson-seed rerun
of one of the prototype inputs. Snap = argmax cos(query, codebook).

If stability is ~0.96 and distinctness is ~0.00 (per the substrate
probe and bundle test), this should be K/K correct — the prototype
self-cosine dominates any off-diagonal by a huge margin.

Protocol:
  1. Pick K disjoint 50-neuron input patterns p_1..p_K.
  2. Compile codebook: run each pattern once with seed S_i, record
     out_i as prototype vector for class i.
  3. For each pattern i, run with a DIFFERENT Poisson seed, get query
     q_i, predict argmax_j cos(q_i, out_j). Correct iff argmax == i.
  4. Report K/K accuracy and the cosine gap (best vs second-best).

We also run the K=16 case because that is the scenario count the
fuzzy-conditional experiment uses; reaching 16/16 on real W is the
apples-to-apples equivalent of the polar-decomp fuzzy_conditional
560/560 result.
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

K_CLASSES = 16


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


def main():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"device: {device}")

    t0 = perf_counter()
    weights = get_weights(CONN_PATH, COMP_PATH, WT_DIR, csr=True).to(device)
    print(f"weights: {weights.shape}, nnz={weights._nnz()} ({perf_counter()-t0:.1f}s)")

    model = TorchModel(1, N_NEURONS, DT, MODEL_PARAMS, weights, device=device).to(device)

    rng = np.random.default_rng(42)
    used = np.array([], dtype=int)
    patterns = []
    for k in range(K_CLASSES):
        while True:
            p = rng.choice(N_NEURONS, size=N_INPUT, replace=False)
            if np.intersect1d(p, used).size == 0:
                break
        patterns.append(p)
        used = np.concatenate([used, p])
    assert used.size == K_CLASSES * N_INPUT

    print(f"\ncompiling {K_CLASSES}-class codebook ({N_INPUT} neurons/class, disjoint)")
    t = perf_counter()
    codebook = []
    for k in range(K_CLASSES):
        out = run_once(model, build_rates(patterns[k]), seed=2000 + k, device=device)
        codebook.append(out)
    codebook = np.stack(codebook, axis=0)  # (K, N_NEURONS)
    print(f"  compile: {perf_counter()-t:.1f}s")

    norms = np.linalg.norm(codebook, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    codebook_unit = codebook / norms

    print(f"\nrunning {K_CLASSES} queries (fresh Poisson seeds, same inputs)")
    t = perf_counter()
    correct = 0
    gaps = []
    for k in range(K_CLASSES):
        q = run_once(model, build_rates(patterns[k]), seed=5000 + k, device=device)
        qn = np.linalg.norm(q)
        q_unit = q / qn if qn > 0 else q
        scores = codebook_unit @ q_unit  # (K,)
        pred = int(np.argmax(scores))
        top2 = np.sort(scores)[-2:]
        gap = float(top2[1] - top2[0])
        gaps.append(gap)
        ok = "OK " if pred == k else "ERR"
        print(f"  class {k:2d}: pred={pred:2d}  cos_best={scores[pred]:.4f}  "
              f"gap={gap:.4f}  {ok}")
        if pred == k:
            correct += 1
    print(f"  query: {perf_counter()-t:.1f}s")

    print(f"\nSNAP RESULT: {correct}/{K_CLASSES} correct")
    print(f"  mean best-vs-second-best gap: {np.mean(gaps):.4f}")
    print(f"  min  best-vs-second-best gap: {np.min(gaps):.4f}")


if __name__ == "__main__":
    main()
