"""Quick test to verify the pipeline state and fix issues."""
import sys, json, os
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import numpy as np
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# Load embeddings
data = np.load(str(DATA_DIR / 'embeddings.npz'), allow_pickle=True)
emb = data['vectors']
print(f"Embeddings: {emb.shape}", flush=True)

# Load index
with open(str(DATA_DIR / 'embedding_index.json'), encoding='utf-8') as f:
    index = json.load(f)
print(f"Index entries: {len(index)}", flush=True)

# Load items
with open(str(DATA_DIR / 'items.json'), encoding='utf-8') as f:
    items = json.load(f)
full = sum(1 for i in items if i['triples'])
print(f"Items: {len(items)}, fully imported: {full}, stubs: {len(items)-full}", flush=True)

# Mismatch check
if len(index) != emb.shape[0]:
    print(f"WARNING: Index ({len(index)}) != Embeddings ({emb.shape[0]}) - MISMATCH!", flush=True)
else:
    print("Index and embeddings are aligned.", flush=True)

# Walk state
with open(str(DATA_DIR / 'walk_state.json'), encoding='utf-8') as f:
    state = json.load(f)
print(f"Walk state: queue={len(state['queue'])}, visited={len(state['visited'])}, imported={state['imported_count']}", flush=True)

# Test Ollama
try:
    import ollama
    result = ollama.embed(model="mxbai-embed-large", input=["test"])
    print(f"Ollama OK: got {len(result.embeddings[0])}-dim vector", flush=True)
except Exception as e:
    print(f"Ollama FAILED: {e}", flush=True)

# Test Wikidata
try:
    import requests
    resp = requests.get("https://www.wikidata.org/w/api.php", params={
        "action": "wbgetentities", "ids": "Q5", "format": "json", "languages": "en"
    }, headers={"User-Agent": "embedding-mapping/0.1"}, timeout=10)
    label = resp.json()["entities"]["Q5"]["labels"]["en"]["value"]
    print(f"Wikidata API OK: Q5 = '{label}'", flush=True)
except Exception as e:
    print(f"Wikidata API FAILED: {e}", flush=True)

# Test SutraDB
try:
    resp = requests.get("http://localhost:3030/health", timeout=5)
    print(f"SutraDB: {resp.text.strip()}", flush=True)
except Exception as e:
    print(f"SutraDB: not running ({e})", flush=True)

print("Done!", flush=True)
