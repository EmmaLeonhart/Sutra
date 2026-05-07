"""Rotation binding capacity on real LLM embeddings, across substrates.

Why this experiment exists:
    The companion script `rotation_binding_capacity.py` measures
    capacity as a property of the rotation algebra over random
    vectors. The paper's central claim is about behavior on
    natural anisotropic LLM embeddings, so the same experiment
    is repeated here on real embedded vocabularies. Rotation
    binding is compared head-to-head against Hadamard binding
    (the textbook VSA scheme that the paper argues fails on
    these substrates) on the same codebook.

What this experiment measures:
    For each of three frozen LLM substrates:
        nomic-embed-text   (768-d)
        all-minilm         (384-d)
        mxbai-embed-large  (1024-d)
    and for two binding schemes:
        rotation           (R_role @ filler, Haar-random orthogonal)
        Hadamard           (role .* filler, element-wise multiply)
    we measure decode accuracy as a function of bundle width k over
    a fixed 200-word LLM-embedded codebook.

    For each (substrate, scheme, k) pair: 10 trials, each picks
    k random (role, filler) pairs from the codebook, bundles, then
    for each role unbinds + argmax-cosines against the full
    codebook to recover the filler. Report mean accuracy, signal
    cosine, noise cosine.

Reproducible: seeded RNG, fixed vocabulary. Re-running produces the
same numbers modulo Ollama embedding determinism (which is
deterministic for a given model + input).

Usage:
    python experiments/rotation_binding_capacity_llm.py
"""

from __future__ import annotations

import json
import sys
import time
import urllib.request
from pathlib import Path

import numpy as np

# ---------------------------------------------------------------------
# Vocabulary: 200 common nouns spanning categories so the codebook
# has semantic diversity rather than clumping in one cluster.
# ---------------------------------------------------------------------
VOCAB = sorted(set([
    # animals (20)
    "cat", "dog", "horse", "cow", "elephant", "lion", "tiger", "bear",
    "wolf", "fox", "rabbit", "snake", "fish", "whale", "eagle", "owl",
    "spider", "ant", "bee", "butterfly",
    # foods (16)
    "apple", "banana", "bread", "rice", "pasta", "cheese", "milk", "egg",
    "carrot", "tomato", "onion", "potato", "chicken", "beef", "pepper", "lemon",
    # objects (16)
    "chair", "table", "bed", "lamp", "clock", "phone", "computer", "book",
    "pen", "paper", "bag", "cup", "knife", "shoe", "shirt", "key",
    # places (16)
    "house", "school", "hospital", "library", "park", "forest", "mountain",
    "river", "ocean", "city", "street", "bridge", "office", "shop",
    "restaurant", "hotel",
    # abstract (16)
    "music", "color", "light", "fire", "water", "wind", "rain", "money",
    "time", "year", "day", "night", "north", "south", "east", "west",
]))

SUBSTRATES = [
    ("nomic-embed-text", 768),
    ("all-minilm",       384),
    ("mxbai-embed-large", 1024),
]

BUNDLE_WIDTHS = [2, 4, 8, 16, 24, 32, 48]
TRIALS_PER_K = 10
SEED = 42


# ---------------------------------------------------------------------
# Ollama embedding helpers
# ---------------------------------------------------------------------

