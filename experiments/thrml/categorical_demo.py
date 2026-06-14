"""Sutra -> thrml exploration, approach D: CATEGORICAL-node encoding.

Instead of a Sutra value = an N-bit spin register, a value = one thrml
CategoricalNode (K states, a uint8). The cleanest thing categorical buys you: an
ARBITRARY UNARY FUNCTION f: x -> y is a SINGLE K x K factor (a lookup table) --
clamp x, sample y, get f(x). In the bit-register encoding the same f needs a
Boolean circuit (several AND/XOR gadgets). The trade-off: 1 categorical node (K
states) vs ceil(log2 K) spins, and table size K^2.

MEASURED: clamp x to each of the K states, sample y, exact y == f(x), vs chance
1/K.

Run:  python experiments/thrml/categorical_demo.py [--k 5 --beta 4]
"""
from __future__ import annotations

import argparse

import jax
import jax.numpy as jnp

from thrml import Block, SamplingSchedule, sample_states
from thrml.block_sampling import BlockGibbsSpec
from thrml.factor import FactorSamplingProgram
from thrml.models import CategoricalEBMFactor, CategoricalGibbsConditional
from thrml.pgm import CategoricalNode


def run(K, beta, seed):
    # f(x) = (3x + 1) mod K  -- a nontrivial unary function (a permutation here).
    f = [(3 * i + 1) % K for i in range(K)]
    x, y = CategoricalNode(), CategoricalNode()
    # lookup-table factor: weight (1, K, K); high at the valid (i, f(i)) cells so
    # those configs are low energy. (sign verified by measurement below.)
    W = jnp.zeros((1, K, K)).at[0, jnp.arange(K), jnp.array(f)].set(beta)
    factor = CategoricalEBMFactor([Block([x]), Block([y])], W)
    spec = BlockGibbsSpec([Block([y])], [Block([x])])   # default uint8 categorical SD
    prog = FactorSamplingProgram(spec, [CategoricalGibbsConditional(K)], [factor], [])
    sched = SamplingSchedule(n_warmup=80, n_samples=150, steps_per_sample=2)
    key = jax.random.key(seed)
    hits = 0
    for xv in range(K):
        key, ki, ks = jax.random.split(key, 3)
        init = [jax.random.randint(ki, (1,), 0, K).astype(jnp.uint8)]
        clamp = [jnp.array([xv], dtype=jnp.uint8)]
        samp = sample_states(ks, prog, sched, init, clamp, [Block([y])])
        ys = jnp.asarray(samp[0]).reshape(-1)            # (S,) uint8 states
        vals, counts = jnp.unique(ys, return_counts=True)
        yhat = int(vals[int(jnp.argmax(counts))])
        hits += int(yhat == f[xv])
    return hits / K, f


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=int, default=5)
    ap.add_argument("--beta", type=float, default=4.0)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    acc, f = run(args.k, args.beta, args.seed)
    print(f"thrml approach D: categorical lookup-table f(x)=(3x+1)%{args.k} as ONE "
          f"{args.k}x{args.k} factor, backend={jax.default_backend()}")
    print(f"  table f = {f}")
    print(f"  clamp x -> sample y == f(x) exact: {acc:.3f}   chance: {1/args.k:.3f}")


if __name__ == "__main__":
    main()
