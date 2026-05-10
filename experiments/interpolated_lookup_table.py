"""Substrate-pure interpolated lookup table for exp / ln.

Different architecture from `bound_table_transcendentals.py` — that
experiment bound N table entries into a single 2-component bundle and
ran into the pigeonhole limit (85% relative error on exp, 117% on ln).
This experiment stores the table as a length-N value tensor and looks
up via a soft-index dot product:

  values[i] = f(x_i)                     # precomputed at compile time
  weight[i](x) = max(0, 1 - |x - x_i|/dx)  # triangle, width 2*dx
  lookup(x)  = sum_i weight[i] * values[i]

The triangle activation gives exact linear interpolation: at a sample
point x_i, weight has a single 1.0 and N-1 zeros; between two adjacent
samples, weight has two non-zero values that sum to 1 and blend linearly.
Higher-order interpolation = wider activation kernels.

Substrate-purity check: every step inside `lookup()` is a tensor op
(elementwise subtract, abs, clamp, divide, dot product). No Python
control flow on x. The lookup is one matvec when batched, one dot
product when scalar.

This is what Emma described in the 2026-05-10 chat as "a straight up
function lookup table" — distinct from the VSA-bundled table the prior
attempt built. The "table" here is just an array of values; the
substrate constraint is on the operations, not on the storage shape.
"""
from __future__ import annotations

import math
import time

import torch


def build_table(
    func, lo: float, hi: float, n_samples: int, dtype=torch.float64
) -> tuple[torch.Tensor, torch.Tensor, float, float]:
    """Build the lookup table for `func` on [lo, hi] with `n_samples`
    equally-spaced sample points. Returns (xs, values, lo, dx) where
    dx is the inter-sample spacing.
    """
    xs = torch.linspace(lo, hi, n_samples, dtype=dtype)
    values = torch.tensor(
        [func(float(x)) for x in xs], dtype=dtype
    )
    dx = float((hi - lo) / (n_samples - 1))
    return xs, values, lo, dx


def lookup_scalar(
    xs: torch.Tensor, values: torch.Tensor, dx: float, x: float
) -> torch.Tensor:
    """Single-x lookup. All ops on the table are tensor ops; the only
    scalar is the input x itself, which the caller already holds.

    Triangle weight: w_i = max(0, 1 - |x - x_i|/dx). For x exactly on
    a sample, w has one 1.0; for x between two adjacent samples, w has
    two values that sum to 1 and blend linearly (== linear interpolation).
    """
    d = (xs - x).abs() / dx
    w = (1.0 - d).clamp(min=0.0)
    return torch.dot(w, values)


def lookup_vector(
    xs: torch.Tensor, values: torch.Tensor, dx: float, x: torch.Tensor
) -> torch.Tensor:
    """Batched lookup over a 1D tensor of inputs. Every op is tensor,
    no Python loop. The intermediate weight matrix is shape (B, N).
    """
    # x: (B,), xs: (N,) -> d: (B, N)
    d = (x.unsqueeze(-1) - xs.unsqueeze(0)).abs() / dx
    w = (1.0 - d).clamp(min=0.0)
    return w @ values


def measure(func, name: str, lo: float, hi: float, n_samples: int) -> dict:
    xs, values, _, dx = build_table(func, lo, hi, n_samples)

    # Test on a dense grid that does NOT coincide with sample points.
    # Offset by half a sample so we exercise the worst-case interpolation
    # midpoint between two sample points.
    n_test = 10_000
    x_test = torch.linspace(
        lo + dx / 2, hi - dx / 2, n_test, dtype=torch.float64
    )
    y_true = torch.tensor([func(float(x)) for x in x_test], dtype=torch.float64)
    y_hat = lookup_vector(xs, values, dx, x_test)

    abs_err = (y_hat - y_true).abs()
    rel_err = abs_err / y_true.abs().clamp(min=1e-12)

    # Also time a single scalar lookup for the cost story.
    t0 = time.perf_counter()
    for _ in range(1000):
        lookup_scalar(xs, values, dx, 1.0)
    t_scalar_us = (time.perf_counter() - t0) * 1e3  # ms for 1000 calls = us per call

    return {
        "function": name,
        "domain": (lo, hi),
        "N": n_samples,
        "dx": dx,
        "max_abs_err": float(abs_err.max()),
        "mean_abs_err": float(abs_err.mean()),
        "max_rel_err": float(rel_err.max()),
        "mean_rel_err": float(rel_err.mean()),
        "scalar_lookup_us": t_scalar_us,
    }


def fmt(x: float) -> str:
    if x == 0:
        return "0"
    return f"{x:.2e}"


def main() -> None:
    print("Substrate-pure interpolated lookup table — exp and ln")
    print("=" * 72)
    print(
        "Architecture: length-N value tensor + triangle-weight soft-index"
        " dot product."
    )
    print(
        "Compare against bound-table failure (planning/findings/2026-04-29-...)"
    )
    print("which got rel error ~85% on exp, ~117% on ln regardless of N.")
    print()

    results = []
    cases = [
        (math.exp, "exp", -2.0, 2.0),
        (math.exp, "exp", -5.0, 5.0),
        (math.log, "ln",  0.1, 10.0),
        (math.log, "ln",  0.5, 100.0),
    ]

    header = (
        f"{'function':>8}  {'domain':>14}  {'N':>5}  "
        f"{'dx':>10}  {'max_abs':>10}  {'max_rel':>10}  "
        f"{'mean_rel':>10}  {'us/call':>8}"
    )
    print(header)
    print("-" * len(header))

    for func, name, lo, hi in cases:
        for N in (64, 256, 1024, 4096):
            r = measure(func, name, lo, hi, N)
            results.append(r)
            print(
                f"{r['function']:>8}  "
                f"[{r['domain'][0]:>4.1f},{r['domain'][1]:>5.1f}]  "
                f"{r['N']:>5}  "
                f"{r['dx']:>10.3e}  "
                f"{fmt(r['max_abs_err']):>10}  "
                f"{fmt(r['max_rel_err']):>10}  "
                f"{fmt(r['mean_rel_err']):>10}  "
                f"{r['scalar_lookup_us']:>8.1f}"
            )

    print()
    print("Substrate-purity audit of lookup_scalar / lookup_vector:")
    print("  - (xs - x).abs() / dx     -- elementwise sub + abs + div")
    print("  - (1.0 - d).clamp(min=0)  -- elementwise sub + clamp")
    print("  - torch.dot(w, values)    -- single matvec / dot")
    print(
        "All four are tensor ops. No Python `if` / `for` over x. No scalar"
        " extraction inside the lookup. Build step (linspace + Python list"
        " comprehension over math.exp) is compile-time only."
    )


if __name__ == "__main__":
    main()
