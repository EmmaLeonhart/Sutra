"""
Load the full-brain FlyWire connectome into a Sutra-usable form.

Reads the bulk CSV exports from https://codex.flywire.ai/api/download
(snapshot v783) and produces:

- A scipy sparse CSR matrix of synapse counts, shape (n_neurons, n_neurons).
  matrix[i, j] is the total synapse count from neuron i onto neuron j.
- A neuron-ID → row-index map.
- Per-neuron metadata: predicted neurotransmitter, super-class, class,
  sub-class, side, primary cell type.
- Per-connection neurotransmitter labels, in a separate sparse array of
  the same shape as the count matrix.

Everything is cached to a single flywire_cache.npz next to the source
CSVs. Second run reads the cache in ~1s instead of reparsing ~70 MB of
gzipped CSV.

IMPORTANT — where the data lives:

The raw CSVs are kept OUTSIDE this git repo at
    C:\\Users\\Immanuelle\\flybrain\\
on purpose. This repo is frequently rebased, reset, and force-pushed
during paper iteration; anything inside it can disappear without
warning. The authoritative copy of the 14 GB FlyWire download lives
in the external directory and is never touched by git operations.

A working mirror of the small-enough files (everything except
skeletons and the 2.6 GB synapse table) is also kept inside the repo
at fly-brain/flywire_data/ for convenience. That path is gitignored.

Resolution order for the data directory:
1. FLYWIRE_DATA_DIR environment variable, if set
2. fly-brain/flywire_data/ relative to this file (working mirror)
3. C:\\Users\\Immanuelle\\flybrain\\ (primary, external)

Usage:
    from flywire_loader import load_flywire
    conn = load_flywire()                 # returns FlyWireConnectome
    print(conn.n_neurons)                 # 139k-ish
    row = conn.index_of(720575940596125868)
    outgoing = conn.counts.getrow(row)    # scipy sparse row
"""

from __future__ import annotations

import gzip
import io
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np

# Windows Unicode fix — without this, print() dies on any emoji or
# non-ASCII character in the data when running from a non-UTF-8 shell.
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')


HERE = Path(__file__).parent
REPO_MIRROR = HERE / 'flywire_data'
PRIMARY_EXTERNAL = Path.home() / 'flybrain'
CACHE_NAME = 'flywire_cache.npz'


def _resolve_data_dir() -> Path:
    """Find the FlyWire data directory; see module docstring for order."""
    env = os.environ.get('FLYWIRE_DATA_DIR')
    if env:
        p = Path(env)
        if p.is_dir():
            return p
    if REPO_MIRROR.is_dir() and (REPO_MIRROR / 'connections_princeton.csv.gz').exists():
        return REPO_MIRROR
    if PRIMARY_EXTERNAL.is_dir() and (PRIMARY_EXTERNAL / 'connections_princeton.csv.gz').exists():
        return PRIMARY_EXTERNAL
    raise FileNotFoundError(
        "No FlyWire data directory found. Expected one of:\n"
        f"  $FLYWIRE_DATA_DIR (unset or not a dir)\n"
        f"  {REPO_MIRROR}\n"
        f"  {PRIMARY_EXTERNAL}\n"
        "Download from https://codex.flywire.ai/api/download (snapshot v783) "
        "and place at least connections_princeton.csv.gz, neurons.csv.gz, "
        "classification.csv.gz, consolidated_cell_types.csv.gz into one of "
        "those directories."
    )


