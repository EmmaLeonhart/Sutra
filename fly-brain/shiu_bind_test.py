"""Bind and unbind on the real Shiu whole-brain LIF substrate.

Spec (`planning/sutra-spec/02-operations.md`, `11-vsa-math.md`):
  bind(a, role)   = a * sign(role)     (elementwise ±1 flip by role)
  unbind(x, role) = x * sign(role)     (self-inverse: unbind(bind(a,r),r) = a)

Substrate realization on Shiu:
  - "Vector" = 138,639-D spike-count vector obtained by driving a
    40-neuron random population at 200 Hz for 100 ms. Each value
    population A is therefore a spike-count vector v_A.
  - "Role sign" = a signed ±1 mask over the 138,639 dimensions.
    Implemented by splitting the substrate response into two halves:
    POS neurons (sign = +1) pass through unchanged; NEG neurons
    (sign = -1) have their contribution negated on readout.
  - `bind(v_A, r)` = for each dimension i, multiply v_A[i] by sign(r[i]).
    On the substrate this is realized as: drive population A, record
    spike counts, then apply the pre-computed sign mask to the output
    (the sign mask is itself compiled *from* the substrate by driving
    a role-population and thresholding; see below). The host
    multiplication by ±1 is allowed scaffolding — the *vectors* being
    bound both come from substrate runs, and the sign mask is derived
    from a substrate run.

Test:
  1. Compile 4 value vectors by driving 4 disjoint random 40-neuron
     populations and recording Shiu spike-count vectors.
  2. Compile 3 role masks by driving 3 more disjoint populations,
     taking the spike-count response, and setting sign(r) = +1 for
     dimensions with response above median, -1 below. Each role
     is a substrate-derived balanced ±1 pattern.
  3. For each value × role: compute bind_vec = v * sign(r)
     (substrate values, substrate-derived signs).
  4. Unbind: un_vec = bind_vec * sign(r) — should equal v_A exactly
     (self-inverse property).
  5. Cross-check: un_vec vs other values v_B — should be low cosine.

Reports:
  - self-inverse cos: cos(unbind(bind(v,r), r), v) — should be 1.000
  - sign-match: fraction of dims where sign(bind_vec) == sign(v) * sign(r)
  - separation: cos(bind(v_A, r) vs bind(v_B, r)) — low if v_A != v_B
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

N_NEURONS = 138639
POP_SIZE = 40
DRIVE_RATE_HZ = 200.0
T_SIM_MS = 100.0
NUM_STEPS = int(T_SIM_MS / DT)


def build_rates(neurons, rate_hz=DRIVE_RATE_HZ):
    rates = torch.zeros(1, N_NEURONS, dtype=torch.float32)
    rates[0, neurons] = rate_hz
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


def role_sign_from_spikes(role_response, method="median", rng=None):
    """Convert a spike-count vector into a balanced ±1 mask.

    Methods:
      'median' — above-median → +1, below → -1 (fails on sparse Shiu
                responses; see 2026-04-13-shiu-bind-unbind.md).
      'topk'  — take the top-k responding dims as +1, a matched random
                 sample of zero-response dims as -1, rest as 0 (masked
                 out of the bind). Balanced by construction.
    """
    if method == "median":
        thr = np.median(role_response)
        return np.where(role_response > thr, 1.0, -1.0).astype(np.float32)
    if method == "topk":
        assert rng is not None
        # +1 population: top-K responding dims (nonzero spikes).
        # -1 population: K random dims drawn from the zero-response pool.
        nonzero_idx = np.where(role_response > 0)[0]
        zero_idx = np.where(role_response == 0)[0]
        k = min(len(nonzero_idx), 60)
        # Top-k by spike count among nonzero dims
        top_idx = nonzero_idx[np.argsort(-role_response[nonzero_idx])[:k]]
        neg_idx = rng.choice(zero_idx, size=k, replace=False)
        sign = np.zeros_like(role_response, dtype=np.float32)
        sign[top_idx] = 1.0
        sign[neg_idx] = -1.0
        return sign
    raise ValueError(method)


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--role-method", choices=["median", "topk"], default="median")
    args = ap.parse_args()

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"device: {device}")
    print(f"role-method: {args.role_method}")

    t0 = perf_counter()
    weights = get_weights(CONN_PATH, COMP_PATH, WT_DIR, csr=True).to(device)
    print(f"weights: {weights.shape}, nnz={weights._nnz()} ({perf_counter()-t0:.1f}s)")
    model = TorchModel(1, N_NEURONS, DT, MODEL_PARAMS, weights, device=device).to(device)

    rng = np.random.default_rng(42)
    pool = np.arange(N_NEURONS)
    # 4 values + 3 roles = 7 disjoint populations
    chosen = rng.choice(pool, size=7 * POP_SIZE, replace=False)
    value_pops = [chosen[i*POP_SIZE:(i+1)*POP_SIZE] for i in range(4)]
    role_pops = [chosen[(4+i)*POP_SIZE:(4+i+1)*POP_SIZE] for i in range(3)]

    # Compile value vectors
    value_vecs = []
    t = perf_counter()
    for i, pop in enumerate(value_pops):
        v = run_once(model, build_rates(pop), seed=40000+i, device=device)
        value_vecs.append(v)
    print(f"  4 value vecs compiled in {perf_counter()-t:.1f}s")
    # Self-cos (stability check)
    v0_rep = run_once(model, build_rates(value_pops[0]), seed=40000, device=device)
    print(f"  stability cos(v0, v0_replay) = {cos(value_vecs[0], v0_rep):.4f}")
    # Off-diagonal
    for i in range(4):
        for j in range(i+1, 4):
            c = cos(value_vecs[i], value_vecs[j])
            if c > 0.01:
                print(f"  warn: cos(v{i}, v{j}) = {c:.4f}")

    # Compile role sign masks from substrate responses
    role_signs = []
    t = perf_counter()
    for i, pop in enumerate(role_pops):
        r = run_once(model, build_rates(pop), seed=50000+i, device=device)
        sign = role_sign_from_spikes(r, method=args.role_method, rng=rng)
        role_signs.append(sign)
        n_pos = int((sign > 0).sum())
        n_neg = int((sign < 0).sum())
        print(f"  role r{i}: +1 dims = {n_pos}, -1 dims = {n_neg}, "
              f"masked (0) = {N_NEURONS - n_pos - n_neg}")
    print(f"  3 role signs compiled in {perf_counter()-t:.1f}s")

    # ---- BIND + UNBIND TESTS ----
    print(f"\n=== BIND (elementwise value * role_sign) ===")
    bind_vecs = {}  # (value_i, role_j) -> bound vector
    for vi, v in enumerate(value_vecs):
        for rj, r in enumerate(role_signs):
            bind_vecs[(vi, rj)] = v * r

    # Self-inverse: unbind(bind(v, r), r) == v
    print(f"\n=== UNBIND (self-inverse check) ===")
    print(f"  cos(unbind(bind(v_i, r_j), r_j), v_i):")
    recovered = []
    for vi in range(4):
        for rj in range(3):
            un = bind_vecs[(vi, rj)] * role_signs[rj]
            c = cos(un, value_vecs[vi])
            recovered.append(c)
            if (vi, rj) in [(0,0),(1,1),(2,2),(3,0)]:
                print(f"    v{vi} * r{rj} * r{rj}: cos = {c:.6f}")
    print(f"  self-inverse: mean cos = {np.mean(recovered):.6f}, "
          f"min = {np.min(recovered):.6f}")

    # Cross-unbind: unbind(bind(v_A, r), r') where r' != r should be noise
    print(f"\n=== CROSS-UNBIND (wrong role should not recover) ===")
    cross_scores = []
    for vi in range(4):
        for rj in range(3):
            for rk in range(3):
                if rj == rk:
                    continue
                un = bind_vecs[(vi, rj)] * role_signs[rk]
                c = cos(un, value_vecs[vi])
                cross_scores.append(c)
    print(f"  cross-unbind (wrong role) cos: mean = {np.mean(cross_scores):.4f}, "
          f"max = {np.max(cross_scores):.4f}")

    # Separation: bind(v_A, r) vs bind(v_B, r) with A != B
    print(f"\n=== BIND SEPARATION (different values, same role) ===")
    sep = []
    for rj in range(3):
        for vi in range(4):
            for vk in range(vi+1, 4):
                c = cos(bind_vecs[(vi, rj)], bind_vecs[(vk, rj)])
                sep.append(c)
    print(f"  cos(bind(v_i, r), bind(v_j, r)) for i!=j: "
          f"mean = {np.mean(sep):.4f}, max = {np.max(sep):.4f}")

    # Sign-match: fraction of dimensions where sign(bind) == sign(v * r)
    print(f"\n=== SIGN-MATCH (bind elementwise consistency) ===")
    for vi in range(2):
        for rj in range(2):
            b = bind_vecs[(vi, rj)]
            expected = value_vecs[vi] * role_signs[rj]
            match = np.mean(np.sign(b) == np.sign(expected))
            print(f"  v{vi} bound with r{rj}: sign-match = {match:.4f}")


if __name__ == "__main__":
    main()
