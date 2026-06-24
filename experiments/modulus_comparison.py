"""Compare the two substrate-pure floor-modulus implementations.

Sutra exposes `Math.mod`, `Math.rotation_mod`, and `Math.sawtooth_mod`.
Today `Math.mod` aliases `rotation_mod` because rotation is the
user-preferred default and is exact away from boundaries. This script
measures **both** approaches against Python floor-mod ground truth on
a dense grid and times them on a representative batch, so the default
can be flipped if the data says so.

Two questions:

  1. **Accuracy.** Where in the period is each form most wrong, and
     by how much? rotation_mod is expected to be exact except at the
     atan2 branch cut (integer multiples of m); sawtooth_mod is
     expected to be smooth with Gibbs overshoot near boundaries.

  2. **Latency.** rotation_mod is 2 trig lookups + 1 atan2 + a handful
     of arithmetic ops. sawtooth_mod is N sin lookups + N divisions +
     a reduction. For N=16 we expect sawtooth_mod to be slower per
     call but more amenable to autograd if the substrate ever wires
     it through.

The benchmark exercises the same runtime methods the Sutra compiler
emits into user programs — we instantiate the codegen-emitted `_VSA`
class directly so the numbers reflect production code, not a
hand-coded reproduction.
"""
from __future__ import annotations

import math
import time

import torch

# Reach into the codegen pipeline to get the same _VSA class user
# programs use at runtime. Building it via the codegen ensures the
# benchmark measures the production substrate ops, not a separate
# implementation.
from sutra_compiler.codegen_pytorch import translate_module as torch_translate
from sutra_compiler.lexer import Lexer
from sutra_compiler.parser import Parser


def _build_runtime():
    """Compile a trivial program just so the emitted `_VSA` singleton
    is in scope. `_VSA` is the same runtime singleton every Sutra .su
    program sees — what we measure here is what production code
    measures."""
    src = "function number f() { return 0.0; }\n"
    lexer = Lexer(src, file="<benchmark>")
    tokens = lexer.tokenize()
    parser = Parser(tokens, file="<benchmark>", diagnostics=lexer.diagnostics)
    module = parser.parse_module()
    py = torch_translate(module)
    ns: dict = {}
    exec(py, ns)
    return ns["_VSA"]


def floor_mod_truth(x: float, m: float) -> float:
    """Python ground truth — `x - m * floor(x / m)`. Always in [0, m)
    for m > 0. This is the mathematical floor-mod that both Sutra
    implementations target."""
    return x - m * math.floor(x / m)


def accuracy_sweep(vsa, m: float, n_points: int = 1001):
    """Sweep one period [0, m) on a dense grid, report max + mean abs
    error for both methods."""
    xs = [m * (i / n_points) for i in range(n_points)]
    # Skip the exact boundary x=0 where both methods have known issues
    # (atan2 branch cut for rotation; Gibbs midpoint for sawtooth) so
    # the metric reflects in-period accuracy, not the discontinuity.
    xs = xs[1:]
    truth = [floor_mod_truth(x, m) for x in xs]
    rot = [vsa.rotation_mod(x, m) for x in xs]
    saw = [vsa.sawtooth_mod(x, m) for x in xs]
    rot_err = [abs(r - t) for r, t in zip(rot, truth)]
    saw_err = [abs(s - t) for s, t in zip(saw, truth)]
    return {
        "rotation_max":  max(rot_err),
        "rotation_mean": sum(rot_err) / len(rot_err),
        "sawtooth_max":  max(saw_err),
        "sawtooth_mean": sum(saw_err) / len(saw_err),
    }


def boundary_sweep(vsa, m: float, n_points: int = 201, width: float = 0.05):
    """Zoom in around x = m (the boundary) where Gibbs ripple dominates
    sawtooth_mod and the atan2 branch cut bites rotation_mod. Width is
    a fraction of m."""
    half = width * m
    xs = [m + (-half + (2 * half) * (i / n_points)) for i in range(n_points)]
    truth = [floor_mod_truth(x, m) for x in xs]
    rot = [vsa.rotation_mod(x, m) for x in xs]
    saw = [vsa.sawtooth_mod(x, m) for x in xs]
    rot_err = [abs(r - t) for r, t in zip(rot, truth)]
    saw_err = [abs(s - t) for s, t in zip(saw, truth)]
    return {
        "rotation_max":  max(rot_err),
        "rotation_mean": sum(rot_err) / len(rot_err),
        "sawtooth_max":  max(saw_err),
        "sawtooth_mean": sum(saw_err) / len(saw_err),
    }


def latency(vsa, m: float, n_calls: int = 2000):
    """Per-call latency. Each method runs n_calls times on a fixed
    representative input, then we divide. Warm-up first so torch's
    lazy compilation / kernel cache doesn't tilt the comparison."""
    x = m * 0.37  # arbitrary mid-period point

    # Warm-up
    for _ in range(20):
        vsa.rotation_mod(x, m)
        vsa.sawtooth_mod(x, m)

    t0 = time.perf_counter()
    for _ in range(n_calls):
        vsa.rotation_mod(x, m)
    rot_dt = (time.perf_counter() - t0) / n_calls

    t0 = time.perf_counter()
    for _ in range(n_calls):
        vsa.sawtooth_mod(x, m)
    saw_dt = (time.perf_counter() - t0) / n_calls

    return {
        "rotation_us_per_call": rot_dt * 1e6,
        "sawtooth_us_per_call": saw_dt * 1e6,
        "ratio_saw_over_rot":   saw_dt / rot_dt,
    }


def main():
    vsa = _build_runtime()
    print("Modulus comparison — substrate-pure rotation_mod vs sawtooth_mod")
    print(f"  device     = {vsa.device}")
    print(f"  dtype      = {vsa.dtype}")
    print(f"  torch ver. = {torch.__version__}")
    print()

    for m in (1.0, 3.0, 7.0):
        sweep = accuracy_sweep(vsa, m, n_points=1001)
        bdry = boundary_sweep(vsa, m, n_points=201, width=0.05)
        lat = latency(vsa, m, n_calls=2000)
        print(f"=== m = {m} ===")
        print(f"  in-period accuracy  (dense grid, n=1001, boundary excluded):")
        print(f"    rotation_mod  max={sweep['rotation_max']:.4e}  mean={sweep['rotation_mean']:.4e}")
        print(f"    sawtooth_mod  max={sweep['sawtooth_max']:.4e}  mean={sweep['sawtooth_mean']:.4e}")
        print(f"  boundary accuracy   (±5% of m around x=m):")
        print(f"    rotation_mod  max={bdry['rotation_max']:.4e}  mean={bdry['rotation_mean']:.4e}")
        print(f"    sawtooth_mod  max={bdry['sawtooth_max']:.4e}  mean={bdry['sawtooth_mean']:.4e}")
        print(f"  latency (2000 calls, mid-period x):")
        print(f"    rotation_mod  {lat['rotation_us_per_call']:.2f} µs/call")
        print(f"    sawtooth_mod  {lat['sawtooth_us_per_call']:.2f} µs/call")
        print(f"    sawtooth / rotation = {lat['ratio_saw_over_rot']:.2f}x")
        print()


if __name__ == "__main__":
    main()
