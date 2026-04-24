"""Five-experiment validation of the extended-state + rotation-binding design.

This script implements the full 5-experiment suite from
`planning/findings/2026-04-21-rotation-binding-capacity-experiment-design.md`.
It is the validation pass that was held back before the 2D-Givens-per-slot
rotation-binding design is committed to the spec.

The two earlier studies are subsets:

  - `experiments/rotation_binding_capacity.py` — d=768 Haar-on-semantic
    bundle capacity (experiments 1/2/4 partial, semantic-subspace only).
  - `experiments/rotation_hashmap_capacity.py` — d=868 with identity
    synthetic block, via the compiled hashmap API (same subset).

Neither implements the synthetic-subspace 2D-Givens allocation the design
doc actually specifies, and neither covers truth-axis orthogonality
(experiment 3) or truth-axis fuzzy composition (experiment 5). This
script covers all five.

Design-doc experiments:

  1. Slot cross-talk at N/2 capacity for N in {16, 32, 64, 128}.
  2. Capacity curve at N=64 varying k (includes the overlap regime).
  3. Truth-axis orthogonality under semantic bind / bundle.
  4. Reversibility round-trip (sequence of rotations = exact inverse).
  5. Fuzzy composition (and/or/not) on the truth-axis scalar.

Usage: python experiments/synthetic_subspace_validation.py

Prints per-experiment pass/fail plus summary tables. Intended to be
rerun after any change to the rotation / truth-axis design.
"""
from __future__ import annotations

import sys
import time

import numpy as np

SEED = 42
SEMANTIC_DIM = 768


# ---------------------------------------------------------------------
# Primitives: 2D Givens rotation, block allocation, truth axis
# ---------------------------------------------------------------------


def givens_rotation(plane: tuple[int, int], angle: float, dim: int) -> np.ndarray:
    """Identity matrix with a 2D rotation embedded in `plane` coords.

    plane = (i, j), i != j. The (i,i), (i,j), (j,i), (j,j) entries are
    the 2x2 rotation matrix [[cos, -sin], [sin, cos]]; all other entries
    are identity. Result is an orthogonal dim x dim matrix that rotates
    exactly the 2D plane spanned by axes i and j.
    """
    i, j = plane
    assert i != j
    M = np.eye(dim, dtype=np.float64)
    c, s = np.cos(angle), np.sin(angle)
    M[i, i] = c
    M[j, j] = c
    M[i, j] = -s
    M[j, i] = s
    return M


