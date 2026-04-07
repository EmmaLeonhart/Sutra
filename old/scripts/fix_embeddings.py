"""Fix the corrupted embeddings.npz file by re-saving it properly."""
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import numpy as np
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

print("Loading embeddings...", flush=True)
try:
    data = np.load(str(DATA_DIR / 'embeddings.npz'), allow_pickle=True)
    emb = data['vectors']
    print(f"Loaded: {emb.shape}, dtype={emb.dtype}", flush=True)
except Exception as e:
    print(f"Standard load failed: {e}", flush=True)
    # Try reading as raw numpy
    try:
        emb = np.load(str(DATA_DIR / 'embeddings.npz'))
        print(f"Raw load: {emb.shape}", flush=True)
    except Exception as e2:
        print(f"Raw load also failed: {e2}", flush=True)
        sys.exit(1)

# Re-save cleanly
print("Re-saving as clean npz...", flush=True)
np.savez_compressed(str(DATA_DIR / 'embeddings_clean.npz'), vectors=emb)

# Verify
data2 = np.load(str(DATA_DIR / 'embeddings_clean.npz'))
emb2 = data2['vectors']
print(f"Verified: {emb2.shape}, dtype={emb2.dtype}", flush=True)
assert np.array_equal(emb, emb2), "Data mismatch!"

# Replace
import os, shutil
shutil.move(str(DATA_DIR / 'embeddings.npz'), str(DATA_DIR / 'embeddings_backup.npz'))
shutil.move(str(DATA_DIR / 'embeddings_clean.npz'), str(DATA_DIR / 'embeddings.npz'))
print("Replaced embeddings.npz with clean version.", flush=True)

# Final verify
data3 = np.load(str(DATA_DIR / 'embeddings.npz'))
print(f"Final check: {data3['vectors'].shape}", flush=True)
print("Done!", flush=True)
