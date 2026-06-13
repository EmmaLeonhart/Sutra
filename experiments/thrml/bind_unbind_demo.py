"""Sutra -> thrml exploration, attempt #3: bind / unbind (the transformational op).

The open question: do Sutra's *transformational* ops fall out as energies, or need
a different trick than the memory ops? Answer under test: bipolar VSA bind is
elementwise product, c = a (x) b  (c_i = a_i b_i), which for +/-1 spins is the
constraint a_i b_i c_i = +1. That is a 3-BODY interaction -- not expressible in a
pairwise Ising model, but thrml's SpinEBMFactor takes arbitrary-arity factors
(energy = -Sum_k w_k * product(spins)). So a positive-weight 3-body factor over
(a_i, b_i, c_i) enforces c = a (x) b, and unbind (b = a (x) c) falls out of the
SAME factor by clamping the other two.

MEASURED: clamp a,b -> sample c, per-bit accuracy vs a (x) b (bind); clamp a,c ->
sample b, accuracy vs a (x) c (unbind). Baseline 0.5.

Run:  python experiments/thrml/bind_unbind_demo.py [--n 16 --beta 4]
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


def make_program(a_nodes, b_nodes, c_nodes, free_nodes, clamped_nodes, beta, w):
    n = len(a_nodes)
    factor = SpinEBMFactor([Block(a_nodes), Block(b_nodes), Block(c_nodes)],
                           beta * w * jnp.ones((n,)))
    free_blocks = [Block([nd]) for nd in free_nodes]   # single-site Gibbs
    clamped_blocks = [Block(list(clamped_nodes))]
    spec = BlockGibbsSpec(free_blocks, clamped_blocks, _SD)
    samp = SpinGibbsConditional()
    return FactorSamplingProgram(spec, [samp for _ in free_blocks], [factor], [])


def run_mode(mode, n, beta, seed):
    """mode 'bind': clamp a,b free c, target c=a*b. 'unbind': clamp a,c free b,
    target b=a*c."""
    key = jax.random.key(seed)
    ka, kb, kinit, ksamp = jax.random.split(key, 4)
    a = 2 * jax.random.bernoulli(ka, 0.5, (n,)).astype(jnp.int32) - 1
    b = 2 * jax.random.bernoulli(kb, 0.5, (n,)).astype(jnp.int32) - 1
    c = a * b

    a_nodes = [SpinNode() for _ in range(n)]
    b_nodes = [SpinNode() for _ in range(n)]
    c_nodes = [SpinNode() for _ in range(n)]

    if mode == "bind":
        free_nodes, clamped_nodes = c_nodes, a_nodes + b_nodes
        clamp_vals = jnp.concatenate([(a == 1), (b == 1)])
        target = c
    else:  # unbind: recover b from a and c
        free_nodes, clamped_nodes = b_nodes, a_nodes + c_nodes
        clamp_vals = jnp.concatenate([(a == 1), (c == 1)])
        target = b

    prog = make_program(a_nodes, b_nodes, c_nodes, free_nodes, clamped_nodes, beta, 1.0)
    init_free = [jax.random.bernoulli(k, 0.5, (1,))
                 for k in jax.random.split(kinit, len(free_nodes))]
    schedule = SamplingSchedule(n_warmup=150, n_samples=300, steps_per_sample=4)
    samples = sample_states(ksamp, prog, schedule, init_free, [clamp_vals],
                            [Block(free_nodes)])
    inferred = 2 * jnp.asarray(samples[0]).astype(jnp.int32) - 1  # (S, n)
    acc = float(jnp.mean((inferred == target).astype(jnp.float32)))
    return acc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=16)
    ap.add_argument("--beta", type=float, default=None)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    betas = [args.beta] if args.beta is not None else [1.0, 2.0, 4.0, 6.0]
    print(f"thrml bind/unbind (3-body factor): N={args.n}, backend={jax.default_backend()}")
    print(f"{'beta':>5} {'bind-acc':>9} {'unbind-acc':>11} {'baseline':>9}")
    for b in betas:
        ba = run_mode("bind", args.n, b, args.seed)
        ua = run_mode("unbind", args.n, b, args.seed)
        print(f"{b:>5.1f} {ba:>9.3f} {ua:>11.3f} {0.5:>9.3f}")


if __name__ == "__main__":
    main()
