"""Louvain community detection on the 135,403-neuron giant SCC of real W.

Context (`planning/findings/2026-04-13-shiu-scc-search.md`):
  - SCC analysis of real FlyWire v783 W found one giant SCC of
    135,403 neurons (97.7% of connectome) containing the CX, MB, AL,
    etc. The only small SCCs are R1-6 photoreceptor modules. The
    CX ring attractor is wired *into* the giant SCC, not isolable.
  - Graph-level strong connectivity does not yield iteration substrate
    candidates. Dynamics-aware isolation requires finding *densely-
    connected modules within the giant SCC* that may be dynamically
    isolable even though graph-connected to the rest.

Approach:
  1. Extract the 135,403-node giant-SCC subgraph from real signed W.
  2. Build undirected weighted graph (sum of |w_ij| + |w_ji| per pair
     — undirected-ish for community detection; Louvain is defined on
     undirected graphs). This is a coarse projection but standard.
  3. Run NetworkX Louvain (greedy modularity optimization).
  4. Rank communities by: size (in target range 50-2000 for loop
     substrates), internal/external weight ratio (isolation score),
     modularity contribution.
  5. Cross-reference top communities with FlyWire primary_type to
     label them anatomically.

Output: CSV of top communities at `planning/findings/2026-04-13-shiu-communities.csv`.

Wall clock: Louvain on a 135k-node graph on NetworkX is O(E log V)
per iteration; expect 2-10 minutes on this machine. One-shot run.
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
OUT_PATH = Path(__file__).parent.parent / "planning" / "findings" / "2026-04-13-shiu-communities.csv"

N_NEURONS = 138639


def main():
    t0 = perf_counter()
    import torch
    w_torch = get_weights(CONN_PATH, COMP_PATH, WT_DIR, csr=True)
    indptr = w_torch.crow_indices().cpu().numpy()
    indices = w_torch.col_indices().cpu().numpy()
    values = w_torch.values().cpu().numpy()
    W = sp.csr_matrix((values, indices, indptr), shape=(N_NEURONS, N_NEURONS))
    print(f"W: {W.shape}, nnz={W.nnz} ({perf_counter()-t0:.1f}s)")

    # Binary adjacency for SCC
    A = W.copy()
    A.data = np.ones_like(A.data, dtype=np.int8)
    A.eliminate_zeros()

    t = perf_counter()
    n_comp, labels = connected_components(A, directed=True, connection="strong",
                                          return_labels=True)
    sizes = np.bincount(labels, minlength=n_comp)
    giant_id = int(np.argmax(sizes))
    giant_mask = (labels == giant_id)
    giant_idx = np.where(giant_mask)[0]
    n_giant = giant_idx.size
    print(f"giant SCC: {n_giant} nodes ({perf_counter()-t:.1f}s)")

    # Extract subgraph. Undirected weighted projection: A_und[i,j] = |w_ij| + |w_ji|.
    t = perf_counter()
    W_abs = W.copy()
    W_abs.data = np.abs(W_abs.data)
    W_sub = W_abs[giant_idx, :][:, giant_idx].tocsr()
    W_und = (W_sub + W_sub.T).tocsr()
    print(f"subgraph: {W_und.shape}, nnz={W_und.nnz} ({perf_counter()-t:.1f}s)")

    # Build NetworkX graph. For efficiency, use from_scipy_sparse_array.
    t = perf_counter()
    import networkx as nx
    G = nx.from_scipy_sparse_array(W_und, edge_attribute="weight")
    print(f"NetworkX graph built: {G.number_of_nodes()} nodes, "
          f"{G.number_of_edges()} edges ({perf_counter()-t:.1f}s)")

    # Louvain
    t = perf_counter()
    print("running Louvain (this may take a few minutes)...")
    communities = nx.community.louvain_communities(G, weight="weight",
                                                   resolution=1.0, seed=42)
    print(f"Louvain: {len(communities)} communities "
          f"({perf_counter()-t:.1f}s)")

    # Communities is a list of sets of subgraph-local indices. Map back
    # to global Shiu indices and compute stats.
    comm_sizes = np.array([len(c) for c in communities])
    print(f"  size distribution: max={comm_sizes.max()}, "
          f"median={int(np.median(comm_sizes))}, "
          f"communities in [50, 2000] = {((comm_sizes>=50)&(comm_sizes<=2000)).sum()}")

    # Cell-type join
    ct = pd.read_csv(CELL_TYPES_PATH)
    comp = pd.read_csv(COMP_PATH, index_col=0)
    shiu_ids = comp.index.astype(str)
    id_to_idx = {fid: i for i, fid in enumerate(shiu_ids)}
    type_by_idx = np.array([""] * N_NEURONS, dtype=object)
    ct_str_ids = ct["root_id"].astype(str).values
    ct_types = ct["primary_type"].fillna("").astype(str).values
    for fid, ptype in zip(ct_str_ids, ct_types):
        if fid in id_to_idx:
            type_by_idx[id_to_idx[fid]] = ptype

    # For each community in target range, compute internal/external weight ratio
    # to measure dynamical isolability.
    t = perf_counter()
    qualifying = [(i, list(c)) for i, c in enumerate(communities)
                  if 50 <= len(c) <= 2000]
    print(f"\nranking {len(qualifying)} communities in [50, 2000]...")

    results = []
    W_sub_csc = W_sub.tocsc()
    for comm_id, local_members in qualifying:
        local_members = np.array(local_members)
        global_members = giant_idx[local_members]
        m_set_local = set(local_members.tolist())

        # For isolation, use the DIRECTED weighted W restricted to giant SCC.
        # int_w: sum |w_ij| for i, j both in community
        # ext_w: sum |w_ij| for i OR j in community but not both
        int_w = 0.0
        ext_w = 0.0
        for node in local_members:
            col_start = W_sub_csc.indptr[node]
            col_end = W_sub_csc.indptr[node + 1]
            rows = W_sub_csc.indices[col_start:col_end]
            data = W_sub_csc.data[col_start:col_end]
            for r, d in zip(rows, data):
                if r in m_set_local:
                    int_w += d
                else:
                    ext_w += d
        # Account for outgoing too: use row access
        # W_sub is already |w|; we counted incoming. Scan outgoing via rows.
        # Actually for undirected weighted, Louvain used W_und; here we want
        # directed isolation. Scan both directions via W_sub (CSR rows).
        W_sub_csr = W_sub
        for node in local_members:
            row_start = W_sub_csr.indptr[node]
            row_end = W_sub_csr.indptr[node + 1]
            cols = W_sub_csr.indices[row_start:row_end]
            data = W_sub_csr.data[row_start:row_end]
            for c, d in zip(cols, data):
                if c not in m_set_local:
                    ext_w += d
                # incoming already counted above

        iso = int_w / max(int_w + ext_w, 1e-9)

        # Top-3 primary types
        member_types = type_by_idx[global_members]
        type_counts = pd.Series(member_types).value_counts().head(5)
        type_summary = ",".join(f"{t or '<none>'}:{c}"
                                for t, c in type_counts.items())

        results.append({
            "comm_id": comm_id,
            "size": len(local_members),
            "int_weight": int_w,
            "ext_weight": ext_w,
            "iso_ratio": iso,
            "top_types": type_summary,
        })
    print(f"  ranked in {perf_counter()-t:.1f}s")

    df = pd.DataFrame(results)
    if len(df) == 0:
        print("  no communities in target range; skipping sort / CSV write.")
        return
    df = df.sort_values("iso_ratio", ascending=False).reset_index(drop=True)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_PATH, index=False)
    print(f"\nwrote {OUT_PATH} ({len(df)} communities)")

    print("\nTOP 15 by isolation ratio (high = internally cohesive):")
    print(df.head(15).to_string(index=False))

    print("\nCommunities containing CX ring types (EPG/Delta7/PEN/ER):")
    ring_types = ["EPG", "Delta7", "PEN1", "PEN2", "ER1", "ER2", "ER3",
                  "ER4", "ER5", "ER6", "PFL"]
    for rt in ring_types:
        hits = df[df["top_types"].str.contains(rt, case=False, na=False)]
        if len(hits) > 0:
            print(f"\n  {rt}:")
            print(hits.head(3).to_string(index=False))


if __name__ == "__main__":
    main()
