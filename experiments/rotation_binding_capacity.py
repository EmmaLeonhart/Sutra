"""Rotation-binding capacity experiment — current-prototype variant.

Runs three of the five experiments from
`planning/findings/2026-04-21-rotation-binding-capacity-experiment-design.md`
against the actually-deployed rotation-binding implementation:
role-seeded Haar-random orthogonal rotation in a 768-d substrate,
with no dedicated synthetic subspace (see
`planning/findings/2026-04-22-rotation-binding-prototype-design.md`
for the design compromise).

Experiments 3 and 5 from the design doc (truth-axis orthogonality
and fuzzy composition on the truth axis) are skipped: they require
extended-state-vector runtime support that has not yet landed.

The three experiments run here:

1. **Capacity curve.** Sweep k = number of (role, filler) bindings
   in a bundle over a wide range. Report recovery accuracy per k
   (fraction of queries that argmax-cosine back to the stored filler).
   Answers the question: at what bundle size does rotation binding
   start to fail on a realistic codebook size?

2. **Reversibility.** Confirm that `unbind(role, bind(role, x)) = x`
   within floating-point tolerance. Trivial for Haar rotation, but
   worth measuring so the numerical stability story is on record.

3. **Cross-talk magnitude.** For each k, measure the expected cosine
   between the recovered filler and the correct filler (signal) vs.
   between the recovered filler and a non-matching filler (noise).
   The signal-to-noise ratio predicts where argmax-cosine cleanup
   fails.

Uses all-random vectors rather than Ollama lookups — the capacity of
rotation binding is a property of the rotation algebra, not the
vector distribution. Running on Ollama would add ~30s of API
roundtrips and wouldn't change the conclusions.

Usage: python experiments/rotation_binding_capacity.py
"""
from __future__ import annotations

import hashlib
import os
import sys
import time

import numpy as np

SEED = 42
DIM = 768

# ---------------------------------------------------------------------
# Rotation-binding primitives — a self-contained reimplementation that
# mirrors what `codegen_numpy.py` emits. We don't compile a .su program
# because we want explicit control over trial parameters (k, noise,
# etc.) that the surface language doesn't expose.
# ---------------------------------------------------------------------


def haar_rotation(seed: int, dim: int = DIM) -> np.ndarray:
    """Haar-random orthogonal matrix, seeded."""
    rng = np.random.RandomState(seed)
    A = rng.randn(dim, dim)
    Q, R = np.linalg.qr(A)
    d = np.sign(np.diag(R))
    d[d == 0] = 1.0
    return Q * d


def _role_hash(role: np.ndarray) -> int:
    """Deterministic hash of a role vector, matching codegen_numpy's."""
    h = hashlib.blake2b(role.tobytes(), digest_size=8).digest()
    return int.from_bytes(h, "little") & 0xFFFFFFFF


class RotationRuntime:
    """Mini runtime with rotation cache, matching codegen_numpy.py."""

    def __init__(self, dim: int = DIM) -> None:
        self.dim = dim
        self._cache: dict[int, np.ndarray] = {}

    def rotation_for(self, role: np.ndarray) -> np.ndarray:
        key = _role_hash(role)
        if key not in self._cache:
            self._cache[key] = haar_rotation(key, self.dim)
        return self._cache[key]

    def bind(self, role: np.ndarray, filler: np.ndarray) -> np.ndarray:
        return self.rotation_for(role) @ filler

    def unbind(self, role: np.ndarray, record: np.ndarray) -> np.ndarray:
        return self.rotation_for(role).T @ record

    def bundle(self, *vectors: np.ndarray) -> np.ndarray:
        s = np.sum(np.stack(vectors), axis=0)
        n = np.linalg.norm(s)
        return s / n if n > 0 else s


def random_unit_vectors(n: int, dim: int, rng: np.random.RandomState) -> np.ndarray:
    V = rng.randn(n, dim)
    V = V / (np.linalg.norm(V, axis=1, keepdims=True) + 1e-12)
    return V


# ---------------------------------------------------------------------
# Experiment 1 + 3: Capacity curve + cross-talk
# ---------------------------------------------------------------------


