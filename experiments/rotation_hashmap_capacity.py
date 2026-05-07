"""Rotation-hashmap capacity — extended-state runtime (d=868).

Measures how many distinct keys a rotation-hashmap can store at
d = 868 (post-extended-state) before retrieval accuracy breaks
down.

The extended-state vector (e1ccbbe, 2026-04-23) reserves 100 synthetic
dims alongside 768 semantic dims for a runtime vector of d = 868. The
rotation bind is block-diagonal: Haar in the semantic block, identity
in the synthetic block. Embeddings load as `[semantic | zeros]`. So
operationally, rotation bind + bundle at d=868 with an embed-shaped
input vector is algebraically the same rotation + bundle in the 768-d
semantic block, with 100 inert zero dims along for the ride.

What we want to measure:

1. Does the **hashmap API** (`hashmap_new`/`hashmap_set`/`hashmap_get`
   as runtime methods on `_VSA`) behave the same as raw bind + bundle
   when stressed past the ~32-bundled-bindings threshold found in the
   prior d=768 study (planning/findings/2026-04-22-rotation-binding-
   capacity-results.md)?

2. Does the synthetic block — even though identity-preserved and
   starting zero — shift the curve in any measurable way (e.g. via
   normalization or argmax-cosine denominators)?

3. Cross-talk signature: is the failure mode still signal-magnitude-
   vs-off-codebook-distractor (the d=768 finding), or does some new
   effect appear at d=868?

We exercise the actual compiled `_VSA` from a hello_world compile, then
call hashmap_new/set/get with random d=868 vectors shaped like embed()
output (random semantic block, zero synthetic block). That keeps us on
the real substrate — the same rotation algebra, the same hashmap
runtime the demo programs see — while decoupling the measurement from
Ollama and from clustered-filler effects that belong in a separate
study.

Usage: python experiments/rotation_hashmap_capacity.py
"""
from __future__ import annotations

import os
import sys
import time
import types

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, ".."))
SDK_PATH = os.path.join(REPO_ROOT, "sdk", "sutra-compiler")
sys.path.insert(0, SDK_PATH)

from sutra_compiler.codegen import translate_module  # noqa: E402
from sutra_compiler.lexer import Lexer  # noqa: E402
from sutra_compiler.parser import Parser  # noqa: E402


SEED = 42


def load_vsa():
    """Compile hello_world.su, exec, return the instantiated _VSA.

    hello_world triggers the extended-state layout with defaults —
    semantic_dim=768, synthetic_dim=100, runtime dim=868. Caches from
    prior runs keep the Ollama side cheap.
    """
    path = os.path.join(REPO_ROOT, "examples", "hello_world.su")
    with open(path, encoding="utf-8") as f:
        src = f.read()
    lexer = Lexer(src, file=path)
    tokens = lexer.tokenize()
    parser = Parser(tokens, file=path, diagnostics=lexer.diagnostics)
    module = parser.parse_module()
    py_src = translate_module(module)
    mod = types.ModuleType("_rh_cap_harness")
    mod.__file__ = "<rotation_hashmap_capacity>"
    exec(compile(py_src, mod.__file__, "exec"), mod.__dict__)
    return mod._VSA


def make_embed_shape(n: int, semantic_dim: int, synthetic_dim: int,
                     rng: np.random.RandomState) -> np.ndarray:
    """Random d = (semantic_dim + synthetic_dim) unit vectors with the
    synthetic block zero. Matches the layout `embed()` produces."""
    V = rng.randn(n, semantic_dim)
    V = V / (np.linalg.norm(V, axis=1, keepdims=True) + 1e-12)
    Z = np.zeros((n, synthetic_dim))
    return np.concatenate([V, Z], axis=1)


def run_capacity(vsa, k_values, n_trials, codebook_size, role_pool,
                 rng) -> list[dict]:
    """Sweep k — build a hashmap of k entries, query each, score.

    `role_pool` is a pre-built pool of role vectors; we draw k of them
    per trial. `codebook` is the filler vocabulary; argmax-cosine
    retrieval is against the full codebook (not just the k participating
    fillers) to mirror a realistic dictionary lookup.
    """
    codebook = make_embed_shape(
        codebook_size, vsa.semantic_dim, vsa.synthetic_dim, rng)

    # Warm the rotation cache once for every role we'll use. Each cache
    # miss is a 868x868 QR decomposition — doing it inside the trial
    # loop would dominate runtime.
    print(f"  Pre-computing {len(role_pool)} rotation matrices (d={vsa.dim})...",
          flush=True)
    warm_start = time.time()
    for i in range(len(role_pool)):
        # Force the cache entry to populate by doing a throwaway bind.
        vsa.bind(role_pool[i], role_pool[0])
    print(f"  Done in {time.time() - warm_start:.1f}s.")

    results = []
    for k in k_values:
        if k > len(role_pool) or k > codebook_size:
            print(f"  Skipping k={k} (exceeds pool size).")
            continue

        correct = 0
        total = 0
        signal_sum = 0.0
        noise_sum = 0.0
        noise_count = 0

        for trial in range(n_trials):
            role_idx = rng.choice(len(role_pool), size=k, replace=False)
            filler_idx = rng.choice(codebook_size, size=k, replace=False)

            acc = vsa.hashmap_new()
            for i, j in zip(role_idx, filler_idx):
                acc = vsa.hashmap_set(acc, role_pool[i], codebook[j])

            for i, j in zip(role_idx, filler_idx):
                recovered = vsa.hashmap_get(acc, role_pool[i])
                rec_n = recovered / (np.linalg.norm(recovered) + 1e-12)
                sims = codebook @ rec_n
                best = int(np.argmax(sims))
                total += 1
                if best == j:
                    correct += 1
                signal_sum += float(sims[j])
                for other in filler_idx:
                    if other != j:
                        noise_sum += float(sims[int(other)])
                        noise_count += 1

        accuracy = correct / total if total > 0 else 0.0
        signal_cos = signal_sum / total if total > 0 else 0.0
        noise_cos = noise_sum / noise_count if noise_count > 0 else 0.0
        snr = (signal_cos - noise_cos) / (abs(noise_cos) + 1e-6)
        results.append(dict(
            k=k, accuracy=accuracy, signal_cos_mean=signal_cos,
            noise_cos_mean=noise_cos, snr=snr,
        ))

    return results


