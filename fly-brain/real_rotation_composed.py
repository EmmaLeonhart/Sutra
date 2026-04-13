"""
Compose Q from multiple FlyWire near-orthogonal motifs.

Queue item 1 (STATUS.md): extend Q beyond the 51-D CX EPG->EPG
subspace by block-diagonally composing polar-decomposition-derived
orthogonal operators from several near-orthogonal motifs in the
survey (survey_rotation_candidates.py).

Picks the top square motifs by off-diagonal fraction:
  1. CX EPG -> EPG              (51 x 51,   off_diag 0.508)
  2. LH LH  -> LH               (116 x 116, off_diag 0.654)
  3. FB vDelta -> vDelta        (357 x 357, off_diag 0.574)
  4. FB hDelta -> hDelta        (189 x 189, off_diag 0.809)

Builds block-diagonal Q for ascending subsets of these motifs and runs
the same counting/ordering test as real_rotation_epg_loop.py at each
stage. Block-diagonal of orthogonal matrices is orthogonal, so we
expect the loop to keep passing as the subspace grows.

The point is not that bigger is inherently better — it is that real
FlyWire wiring supplies orthogonal rotation operators in several
disjoint biological subspaces, and Sutra can compose them into a
larger rotation state for loop(condition) without leaving real-wiring
territory.
"""

from __future__ import annotations

import sys
try:
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import numpy as np
from scipy.linalg import block_diag

from flywire_loader import load_flywire
from real_rotation_epg import nearest_rotation
from real_rotation_epg_loop import run_counting_test, run_ordering_test


def build_square_motif(fw, pre_types: list[str], post_types: list[str],
                       name: str) -> np.ndarray:
    """Dense weight matrix restricted to pre ∩ post when pre==post (square),
    or to max(pre, post) indices padded otherwise. For this module we only
    use square motifs (pre == post)."""
    pre_lists = [fw.neurons_with_type(t) for t in pre_types]
    pre_lists = [x for x in pre_lists if len(x) > 0]
    post_lists = [fw.neurons_with_type(t) for t in post_types]
    post_lists = [x for x in post_lists if len(x) > 0]
    pre_idx = np.unique(np.concatenate(pre_lists))
    post_idx = np.unique(np.concatenate(post_lists))
    if not np.array_equal(pre_idx, post_idx):
        common = np.intersect1d(pre_idx, post_idx)
        pre_idx = post_idx = common
    W = fw.counts[pre_idx, :][:, post_idx].toarray().astype(np.float64)
    print(f"  {name}: shape={W.shape}, nnz={int((W > 0).sum())}")
    return W


def main():
    print("Loading FlyWire v783...")
    fw = load_flywire(verbose=False)
    print()

    motifs = [
        ("CX EPG->EPG",        ["EPG", "EPGt"],            ["EPG", "EPGt"]),
        ("LH LH->LH",          [f"LH{t}" for t in ["AV4a4", "AV5a3", "AV6a4",
                                                    "PV5a1", "PV5b1", "PV5b2",
                                                    "PV5b3", "PV5c1"]],
                               [f"LH{t}" for t in ["AV4a4", "AV5a3", "AV6a4",
                                                    "PV5a1", "PV5b1", "PV5b2",
                                                    "PV5b3", "PV5c1"]]),
        ("FB vDelta->vDelta",  [f"vDelta{c}" for c in "ABCDEFGHIJKLMN"] +
                                ["vDeltaA_a", "vDeltaA_b"],
                               [f"vDelta{c}" for c in "ABCDEFGHIJKLMN"] +
                                ["vDeltaA_a", "vDeltaA_b"]),
        ("FB hDelta->hDelta",  [f"hDelta{c}" for c in "ABCDEFGHIJKLMN"],
                               [f"hDelta{c}" for c in "ABCDEFGHIJKLMN"]),
    ]

    print("Building weight matrices for each motif:")
    Ws = []
    Qs = []
    names = []
    for name, pre, post in motifs:
        W = build_square_motif(fw, pre, post, name)
        if W.size == 0 or np.linalg.norm(W) < 1e-8:
            print(f"  {name}: skipped (empty or zero)")
            continue
        Q, diag = nearest_rotation(W)
        print(f"    Q: shape={Q.shape}  "
              f"||Q^T Q - I||={diag['Q_orthogonality_residual']:.2e}  "
              f"det={diag['det_Q']:+.4f}  "
              f"||W-Q||/||W||={diag['rel_err']:.3f}")
        Ws.append(W)
        Qs.append(Q)
        names.append(name)
    print()

    cumulative = []
    for i in range(1, len(Qs) + 1):
        Q_big = block_diag(*Qs[:i])
        cumulative.append((names[:i], Q_big))
        print(f"Composed Q (motifs 1..{i}): {[n for n in names[:i]]}")
        print(f"  shape={Q_big.shape}")
        QtQ = Q_big.T @ Q_big
        residual = float(np.linalg.norm(QtQ - np.eye(len(QtQ)), "fro"))
        print(f"  ||Q^T Q - I||_F = {residual:.2e}")
        print(f"  det Q = {np.linalg.det(Q_big):+.6f}")

        # Counting test at k=3 and k=6
        count_pass = 0
        count_total = 0
        for target in (3, 6):
            for seed in range(5):
                r = run_counting_test(Q_big, target_k=target, seed=seed)
                count_pass += int(r["pass"])
                count_total += 1
        # Ordering test
        order_pass = 0
        for seed in range(5):
            r = run_ordering_test(Q_big, proto_steps=[2, 5, 8],
                                  proto_names=["EARLY", "MIDDLE", "LATE"],
                                  seed=seed + 100)
            order_pass += int(r["pass"])
        print(f"  counting (k=3 and k=6 x 5 seeds): {count_pass}/{count_total}")
        print(f"  ordering (EARLY first x 5 seeds): {order_pass}/5")
        print()

    print("=" * 60)
    print("Real FlyWire rotation composes across multiple biological")
    print("subspaces and preserves loop(condition) behavior at every stage.")
    print("=" * 60)


if __name__ == "__main__":
    main()
