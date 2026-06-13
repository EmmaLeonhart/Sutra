"""Sutra -> thrml exploration, attempt #1: associative memory.

Goal of the whole track (Emma 2026-06-13): try various ways of getting Sutra
computation to actually RUN on Extropic's thrml (energy-based block-Gibbs
sampling), iterating until it works. This is the first attempt.

Mapping under test (locked interpretation): a Sutra *value* = a register of N
spin-node bits. "Bundle" (superposition memory) = Hebbian couplings
W_ij = (1/N) Sum_mu xi^mu_i xi^mu_j on a fully-connected spin graph (the factor
interactions). "Cleanup / similarity retrieval" = block-Gibbs sample_states: the
stored bit-registers should be the low-energy modes the sampler concentrates on.

MEASURED (substrate-honesty bar): fraction of samples within overlap >= 0.9 of a
stored pattern, vs a random-spin baseline. The gap is the signal that the
computation actually happened on the thrml substrate.

Run:  python experiments/thrml/assoc_memory_demo.py [--n 16 --m 3 --beta 2.0]
"""
from __future__ import annotations

import argparse

import jax
import jax.numpy as jnp

from thrml import SpinNode, Block, SamplingSchedule, sample_states
from thrml.models import IsingEBM, IsingSamplingProgram, hinton_init


def build_patterns(key, n: int, m: int):
    """m random +/-1 bit-register patterns of width n (int8 +/-1)."""
    bits = jax.random.bernoulli(key, 0.5, (m, n))
    return (2 * bits.astype(jnp.int32) - 1)  # {0,1} -> {-1,+1}


def hebbian_weights(patterns, n: int):
    """W = (1/n) Sum_mu xi^mu (outer) xi^mu, zero diagonal. Returns the dense
    matrix and the per-edge weight vector for the fully-connected upper triangle."""
    w = (patterns.T @ patterns).astype(jnp.float32) / n  # (n, n)
    w = w - jnp.diag(jnp.diag(w))
    iu = jnp.triu_indices(n, k=1)
    return w, w[iu]


def overlaps(samples_pm1, patterns):
    """Max |overlap| of each sample with any stored pattern. samples_pm1: (S, n)
    in +/-1; patterns: (m, n). overlap_mu = (1/n) Sum_i s_i xi^mu_i."""
    n = patterns.shape[1]
    ov = samples_pm1.astype(jnp.float32) @ patterns.T.astype(jnp.float32) / n  # (S, m)
    return jnp.max(jnp.abs(ov), axis=1)  # (S,)


def run(n: int, m: int, beta_val: float, seed: int, sign: float):
    key = jax.random.key(seed)
    k_pat, k_init, k_samp = jax.random.split(key, 3)
    patterns = build_patterns(k_pat, n, m)
    _w_dense, edge_w = hebbian_weights(patterns, n)

    nodes = [SpinNode() for _ in range(n)]
    iu = jnp.triu_indices(n, k=1)
    edges = [(nodes[int(i)], nodes[int(j)]) for i, j in zip(iu[0], iu[1])]
    biases = jnp.zeros((n,))
    beta = jnp.array(beta_val)
    # `sign` lets us flip the energy convention if stored patterns come out as
    # maxima rather than minima (measured, not assumed).
    model = IsingEBM(nodes, edges, biases, sign * edge_w, beta)

    free_blocks = [Block([nd]) for nd in nodes]  # single-site Gibbs (valid)
    program = IsingSamplingProgram(model, free_blocks, clamped_blocks=[])
    init_state = hinton_init(k_init, model, free_blocks, ())
    schedule = SamplingSchedule(n_warmup=200, n_samples=500, steps_per_sample=5)
    samples = sample_states(k_samp, program, schedule, init_state, [], [Block(nodes)])

    arr = jnp.asarray(samples[0])               # (S, n) bool
    s_pm1 = 2 * arr.astype(jnp.int32) - 1       # {0,1} -> {-1,+1}
    mx = overlaps(s_pm1, patterns)
    frac_recovered = float(jnp.mean(mx >= 0.9))

    # Random-spin baseline (what "no computation" looks like).
    k_base = jax.random.key(seed + 1)
    base = 2 * jax.random.bernoulli(k_base, 0.5, (s_pm1.shape[0], n)).astype(jnp.int32) - 1
    base_mx = overlaps(base, patterns)
    frac_base = float(jnp.mean(base_mx >= 0.9))
    return frac_recovered, frac_base, float(jnp.mean(mx)), float(jnp.mean(base_mx))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=16)
    ap.add_argument("--m", type=int, default=3)
    ap.add_argument("--beta", type=float, default=None,
                    help="single beta; if unset, sweep 0.5..6")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    betas = [args.beta] if args.beta is not None else [0.5, 1.0, 2.0, 4.0, 6.0]
    print(f"thrml assoc-memory attempt: N={args.n} bits, M={args.m} stored patterns, "
          f"backend={jax.default_backend()}")
    print(f"{'beta':>5} {'sign':>5} {'recovered':>10} {'baseline':>9} "
          f"{'mean|ov|':>9} {'base|ov|':>9}")
    best = (-1.0, None)
    for sign in (+1.0, -1.0):
        for b in betas:
            rec, base, mov, bov = run(args.n, args.m, b, args.seed, sign)
            print(f"{b:>5.1f} {sign:>+5.0f} {rec:>10.3f} {base:>9.3f} "
                  f"{mov:>9.3f} {bov:>9.3f}")
            if rec > best[0]:
                best = (rec, (b, sign))
    print(f"\nbest recovered fraction: {best[0]:.3f} at beta/sign={best[1]} "
          f"(baseline ~{base:.3f}); gap = {best[0]-base:.3f}")


if __name__ == "__main__":
    main()