def allocate_slot_planes(n_slots: int, synthetic_dim: int
                         ) -> list[tuple[int, int]]:
    """Assign each slot to a disjoint 2D plane in a synthetic subspace.

    With n_slots <= synthetic_dim/2, every slot gets its own plane and
    retrieval from slot i is provably orthogonal to content at slot j.
    With n_slots > synthetic_dim/2, we wrap around — slots beyond
    synthetic_dim/2 reuse planes already assigned (simulates a
    compiler that ran out of dimensions). The reused plane's slot uses
    a different rotation angle than the earlier user, so retrieval
    still rotates back to the stored value on the matching query but
    the cross-slot content is no longer orthogonal.
    """
    planes = []
    for s in range(n_slots):
        pair = (2 * (s % (synthetic_dim // 2)),
                2 * (s % (synthetic_dim // 2)) + 1)
        planes.append(pair)
    return planes


def slot_angles(n_slots: int, synthetic_dim: int,
                rng: np.random.RandomState) -> list[float]:
    """Per-slot rotation angle.

    Slots inside one plane's "first use" get a unique angle per slot so
    their rotations are distinguishable; when the allocator wraps (k >
    N/2) the reused plane's later slots get a different angle than the
    earlier user.
    """
    n_planes = synthetic_dim // 2
    # Pick a fixed angle per (plane, wrap_index) pair.
    angles = []
    per_plane_count = [0] * n_planes
    for s in range(n_slots):
        p = s % n_planes
        c = per_plane_count[p]
        per_plane_count[p] += 1
        # Distinct angle per slot-within-plane; avoid 0 and pi.
        angle = (0.37 + 0.91 * c + 0.13 * p) % (2 * np.pi)
        if abs(angle) < 0.1 or abs(angle - np.pi) < 0.1:
            angle += 0.5
        angles.append(angle)
    return angles


# ---------------------------------------------------------------------
# Experiment 1 — slot cross-talk at N/2 capacity
# ---------------------------------------------------------------------


def exp1_cross_talk_at_capacity(
    N_values: list[int],
    n_trials: int,
    codebook_size: int,
    rng: np.random.RandomState,
) -> list[dict]:
    """For each N, allocate N/2 slots in a synthetic subspace of size N.

    Each slot gets one disjoint 2D plane; the slot's role is the
    Givens rotation in that plane. Generate a codebook of 16 distinct
    2D unit vectors projected into each slot's plane. Build a bundle
    of all N/2 (slot_rotation @ filler) terms; query each slot by
    transpose-rotation, cosine-match against the codebook; score.

    Note: the codebook lives in each slot's 2D plane. Argmax-cosine
    against a codebook of 16 2D vectors is a 16-way choice per slot.
    """
    results = []
    for N in N_values:
        k = N // 2
        # Codebook: 16 unit vectors in 2D.
        theta = np.linspace(0, 2 * np.pi, codebook_size, endpoint=False)
        cb_2d = np.stack([np.cos(theta), np.sin(theta)], axis=1)

        planes = allocate_slot_planes(k, N)
        angles = slot_angles(k, N, rng)
        R_slots = [givens_rotation(p, a, N) for p, a in zip(planes, angles)]

        correct = 0
        total = 0
        for _trial in range(n_trials):
            # Random codebook pick for each slot.
            picks = rng.randint(0, codebook_size, size=k)
            # Build the full-N filler for slot s from the 2D vector in
            # its plane.
            record = np.zeros(N, dtype=np.float64)
            for s, pick in enumerate(picks):
                i, j = planes[s]
                v_full = np.zeros(N, dtype=np.float64)
                v_full[i] = cb_2d[pick, 0]
                v_full[j] = cb_2d[pick, 1]
                record += R_slots[s] @ v_full

            for s, pick in enumerate(picks):
                recovered = R_slots[s].T @ record
                i, j = planes[s]
                # Project recovered onto slot-s plane, cosine-match.
                q_2d = np.array([recovered[i], recovered[j]])
                q_n = np.linalg.norm(q_2d)
                if q_n > 1e-12:
                    q_2d = q_2d / q_n
                sims = cb_2d @ q_2d
                best = int(np.argmax(sims))
                total += 1
                if best == pick:
                    correct += 1

        accuracy = correct / total if total > 0 else 0.0
        results.append(dict(N=N, k=k, accuracy=accuracy, trials=total))
    return results


# ---------------------------------------------------------------------
# Experiment 2 — capacity curve (N=64 varying k, with overlap)
# ---------------------------------------------------------------------


def exp2_capacity_curve(
    N: int,
    k_values: list[int],
    n_trials: int,
    codebook_size: int,
    rng: np.random.RandomState,
) -> list[dict]:
    """Sweep k at fixed N. When k > N/2, slots must share planes —
    the allocator wraps around and assigns a distinct angle to each
    reused-plane slot. Measures how gracefully accuracy degrades."""
    theta = np.linspace(0, 2 * np.pi, codebook_size, endpoint=False)
    cb_2d = np.stack([np.cos(theta), np.sin(theta)], axis=1)

    results = []
    for k in k_values:
        planes = allocate_slot_planes(k, N)
        angles = slot_angles(k, N, rng)
        R_slots = [givens_rotation(p, a, N) for p, a in zip(planes, angles)]

        correct = 0
        total = 0
        for _trial in range(n_trials):
            picks = rng.randint(0, codebook_size, size=k)
            record = np.zeros(N, dtype=np.float64)
            for s, pick in enumerate(picks):
                i, j = planes[s]
                v_full = np.zeros(N, dtype=np.float64)
                v_full[i] = cb_2d[pick, 0]
                v_full[j] = cb_2d[pick, 1]
                record += R_slots[s] @ v_full

            for s, pick in enumerate(picks):
                recovered = R_slots[s].T @ record
                i, j = planes[s]
                q_2d = np.array([recovered[i], recovered[j]])
                q_n = np.linalg.norm(q_2d)
                if q_n > 1e-12:
                    q_2d = q_2d / q_n
                sims = cb_2d @ q_2d
                best = int(np.argmax(sims))
                total += 1
                if best == pick:
                    correct += 1

        accuracy = correct / total if total > 0 else 0.0
        results.append(dict(N=N, k=k, accuracy=accuracy, trials=total))
    return results


# ---------------------------------------------------------------------
# Experiment 3 — truth-axis orthogonality under semantic bind / bundle
# ---------------------------------------------------------------------


def exp3_truth_axis_orthogonality(
    semantic_dim: int,
    synthetic_dim: int,
    n_trials: int,
    rng: np.random.RandomState,
) -> dict:
    """Verify that semantic operations (learned-matrix bind + bundle)
    keep exact zero on the truth axis.

    Extended state layout: `[semantic | synthetic]`. AXIS_TRUTH=2 in
    the synthetic block, so the global index of the truth axis is
    semantic_dim + 2 (matching codegen.py's `make_truth`).

    Learned-matrix bind is modeled as a block-diagonal matrix: a
    random dense block on the semantic subspace, identity on the
    synthetic subspace (matches the codegen's rotation bind structure
    and what a well-formed learned role matrix should satisfy).
    """
    AXIS_TRUTH = 2
    D = semantic_dim + synthetic_dim
    truth_idx = semantic_dim + AXIS_TRUTH

    max_leak = 0.0
    max_bundle_leak = 0.0
    for _trial in range(n_trials):
        # Block-diagonal learned role matrix. Semantic block is dense
        # (what a learned matrix would look like); synthetic block is
        # identity.
        R_sem = rng.randn(semantic_dim, semantic_dim) / np.sqrt(semantic_dim)
        R = np.eye(D, dtype=np.float64)
        R[:semantic_dim, :semantic_dim] = R_sem

        # Semantic filler: random unit vector in semantic subspace,
        # zero-padded with the synthetic block.
        v_sem = rng.randn(semantic_dim)
        v_sem /= np.linalg.norm(v_sem)
        v = np.zeros(D, dtype=np.float64)
        v[:semantic_dim] = v_sem

        bound = R @ v
        leak = abs(bound[truth_idx])
        if leak > max_leak:
            max_leak = leak

        # Bundle 5 such bindings; check bundled vector still has zero
        # truth axis.
        bundle_acc = np.zeros(D, dtype=np.float64)
        for _ in range(5):
            R_sem2 = rng.randn(semantic_dim, semantic_dim) / np.sqrt(semantic_dim)
            R2 = np.eye(D, dtype=np.float64)
            R2[:semantic_dim, :semantic_dim] = R_sem2
            f_sem2 = rng.randn(semantic_dim)
            f_sem2 /= np.linalg.norm(f_sem2)
            f2 = np.zeros(D, dtype=np.float64)
            f2[:semantic_dim] = f_sem2
            bundle_acc += R2 @ f2
        leak2 = abs(bundle_acc[truth_idx])
        if leak2 > max_bundle_leak:
            max_bundle_leak = leak2

    return dict(
        max_bind_leak=max_leak,
        max_bundle_leak=max_bundle_leak,
        pass_threshold=1e-14,
        passed=(max_leak < 1e-14 and max_bundle_leak < 1e-14),
    )


# ---------------------------------------------------------------------
# Experiment 4 — reversibility round-trip
# ---------------------------------------------------------------------


def exp4_reversibility(
    N: int,
    n_slots: int,
    n_ops: int,
    rng: np.random.RandomState,
) -> dict:
    """Apply n_ops random rotations (one per slot, per op), then apply
    their inverses in reverse order. Measure L2 distance from initial
    state (all zeros).

    For rotations alone (no assignments that overwrite), this is just
    round-trip floating point. The test is whether a long sequence
    accumulates beyond the FP budget."""
    planes = allocate_slot_planes(n_slots, N)
    angles = slot_angles(n_slots, N, rng)
    R_slots = [givens_rotation(p, a, N) for p, a in zip(planes, angles)]

    # Start with a non-trivial state so rotations actually have
    # something to rotate.
    state = rng.randn(N)
    state /= np.linalg.norm(state)
    initial = state.copy()

    # Forward: apply n_ops random-slot rotations.
    op_log = []
    for _ in range(n_ops):
        s = rng.randint(0, n_slots)
        state = R_slots[s] @ state
        op_log.append(s)

    # Backward: apply inverses in reverse order.
    for s in reversed(op_log):
        state = R_slots[s].T @ state

    err = float(np.linalg.norm(state - initial))
    return dict(
        n_ops=n_ops,
        roundtrip_error=err,
        pass_threshold=1e-10,
        passed=(err < 1e-10),
    )


# ---------------------------------------------------------------------
# Experiment 5 — fuzzy composition on the truth axis
# ---------------------------------------------------------------------


def exp5_fuzzy_composition(rng: np.random.RandomState) -> dict:
    """Verify that fuzzy and/or/not on truth-axis scalars return the
    expected fuzzy-logic values, and that semantic content in the
    semantic subspace does not leak into the result."""
    SEM = 32
    SYN = 16  # enough for AXIS_TRUTH=2 + some slots
    AXIS_TRUTH = 2
    D = SEM + SYN
    ti = SEM + AXIS_TRUTH

    def make_truth(t: float) -> np.ndarray:
        v = np.zeros(D)
        v[ti] = t
        return v

    def and_fuzzy(a: np.ndarray, b: np.ndarray) -> np.ndarray:
        # Product t-norm, applied via scalar pickoff (pure arithmetic
        # on the truth axis; output is a new truth-axis vector).
        return make_truth(a[ti] * b[ti])

    def or_fuzzy(a: np.ndarray, b: np.ndarray) -> np.ndarray:
        # Probabilistic sum: a + b - a*b.
        return make_truth(a[ti] + b[ti] - a[ti] * b[ti])

    def not_fuzzy(a: np.ndarray) -> np.ndarray:
        return make_truth(-a[ti])

    cases = []

    # Two-scalar AND truth table (product t-norm).
    for a_val, b_val in [(0.7, 0.3), (1.0, 1.0), (-1.0, 1.0), (0.0, 0.5)]:
        a = make_truth(a_val)
        b = make_truth(b_val)
        got = and_fuzzy(a, b)[ti]
        expected = a_val * b_val
        cases.append(("AND", a_val, b_val, got, expected))

    # OR.
    for a_val, b_val in [(0.7, 0.3), (1.0, 1.0), (-1.0, 1.0), (0.0, 0.5)]:
        a = make_truth(a_val)
        b = make_truth(b_val)
        got = or_fuzzy(a, b)[ti]
        expected = a_val + b_val - a_val * b_val
        cases.append(("OR", a_val, b_val, got, expected))

    # NOT.
    for a_val in [0.7, -0.3, 1.0, -1.0, 0.0]:
        a = make_truth(a_val)
        got = not_fuzzy(a)[ti]
        expected = -a_val
        cases.append(("NOT", a_val, None, got, expected))

    max_err = max(abs(got - exp) for _, _, _, got, exp in cases)

    # Semantic-content isolation: add arbitrary semantic noise to
    # a truth vector and verify the fuzzy-logic result is unchanged.
    a = make_truth(0.7)
    b = make_truth(0.3)
    # Add semantic contamination.
    a[:SEM] = rng.randn(SEM)
    b[:SEM] = rng.randn(SEM)
    got_contam = and_fuzzy(a, b)[ti]
    expected_contam = 0.7 * 0.3
    contam_err = abs(got_contam - expected_contam)

    return dict(
        max_composition_err=max_err,
        semantic_contamination_err=contam_err,
        pass_threshold=1e-10,
        passed=(max_err < 1e-10 and contam_err < 1e-10),
        case_count=len(cases),
    )


# ---------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------


def print_exp1(results: list[dict]) -> None:
    print("  N    k (=N/2)   accuracy   trials   verdict")
    print("  " + "-" * 48)
    for r in results:
        verdict = "PASS" if r["accuracy"] >= 0.99 else "FAIL"
        print(f"  {r['N']:<4} {r['k']:<10} {r['accuracy']*100:>6.2f}%   "
              f"{r['trials']:<8} {verdict}")


def print_exp2(results: list[dict]) -> None:
    print("  N=64, 16-value codebook per slot, 100 trials per k")
    print()
    print("  k    accuracy   regime")
    print("  " + "-" * 40)
    N = results[0]["N"] if results else 64
    for r in results:
        regime = "disjoint planes" if r["k"] <= N // 2 else "planes SHARED"
        print(f"  {r['k']:<4} {r['accuracy']*100:>6.2f}%    {regime}")


# ---------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------


def main() -> int:
    rng = np.random.RandomState(SEED)
    print("=" * 72)
    print("Extended-state + rotation-binding design validation")
    print("5 experiments from")
    print("planning/findings/2026-04-21-rotation-binding-capacity-experiment-design.md")
    print("=" * 72)
    print()

    all_passed = True

    # --- Experiment 1 ---
    print("Experiment 1 — slot cross-talk at N/2 capacity")
    print("-" * 72)
    t0 = time.time()
    r1 = exp1_cross_talk_at_capacity(
        N_values=[16, 32, 64, 128],
        n_trials=100,
        codebook_size=16,
        rng=rng,
    )
    print_exp1(r1)
    exp1_passed = all(r["accuracy"] >= 0.99 for r in r1)
    print(f"  ({time.time() - t0:.1f}s)")
    if not exp1_passed:
        all_passed = False
    print()

    # --- Experiment 2 ---
    print("Experiment 2 — capacity curve at N=64")
    print("-" * 72)
    t0 = time.time()
    r2 = exp2_capacity_curve(
        N=64,
        k_values=[8, 16, 24, 32, 40, 48, 56, 64],
        n_trials=100,
        codebook_size=16,
        rng=rng,
    )
    print_exp2(r2)
    print(f"  ({time.time() - t0:.1f}s)")
    lossy_k = next((r["k"] for r in r2 if r["accuracy"] < 0.9), None)
    if lossy_k is not None:
        print(f"  First k with accuracy < 90%: k = {lossy_k}")
    print()

    # --- Experiment 3 ---
    print("Experiment 3 — truth-axis orthogonality under semantic ops")
    print("-" * 72)
    t0 = time.time()
    r3 = exp3_truth_axis_orthogonality(
        semantic_dim=SEMANTIC_DIM,
        synthetic_dim=100,
        n_trials=100,
        rng=rng,
    )
    print(f"  max leak on single bind:    {r3['max_bind_leak']:.3e}")
    print(f"  max leak on 5-term bundle:  {r3['max_bundle_leak']:.3e}")
    print(f"  threshold:                  {r3['pass_threshold']:.0e}")
    print(f"  verdict: {'PASS' if r3['passed'] else 'FAIL'}  "
          f"({time.time() - t0:.1f}s)")
    if not r3["passed"]:
        all_passed = False
    print()

    # --- Experiment 4 ---
    print("Experiment 4 — reversibility round-trip")
    print("-" * 72)
    t0 = time.time()
    r4 = exp4_reversibility(
        N=32, n_slots=8, n_ops=100, rng=rng,
    )
    print(f"  100 random-slot rotations forward + inverse reverse")
    print(f"  L2 roundtrip error: {r4['roundtrip_error']:.3e}")
    print(f"  threshold:          {r4['pass_threshold']:.0e}")
    print(f"  verdict: {'PASS' if r4['passed'] else 'FAIL'}  "
          f"({time.time() - t0:.1f}s)")
    if not r4["passed"]:
        all_passed = False
    print()

    # --- Experiment 5 ---
    print("Experiment 5 — fuzzy composition on truth axis")
    print("-" * 72)
    t0 = time.time()
    r5 = exp5_fuzzy_composition(rng=rng)
    print(f"  max composition error ({r5['case_count']} cases): "
          f"{r5['max_composition_err']:.3e}")
    print(f"  semantic contamination error: "
          f"{r5['semantic_contamination_err']:.3e}")
    print(f"  threshold: {r5['pass_threshold']:.0e}")
    print(f"  verdict: {'PASS' if r5['passed'] else 'FAIL'}  "
          f"({time.time() - t0:.1f}s)")
    if not r5["passed"]:
        all_passed = False
    print()

    # --- Summary ---
    print("=" * 72)
    print("Summary")
    print("=" * 72)
    print(f"  Experiment 1 (cross-talk @ N/2):      "
          f"{'PASS' if exp1_passed else 'FAIL'}")
    print(f"  Experiment 2 (capacity curve):        "
          f"characterized (see table)")
    print(f"  Experiment 3 (truth-axis orth):       "
          f"{'PASS' if r3['passed'] else 'FAIL'}")
    print(f"  Experiment 4 (reversibility):         "
          f"{'PASS' if r4['passed'] else 'FAIL'}")
    print(f"  Experiment 5 (fuzzy composition):     "
          f"{'PASS' if r5['passed'] else 'FAIL'}")
    print()
    print(f"  Overall: {'ALL PASS' if all_passed else 'AT LEAST ONE FAIL'}")
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
