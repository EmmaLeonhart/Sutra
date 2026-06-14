"""Sutra -> thrml exploration, approach A (sample-and-verify), demo A2:
the AND gate -- completing the logic-gate primitive set.

So far on the substrate: bind = XNOR (3-body product), parity = XOR (n-body
product), majority = carry (pairwise sign-of-sum). The missing primitive is AND
(z = a & b), which is NOT a clean spin product -- it needs a derived Ising
gadget. From the standard QUBO AND penalty  P = ab - 2(a+b)z + 3z  (>=0, =0 iff
z=a&b), with bit x = (1+sigma_x)/2, algebra gives

  4*P = 3 - A - B + A*B + 2*Z - 2*A*Z - 2*B*Z   (A,B,Z spins)

so E = sum of: biases (-1/4)A (-1/4)B (+1/2)Z and couplings (+1/4)AB (-1/2)AZ
(-1/2)BZ. SpinEBMFactor energy is -w*prod(sigma), so weight w = -(coeff):
  bias a:+1/4  b:+1/4  z:-1/2 ; pair ab:-1/4  az:+1/2  bz:+1/2.
This derivation is VERIFIED EMPIRICALLY below (clamp a,b, sample z, check z=a&b);
if a coefficient were wrong the exact-rate would drop.

MEASURED: per-bit exact z = a & b over random a,b, element-wise across N bits.

Run:  python experiments/thrml/logic_gates_demo.py [--n 8 --beta 3 --trials 40]
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


def and_program(n, beta):
    a = [SpinNode() for _ in range(n)]
    b = [SpinNode() for _ in range(n)]
    z = [SpinNode() for _ in range(n)]
    one = jnp.ones((n,))
    factors = [
        SpinEBMFactor([Block(a)], beta * 0.25 * one),          # bias a: +1/4
        SpinEBMFactor([Block(b)], beta * 0.25 * one),          # bias b: +1/4
        SpinEBMFactor([Block(z)], beta * -0.5 * one),          # bias z: -1/2
        SpinEBMFactor([Block(a), Block(b)], beta * -0.25 * one),  # ab: -1/4
        SpinEBMFactor([Block(a), Block(z)], beta * 0.5 * one),    # az: +1/2
        SpinEBMFactor([Block(b), Block(z)], beta * 0.5 * one),    # bz: +1/2
    ]
    free_blocks = [Block([nd]) for nd in z]
    spec = BlockGibbsSpec(free_blocks, [Block(a + b)], _SD)
    prog = FactorSamplingProgram(spec, [SpinGibbsConditional() for _ in z], factors, [])
    return prog, z


def run(n, beta, trials, seed):
    prog, z_nodes = and_program(n, beta)
    sched = SamplingSchedule(n_warmup=100, n_samples=120, steps_per_sample=3)
    key = jax.random.key(seed)
    bit_acc = 0.0
    for t in range(trials):
        key, ka, kb, ki, ks = jax.random.split(key, 5)
        av = jax.random.randint(ka, (n,), 0, 2)
        bv = jax.random.randint(kb, (n,), 0, 2)
        clamp = jnp.concatenate([av, bv]).astype(bool)
        init = [jax.random.bernoulli(k, 0.5, (1,)) for k in jax.random.split(ki, n)]
        samp = sample_states(ks, prog, sched, init, [clamp], [Block(z_nodes)])
        z = (jnp.mean(jnp.asarray(samp[0]).astype(jnp.float32), axis=0) > 0.5).astype(jnp.int32)
        bit_acc += float(jnp.mean((z == (av & bv)).astype(jnp.float32)))
    return bit_acc / trials


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=8)
    ap.add_argument("--beta", type=float, default=None)
    ap.add_argument("--trials", type=int, default=40)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    betas = [args.beta] if args.beta is not None else [1.0, 2.0, 3.0, 4.0]
    print(f"thrml AND gate (derived Ising gadget): N={args.n} bits element-wise, "
          f"{args.trials} trials, backend={jax.default_backend()}")
    print(f"{'beta':>5} {'z=a&b exact':>13} {'chance':>8}")
    for b in betas:
        acc = run(args.n, b, args.trials, args.seed)
        print(f"{b:>5.1f} {acc:>13.3f} {0.5:>8.3f}")


if __name__ == "__main__":
    main()
