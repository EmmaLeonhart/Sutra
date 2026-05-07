"""Quantitative head-to-head: Sutra rotation binding vs. TorchHD's
binding schemes (MAP / HRR / FHRR) on the same role-filler retrieval
task, same dimensionality, same codebook.

Reports decode accuracy and signal/noise cosine for each scheme so
the comparison against the standard VSA library is on real numbers
rather than prose.

The task:
    Standard VSA bundled-role-filler retrieval. For a bundle width
    k, generate k (role, filler) pairs, bind each pair via the
    binding scheme under test, sum the bound pairs into a single
    bundle vector, then for each role unbind it and argmax-cosine
    against a 200-filler codebook. Accuracy = fraction of roles
    that recover the matched filler. Signal cos = mean cosine of
    recovered vector to correct filler. Noise cos = mean cosine to
    other participating fillers.

Schemes compared:
    1. Sutra rotation binding — role-seeded Haar-random orthogonal
       Q in 768-d, bind = Q @ filler, unbind = Q^T @ bundle.
    2. TorchHD MAP — bipolar {-1, +1} hypervectors, bind = Hadamard
       product, unbind = same (involution). The classical VSA scheme.
    3. TorchHD HRR — real-valued hypervectors, bind = circular
       convolution, unbind = circular correlation. Plate's holographic
       reduced representation.
    4. TorchHD FHRR — complex-valued (phasor) HRR, bind = element-
       wise complex multiply, unbind = element-wise complex multiply
       with conjugate.

All schemes run on the same dimensionality (d=768) and same
codebook size (200 fillers) for an apples-to-apples comparison.

Usage:
    python experiments/sutra_vs_torchhd.py
"""

from __future__ import annotations

import time
from typing import Callable

import numpy as np
import torch
import torchhd

SEED = 42
DIM = 768
CODEBOOK_SIZE = 200
BUNDLE_WIDTHS = [2, 4, 8, 16, 24, 32, 48, 64, 96, 128]
TRIALS_PER_K = 10


# --- Sutra rotation binding (self-contained, mirrors the runtime) ---

def haar_rotation(seed: int, dim: int = DIM) -> np.ndarray:
    """Role-seeded Haar-random orthogonal matrix."""
    rng = np.random.default_rng(seed)
    G = rng.standard_normal((dim, dim))
    Q, R = np.linalg.qr(G)
    Q = Q * np.sign(np.diag(R))
    return Q


def sutra_run(k: int, codebook: np.ndarray, rng: np.random.Generator) -> tuple[float, float, float]:
    """Sutra rotation binding on k random (role, filler) pairs from codebook."""
    n = codebook.shape[0]
    role_idxs = rng.choice(n, size=k, replace=False)
    filler_idxs = rng.choice(n, size=k, replace=False)
    rotations = [haar_rotation(int(r) + 10_000) for r in role_idxs]

    # Build bundle = sum_i R_i @ filler_i
    bundle = np.zeros(DIM)
    for R, fi in zip(rotations, filler_idxs):
        bundle += R @ codebook[fi]
    bundle /= np.linalg.norm(bundle) + 1e-12

    # For each role, unbind and decode
    correct = 0
    sig_cosines = []
    noise_cosines = []
    for R, fi in zip(rotations, filler_idxs):
        recovered = R.T @ bundle
        # cosine to all codebook fillers
        rn = recovered / (np.linalg.norm(recovered) + 1e-12)
        cn = codebook / (np.linalg.norm(codebook, axis=1, keepdims=True) + 1e-12)
        cos_all = cn @ rn
        # signal = cosine to correct filler; noise = mean cos to OTHER participating fillers
        sig = float(cos_all[fi])
        other_in_bundle = [j for j in filler_idxs if j != fi]
        noise = float(np.mean(cos_all[other_in_bundle])) if other_in_bundle else 0.0
        if int(np.argmax(cos_all)) == int(fi):
            correct += 1
        sig_cosines.append(sig)
        noise_cosines.append(noise)
    return correct / k, float(np.mean(sig_cosines)), float(np.mean(noise_cosines))


# --- TorchHD scheme runner (works for MAP / HRR / FHRR) ---

