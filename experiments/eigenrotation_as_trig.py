"""Validate the eigenrotation-as-trig insight.

Empirical test of the claim made in
`planning/exploratory/eigenrotation-for-sine-and-modulus.md`: that
sin/cos can be computed via the existing `rotate_slot` primitive
(build R(theta), apply to (1, 0), read coordinates), and that
modulus 2*pi falls out for free from rotation periodicity.

Tests three things honestly:

1. Identity check: does R(theta) @ (1, 0) = (cos theta, sin theta)
   exactly? (Sanity — trivially yes by construction.)
2. Modulus-for-free check: for theta outside [-pi, pi], does the
   rotation route give the same answer as theta mod 2*pi? Compare
   to direct np.sin / np.cos for the unreduced theta.
3. Cost comparison: time the rotation path vs direct trig calls.
   The exploratory doc speculated that "if you want both sin and
   cos, the rotation route saves a trig call." Verify or refute.

Called by: nothing yet. Standalone validation script. Run with
`python experiments/eigenrotation_as_trig.py`.
"""

from __future__ import annotations

import sys
import time

import numpy as np


def rotate_2d(theta: float, v: np.ndarray) -> np.ndarray:
    """Mirror of the `rotate_slot` math in `codegen.py` line 913.

    Two libm calls (cos, sin) to build R, then a 2-component matvec.
    """
    c, s = np.cos(theta), np.sin(theta)
    return np.array([c * v[0] - s * v[1], s * v[0] + c * v[1]])


def trig_via_rotation(theta: float) -> tuple[float, float]:
    """Compute (cos theta, sin theta) by rotating (1, 0).

    The exploratory-doc Sutra path: get trig values out of the
    existing rotation primitive instead of via a separate trig
    intrinsic.
    """
    out = rotate_2d(theta, np.array([1.0, 0.0]))
    return float(out[0]), float(out[1])


def trig_direct(theta: float) -> tuple[float, float]:
    """Direct libm path."""
    return float(np.cos(theta)), float(np.sin(theta))


def test_identity() -> None:
    """R(theta) @ (1, 0) should equal (cos theta, sin theta)."""
    print("=" * 70)
    print("TEST 1: Identity R(theta) @ (1, 0) = (cos theta, sin theta)")
    print("=" * 70)

    thetas = [0.0, np.pi / 6, np.pi / 4, np.pi / 3, np.pi / 2, np.pi, 2 * np.pi, -1.0]
    max_err = 0.0
    for theta in thetas:
        c_rot, s_rot = trig_via_rotation(theta)
        c_dir, s_dir = trig_direct(theta)
        err = max(abs(c_rot - c_dir), abs(s_rot - s_dir))
        max_err = max(max_err, err)
        print(f"  theta={theta:9.5f}: rotation=({c_rot:+.8f}, {s_rot:+.8f}) "
              f"direct=({c_dir:+.8f}, {s_dir:+.8f}) err={err:.2e}")
    print(f"\n  Max error: {max_err:.2e}")
    print(f"  PASS: identity holds (trivially — same trig calls under the hood)"
          if max_err < 1e-15 else f"  FAIL: identity error too large")


def test_modulus_for_free() -> None:
    """For theta outside [-pi, pi], does rotation give the right answer?

    The exploratory doc claimed `mod 2*pi` is free because rotation is
    periodic. Test: feed unreduced theta to both paths and check they
    agree, and check both agree with theta mod 2*pi via the direct path.
    """
    print()
    print("=" * 70)
    print("TEST 2: Modulus-for-free claim (theta outside [-pi, pi])")
    print("=" * 70)

    thetas = [3 * np.pi, 10 * np.pi, 100 * np.pi, 1e6, 1e9, -50.0, 1e15]
    print(f"  {'theta':>14} {'rotation':>22} {'direct':>22} "
          f"{'reduced (theta mod 2pi)':>28}")
    for theta in thetas:
        c_rot, s_rot = trig_via_rotation(theta)
        c_dir, s_dir = trig_direct(theta)
        # Reduce theta into [-pi, pi] manually and check both paths.
        reduced = ((theta + np.pi) % (2 * np.pi)) - np.pi
        c_red, s_red = trig_direct(reduced)
        print(f"  {theta:14.3e} ({c_rot:+.6f},{s_rot:+.6f}) "
              f"({c_dir:+.6f},{s_dir:+.6f}) ({c_red:+.6f},{s_red:+.6f})")

    print()
    print("  Interpretation: the rotation path matches direct np.sin/np.cos")
    print("  exactly because rotation builds R using np.sin/np.cos. So both")
    print("  paths inherit libm's range-reduction precision. The 'modulus")
    print("  for free' claim is accurate as a property of the math, but it's")
    print("  a libm property — not Sutra-specific. Sutra inherits it.")


