"""
Can the FlyWire CX EPG->EPG recurrent matrix act as a rotation operator
for Sutra's geometric loops?

Context: the paper's geometric loops currently use a synthetic Givens
rotation R. The usual real-wiring candidate ALPN->LHLN (rank 415,
cond 1e16, compressive) cannot rotate. But the survey in
survey_rotation_candidates.py found the EPG->EPG recurrent matrix
(51 neurons, effective rank 49, cond=97, off_diag=0.508) is an order
of magnitude closer to orthogonal than anything else in FlyWire.

This script takes the real EPG->EPG weight matrix W, computes its
nearest rotation matrix Q via polar decomposition (W = QP, Q
orthogonal, P symmetric positive semidefinite), and measures:

  1. How close the biological W is to its nearest rotation Q
     (Frobenius distance; smaller = more rotation-like).
  2. Whether iterating Q (Q^i) preserves vector norm and angles —
     the defining property of rotation — on random test vectors.
  3. Whether Q can be used in place of synthetic Givens R in a
     geometric-loop toy test: does Q^3 v produce a vector
     distinguishable from Q^2 v and Q^4 v under cosine similarity?

If Q iterates cleanly, the story changes from "we use a synthetic
rotation because the connectome cannot rotate" to "the rotation
operator in our geometric loops is derived from the real CX recurrent
projection, via polar decomposition to the nearest orthogonal matrix."
"""

from __future__ import annotations

import sys
try:
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import numpy as np
from flywire_loader import load_flywire


def build_epg_to_epg(fw) -> np.ndarray:
    """Extract dense 51x51 EPG->EPG synapse count matrix from FlyWire."""
    epg_types = ["EPG", "EPGt"]
    idxs = []
    for t in epg_types:
        idx = fw.neurons_with_type(t)
        if len(idx):
            idxs.append(idx)
    all_idx = np.unique(np.concatenate(idxs))
    W = fw.counts[all_idx, :][:, all_idx].toarray().astype(np.float64)
    return W


def nearest_rotation(W: np.ndarray) -> tuple[np.ndarray, dict]:
    """Nearest proper rotation in SO(n) to W (Kabsch-corrected polar
    decomposition).

    Plain polar decomposition W = Q P via SVD can yield det(Q) = -1
    (a rotoinversion) depending on W. block_diag composition across
    motifs then inherits det = (-1)^(# rotoinversion blocks), which is
    -1 for the paper's 140-D EPG+hDelta Q — a genuine construction bug
    that capped the spiking cosine readout at target k. Kabsch fix: if
    det(U V^T) < 0 after the SVD, flip the sign on the last singular
    direction so the returned Q lives in SO(n). See
    planning/findings/2026-04-13-140D-spiking-cosine-v2-9-of-10.md.
    """
    U, s, Vt = np.linalg.svd(W, full_matrices=False)
    D = np.eye(len(s))
    if np.linalg.det(U @ Vt) < 0:
        D[-1, -1] = -1.0
    Q = U @ D @ Vt
    # Diagnostics
    P = Vt.T @ D @ np.diag(s) @ Vt  # symmetric psd part, post sign correction
    err_Q = np.linalg.norm(W - Q, "fro")
    norm_W = np.linalg.norm(W, "fro")
    QtQ = Q.T @ Q
    off_I = np.linalg.norm(QtQ - np.eye(len(QtQ)), "fro")
    det_Q = np.linalg.det(Q)
    return Q, {
        "frob_W": norm_W,
        "frob_W_minus_Q": err_Q,
        "rel_err": err_Q / norm_W,
        "Q_orthogonality_residual": off_I,
        "det_Q": det_Q,
        "sv_min": float(s.min()),
        "sv_max": float(s.max()),
        "cond": float(s.max() / s.min()),
    }


def measure_rotation_behavior(Q: np.ndarray, n_trials: int = 50,
                              rng=None) -> dict:
    """Check that Q^i preserves vector norm + that iterated applications
    produce angularly distinct states."""
    if rng is None:
        rng = np.random.RandomState(42)
    dim = Q.shape[0]
    norm_ratios = []
    distinct_cos = []  # cos(Q^0 v, Q^k v) — should decrease with k
    for _ in range(n_trials):
        v = rng.randn(dim)
        v /= np.linalg.norm(v)
        current = v.copy()
        for k in range(1, 11):
            current = Q @ current
            norm_ratios.append(np.linalg.norm(current))
            if k in (1, 3, 5, 7, 10):
                cos = float(v @ current / (np.linalg.norm(v) *
                                           np.linalg.norm(current) + 1e-12))
                distinct_cos.append((k, cos))
    norm_arr = np.array(norm_ratios)
    by_k: dict[int, list[float]] = {}
    for k, c in distinct_cos:
        by_k.setdefault(k, []).append(c)
    return {
        "norm_mean": float(norm_arr.mean()),
        "norm_std": float(norm_arr.std()),
        "cos_by_k": {k: (float(np.mean(v)), float(np.std(v)))
                     for k, v in sorted(by_k.items())},
    }


