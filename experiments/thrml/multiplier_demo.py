"""Sutra -> thrml exploration, approach A (sample-and-verify), demo A3:
a 2x2-bit MULTIPLIER -- composing the gate primitives into a real circuit.

A2 gave a universal gate set (AND derived gadget, XOR=parity, the adder). This
demo composes them into an actual arithmetic circuit and runs it via
sample-and-verify -- the proof that ARBITRARY Boolean circuits compile to thrml
factors, not just the hand-picked ops.

2x2 multiply, a=a1a0, b=b1b0, product p3p2p1p0:
  partial products (AND gates):  w=a0&b0  x=a1&b0  y=a0&b1  z=a1&b1
  p0 = w
  p1 = x XOR y ,  c1 = x AND y     (half adder)
  p2 = z XOR c1,  c2 = z AND c1     (half adder)
  p3 = c2
All as spin factors: AND = derived gadget (biases + 2-body), XOR = 3-body parity
(prod sigma=+1), equality = 2-body bind.

MEASURED: sample-and-verify exact product over all 16 (a,b) pairs vs chance.
(Energy-based bonus: the same graph run with the PRODUCT clamped would sample the
FACTORS -- integer factoring. Noted, not measured here.)

Run:  python experiments/thrml/multiplier_demo.py [--beta 3 --reps 16]
"""
from __future__ import annotations

import argparse

import jax
import jax.numpy as jnp

from thrml import SpinNode, Block, SamplingSchedule, sample_states
from thrml.block_sampling import BlockGibbsSpec
from thrml.factor import FactorSamplingProgram
from thrml.models import SpinEBMFactor, SpinGibbsConditional

_SD = {SpinNode: jax.ShapeDtypeStruct((), jnp.bool_)}


def and_factors(i1, i2, o, beta):
    """6-factor derived AND gadget: o = i1 & i2 (single nodes)."""
    one = jnp.ones((1,))
    return [
        SpinEBMFactor([Block([i1])], beta * 0.25 * one),
        SpinEBMFactor([Block([i2])], beta * 0.25 * one),
        SpinEBMFactor([Block([o])], beta * -0.5 * one),
        SpinEBMFactor([Block([i1]), Block([i2])], beta * -0.25 * one),
        SpinEBMFactor([Block([i1]), Block([o])], beta * 0.5 * one),
        SpinEBMFactor([Block([i2]), Block([o])], beta * 0.5 * one),
    ]


def xor_factor(x, y, z, beta):
    """z = x ^ y. For bits with sigma=2*bit-1, even-#-of-1s over 3 vars means
    prod(sigma) = -1 (3 spins: even #1s -> odd #0s -> odd # of -1 factors), so the
    factor weight is NEGATIVE (verified analytically: with this sign the correct
    assignment is the unique global energy min). A POSITIVE weight here silently
    encodes XNOR -- the sign bug found 2026-06-14 that broke ground-state decode."""
    return [SpinEBMFactor([Block([x]), Block([y]), Block([z])], -beta * jnp.ones((1,)))]


def eq_factor(p, q, beta):
    """p = q  <=>  sigma_p sigma_q = +1 (2-body)."""
    return [SpinEBMFactor([Block([p]), Block([q])], beta * jnp.ones((1,)))]


def build(beta):
    a0, a1, b0, b1 = (SpinNode() for _ in range(4))
    w, x, y, z = (SpinNode() for _ in range(4))   # partial products
    c1, c2 = SpinNode(), SpinNode()               # carries
    p0, p1, p2, p3 = (SpinNode() for _ in range(4))
    f = []
    f += and_factors(a0, b0, w, beta)
    f += and_factors(a1, b0, x, beta)
    f += and_factors(a0, b1, y, beta)
    f += and_factors(a1, b1, z, beta)
    f += eq_factor(p0, w, beta)
    f += xor_factor(x, y, p1, beta) + and_factors(x, y, c1, beta)
    f += xor_factor(z, c1, p2, beta) + and_factors(z, c1, c2, beta)
    f += eq_factor(p3, c2, beta)
    inputs = [a0, a1, b0, b1]
    free = [w, x, y, z, c1, c2, p0, p1, p2, p3]
    prod = [p0, p1, p2, p3]
    return inputs, free, prod, f


def run(beta, reps, seed):
    inputs, free, prod, factors = build(beta)
    free_blocks = [Block([nd]) for nd in free]
    spec = BlockGibbsSpec(free_blocks, [Block(inputs)], _SD)
    prog = FactorSamplingProgram(spec, [SpinGibbsConditional() for _ in free],
                                 factors, [])
    sched = SamplingSchedule(n_warmup=400, n_samples=300, steps_per_sample=6)
    key = jax.random.key(seed)
    exact = best = 0
    trials = 0
    for a in range(4):
        for b in range(4):
            for _r in range(reps):
                trials += 1
                key, ki, ks = jax.random.split(key, 3)
                clamp = jnp.array([a & 1, (a >> 1) & 1, b & 1, (b >> 1) & 1], bool)
                init = [jax.random.bernoulli(k, 0.5, (1,))
                        for k in jax.random.split(ki, len(free))]
                samp = sample_states(ks, prog, sched, init, [clamp],
                                     [Block(prod)] + [Block([nd]) for nd in free])
                pbits = jnp.asarray(samp[0]).astype(jnp.int32)       # (S,4) product
                # verify: among samples, the correct product is a*b; decode each,
                # keep the modal AND check best-of-S.
                pw = 2 ** jnp.arange(4)
                ints = (pbits * pw).sum(axis=1)
                vals, counts = jnp.unique(ints, return_counts=True)
                got = int(vals[int(jnp.argmax(counts))])
                exact += int(got == a * b)
                best += int(bool(jnp.any(ints == a * b)))
    return exact / trials, best / trials


def main():
    ap = argparse.ArgumentParser()
    # beta=1.5 is the working point: deeper circuits need WARMER sampling so
    # single-site Gibbs mixes (cold beta freezes in local minima -- beta=3 ->
    # best-of-S 0.25). best-of-S = the sample-and-verify success rate here, since
    # the correct product is the unique gate-satisfying assignment.
    ap.add_argument("--beta", type=float, default=1.5)
    ap.add_argument("--reps", type=int, default=4)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    acc, best = run(args.beta, args.reps, args.seed)
    print(f"thrml 2x2 multiplier (composed gates, sample-and-verify): beta={args.beta}, "
          f"{args.reps} reps x 16 pairs, backend={jax.default_backend()}")
    print(f"  sample-and-verify (best-of-S): {best:.3f}   modal-exact: {acc:.3f}   "
          f"chance: {1/16:.4f}")


if __name__ == "__main__":
    main()