@dataclass
class FlyWireConnectome:
    """The loaded FlyWire brain, in a Sutra-friendly form."""
    root_ids: np.ndarray              # shape (n_neurons,), int64 neuron IDs
    id_to_row: dict                   # root_id -> row index
    counts: 'scipy.sparse.csr_matrix' # (n, n) synapse-count matrix
    nt_labels: np.ndarray             # shape (n_connections,), neurotransmitter str
    super_class: np.ndarray           # shape (n_neurons,), e.g. 'optic', 'central'
    cls: np.ndarray                   # shape (n_neurons,), classification 'class'
    sub_class: np.ndarray             # shape (n_neurons,), classification 'sub_class'
    side: np.ndarray                  # shape (n_neurons,), 'left' / 'right' / 'center'
    primary_type: np.ndarray          # shape (n_neurons,), cell type e.g. 'T4b'
    nt_type: np.ndarray               # shape (n_neurons,), predicted NT per-neuron
    data_dir: Path

    @property
    def n_neurons(self) -> int:
        return len(self.root_ids)

    @property
    def n_connections(self) -> int:
        return self.counts.nnz

    def index_of(self, root_id: int) -> int:
        return self.id_to_row[int(root_id)]

    def neurons_in_region(self, super_class: str) -> np.ndarray:
        """Return row indices of all neurons whose super_class matches."""
        return np.where(self.super_class == super_class)[0]

    def neurons_with_type(self, primary_type: str) -> np.ndarray:
        """Return row indices of all neurons with the given cell type (e.g. 'KC')."""
        return np.where(self.primary_type == primary_type)[0]

    def subgraph(self, row_indices: np.ndarray) -> 'scipy.sparse.csr_matrix':
        """Extract the pre × post connectivity submatrix for a neuron subset."""
        sub = self.counts[row_indices, :][:, row_indices]
        return sub


def _read_csv_gz(path: Path, cols: list[str]):
    """Read a gzipped CSV with pandas, returning only the requested columns."""
    import pandas as pd
    return pd.read_csv(path, compression='gzip', usecols=cols, low_memory=False)


def _build_from_csvs(data_dir: Path, verbose: bool = True) -> FlyWireConnectome:
    import pandas as pd
    import scipy.sparse as sp

    t0 = time.time()
    if verbose:
        print(f"[flywire] loading neurons.csv.gz from {data_dir}")
    neurons_df = _read_csv_gz(
        data_dir / 'neurons.csv.gz',
        ['root_id', 'nt_type', 'nt_type_score']
    )
    root_ids = neurons_df['root_id'].to_numpy(dtype=np.int64)
    id_to_row = {int(rid): i for i, rid in enumerate(root_ids)}
    n = len(root_ids)
    if verbose:
        print(f"[flywire]   {n} neurons")

    if verbose:
        print(f"[flywire] loading classification.csv.gz")
    cls_df = _read_csv_gz(
        data_dir / 'classification.csv.gz',
        ['root_id', 'super_class', 'class', 'sub_class', 'side']
    ).set_index('root_id').reindex(root_ids).fillna('')
    super_class = cls_df['super_class'].to_numpy(dtype=object)
    cls_arr = cls_df['class'].to_numpy(dtype=object)
    sub_class = cls_df['sub_class'].to_numpy(dtype=object)
    side = cls_df['side'].to_numpy(dtype=object)

    if verbose:
        print(f"[flywire] loading consolidated_cell_types.csv.gz")
    types_df = _read_csv_gz(
        data_dir / 'consolidated_cell_types.csv.gz',
        ['root_id', 'primary_type']
    ).set_index('root_id').reindex(root_ids).fillna('')
    primary_type = types_df['primary_type'].to_numpy(dtype=object)

    nt_type = neurons_df['nt_type'].fillna('').to_numpy(dtype=object)

    if verbose:
        print(f"[flywire] loading connections_princeton.csv.gz "
              f"(this is the big one, ~30s)")
    conn_df = pd.read_csv(
        data_dir / 'connections_princeton.csv.gz',
        compression='gzip',
        usecols=['pre_root_id', 'post_root_id', 'syn_count', 'nt_type'],
        dtype={'pre_root_id': np.int64, 'post_root_id': np.int64,
               'syn_count': np.int32, 'nt_type': str},
        low_memory=False,
    )
    if verbose:
        print(f"[flywire]   {len(conn_df)} connection rows")

    pre_idx = conn_df['pre_root_id'].map(id_to_row).to_numpy()
    post_idx = conn_df['post_root_id'].map(id_to_row).to_numpy()
    mask = ~(pd.isna(pre_idx) | pd.isna(post_idx))
    dropped = (~mask).sum()
    if verbose and dropped:
        print(f"[flywire]   dropping {dropped} connections with unknown root_ids")
    pre_idx = pre_idx[mask].astype(np.int64)
    post_idx = post_idx[mask].astype(np.int64)
    syn = conn_df['syn_count'].to_numpy()[mask].astype(np.int32)
    nt_labels = conn_df['nt_type'].to_numpy()[mask].astype(object)

    counts = sp.coo_matrix((syn, (pre_idx, post_idx)), shape=(n, n)).tocsr()
    if verbose:
        print(f"[flywire]   built CSR: {counts.nnz} nonzero entries, "
              f"sum = {counts.sum()} total synapses")

    fw = FlyWireConnectome(
        root_ids=root_ids,
        id_to_row=id_to_row,
        counts=counts,
        nt_labels=nt_labels,
        super_class=super_class,
        cls=cls_arr,
        sub_class=sub_class,
        side=side,
        primary_type=primary_type,
        nt_type=nt_type,
        data_dir=data_dir,
    )
    if verbose:
        print(f"[flywire] done in {time.time() - t0:.1f}s")
    return fw


