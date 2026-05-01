"""Crosstalk noise accumulation across chained bind-unbind cycles.

Why this experiment exists:
    Reviewer post 2191 (Weak Accept) con #2: "Lacks a formal error
    analysis regarding the accumulation of VSA noise (crosstalk)
    across deep nested operations."
    The single-cycle capacity table (§3.1) measures one bind-unbind.
    Real Sutra programs chain bind / unbind / bundle calls — a
    role-filler record is decoded, the recovered filler becomes the
    role of a sub-record, etc. Each cycle adds noise. This script
    quantifies how that noise accumulates.

What this experiment measures:
    For each frozen LLM substrate {nomic-embed-text, all-minilm,
    mxbai-embed-large}: build an 84-word codebook (same vocab as
    rotation_binding_capacity_llm.py). For chain length N in
    {1, 2, 4, 8, 16, 32}, run T trials. Each trial:
      1. Pick a starting filler vector v_0 from the codebook.
      2. Pick N independent role rotations R_1 ... R_N.
      3. Repeatedly bind: v_i = R_i @ v_{i-1}, plus crosstalk: at
         each step bundle in K-1 distractor (role, filler) pairs
         to simulate the bundle context the unbind has to
         disambiguate against.
      4. Unbind in reverse: v_hat_i = R_i^T @ v_{i+1}, peeling the
         chain back. Optionally clean up via argmax_cosine after
         each unbind.
    Report: cosine of the final recovered v_hat_0 against the
    original v_0 (both normalized), and accuracy of the
    argmax-cosine against the codebook.

    Two flavors per chain length: "raw" (no cleanup between cycles)
    and "snapped" (argmax-cosine cleanup after each unbind, replacing
    the recovered vector with its nearest-codebook entry).

Usage:
    python experiments/crosstalk_chain.py
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np

# Reuse the codebook + Ollama embed code from the capacity experiment.
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from rotation_binding_capacity_llm import (  # noqa: E402
    SUBSTRATES,
    build_codebook,
    haar_rotation,
)

CHAIN_LENGTHS = [1, 2, 4, 8, 16, 32]
BUNDLE_WIDTH = 4   # K-1 distractors per cycle (each cycle bundles k pairs)
TRIALS = 20
SEED = 42


def chain_one_trial(
    codebook: np.ndarray,
    chain_len: int,
    bundle_width: int,
    rng: np.random.Generator,
    cleanup: bool,
) -> tuple[float, bool]:
    """Run one chain trial. Returns (cos to original, accuracy bool)."""
    n, dim = codebook.shape

    # Pick starting filler.
    f0_idx = int(rng.integers(0, n))
    v = codebook[f0_idx].copy()

    # Pre-pick chain-length role rotations.
    chain_role_idxs = rng.choice(n, size=chain_len, replace=False)
    chain_rotations = [haar_rotation(int(r) + 10_000, dim) for r in chain_role_idxs]

    # Forward: at each step bind v with the next chain role and
    # bundle in (bundle_width - 1) distractor (role, filler) pairs.
    history = [v.copy()]
    for i, R in enumerate(chain_rotations):
        # The chain itself: v <- R @ v
        new_v = R @ v
        # Distractor pairs: (bundle_width - 1) random (role, filler) pairs.
        if bundle_width > 1:
            d_role_idxs = rng.choice(n, size=bundle_width - 1, replace=False)
            d_filler_idxs = rng.choice(n, size=bundle_width - 1, replace=False)
            d_rotations = [haar_rotation(int(r) + 50_000 + i, dim) for r in d_role_idxs]
            for Rd, fi in zip(d_rotations, d_filler_idxs):
                new_v = new_v + Rd @ codebook[fi]
            new_v = new_v / (np.linalg.norm(new_v) + 1e-12)
        v = new_v
        history.append(v.copy())

    # Backward: unbind in reverse to peel back to v_0.
    recovered = v.copy()
    for i in range(chain_len - 1, -1, -1):
        recovered = chain_rotations[i].T @ recovered
        recovered = recovered / (np.linalg.norm(recovered) + 1e-12)
        if cleanup:
            sims = codebook @ recovered
            best = int(np.argmax(sims))
            recovered = codebook[best].copy()

    # Cosine to original (both normalized).
    v0_n = codebook[f0_idx] / (np.linalg.norm(codebook[f0_idx]) + 1e-12)
    rec_n = recovered / (np.linalg.norm(recovered) + 1e-12)
    cos = float(np.dot(v0_n, rec_n))
    sims_full = codebook @ rec_n
    accurate = int(np.argmax(sims_full)) == f0_idx
    return cos, accurate


def run_substrate(model: str, dim: int) -> dict:
    print(f"\n{'=' * 78}")
    print(f"Substrate: {model}")
    print(f"{'=' * 78}")
    codebook, _vocab = build_codebook(model, dim)
    n, actual_dim = codebook.shape

    results = {"substrate": model, "dim": actual_dim, "n_codebook": n,
               "raw": {}, "snapped": {}}

    print(f"\nbundle_width={BUNDLE_WIDTH} distractors per cycle, "
          f"trials={TRIALS}")
    print(f"\n{'chain':>5}  "
          f"{'raw cos':>10}  {'raw acc':>9}  "
          f"{'snap cos':>10}  {'snap acc':>9}")
    print("-" * 60)
    for L in CHAIN_LENGTHS:
        if L >= n:
            continue
        cos_raw_list = []
        acc_raw_list = []
        cos_snap_list = []
        acc_snap_list = []
        for t in range(TRIALS):
            rng_r = np.random.default_rng(SEED + 1000 * t + L)
            rng_s = np.random.default_rng(SEED + 1000 * t + L)
            cr, ar = chain_one_trial(codebook, L, BUNDLE_WIDTH, rng_r, cleanup=False)
            cs, as_ = chain_one_trial(codebook, L, BUNDLE_WIDTH, rng_s, cleanup=True)
            cos_raw_list.append(cr); acc_raw_list.append(int(ar))
            cos_snap_list.append(cs); acc_snap_list.append(int(as_))
        raw_cos = float(np.mean(cos_raw_list))
        raw_acc = float(np.mean(acc_raw_list))
        snap_cos = float(np.mean(cos_snap_list))
        snap_acc = float(np.mean(acc_snap_list))
        results["raw"][L] = {"cos": raw_cos, "accuracy": raw_acc}
        results["snapped"][L] = {"cos": snap_cos, "accuracy": snap_acc}
        print(f"{L:>5}  {raw_cos:>+10.4f}  {raw_acc:>9.1%}  "
              f"{snap_cos:>+10.4f}  {snap_acc:>9.1%}")
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

    out_path = HERE / "crosstalk_chain_results.json"
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"Results written to {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