def loop_resolution_test(Q: np.ndarray, rng=None) -> dict:
    """Can we distinguish Q^3 v from Q^2 v, Q^4 v by cosine? This is the
    geometric-loop resolution question: each rotation step must produce
    a state angularly separated from neighbors."""
    if rng is None:
        rng = np.random.RandomState(1234)
    dim = Q.shape[0]
    v = rng.randn(dim)
    v /= np.linalg.norm(v)
    states = [v.copy()]
    current = v.copy()
    for _ in range(10):
        current = Q @ current
        states.append(current.copy())
    states = [s / (np.linalg.norm(s) + 1e-12) for s in states]
    # cos similarity between adjacent iterations
    adj = [float(states[i] @ states[i + 1]) for i in range(len(states) - 1)]
    # cos similarity between Q^3 and Q^k for k in 0..10
    cos_to_3 = [float(states[3] @ states[k]) for k in range(len(states))]
    return {
        "adj_cos_mean": float(np.mean(adj)),
        "adj_cos_min": float(np.min(adj)),
        "adj_cos_max": float(np.max(adj)),
        "cos_to_step3": cos_to_3,
    }


def main():
    print("Loading FlyWire v783...")
    fw = load_flywire(verbose=False)
    print(f"  {fw.n_neurons} neurons, {fw.n_connections} connections\n")

    print("Extracting EPG -> EPG recurrent weight matrix...")
    W = build_epg_to_epg(fw)
    print(f"  shape = {W.shape}, nnz = {int((W > 0).sum())}, "
          f"||W||_F = {np.linalg.norm(W, 'fro'):.1f}\n")

    print("Polar decomposition W = Q P (Q = nearest orthogonal matrix)...")
    Q, diag = nearest_rotation(W)
    print(f"  ||W - Q||_F / ||W||_F = {diag['rel_err']:.3f}  "
          f"(lower = W is more rotation-like)")
    print(f"  ||Q^T Q - I||_F       = {diag['Q_orthogonality_residual']:.2e}  "
          f"(should be ~0)")
    print(f"  det(Q)                = {diag['det_Q']:+.6f}  "
          f"(+1 = proper rotation, -1 = rotation+reflection)")
    print(f"  W singular values:   min={diag['sv_min']:.2f}  "
          f"max={diag['sv_max']:.2f}  cond={diag['cond']:.1f}\n")

    print("Behavioral test: does Q^i preserve norm on random vectors?")
    beh = measure_rotation_behavior(Q)
    print(f"  mean ||Q^k v||  =  {beh['norm_mean']:.4f}  "
          f"(should be exactly 1.0 for pure rotation)")
    print(f"  std ||Q^k v||   =  {beh['norm_std']:.2e}")
    print(f"  cos(v, Q^k v) by k:")
    for k, (m, s) in beh["cos_by_k"].items():
        print(f"    k={k:2d}  mean={m:+.3f}  std={s:.3f}")
    print()

    print("Loop resolution test: are Q^i states angularly distinct?")
    res = loop_resolution_test(Q)
    print(f"  adjacent-step cos  mean={res['adj_cos_mean']:.3f}  "
          f"min={res['adj_cos_min']:.3f}  max={res['adj_cos_max']:.3f}")
    print(f"  cos(Q^3 v, Q^k v) for k=0..10:")
    for k, c in enumerate(res['cos_to_step3']):
        print(f"    k={k:2d}  cos={c:+.3f}")
    print()

    gate_rotation = (
        diag["Q_orthogonality_residual"] < 1e-8
        and abs(abs(diag["det_Q"]) - 1.0) < 1e-6
        and abs(beh["norm_mean"] - 1.0) < 1e-3
    )
    gate_useful = res["adj_cos_max"] < 0.99  # states actually separate
    print("=" * 60)
    print(f"Q is a proper orthogonal matrix:  {'YES' if gate_rotation else 'NO'}")
    print(f"Iterated Q produces distinct states: {'YES' if gate_useful else 'NO'}")
    print(f"Biological W is {100 * diag['rel_err']:.1f}% away from its "
          f"nearest rotation (Frobenius, relative)")
    print("=" * 60)


if __name__ == "__main__":
    main()