def _save_cache(fw: FlyWireConnectome, cache_path: Path) -> None:
    np.savez_compressed(
        cache_path,
        root_ids=fw.root_ids,
        counts_data=fw.counts.data,
        counts_indices=fw.counts.indices,
        counts_indptr=fw.counts.indptr,
        counts_shape=np.array(fw.counts.shape),
        nt_labels=fw.nt_labels.astype(str),
        super_class=fw.super_class.astype(str),
        cls=fw.cls.astype(str),
        sub_class=fw.sub_class.astype(str),
        side=fw.side.astype(str),
        primary_type=fw.primary_type.astype(str),
        nt_type=fw.nt_type.astype(str),
    )


def _load_cache(cache_path: Path, data_dir: Path) -> FlyWireConnectome:
    import scipy.sparse as sp
    z = np.load(cache_path, allow_pickle=False)
    root_ids = z['root_ids']
    shape = tuple(z['counts_shape'].tolist())
    counts = sp.csr_matrix(
        (z['counts_data'], z['counts_indices'], z['counts_indptr']),
        shape=shape,
    )
    return FlyWireConnectome(
        root_ids=root_ids,
        id_to_row={int(rid): i for i, rid in enumerate(root_ids)},
        counts=counts,
        nt_labels=z['nt_labels'],
        super_class=z['super_class'],
        cls=z['cls'],
        sub_class=z['sub_class'],
        side=z['side'],
        primary_type=z['primary_type'],
        nt_type=z['nt_type'],
        data_dir=data_dir,
    )


def load_flywire(*, rebuild: bool = False, verbose: bool = True) -> FlyWireConnectome:
    """
    Load the full FlyWire connectome, using the cache if available.

    Pass rebuild=True to force a reparse of the CSVs (e.g., after
    re-downloading them).
    """
    data_dir = _resolve_data_dir()
    cache_path = data_dir / CACHE_NAME
    if cache_path.exists() and not rebuild:
        if verbose:
            print(f"[flywire] loading cache {cache_path}")
        return _load_cache(cache_path, data_dir)
    fw = _build_from_csvs(data_dir, verbose=verbose)
    if verbose:
        print(f"[flywire] writing cache {cache_path}")
    _save_cache(fw, cache_path)
    return fw


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--rebuild', action='store_true',
                    help='force reparse of CSVs even if cache exists')
    args = ap.parse_args()

    fw = load_flywire(rebuild=args.rebuild)
    print()
    print(f"n_neurons = {fw.n_neurons}")
    print(f"n_connections = {fw.n_connections}")
    print(f"total synapses = {int(fw.counts.sum())}")

    print("\ntop 10 super_class counts:")
    unique, counts = np.unique(fw.super_class, return_counts=True)
    for u, c in sorted(zip(unique, counts), key=lambda p: -p[1])[:10]:
        print(f"  {c:>8d}  {u}")

    print("\nspot-check Kenyon cells:")
    kcs = fw.neurons_with_type('KC')
    print(f"  {len(kcs)} KCs by primary_type == 'KC' (FlyWire may split by subtype)")
    for pt in ['KCg', 'KCa', 'KCab', 'KCy', "KCy'"]:
        n_pt = (fw.primary_type == pt).sum()
        if n_pt:
            print(f"  {n_pt:>6d}  primary_type = {pt}")
