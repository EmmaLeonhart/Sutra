"""
Spiking loop test on the composed 713-D real-wiring Q.

Hypothesis: the 3/5 spiking result with the 51-D EPG Q
(`real_rotation_epg_loop_spiking.py`) fails on two seeds because
`cos(Q v, Q^3 v) = cos(v, Q^2 v)` is numerically close to 1 for the
EPG recurrent spectrum on those seeds. If that is the culprit,
running the same test with Q composed block-diagonally from four
FlyWire motifs (EPG + LH + vDelta + hDelta, total 713-D, built by
`real_rotation_composed.py`) should help: Q^2 is now
block-diagonal across four independent subspaces, and cos(v, Q^2 v)
averages across all four blocks — so unless *every* block's spectrum
has Q^2 near identity for this particular v_0, the numpy-level gap
between cos(state_1, proto) and cos(state_3, proto) widens and
survives spike noise.

If this brings spiking loop performance up to 5/5, the fix is
principled (mixed spectrum from multiple biological motifs, no
tuning of thresholds). If it doesn't, the bottleneck is cosine
readout SNR rather than spectral structure, and we should move to
KC-Jaccard termination.

Wall clock note: 713x713 synapse matrix is ~500k synapses, much
larger than the 51x51 EPG case. SIM_MS held at 3000ms for
apples-to-apples comparison.
"""

from __future__ import annotations

import sys
import time
try:
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import numpy as np
from scipy.linalg import block_diag

from flywire_loader import load_flywire
from real_rotation_epg import nearest_rotation
from real_rotation_composed import build_square_motif
import neural_vsa
from neural_vsa import neural_linear_map

neural_vsa.SIM_MS = 3000.0


def build_composed_Q(fw):
    motifs = [
        ("CX EPG->EPG",       ["EPG", "EPGt"], ["EPG", "EPGt"]),
        ("LH LH->LH",         [f"LH{t}" for t in ["AV4a4", "AV5a3", "AV6a4",
                                                   "PV5a1", "PV5b1", "PV5b2",
                                                   "PV5b3", "PV5c1"]],
                              [f"LH{t}" for t in ["AV4a4", "AV5a3", "AV6a4",
                                                   "PV5a1", "PV5b1", "PV5b2",
                                                   "PV5b3", "PV5c1"]]),
        ("FB vDelta->vDelta", [f"vDelta{c}" for c in "ABCDEFGHIJKLMN"] +
                               ["vDeltaA_a", "vDeltaA_b"],
                              [f"vDelta{c}" for c in "ABCDEFGHIJKLMN"] +
                               ["vDeltaA_a", "vDeltaA_b"]),
        ("FB hDelta->hDelta", [f"hDelta{c}" for c in "ABCDEFGHIJKLMN"],
                              [f"hDelta{c}" for c in "ABCDEFGHIJKLMN"]),
    ]
    Qs = []
    for name, pre, post in motifs:
        W = build_square_motif(fw, pre, post, name)
        if W.size == 0 or np.linalg.norm(W) < 1e-8:
            continue
        Q, _ = nearest_rotation(W)
        Qs.append(Q)
    return block_diag(*Qs)


def spiking_counting(Q: np.ndarray, target_k: int, max_iters: int = 6,
                     seed: int = 0) -> dict:
    rng = np.random.RandomState(seed)
    dim = Q.shape[0]
    v0 = rng.randn(dim)
    v0 /= np.linalg.norm(v0)
    proto = np.linalg.matrix_power(Q, target_k) @ v0
    proto /= np.linalg.norm(proto)
    state = v0.copy()
    cos_by_k = [float(state @ proto)]
    for k in range(1, max_iters + 1):
        state = neural_linear_map(Q, state, seed=seed * 31 + k)
        n = np.linalg.norm(state)
        if n < 1e-9:
            break
        s_norm = state / n
        cos_by_k.append(float(s_norm @ proto))
        state = s_norm
    argmax_k = int(np.argmax(cos_by_k))
    return {"target_k": target_k, "argmax_k": argmax_k,
            "peak_cos": float(np.max(cos_by_k)),
            "cos_by_k": cos_by_k, "pass": argmax_k == target_k}


def main():
    print("Loading FlyWire + building composed Q across 4 motifs...")
    fw = load_flywire(verbose=False)
    Q = build_composed_Q(fw)
    print(f"Composed Q: shape={Q.shape}")
    QtQ = Q.T @ Q
    print(f"  ||Q^T Q - I||_F = "
          f"{np.linalg.norm(QtQ - np.eye(len(QtQ)), 'fro'):.2e}")
    print(f"  det Q = {np.linalg.det(Q):+.6f}\n")

    # Numpy baseline — what is the argmax profile before noise?
    print("Numpy baseline (5 seeds, target k=3):")
    for seed in range(5):
        rng = np.random.RandomState(seed)
        v0 = rng.randn(Q.shape[0])
        v0 /= np.linalg.norm(v0)
        proto = np.linalg.matrix_power(Q, 3) @ v0
        proto /= np.linalg.norm(proto)
        np_cos = []
        st = v0.copy()
        for k in range(7):
            s = st / np.linalg.norm(st)
            np_cos.append(float(s @ proto))
            st = Q @ st
        print(f"  seed={seed}  "
              + " ".join(f"k{i}={c:+.2f}" for i, c in enumerate(np_cos))
              + f"  argmax_k={int(np.argmax(np_cos))}")
    print()

    # Spiking
    target = 3
    max_iters = 6
    seeds = [0, 1, 2, 3, 4]
    print(f"Spiking (composed 713-D Q, target k={target}, "
          f"SIM_MS={neural_vsa.SIM_MS}, {len(seeds)} seeds)")
    t0 = time.time()
    results = []
    for seed in seeds:
        ts = time.time()
        r = spiking_counting(Q, target_k=target, max_iters=max_iters, seed=seed)
        dt = time.time() - ts
        results.append(r)
        cs = " ".join(f"k{i}={c:+.2f}" for i, c in enumerate(r["cos_by_k"]))
        print(f"  seed={seed}  argmax_k={r['argmax_k']}  "
              f"peak_cos={r['peak_cos']:+.3f}  {cs}  "
              f"{'PASS' if r['pass'] else 'FAIL'}  [{dt:.0f}s]")
    n_pass = sum(int(r["pass"]) for r in results)
    print()
    print("=" * 60)
    print(f"Composed-Q spiking counting at k={target}: {n_pass}/{len(seeds)}")
    print(f"Wall clock: {time.time() - t0:.0f}s")
    print("=" * 60)


if __name__ == "__main__":
    main()
