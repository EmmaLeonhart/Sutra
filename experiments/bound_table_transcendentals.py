"""Proof-of-concept: bound-table lookup for transcendentals.

Tests the user's design absorbed into todo.md § "Transcendental functions —
design absorbed from voice chat" (originally explored in a 2026-04-29 voice
chat; the chat file was deleted 2026-05-02 once the design was inlined):

  - exp and ln stored as bound tables in a reserved 2D plane
  - x -> angle via linear map theta(x) = (x - LO) / (HI - LO) * 2*pi
  - Bound entry i: rotate make_real(f(x_i)) by R(theta_i) in the 2D plane
  - Bundled table: T = sum_i bound_i
  - Lookup f(x): rotate T by R(theta(x))^T, read synthetic[0]
  - "Natural interpolation" should fall out of the rotation algebra

Goal here: measure precision vs N, characterize the cross-talk, see whether
the interpolation behavior matches what the user described before wiring
this into the codegen prelude.

No Sutra dependencies. Pure torch. Run directly.
"""
from __future__ import annotations

import math

import torch


def build_bound_table(
    func, lo: float, hi: float, n_samples: int, angular_range: float = 2 * math.pi,
    dim: int = 2,
) -> tuple[torch.Tensor, float]:
    """Build a bound lookup table for `func` on [lo, hi].

    `angular_range` controls how much of the unit circle the binding
    angles span. Default 2*pi = full circle. Smaller values = bind into
    a sub-arc, eliminating wrap-around crosstalk at the cost of less
    angular separation between adjacent samples.
    """
    # Equally spaced angles in [0, angular_range) — N angles total.
    thetas = torch.arange(n_samples, dtype=torch.float64) * (angular_range / n_samples)
    xs = lo + (thetas / angular_range) * (hi - lo)
    ys = torch.tensor([func(float(x)) for x in xs], dtype=torch.float64)

    T = torch.zeros(dim, dtype=torch.float64)
    T[0] = (ys * torch.cos(thetas)).sum()
    T[1] = (ys * torch.sin(thetas)).sum()

    scale = angular_range / (hi - lo)
    return T, scale


def lookup(
    T: torch.Tensor, scale: float, lo: float, x: float, n_samples: int
) -> tuple[float, float]:
    """Look up f(x) by rotating T by R(theta(x))^T and reading both axes.

    Returns (synthetic[0] reading, synthetic[1] reading) after normalization.
    For Fourier-friendly f, synthetic[0] approximates f(x) and synthetic[1]
    approximates 0 (the "nothing" partner the user described).
    """
    theta = (x - lo) * scale
    c = math.cos(theta)
    s = math.sin(theta)
    # R(theta)^T @ T = (c*T[0] + s*T[1], -s*T[0] + c*T[1])
    # Normalization 2/N: each cos basis function has L2 norm sqrt(N/2),
    # so the inner product is N/2 times the recovered coefficient.
    norm = 2.0 / n_samples
    re = norm * (c * float(T[0]) + s * float(T[1]))
    im = norm * (-s * float(T[0]) + c * float(T[1]))
    return re, im


def measure(name: str, func, lo: float, hi: float, n_samples: int,
            angular_range: float = 2 * math.pi):
    """Build the table, measure recall + interpolation error."""
    T, scale = build_bound_table(func, lo, hi, n_samples, angular_range)

    # Recall at the exact sample points
    sample_thetas = torch.arange(n_samples, dtype=torch.float64) * (2 * math.pi / n_samples)
    sample_xs = lo + (sample_thetas / (2 * math.pi)) * (hi - lo)
    sample_truth = torch.tensor([func(float(x)) for x in sample_xs], dtype=torch.float64)
    sample_recall_pairs = [lookup(T, scale, lo, float(x), n_samples) for x in sample_xs]
    sample_recall = torch.tensor([p[0] for p in sample_recall_pairs], dtype=torch.float64)
    sample_imag = torch.tensor([p[1] for p in sample_recall_pairs], dtype=torch.float64)
    sample_err = (sample_recall - sample_truth).abs()

    # Off-sample (between samples) — test interpolation quality
    n_test = 1000
    test_xs = torch.linspace(lo, hi, n_test, dtype=torch.float64)
    test_truth = torch.tensor([func(float(x)) for x in test_xs], dtype=torch.float64)
    test_recall_pairs = [lookup(T, scale, lo, float(x), n_samples) for x in test_xs]
    test_recall = torch.tensor([p[0] for p in test_recall_pairs], dtype=torch.float64)
    test_imag = torch.tensor([p[1] for p in test_recall_pairs], dtype=torch.float64)
    test_err = (test_recall - test_truth).abs()

    # Truth scale for relative error
    truth_max = float(test_truth.abs().max())

    arc_frac = angular_range / (2 * math.pi)
    print(f"\n=== {name} on [{lo}, {hi}] N={n_samples} arc={arc_frac:.3f}*2pi ===")
    print(
        f"  At-sample  max abs err: {float(sample_err.max()):.4e}  "
        f"(rel {float(sample_err.max()) / truth_max:.4e})"
    )
    print(
        f"  Off-sample max abs err: {float(test_err.max()):.4e}  "
        f"(rel {float(test_err.max()) / truth_max:.4e})"
    )
    print(
        f"  synthetic[1] max abs:   {float(test_imag.abs().max()):.4e}  "
        f"(should be near 0 if function is Fourier-friendly)"
    )
    # Show actual reconstructed values at a few points
    show_xs = torch.linspace(lo, hi, 7, dtype=torch.float64)
    print(f"  truth vs recall at 7 points:")
    for x in show_xs:
        t = func(float(x))
        r, im = lookup(T, scale, lo, float(x), n_samples)
        print(
            f"    x={float(x):+.3f}  truth={t:+.6f}  recall={r:+.6f}  "
            f"err={r - t:+.2e}  syn[1]={im:+.2e}"
        )


def main():
    # Test the user's "limit angular range so cos stays positive" hypothesis.
    # Quarter circle [0, pi/2] keeps all crosstalk positive (cos >= 0 for
    # any angle difference within pi/2).
    print("\n========== FULL CIRCLE (baseline, has wrap-around problem) ==========")
    measure("exp", math.exp, lo=-2.0, hi=2.0, n_samples=1024)

    print("\n========== HALF CIRCLE (eliminates pi-wrap, keeps pi/2-wrap) ==========")
    measure("exp", math.exp, lo=-2.0, hi=2.0, n_samples=1024, angular_range=math.pi)

    print("\n========== QUARTER CIRCLE (cos >= 0 everywhere) ==========")
    measure("exp", math.exp, lo=-2.0, hi=2.0, n_samples=1024,
            angular_range=math.pi / 2)

    print("\n========== EIGHTH CIRCLE (cos >= 0.707) ==========")
    measure("exp", math.exp, lo=-2.0, hi=2.0, n_samples=1024,
            angular_range=math.pi / 4)

    print("\n========== TINY ARC pi/16 (cos >= 0.98) ==========")
    measure("exp", math.exp, lo=-2.0, hi=2.0, n_samples=1024,
            angular_range=math.pi / 16)

    # And ln, same sweep
    print("\n========== ln, full circle ==========")
    measure("ln", math.log, lo=0.1, hi=10.0, n_samples=1024)
    print("\n========== ln, quarter circle ==========")
    measure("ln", math.log, lo=0.1, hi=10.0, n_samples=1024,
            angular_range=math.pi / 2)


if __name__ == "__main__":
    main()