def run_capacity_and_crosstalk(
    k_values: list[int],
    n_trials: int,
    filler_codebook_size: int,
    role_pool_size: int,
    rng: np.random.RandomState,
) -> list[dict]:
    """Sweep k. For each k, measure recovery accuracy + signal / noise.

    Pre-computes a large role pool + filler codebook so the rotation
    matrices are drawn once and reused across trials (saves ~15 minutes
    of QR decompositions).

    Returns a list of per-k dicts with keys:
      k, accuracy, signal_cos_mean, noise_cos_mean, snr
    """
    vsa = RotationRuntime()

    # Pool of roles and fillers used across all trials.
    role_pool = random_unit_vectors(role_pool_size, DIM, rng)
    filler_codebook = random_unit_vectors(filler_codebook_size, DIM, rng)

    # Warm the rotation cache by accessing each role once.
    print(f"  Pre-computing {role_pool_size} rotation matrices...",
          flush=True)
    warm_start = time.time()
    for i in range(role_pool_size):
        vsa.rotation_for(role_pool[i])
    print(f"  Done in {time.time() - warm_start:.1f}s.")

    results = []
    for k in k_values:
        if k > role_pool_size or k > filler_codebook_size:
            print(f"  Skipping k={k} (exceeds pool size).")
            continue

        correct = 0
        total = 0
        signal_sum = 0.0
        noise_sum = 0.0
        noise_count = 0

        for trial in range(n_trials):
            # Pick k distinct roles and k distinct fillers.
            role_idx = rng.choice(role_pool_size, size=k, replace=False)
            filler_idx = rng.choice(filler_codebook_size, size=k, replace=False)

            # Build the bundle.
            terms = [vsa.bind(role_pool[i], filler_codebook[j])
                     for i, j in zip(role_idx, filler_idx)]
            record = vsa.bundle(*terms)

            # Query each role, verify argmax lands on the matched filler.
            for i, j in zip(role_idx, filler_idx):
                recovered = vsa.unbind(role_pool[i], record)
                # Cosine with each filler in the CODEBOOK (not just the k
                # participating fillers — realistic query against an
                # external dictionary).
                rec_n = recovered / (np.linalg.norm(recovered) + 1e-12)
                sims = filler_codebook @ rec_n
                best = int(np.argmax(sims))
                total += 1
                if best == j:
                    correct += 1
                # Cross-talk metric: cosine to correct filler (signal)
                # vs. cosine to other participating fillers (noise).
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


# ---------------------------------------------------------------------
# Experiment 4: Reversibility round-trip
# ---------------------------------------------------------------------


def run_reversibility(n_trials: int, rng: np.random.RandomState) -> dict:
    """Measure ||unbind(role, bind(role, x)) - x||."""
    vsa = RotationRuntime()
    roles = random_unit_vectors(n_trials, DIM, rng)
    xs = random_unit_vectors(n_trials, DIM, rng)
    errs = []
    for role, x in zip(roles, xs):
        bound = vsa.bind(role, x)
        recovered = vsa.unbind(role, bound)
        errs.append(float(np.linalg.norm(recovered - x)))
    errs_arr = np.array(errs)
    return dict(
        mean=float(errs_arr.mean()),
        max=float(errs_arr.max()),
        min=float(errs_arr.min()),
    )


# ---------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------


def print_capacity_table(results: list[dict]) -> None:
    print()
    print(f"  {'k':>3}  {'accuracy':>9}  {'signal cos':>11}  "
          f"{'noise cos':>10}  {'SNR':>7}")
    print(f"  {'-'*3}  {'-'*9}  {'-'*11}  {'-'*10}  {'-'*7}")
    for r in results:
        print(f"  {r['k']:>3}  {r['accuracy']*100:>7.1f}%  "
              f"{r['signal_cos_mean']:>+11.4f}  "
              f"{r['noise_cos_mean']:>+10.4f}  "
              f"{r['snr']:>7.2f}")


def main() -> int:
    rng = np.random.RandomState(SEED)
    print("=" * 72)
    print("Rotation-binding capacity experiment (current prototype, d=768)")
    print("=" * 72)
    print("Substrate: role-seeded Haar-random orthogonal in 768-d (the")
    print("implementation that landed 2026-04-22; no synthetic subspace).")
    print()

    # --- Reversibility ---
    print("Experiment 4 — Reversibility round-trip")
    print("-" * 72)
    rev = run_reversibility(n_trials=100, rng=rng)
    print(f"  ||unbind(role, bind(role, x)) - x||")
    print(f"  mean: {rev['mean']:.3e}   max: {rev['max']:.3e}   "
          f"min: {rev['min']:.3e}")
    print(f"  Interpretation: Haar Q is orthogonal so Q^T Q = I exactly.")
    print(f"  Any error above 1e-10 would indicate numerical drift.")
    print()

    # --- Capacity / cross-talk ---
    print("Experiment 1+3 — Capacity curve and cross-talk")
    print("-" * 72)
    k_values = [2, 4, 8, 12, 16, 24, 32, 48, 64, 96, 128]
    results = run_capacity_and_crosstalk(
        k_values=k_values,
        n_trials=10,
        filler_codebook_size=200,
        role_pool_size=200,
        rng=rng,
    )
    print("  Recovery against a 200-filler codebook, 10 trials per k:")
    print_capacity_table(results)
    print()
    print("  Interpretation:")
    print("  - `accuracy` is fraction of queries where argmax-cosine lands")
    print("    on the matched filler (200-way choice).")
    print("  - `signal cos` is the mean cosine between recovered and correct")
    print("    filler. `noise cos` is the mean cosine to other participating")
    print("    fillers.")
    print("  - SNR = (signal - noise) / |noise|. Larger = better separation.")
    print("  - Theory: signal ~= 1/k for bundled-k retrieval, noise ~= 1/sqrt(d).")
    print("    Intersection is around k ~= sqrt(d) ~= 28 for d=768.")
    print()

    print("=" * 72)
    print("Summary")
    print("=" * 72)
    # Find the crossover k where accuracy < 0.9
    lossy_k = next((r['k'] for r in results if r['accuracy'] < 0.9), None)
    crit_k = next((r['k'] for r in results if r['accuracy'] < 0.5), None)
    if lossy_k is not None:
        print(f"  First k with accuracy < 90%: k = {lossy_k}")
    if crit_k is not None:
        print(f"  First k with accuracy < 50%: k = {crit_k}")
    print(f"  Reversibility error: ~{rev['mean']:.1e} (FP roundoff)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