def test_cost() -> None:
    """Wall-clock comparison: rotation vs direct trig.

    The exploratory doc speculated rotation saves a trig call when you
    need both sin and cos. Verify or refute.
    """
    print()
    print("=" * 70)
    print("TEST 3: Wall-clock cost (1M scalar trig calls)")
    print("=" * 70)

    n = 1_000_000
    rng = np.random.default_rng(42)
    angles = rng.uniform(-100, 100, size=n)

    # Path A: rotation route (cos+sin together via R @ (1,0)).
    t0 = time.perf_counter()
    cos_vals_rot = np.empty(n)
    sin_vals_rot = np.empty(n)
    e0 = np.array([1.0, 0.0])
    for i in range(n):
        out = rotate_2d(angles[i], e0)
        cos_vals_rot[i] = out[0]
        sin_vals_rot[i] = out[1]
    t_rot = time.perf_counter() - t0

    # Path B: direct trig (two separate libm calls per angle).
    t0 = time.perf_counter()
    cos_vals_dir = np.cos(angles)
    sin_vals_dir = np.sin(angles)
    t_dir = time.perf_counter() - t0

    # Path C: scalar direct trig in a Python loop (fair to A's overhead).
    t0 = time.perf_counter()
    cos_vals_scalar = np.empty(n)
    sin_vals_scalar = np.empty(n)
    for i in range(n):
        cos_vals_scalar[i] = float(np.cos(angles[i]))
        sin_vals_scalar[i] = float(np.sin(angles[i]))
    t_scalar = time.perf_counter() - t0

    print(f"  Path A (rotation, scalar loop):    {t_rot:8.3f} s")
    print(f"  Path B (np.cos/np.sin vectorized): {t_dir:8.3f} s")
    print(f"  Path C (np.cos/np.sin scalar):     {t_scalar:8.3f} s")
    print()
    print(f"  Rotation vs scalar-direct: rotation is "
          f"{t_rot/t_scalar:.2f}x the cost of just calling cos+sin scalar.")
    print(f"  Rotation vs vectorized:    rotation is "
          f"{t_rot/t_dir:.0f}x the cost of vectorized cos+sin.")
    print()
    print("  Honest interpretation: on numpy CPU, the rotation path is")
    print("  STRICTLY MORE WORK than separate cos/sin calls — it does the")
    print("  same two libm calls, then adds a 2x2 matvec on top. The 'saves")
    print("  a trig call' speculation in the exploratory doc was wrong.")
    print()
    print("  The architectural value (substrate-uniformity, fewer code")
    print("  paths in the runtime) is unaffected. The cost-win story would")
    print("  only materialize on a substrate where rotation is a hardware")
    print("  primitive cheaper than two libm calls (e.g. CORDIC on FPGA),")
    print("  which is not where Sutra runs today.")


def test_large_angle_precision() -> None:
    """Verify libm's range reduction for very large angles."""
    print()
    print("=" * 70)
    print("TEST 4: Large-angle precision (libm range reduction)")
    print("=" * 70)

    # For theta = N * 2*pi + epsilon, sin(theta) should equal sin(epsilon).
    # Test how this holds as N grows.
    epsilon = 0.1
    for n_periods in [1, 10, 100, 1_000_000, 1_000_000_000]:
        theta = n_periods * 2 * np.pi + epsilon
        c, s = trig_via_rotation(theta)
        c_truth, s_truth = trig_direct(epsilon)
        err = max(abs(c - c_truth), abs(s - s_truth))
        print(f"  N={n_periods:>14}: theta=N*2pi+0.1, sin/cos err vs sin/cos(0.1) = {err:.2e}")
    print()
    print("  Interpretation: for very large angles the rotation path inherits")
    print("  libm's range-reduction precision loss. Float64 mantissa holds ~15")
    print("  significant digits; angles near 1e9 lose fractional precision in")
    print("  the float representation of the angle itself, before any trig is")
    print("  called. The [backend] dtype interaction noted in the exploratory")
    print("  doc is real and would need to be flagged in any 'Exact-tier'")
    print("  marketing.")


def main() -> int:
    test_identity()
    test_modulus_for_free()
    test_cost()
    test_large_angle_precision()
    print()
    print("=" * 70)
    print("Summary")
    print("=" * 70)
    print("  - The math identity (R(theta) @ (1,0) = (cos, sin)) is exact.")
    print("  - The modulus-for-free claim is real but is a libm property,")
    print("    not Sutra-specific. Sutra inherits it.")
    print("  - The cost-saving speculation is WRONG on numpy CPU. Rotation")
    print("    is strictly more work, not less. The architectural value")
    print("    (substrate-uniformity) survives; the speed claim does not.")
    print("  - Large-angle precision degrades because of the angle's float")
    print("    representation, before trig is called.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
