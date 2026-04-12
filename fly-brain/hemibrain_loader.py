"""
Load real PN→KC connectivity from the Janelia hemibrain v1.2.1 connectome.

Replaces the random projection matrix in mushroom_body_model.py with
actual synaptic wiring from the right mushroom body of Drosophila
melanogaster, as reconstructed by Scheffer et al. (2020).

Data source: neuPrint (neuprint.janelia.org), hemibrain:v1.2.1 dataset.
License: CC-BY.

Usage:
    # Download and cache the connectivity matrix
    python hemibrain_loader.py --token YOUR_NEUPRINT_TOKEN

    # Or set the token as an environment variable
    set NEUPRINT_APPLICATION_CREDENTIALS=YOUR_TOKEN
    python hemibrain_loader.py

    # The matrix is saved to hemibrain_pn_kc.npz and reused by
    # mushroom_body_model.py when use_hemibrain=True.

Requirements:
    pip install neuprint-python pandas numpy
"""

import argparse
import os
import sys
import numpy as np

# Windows Unicode fix
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

CACHE_FILE = os.path.join(os.path.dirname(__file__), 'hemibrain_pn_kc.npz')
NEUPRINT_SERVER = 'neuprint.janelia.org'
DATASET = 'hemibrain:v1.2.1'


def fetch_pn_kc_connectivity(token):
    """
    Query neuPrint for all PN→KC synaptic connections in the mushroom body.

    Returns:
        pn_ids: array of PN body IDs
        kc_ids: array of KC body IDs
        matrix: binary connectivity matrix (n_kc x n_pn), 1 where synapse exists
        weight_matrix: weighted connectivity matrix (n_kc x n_pn), synapse counts
    """
    from neuprint import Client, NeuronCriteria as NC, fetch_adjacencies

    c = Client(NEUPRINT_SERVER, dataset=DATASET, token=token)
    print(f"Connected to neuPrint: {c.fetch_version()}")

    # Fetch all PN→KC connections in the mushroom body calyx
    # PNs: olfactory projection neurons that project to the MB calyx
    # KCs: Kenyon cells — the sparse coding layer
    # We use regex patterns to match the hemibrain type annotations
    print("Querying PN→KC connectivity (this may take a minute)...")

    # Hemibrain types PN neurons as various glomerular types,
    # but they're reliably found by querying for neurons with
    # output in the MB calyx (CA) region
    pn_criteria = NC(
        inputRois=['AL(R)'],    # antennal lobe (PN cell bodies)
        outputRois=['CA(R)'],   # calyx of mushroom body (PN axon terminals)
        status='Traced',
        cropped=False,
    )
    kc_criteria = NC(
        type='KC.*',            # all Kenyon cell subtypes
        status='Traced',
        cropped=False,
    )

    neurons_df, conn_df = fetch_adjacencies(
        sources=pn_criteria,
        targets=kc_criteria,
        rois=['CA(R)'],         # only synapses in the calyx
        min_total_weight=1,
    )

    # Aggregate per-ROI weights into total connection weights
    total_conn = conn_df.groupby(
        ['bodyId_pre', 'bodyId_post'], as_index=False
    )['weight'].sum()

    pn_ids = np.sort(total_conn['bodyId_pre'].unique())
    kc_ids = np.sort(total_conn['bodyId_post'].unique())

    print(f"Found {len(pn_ids)} PNs and {len(kc_ids)} KCs")
    print(f"Total connections: {len(total_conn)}")

    # Build connectivity matrices
    pn_idx = {bid: i for i, bid in enumerate(pn_ids)}
    kc_idx = {bid: i for i, bid in enumerate(kc_ids)}

    binary_matrix = np.zeros((len(kc_ids), len(pn_ids)), dtype=np.float64)
    weight_matrix = np.zeros((len(kc_ids), len(pn_ids)), dtype=np.float64)

    for _, row in total_conn.iterrows():
        pi = pn_idx[row['bodyId_pre']]
        ki = kc_idx[row['bodyId_post']]
        binary_matrix[ki, pi] = 1.0
        weight_matrix[ki, pi] = row['weight']

    # Report statistics
    fan_ins = binary_matrix.sum(axis=1)  # PNs per KC
    print(f"\nConnectivity statistics:")
    print(f"  Mean PN fan-in per KC: {fan_ins.mean():.1f}")
    print(f"  Median PN fan-in per KC: {np.median(fan_ins):.1f}")
    print(f"  Min/Max fan-in: {fan_ins.min():.0f} / {fan_ins.max():.0f}")
    print(f"  Matrix density: {binary_matrix.mean():.4f}")
    print(f"  Total synapses: {weight_matrix.sum():.0f}")

    return pn_ids, kc_ids, binary_matrix, weight_matrix