def torchhd_run(
    k: int,
    n: int,
    vsa_kind: str,
    rng_seed: int,
) -> tuple[float, float, float]:
    """Run k role-filler bind/unbind via the named torchhd VSA type.

    vsa_kind: one of 'MAP', 'HRR', 'FHRR'. Codebook is generated
    from the matching torchhd.random distribution at the requested
    dimensionality.
    """
    torch.manual_seed(rng_seed)
    # codebook of n fillers, k roles drawn separately
    codebook = torchhd.random(n, DIM, vsa=vsa_kind)
    roles = torchhd.random(k, DIM, vsa=vsa_kind)

    # pick k filler indices from the codebook
    filler_idxs = torch.randperm(n)[:k]
    fillers = codebook[filler_idxs]

    # bind each (role, filler) and bundle
    bound = torchhd.bind(roles, fillers)
    bundle = torchhd.multiset(bound)  # multiset == bundle for torchhd

    # for each role, unbind and decode by cosine against full codebook
    correct = 0
    sig_cosines = []
    noise_cosines = []
    for i in range(k):
        recovered = torchhd.bind(bundle, torchhd.inverse(roles[i]))
        sims = torchhd.cosine_similarity(recovered, codebook)
        sims = sims.detach().cpu().numpy().astype(np.float64)
        target = int(filler_idxs[i].item())
        sig = float(sims[target])
        other_in_bundle = [int(filler_idxs[j].item()) for j in range(k) if j != i]
        noise = float(np.mean(sims[other_in_bundle])) if other_in_bundle else 0.0
        if int(np.argmax(sims)) == target:
            correct += 1
        sig_cosines.append(sig)
        noise_cosines.append(noise)

    return correct / k, float(np.mean(sig_cosines)), float(np.mean(noise_cosines))


def main() -> None:
    print("=" * 78)
    print("Sutra (rotation) vs. TorchHD (MAP / HRR / FHRR)")
    print("=" * 78)
    print(f"d = {DIM}, codebook = {CODEBOOK_SIZE} fillers, "
          f"trials per k = {TRIALS_PER_K}")
    print()

    # Sutra codebook: random unit vectors in 768-d
    np.random.seed(SEED)
    rng = np.random.default_rng(SEED)
    sutra_codebook = rng.standard_normal((CODEBOOK_SIZE, DIM))
    sutra_codebook /= np.linalg.norm(sutra_codebook, axis=1, keepdims=True)

    schemes: list[tuple[str, Callable[[int, int], tuple[float, float, float]]]] = [
        ("Sutra-rotation", lambda k, t: sutra_run(k, sutra_codebook, np.random.default_rng(SEED + t))),
        ("TorchHD-MAP",    lambda k, t: torchhd_run(k, CODEBOOK_SIZE, "MAP",  SEED + t)),
        ("TorchHD-HRR",    lambda k, t: torchhd_run(k, CODEBOOK_SIZE, "HRR",  SEED + t)),
        ("TorchHD-FHRR",   lambda k, t: torchhd_run(k, CODEBOOK_SIZE, "FHRR", SEED + t)),
    ]

    # Header
    print(f"{'k':>4}", end="")
    for name, _ in schemes:
        print(f"  {name:>16}", end="")
    print()
    print(f"{'':>4}", end="")
    for _ in schemes:
        print(f"  {'acc | signal':>16}", end="")
    print()

    for k in BUNDLE_WIDTHS:
        print(f"{k:>4}", end="")
        for name, fn in schemes:
            accs, sigs = [], []
            for t in range(TRIALS_PER_K):
                try:
                    acc, sig, _ = fn(k, t)
                    accs.append(acc)
                    sigs.append(sig)
                except Exception as e:
                    accs.append(float("nan"))
                    sigs.append(float("nan"))
            mean_acc = float(np.mean(accs))
            mean_sig = float(np.mean(sigs))
            print(f"  {mean_acc:>5.1%} | {mean_sig:+.3f}", end="")
        print()

    print()
    print("Interpretation:")
    print("  - 'acc' is fraction of unbound queries that argmax-cosine")
    print("    back to the correct filler in the {}-filler codebook.".format(CODEBOOK_SIZE))
    print("  - 'signal' is mean cosine of the unbound recovery to the")
    print("    correct filler (higher = cleaner separation from noise).")
    print()


if __name__ == "__main__":
    t0 = time.monotonic()
    main()
    print(f"Total runtime: {time.monotonic() - t0:.1f}s")
