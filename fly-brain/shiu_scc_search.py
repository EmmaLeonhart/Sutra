"""Find candidate loop substrates in real W via strongly-connected-component analysis.

Drosophila ring-attractor recruitment via direct EPG drive failed on
the Shiu substrate (see planning/findings/2026-04-13-shiu-cx-no-recurrence.md
and shiu-cx-strong-drive-marginal.md). The EPG-only slice does not
rotate on its own — the ring dynamics live in a wider subnetwork.

This script asks: what closed-loop substrates does the real FlyWire
v783 W contain that could potentially support Sutra's `loop (condition)`
eigenrotation? Graph-analytic approach, not biology-guided:

  1. Compute strongly-connected components (SCCs) of the real signed W.
  2. Filter SCCs by size (10 ≤ |SCC| ≤ 500) — big enough to hold
     state, small enough to be a loop rather than a diffuse network.
  3. Rank candidates by (a) external in-degree ratio (lower =
     more isolated loop, less perturbed by outside signal), (b) edge
     weight uniformity (lower std/mean = more stable iteration).
  4. Cross-reference with FlyWire primary_type to label what each
     SCC is anatomically.

Output: a CSV of top SCC candidates with size, composition, and
isolation score, usable as a shortlist for follow-up probe scripts
(drive the SCC, measure closed-loop persistence after drive release).
"""
from __future__ import annotations

import sys
from pathlib import Path
from time import perf_counter

import numpy as np
import pandas as pd
import scipy.sparse as sp
from scipy.sparse.csgraph import connected_components

SHIU_REPO = Path(r"C:/Users/Immanuelle/shiu-fly-brain")
FLYBRAIN_DIR = Path(r"C:/Users/Immanuelle/flybrain")
sys.path.insert(0, str(SHIU_REPO / "code"))

from run_pytorch import get_weights  # noqa: E402

CONN_PATH = SHIU_REPO / "data" / "2025_Connectivity_783.parquet"
COMP_PATH = SHIU_REPO / "data" / "2025_Completeness_783.csv"
CELL_TYPES_PATH = FLYBRAIN_DIR / "consolidated_cell_types.csv.gz"
WT_DIR = SHIU_REPO / "data"
OUT_PATH = Path(__file__).parent.parent / "planning" / "findings" / "2026-04-13-shiu-scc-candidates.csv"

N_NEURONS = 138639
SIZE_MIN = 10
SIZE_MAX = 500