def run_reversibility(vsa, n_trials, rng) -> dict:
    """||hashmap_get(hashmap_set(new, k, v), k) - v|| for k=1 stores.

    k=1 isolates round-trip error: one stored value, retrieved by its
    own key, no cross-talk. Non-zero result here means the rotation
    (Haar) isn't acting orthogonally — a numerical-stability canary.
    """
    roles = make_embed_shape(
        n_trials, vsa.semantic_dim, vsa.synthetic_dim, rng)
    vals = make_embed_shape(
        n_trials, vsa.semantic_dim, vsa.synthetic_dim, rng)
    errs = []
    for role, val in zip(roles, vals):
        acc = vsa.hashmap_new()
        acc = vsa.hashmap_set(acc, role, val)
        recovered = vsa.hashmap_get(acc, role)
        errs.append(float(np.linalg.norm(recovered - val)))
    errs_arr = np.array(errs)
    return dict(
        mean=float(errs_arr.mean()),
        max=float(errs_arr.max()),
        min=float(errs_arr.min()),
    )


def print_capacity_table(results: list[dict]) -> None:
    print()
    print(f"  {'k':>3}  {'accuracy':>9}  {'signal cos':>11}  "
          f"{'noise cos':>10}  {'SNR':>10}")
    print(f"  {'-'*3}  {'-'*9}  {'-'*11}  {'-'*10}  {'-'*10}")
    for r in results:
        print(f"  {r['k']:>3}  {r['accuracy']*100:>7.1f}%  "
              f"{r['signal_cos_mean']:>+11.4f}  "
              f"{r['noise_cos_mean']:>+10.4f}  "
              f"{r['snr']:>10.2f}")


def main() -> int:
    rng = np.random.RandomState(SEED)
    print("=" * 72)
    print("Rotation-hashmap capacity — extended-state runtime")
    print("=" * 72)

    print("Loading compiled _VSA from hello_world.su ...", flush=True)
    vsa = load_vsa()
    print(f"  semantic_dim = {vsa.semantic_dim}")
    print(f"  synthetic_dim = {vsa.synthetic_dim}")
    print(f"  runtime dim = {vsa.dim}")
    print("  rotation: block-diagonal (Haar on semantic, identity on synthetic)")
    print()

    print("Experiment A — Reversibility round-trip (hashmap API)")
    print("-" * 72)
    rev = run_reversibility(vsa, n_trials=50, rng=rng)
    print(f"  ||hashmap_get(hashmap_set(new, k, v), k) - v|| over 50 trials")
    print(f"  mean: {rev['mean']:.3e}   max: {rev['max']:.3e}   "
          f"min: {rev['min']:.3e}")
    print()

    print("Experiment B — Capacity curve through hashmap API")
    print("-" * 72)
    k_values = [2, 4, 8, 12, 16, 24, 32, 48, 64, 96, 128]
    codebook_size = 200
    role_pool_size = max(k_values) + 10

    role_pool = make_embed_shape(
        role_pool_size, vsa.semantic_dim, vsa.synthetic_dim, rng)

    results = run_capacity(
        vsa=vsa,
        k_values=k_values,
        n_trials=10,
        codebook_size=codebook_size,
        role_pool=role_pool,
        rng=rng,
    )
    print(f"  Retrieval against a {codebook_size}-filler codebook, "
          f"10 trials per k:")
    print_capacity_table(results)
    print()

    print("=" * 72)
    print("Summary")
    print("=" * 72)
    lossy_k = next((r['k'] for r in results if r['accuracy'] < 0.9), None)
    crit_k = next((r['k'] for r in results if r['accuracy'] < 0.5), None)
    if lossy_k is not None:
        print(f"  First k with accuracy < 90%: k = {lossy_k}")
    else:
        print(f"  No k in the sweep dropped below 90%.")
    if crit_k is not None:
        print(f"  First k with accuracy < 50%: k = {crit_k}")
    else:
        print(f"  No k in the sweep dropped below 50%.")
    print(f"  Hashmap round-trip error: ~{rev['mean']:.1e} (FP roundoff)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