def ollama_embed(model: str, text: str) -> np.ndarray:
    """Fetch an embedding from Ollama. Returns a 1D np.ndarray."""
    req = urllib.request.Request(
        "http://localhost:11434/api/embeddings",
        data=json.dumps({"model": model, "prompt": text}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        obj = json.loads(resp.read().decode("utf-8"))
    return np.array(obj["embedding"], dtype=np.float64)


CACHE_DIR = Path(__file__).parent / "_embedding_cache"


def build_codebook(model: str, expected_dim: int) -> tuple[np.ndarray, list[str]]:
    """Embed the full vocabulary on the given Ollama model. Returns
    (codebook[n_words, dim], vocab_list). Disk-caches per (model,
    vocab_hash) so reruns don't re-embed. Mean-centers for nomic."""
    import hashlib
    CACHE_DIR.mkdir(exist_ok=True)
    vocab_hash = hashlib.sha256("\n".join(VOCAB).encode()).hexdigest()[:16]
    cache_key = f"{model}_{vocab_hash}.npz"
    cache_path = CACHE_DIR / cache_key
    if cache_path.exists():
        print(f"  cache hit: {cache_path.name}")
        z = np.load(cache_path)
        cb = z["cb"]
    else:
        print(f"  embedding {len(VOCAB)} words via {model} "
              f"(no cache, this takes ~{2 * len(VOCAB)}s)...")
        t0 = time.monotonic()
        rows = []
        for i, w in enumerate(VOCAB):
            rows.append(ollama_embed(model, w))
            if (i + 1) % 20 == 0:
                print(f"    {i+1}/{len(VOCAB)}  ({time.monotonic()-t0:.0f}s elapsed)")
        cb = np.stack(rows, axis=0)
        np.savez(cache_path, cb=cb)
        print(f"  done in {time.monotonic() - t0:.1f}s, cached to "
              f"{cache_path.name}")
    if cb.shape[1] != expected_dim:
        print(f"    WARNING: expected dim {expected_dim}, got {cb.shape[1]}",
              file=sys.stderr)
    if model == "nomic-embed-text":
        cb = cb - cb.mean(axis=0, keepdims=True)
    cb /= np.linalg.norm(cb, axis=1, keepdims=True) + 1e-12
    print(f"  shape={cb.shape}")
    return cb, list(VOCAB)


# ---------------------------------------------------------------------
# Binding schemes
# ---------------------------------------------------------------------

def haar_rotation(seed: int, dim: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    G = rng.standard_normal((dim, dim))
    Q, R = np.linalg.qr(G)
    return Q * np.sign(np.diag(R))


def trial_rotation(k: int, codebook: np.ndarray,
                   rng: np.random.Generator) -> tuple[float, float, float]:
    """One rotation-binding trial: pick k random (role, filler) pairs,
    bind, bundle, then for each role unbind and argmax-cosine."""
    n, dim = codebook.shape
    role_idxs = rng.choice(n, size=k, replace=False)
    filler_idxs = rng.choice(n, size=k, replace=False)
    rotations = [haar_rotation(int(r) + 10_000, dim) for r in role_idxs]

    bundle = np.zeros(dim)
    for R, fi in zip(rotations, filler_idxs):
        bundle += R @ codebook[fi]
    bundle /= np.linalg.norm(bundle) + 1e-12

    correct = 0
    sigs = []
    noises = []
    cb_norms = codebook  # already unit-normalized
    for R, fi in zip(rotations, filler_idxs):
        recovered = R.T @ bundle
        recovered /= np.linalg.norm(recovered) + 1e-12
        cos_all = cb_norms @ recovered
        sigs.append(float(cos_all[fi]))
        others = [j for j in filler_idxs if j != fi]
        noises.append(float(np.mean(cos_all[others])) if others else 0.0)
        if int(np.argmax(cos_all)) == int(fi):
            correct += 1
    return correct / k, float(np.mean(sigs)), float(np.mean(noises))


def trial_hadamard(k: int, codebook: np.ndarray,
                   rng: np.random.Generator) -> tuple[float, float, float]:
    """One Hadamard-binding trial: bind = element-wise product, unbind
    same (Hadamard is involutive over {-1, +1}; over reals we just
    re-multiply with role)."""
    n, dim = codebook.shape
    role_idxs = rng.choice(n, size=k, replace=False)
    filler_idxs = rng.choice(n, size=k, replace=False)

    bundle = np.zeros(dim)
    for ri, fi in zip(role_idxs, filler_idxs):
        bundle += codebook[ri] * codebook[fi]
    bundle /= np.linalg.norm(bundle) + 1e-12

    correct = 0
    sigs = []
    noises = []
    cb = codebook
    for ri, fi in zip(role_idxs, filler_idxs):
        recovered = codebook[ri] * bundle
        recovered /= np.linalg.norm(recovered) + 1e-12
        cos_all = cb @ recovered
        sigs.append(float(cos_all[fi]))
        others = [j for j in filler_idxs if j != fi]
        noises.append(float(np.mean(cos_all[others])) if others else 0.0)
        if int(np.argmax(cos_all)) == int(fi):
            correct += 1
    return correct / k, float(np.mean(sigs)), float(np.mean(noises))


# ---------------------------------------------------------------------
# Main sweep
# ---------------------------------------------------------------------

def run_substrate(model: str, dim: int) -> dict:
    print(f"\n{'=' * 78}")
    print(f"Substrate: {model}  (expected dim {dim})")
    print(f"{'=' * 78}")
    codebook, _vocab = build_codebook(model, dim)
    n, actual_dim = codebook.shape

    results = {"substrate": model, "dim": actual_dim, "n_codebook": n,
               "rotation": {}, "hadamard": {}}

    print(f"\n{'k':>4}  {'rotation acc':>12}  {'rot signal':>10}  "
          f"{'hadamard acc':>12}  {'had signal':>10}")
    print("-" * 70)
    for k in BUNDLE_WIDTHS:
        if k >= n:
            continue
        rot_accs, rot_sigs = [], []
        had_accs, had_sigs = [], []
        for t in range(TRIALS_PER_K):
            rng_r = np.random.default_rng(SEED + 1000 * t + k)
            rng_h = np.random.default_rng(SEED + 2000 * t + k)
            ra, rs, _ = trial_rotation(k, codebook, rng_r)
            ha, hs, _ = trial_hadamard(k, codebook, rng_h)
            rot_accs.append(ra); rot_sigs.append(rs)
            had_accs.append(ha); had_sigs.append(hs)
        rot_acc = float(np.mean(rot_accs))
        rot_sig = float(np.mean(rot_sigs))
        had_acc = float(np.mean(had_accs))
        had_sig = float(np.mean(had_sigs))
        results["rotation"][k] = {"accuracy": rot_acc, "signal_cos": rot_sig}
        results["hadamard"][k] = {"accuracy": had_acc, "signal_cos": had_sig}
        print(f"{k:>4}  {rot_acc:>11.1%}  {rot_sig:>+10.4f}  "
              f"{had_acc:>11.1%}  {had_sig:>+10.4f}")

    return results


def main() -> int:
    out: list[dict] = []
    t0 = time.monotonic()
    for model, dim in SUBSTRATES:
        try:
            out.append(run_substrate(model, dim))
        except Exception as e:
            print(f"FAILED on {model}: {e}", file=sys.stderr)
            out.append({"substrate": model, "error": str(e)})

    print(f"\n{'=' * 78}")
    print(f"Total time: {time.monotonic() - t0:.1f}s")
    print(f"{'=' * 78}")

    out_path = Path(__file__).parent / "rotation_binding_capacity_llm_results.json"
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"\nResults written to {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