def main():
    t0 = perf_counter()
    # Use CSR-form weights on CPU for csgraph. The torch get_weights
    # returns a torch sparse tensor; we want scipy sparse.
    import torch
    w_torch = get_weights(CONN_PATH, COMP_PATH, WT_DIR, csr=True)
    # Convert torch sparse CSR to scipy sparse CSR via COO round-trip.
    if w_torch.is_sparse_csr:
        indptr = w_torch.crow_indices().cpu().numpy()
        indices = w_torch.col_indices().cpu().numpy()
        values = w_torch.values().cpu().numpy()
        W = sp.csr_matrix((values, indices, indptr), shape=(N_NEURONS, N_NEURONS))
    else:
        W = sp.csr_matrix(w_torch.to_dense().cpu().numpy())
    print(f"W: {W.shape}, nnz={W.nnz} ({perf_counter()-t0:.1f}s)")

    # Binary adjacency: an edge exists if |w| > 0 (ignore sign for SCC).
    A = W.copy()
    A.data = np.ones_like(A.data, dtype=np.int8)
    A.eliminate_zeros()

    t = perf_counter()
    n_comp, labels = connected_components(A, directed=True, connection="strong",
                                          return_labels=True)
    print(f"SCCs: {n_comp} ({perf_counter()-t:.1f}s)")

    # Component sizes
    sizes = np.bincount(labels, minlength=n_comp)
    print(f"  largest SCC size: {sizes.max()}")
    print(f"  SCCs with size &gt;= 2: {(sizes >= 2).sum()}")
    print(f"  SCCs with size in [{SIZE_MIN}, {SIZE_MAX}]: "
          f"{((sizes >= SIZE_MIN) & (sizes <= SIZE_MAX)).sum()}")

    # Load cell types
    ct = pd.read_csv(CELL_TYPES_PATH)
    comp = pd.read_csv(COMP_PATH, index_col=0)
    shiu_ids = comp.index.astype(str)
    id_to_idx = {fid: i for i, fid in enumerate(shiu_ids)}
    # Build per-Shiu-idx primary_type (many will be NaN for neurons
    # without FlyWire type annotation)
    type_by_idx = np.array([""] * N_NEURONS, dtype=object)
    ct_str_ids = ct["root_id"].astype(str).values
    ct_types = ct["primary_type"].fillna("").astype(str).values
    for fid, ptype in zip(ct_str_ids, ct_types):
        if fid in id_to_idx:
            type_by_idx[id_to_idx[fid]] = ptype

    # For each qualifying SCC, compute:
    #   - size
    #   - dominant primary_type (top-3 by member count)
    #   - external in-degree ratio: edges INTO scc from outside / total
    #     edges INTO scc. Low = isolated loop.
    #   - internal edge-weight mean and std (over abs(w)).
    candidates = []
    qualifying = np.where((sizes >= SIZE_MIN) & (sizes <= SIZE_MAX))[0]
    print(f"\nranking {len(qualifying)} qualifying SCCs...")

    # Build incoming lists via CSC for efficiency
    W_csc = W.tocsc()
    W_abs = W_csc.copy()
    W_abs.data = np.abs(W_abs.data)

    t = perf_counter()
    for comp_id in qualifying:
        members = np.where(labels == comp_id)[0]
        m_set = set(members.tolist())
        # Incoming edges per member column
        ext_in = 0
        int_in = 0
        int_weights = []
        for node in members:
            col_start = W_csc.indptr[node]
            col_end = W_csc.indptr[node + 1]
            rows = W_csc.indices[col_start:col_end]
            data = W_csc.data[col_start:col_end]
            for r, d in zip(rows, data):
                if r in m_set:
                    int_in += 1
                    int_weights.append(abs(d))
                else:
                    ext_in += 1
        tot_in = ext_in + int_in
        ext_ratio = ext_in / max(tot_in, 1)
        mean_w = float(np.mean(int_weights)) if int_weights else 0.0
        std_w = float(np.std(int_weights)) if int_weights else 0.0
        # Top-3 primary types
        member_types = type_by_idx[members]
        type_counts = pd.Series(member_types).value_counts().head(3)
        type_summary = ",".join(f"{t or '<none>'}:{c}"
                                for t, c in type_counts.items())
        candidates.append({
            "scc_id": int(comp_id),
            "size": int(len(members)),
            "ext_in_ratio": ext_ratio,
            "int_edges": int_in,
            "weight_mean": mean_w,
            "weight_cv": std_w / max(mean_w, 1e-9),
            "top_types": type_summary,
        })
    print(f"  ranked in {perf_counter()-t:.1f}s")

    df = pd.DataFrame(candidates)
    # Score: we want low ext_in_ratio (isolated), low weight_cv (uniform).
    # Combined rank score: normalize both, sum.
    df["ext_rank"] = df["ext_in_ratio"].rank(pct=True)
    df["cv_rank"] = df["weight_cv"].rank(pct=True)
    df["score"] = df["ext_rank"] + df["cv_rank"]
    df = df.sort_values("score").reset_index(drop=True)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_PATH, index=False)
    print(f"\nwrote {OUT_PATH} ({len(df)} SCCs)")

    print("\nTOP 15 candidates (low ext_in_ratio + low weight_cv):")
    print(df.head(15).to_string(index=False))

    print("\nNOTABLE: any SCC containing known CX types (EPG, Delta7, PEN, ER):")
    ring_types = ["EPG", "Delta7", "PEN_a", "PEN_b", "PEN1", "PEN2",
                  "ER1", "ER2", "ER3", "ER4", "ER5", "ER6"]
    for rt in ring_types:
        hits = df[df["top_types"].str.contains(rt, case=False, na=False)]
        if len(hits) > 0:
            print(f"  SCCs containing {rt}:")
            print(hits.head(3).to_string(index=False))


if __name__ == "__main__":
    main()