def save_cache(pn_ids, kc_ids, binary_matrix, weight_matrix, path=CACHE_FILE):
    """Save the connectivity data to a compressed .npz file."""
    np.savez_compressed(
        path,
        pn_ids=pn_ids,
        kc_ids=kc_ids,
        binary_matrix=binary_matrix,
        weight_matrix=weight_matrix,
    )
    size_mb = os.path.getsize(path) / (1024 * 1024)
    print(f"\nSaved to {path} ({size_mb:.1f} MB)")


def load_cache(path=CACHE_FILE):
    """Load cached connectivity data. Returns None if cache doesn't exist."""
    if not os.path.exists(path):
        return None
    data = np.load(path)
    return {
        'pn_ids': data['pn_ids'],
        'kc_ids': data['kc_ids'],
        'binary_matrix': data['binary_matrix'],
        'weight_matrix': data['weight_matrix'],
    }


def get_hemibrain_matrix(token=None):
    """
    Get the hemibrain PN→KC connectivity matrix, using cache if available.

    This is the main entry point for mushroom_body_model.py.

    Returns:
        dict with keys: pn_ids, kc_ids, binary_matrix, weight_matrix
    """
    cached = load_cache()
    if cached is not None:
        print(f"Loaded hemibrain connectivity from cache ({CACHE_FILE})")
        n_kc, n_pn = cached['binary_matrix'].shape
        print(f"  {n_pn} PNs, {n_kc} KCs")
        return cached

    if token is None:
        token = os.environ.get('NEUPRINT_APPLICATION_CREDENTIALS')
    if token is None:
        raise RuntimeError(
            "No neuPrint token. Get one from neuprint.janelia.org "
            "(Account > Auth Token) and pass via --token or set "
            "NEUPRINT_APPLICATION_CREDENTIALS environment variable."
        )

    pn_ids, kc_ids, binary_matrix, weight_matrix = fetch_pn_kc_connectivity(token)
    save_cache(pn_ids, kc_ids, binary_matrix, weight_matrix)
    return {
        'pn_ids': pn_ids,
        'kc_ids': kc_ids,
        'binary_matrix': binary_matrix,
        'weight_matrix': weight_matrix,
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Download hemibrain PN→KC connectivity from neuPrint'
    )
    parser.add_argument('--token', type=str, default=None,
                        help='neuPrint API token (or set NEUPRINT_APPLICATION_CREDENTIALS)')
    parser.add_argument('--force', action='store_true',
                        help='Re-download even if cache exists')
    args = parser.parse_args()

    if args.force and os.path.exists(CACHE_FILE):
        os.remove(CACHE_FILE)
        print(f"Removed existing cache: {CACHE_FILE}")

    data = get_hemibrain_matrix(token=args.token)
    n_kc, n_pn = data['binary_matrix'].shape
    fan_ins = data['binary_matrix'].sum(axis=1)

    print(f"\nReady to use: {n_pn} PNs → {n_kc} KCs")
    print(f"Mean fan-in: {fan_ins.mean():.1f} (biological expectation: ~7)")
    print(f"\nTo use in the model, call mushroom_body_model.build_model(use_hemibrain=True)")
