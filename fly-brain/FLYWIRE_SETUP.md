# FlyWire Connectome — Setup and Data Locations

## Where the data lives (read this first)

The FlyWire v783 bulk download is stored in **two locations on purpose:**

1. **`C:\Users\Immanuelle\flybrain\`** — the authoritative copy, **outside this git repo**. About 14 GB including skeletons, synapse table, and all CSV annotations. This directory is never touched by git operations and survives repo resets, rebases, fresh clones, and force-pushes.

2. **`fly-brain/flywire_data/`** — a working mirror inside the repo, **gitignored** (see `.gitignore`). Only the small-enough essential files (~74 MB total: connectivity, neurons, classification, cell types, connectivity tags, neuropil table). Skeletons and the 2.6 GB synapse table live only in the external copy.

**Why redundant?** This repo is frequently rebased and force-pushed during paper iteration. Untracked files inside it can disappear without warning. The external copy is the one you trust long-term. The in-repo mirror is for convenience during active work.

**After a fresh clone of this repo:**
```powershell
# Recreate the working mirror from the stable external copy.
mkdir fly-brain\flywire_data
copy C:\Users\Immanuelle\flybrain\classification.csv.gz          fly-brain\flywire_data\
copy C:\Users\Immanuelle\flybrain\connections_princeton.csv.gz   fly-brain\flywire_data\
copy C:\Users\Immanuelle\flybrain\consolidated_cell_types.csv.gz fly-brain\flywire_data\
copy C:\Users\Immanuelle\flybrain\connectivity_tags.csv.gz       fly-brain\flywire_data\
copy C:\Users\Immanuelle\flybrain\neurons.csv.gz                 fly-brain\flywire_data\
copy C:\Users\Immanuelle\flybrain\neuropil_synapse_table.csv.gz  fly-brain\flywire_data\
```

If you can't find the external directory either (machine reimage etc.), re-download from **https://codex.flywire.ai/api/download** (snapshot `v783`) — same files, no auth required.

## Files and what they contain

| File | Size | What for |
| --- | --- | --- |
| `connections_princeton.csv.gz` | 66 MB | **Core connectivity.** Columns: `pre_root_id`, `post_root_id`, `neuropil`, `syn_count`, `nt_type`. 5.3M rows. |
| `neurons.csv.gz` | 1.7 MB | Per-neuron metadata: predicted neurotransmitter, soma side. 139k rows. |
| `classification.csv.gz` | 913 KB | Hierarchical annotations: `super_class`, `class`, `sub_class`, `side`, `nerve`. |
| `consolidated_cell_types.csv.gz` | 881 KB | Primary cell type per neuron (e.g., `T4b`, `KCab`, `MBON-α2sc`). |
| `connectivity_tags.csv.gz` | 623 KB | Community-contributed connectivity tags. |
| `neuropil_synapse_table.csv.gz` | 4.5 MB | Per-neuropil pre/post synapse counts per neuron. |
| `fafb_v783_princeton_synapse_table.csv.gz` | 2.6 GB | Per-synapse spatial coordinates. **External copy only.** |
| `sk_lod1_783_healed.zip` | 11 GB | Per-neuron 3D skeletons. **External copy only.** |

## Loading the data

```python
from flywire_loader import load_flywire

conn = load_flywire()          # ~3s on first run, ~1s from cache
print(conn.n_neurons)          # 139255
print(conn.n_connections)      # 3.7M unique (pre, post) pairs
print(int(conn.counts.sum()))  # 50.7M total synapses

# Find Kenyon cells.
kcs = conn.neurons_with_type('KCab')
mb_submatrix = conn.subgraph(kcs)

# Find the central complex.
cx_indices = conn.neurons_in_region('central')
```

First run parses the gzipped CSVs (~3s) and writes `flywire_cache.npz` in whichever data directory was used. Subsequent runs load from the cache in <1 s. Use `load_flywire(rebuild=True)` after redownloading any CSV.

The loader resolves the data directory in this order:

1. `$FLYWIRE_DATA_DIR` environment variable
2. `fly-brain/flywire_data/` (the in-repo working mirror)
3. `C:\Users\Immanuelle\flybrain\` (the external authoritative copy)

Whichever is found first (and contains `connections_princeton.csv.gz`) is used.

## Data source attribution

FlyWire community connectome, snapshot **v783**, downloaded from https://codex.flywire.ai/api/download. Citations:

- Dorkenwald S. *et al.* *Neuronal wiring diagram of an adult brain.* Nature (2024).
- Schlegel P. *et al.* *Whole-brain annotation and multi-connectome cell typing of Drosophila.* Nature (2024).

Data license: CC-BY-4.0.
