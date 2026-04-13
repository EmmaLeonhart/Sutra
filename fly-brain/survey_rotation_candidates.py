"""
Survey candidate FlyWire connectome motifs for near-orthogonal rotation.

The question: can any real biological weight matrix W between two neuron
populations act as a rotation — i.e. W^T W ≈ I up to scale — well enough
to implement R^i · v iteration over the whole vector space, not just a
1-D ring angle?

We score each candidate on:
  - shape (rows x cols, rank cap = min)
  - condition number (tighter = closer to unitary after normalization)
  - singular-value flatness: sv_max / sv_median, sv_max / sv_min over
    nonzero SVs. Ratio 1.0 = perfect rotation.
  - off-diagonal energy of W^T W / ||W||^2 after row/col normalization
    (lower = closer to orthogonal)

This is not trying to make a single motif BE the rotation — just to
find which motifs are least hostile to the operation so we know where
to target the real-wiring rotation work.
"""

from __future__ import annotations

import sys
import io
import numpy as np
from pathlib import Path

try:
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from flywire_loader import load_flywire


def score_matrix(W: np.ndarray, name: str) -> dict:
    """Return a dict of orthogonality metrics for a dense weight matrix W."""
    rows, cols = W.shape
    rank_cap = min(rows, cols)

    fro = np.linalg.norm(W, "fro")
    if fro < 1e-12:
        return {"name": name, "shape": (rows, cols), "rank_cap": rank_cap,
                "status": "zero matrix", "cond": float("inf"),
                "sv_flatness_med": float("inf"), "off_diag_frac": float("inf")}

    # SVD — truncate at rank_cap
    try:
        svs = np.linalg.svd(W, compute_uv=False)
    except np.linalg.LinAlgError:
        return {"name": name, "shape": (rows, cols), "rank_cap": rank_cap,
                "status": "svd failed"}
    sv_max = svs[0]
    nonzero = svs[svs > 1e-8 * sv_max]
    effective_rank = len(nonzero)
    sv_min_nz = nonzero[-1] if len(nonzero) else 0.0
    sv_med = np.median(nonzero) if len(nonzero) else 0.0
    cond = sv_max / sv_min_nz if sv_min_nz > 0 else float("inf")
    flatness = sv_max / sv_med if sv_med > 0 else float("inf")

    # Orthogonality residual: scale W so largest sv is 1, then measure
    # off-diagonal mass of W^T W.
    Ws = W / sv_max
    G = Ws.T @ Ws
    diag_mass = float(np.sum(np.diag(G) ** 2))
    total_mass = float(np.sum(G ** 2))
    off_diag_frac = (total_mass - diag_mass) / total_mass if total_mass > 0 else 0.0

    return {
        "name": name,
        "shape": (rows, cols),
        "rank_cap": rank_cap,
        "effective_rank": effective_rank,
        "fro_norm": float(fro),
        "sv_max": float(sv_max),
        "sv_min_nz": float(sv_min_nz),
        "cond": float(cond),
        "sv_flatness_med": float(flatness),
        "off_diag_frac": float(off_diag_frac),
        "status": "ok",
    }


def pick_type_pair(fw, pre_types, post_types):
    """Build a dense W for synapses from any pre_type to any post_type."""
    pre_lists = [fw.neurons_with_type(t) for t in pre_types]
    pre_lists = [x for x in pre_lists if len(x) > 0]
    post_lists = [fw.neurons_with_type(t) for t in post_types]
    post_lists = [x for x in post_lists if len(x) > 0]
    if not pre_lists or not post_lists:
        return None, None, None
    pre_idx = np.concatenate(pre_lists)
    post_idx = np.concatenate(post_lists)
    pre_idx = np.unique(pre_idx)
    post_idx = np.unique(post_idx)
    W = fw.counts[pre_idx, :][:, post_idx].toarray().astype(np.float32)
    return W, pre_idx, post_idx


def main():
    print("Loading FlyWire v783...")
    fw = load_flywire(verbose=False)
    print(f"  {fw.n_neurons} neurons, {fw.n_connections} connections")
    print()

    pens = ["PEN_a/PEN1", "PEN_b/PEN2"]
    epgs = ["EPG", "EPGt"]
    mbons = [f"MBON{i:02d}" for i in range(1, 36)]
    kcs = ["KCg-m", "KCab", "KCapbp-m", "KCapbp-ap2", "KCg-d", "KCapbp-ap1"]
    hdeltas = [f"hDelta{c}" for c in "ABCDEFGHIJKLMN"]
    vdeltas = [f"vDelta{c}" for c in "ABCDEFGHIJKLMN"] + ["vDeltaA_a", "vDeltaA_b"]
    ers = [f"ER{n}{s}" for n in "12345" for s in ["", "a", "b", "c", "d",
                                                   "w", "a_a", "a_b", "3a_a"]]
    lhs = [f"LH{t}" for t in ["AV4a4", "AV5a3", "AV6a4", "PV5a1", "PV5b1",
                               "PV5b2", "PV5b3", "PV5c1"]]

    candidates = [
        # Central complex ring — EPG / PEN / PEG
        ("CX: PEN+PEG -> EPG", pens + ["PEG"], epgs),
        ("CX: EPG -> PEN",    epgs,            pens),
        ("CX: EPG -> EPG",    epgs,            epgs),
        # Fan-shaped body recurrent Delta cells (columnar)
        ("FB: hDelta -> hDelta",  hdeltas, hdeltas),
        ("FB: vDelta -> vDelta",  vdeltas, vdeltas),
        ("FB: hDelta -> vDelta",  hdeltas, vdeltas),
        # Ellipsoid body ring
        ("EB: ER -> ER",      ers, ers),
        ("EB: ER -> EPG",     ers, epgs),
        # MB: KC -> MBON, KC -> KC
        ("MB: KC -> MBON",    kcs, mbons),
        ("MB: KC -> KC",      kcs, kcs),
        # Lateral horn (subset)
        ("LH: LH -> LH",      lhs, lhs),
    ]

    results = []
    for name, pre, post in candidates:
        W, pre_idx, post_idx = pick_type_pair(fw, pre, post)
        if W is None:
            print(f"SKIP  {name:40}  types not found")
            continue
        r = score_matrix(W, name)
        results.append(r)
        if r.get("status") != "ok":
            print(f"SKIP  {name:40}  {r.get('status')}")
            continue
        print(f"{name:40}  shape={r['shape']}  "
              f"eff_rank={r['effective_rank']:4d}  "
              f"cond={r['cond']:.2e}  "
              f"flat(max/med)={r['sv_flatness_med']:.2f}  "
              f"off_diag={r['off_diag_frac']:.3f}")

    if not results:
        print("\nNo candidates scored. Check type names.")
        return

    print()
    print("Ranking by off_diag_frac (lower = closer to orthogonal):")
    scored = [r for r in results if r.get("status") == "ok"]
    for r in sorted(scored, key=lambda x: x["off_diag_frac"]):
        print(f"  {r['off_diag_frac']:.3f}  {r['name']:40} "
              f"(eff_rank={r['effective_rank']}, cond={r['cond']:.1e})")


if __name__ == "__main__":
    main()
