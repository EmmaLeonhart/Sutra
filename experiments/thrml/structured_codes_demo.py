"""Sutra -> thrml exploration, approach F: denser / structured codes.

#2 measured the associative-memory capacity wall: RANDOM +/-1 patterns recover
cleanly only up to ~0.14*N stored (the Hopfield bound; crosstalk degrades beyond).
Approach F pushes past it with STRUCTURED codes. The cleanest: ORTHOGONAL patterns
(rows of a Hadamard matrix) have ZERO Hebbian crosstalk -- W = sum_mu xi xi^T has
no off-target interference -- so every stored pattern stays an exact attractor up
to M = N.

Demo: clamped-cue retrieval (clamp half a stored value's bits, infer the rest) on
the SAME thrml Ising machinery as #2, comparing RANDOM vs HADAMARD codebooks as M
(number stored) grows at fixed N.

MEASURED: inferred-half per-bit accuracy vs M, for both code families. Expect
random to fall off near M ~ 0.14*N and Hadamard to stay ~1.0 up to M = N.

Run:  python experiments/thrml/structured_codes_demo.py [--n 16 --beta 5]
"""
from __future__ import annotations

import argparse

import jax
import jax.numpy as jnp

from thrml import SpinNode, Block, SamplingSchedule, sample_states
from thrml.models import IsingEBM, IsingSamplingProgram, hinton_init


def hadamard(n):
    """Sylvester Hadamard matrix of size n (n a power of 2), +/-1."""
    H = jnp.ones((1, 1))
    while H.shape[0] < n:
        H = jnp.block([[H, H], [H, -H]])
    return H[:n, :n].astype(jnp.int32)


def retrieve(patterns, n, beta, seed):
    """Mean inferred-half per-bit accuracy over all stored patterns as targets."""
    m = patterns.shape[0]
    w = (patterns.T @ patterns).astype(jnp.float32) / n
    w = w - jnp.diag(jnp.diag(w))
    iu = jnp.triu_indices(n, k=1)
    nodes = [SpinNode() for _ in range(n)]
    edges = [(nodes[int(i)], nodes[int(j)]) for i, j in zip(iu[0], iu[1])]
    model = IsingEBM(nodes, edges, jnp.zeros((n,)), beta * w[iu], jnp.array(beta))
    cue_idx = list(range(n // 2)); hid_idx = list(range(n // 2, n))
    cue_nodes = [nodes[i] for i in cue_idx]; hid_nodes = [nodes[i] for i in hid_idx]
    prog = IsingSamplingProgram(model, [Block([h]) for h in hid_nodes],
                                clamped_blocks=[Block(cue_nodes)])
    sched = SamplingSchedule(n_warmup=150, n_samples=200, steps_per_sample=4)
    accs = []
    for mu in range(m):
        target = patterns[mu]
        k = jax.random.key(seed * 100 + mu + 1)
        ki, ks = jax.random.split(k, 2)
        init = hinton_init(ki, model, [Block([h]) for h in hid_nodes], ())
        cue = (target[jnp.array(cue_idx)] == 1)
        samp = sample_states(ks, prog, sched, init, [cue], [Block(hid_nodes)])
        inferred = 2 * jnp.asarray(samp[0]).astype(jnp.int32) - 1
        accs.append(float(jnp.mean((inferred == target[jnp.array(hid_idx)]).astype(jnp.float32))))
    return sum(accs) / len(accs)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=16)
    ap.add_argument("--beta", type=float, default=5.0)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    n = args.n
    H = hadamard(n)
    print(f"thrml approach F: structured (Hadamard) vs random codes, N={n}, "
          f"Hopfield wall ~{0.14*n:.1f}, backend={jax.default_backend()}")
    print(f"{'M stored':>9} {'random acc':>11} {'hadamard acc':>13}")
    for m in [2, 4, 8, 12, n]:
        if m > n:
            continue
        krand = jax.random.key(args.seed)
        rand = 2 * jax.random.bernoulli(krand, 0.5, (m, n)).astype(jnp.int32) - 1
        had = H[:m]
        r = retrieve(rand, n, args.beta, args.seed)
        h = retrieve(had, n, args.beta, args.seed + 7)
        print(f"{m:>9} {r:>11.3f} {h:>13.3f}")


if __name__ == "__main__":
    main()
