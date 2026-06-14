"""Sutra -> thrml exploration, approach E: JOINT-EBM composition.

#5 ran the VSA key-value query in TWO staged sampling runs with a host hand-off
(unbind -> read u on the host -> cleanup). Approach E composes both ops into ONE
energy model sampled in a SINGLE run, with NO host readout between stages: the
unbind 3-body factor and the cleanup Hebbian couplings coexist over the same u
nodes. They COMPETE -- unbind pulls u toward the noisy filler (evidence), cleanup
pulls u toward the nearest clean codebook vector (prior) -- and at a balanced
strength u settles to the clean filler in one shot.

  factors over u (free), M and r_j clamped:
    unbind:  3-body  M_i r_j_i u_i = +1   (weight w_u)   -> u ~ M (x) r_j (noisy f_j)
    cleanup: Hebbian 2-body over u pairs   (weight w_c)   -> attractors at clean fillers

MEASURED: exact recovery of f_j vs the cleanup/unbind weight ratio, vs #5's
staged result (1.000 at N=16) and raw unbind (0.000). The point: does removing
the host hand-off still recover the filler, and at what balance.

Run:  python experiments/thrml/joint_kv_demo.py [--n 16 --k 2 --beta 4]
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


def query(n, fillers, roles, M_bits, j, beta, lam, seed):
    """One joint-EBM query of role j. lam = cleanup/unbind weight ratio."""
    M_nodes = [SpinNode() for _ in range(n)]
    r_nodes = [SpinNode() for _ in range(n)]
    u_nodes = [SpinNode() for _ in range(n)]
    # cleanup Hebbian over u
    W = (fillers.T @ fillers).astype(jnp.float32) / n
    W = W - jnp.diag(jnp.diag(W))
    iu = jnp.triu_indices(n, k=1)
    u_left = [u_nodes[int(i)] for i in iu[0]]
    u_right = [u_nodes[int(i)] for i in iu[1]]
    factors = [
        SpinEBMFactor([Block(M_nodes), Block(r_nodes), Block(u_nodes)],
                      beta * jnp.ones((n,))),                       # unbind (w_u=beta)
        SpinEBMFactor([Block(u_left), Block(u_right)],
                      beta * lam * W[iu]),                          # cleanup (w_c=beta*lam)
    ]
    free_blocks = [Block([nd]) for nd in u_nodes]
    spec = BlockGibbsSpec(free_blocks, [Block(M_nodes + r_nodes)], _SD)
    prog = FactorSamplingProgram(spec, [SpinGibbsConditional() for _ in u_nodes],
                                 factors, [])
    sched = SamplingSchedule(n_warmup=200, n_samples=250, steps_per_sample=4)
    key = jax.random.key(seed)
    ki, ks = jax.random.split(key, 2)
    clamp = jnp.concatenate([(M_bits == 1), (roles[j] == 1)]).astype(bool)
    init = [jax.random.bernoulli(k, 0.5, (1,)) for k in jax.random.split(ki, n)]
    samp = sample_states(ks, prog, sched, init, [clamp], [Block(u_nodes)])
    u = (jnp.mean(jnp.asarray(samp[0]).astype(jnp.float32), axis=0) > 0.5)
    u_pm1 = 2 * u.astype(jnp.int32) - 1
    return int(jnp.all(u_pm1 == fillers[j]))


def run(n, K, beta, lam, seed, records=4):
    hits = trials = 0
    for s in range(records):
        key = jax.random.key(seed + s)
        kf, kr = jax.random.split(key)
        fillers = 2 * jax.random.bernoulli(kf, 0.5, (K, n)).astype(jnp.int32) - 1
        roles = 2 * jax.random.bernoulli(kr, 0.5, (K, n)).astype(jnp.int32) - 1
        M = jnp.sign(jnp.sum(roles * fillers, axis=0))
        M = jnp.where(M == 0, 1, M)
        for j in range(K):
            trials += 1
            hits += query(n, fillers, roles, M, j, beta, lam, seed * 100 + s * 10 + j)
    return hits / trials


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=16)
    ap.add_argument("--k", type=int, default=2)
    ap.add_argument("--beta", type=float, default=4.0)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    print(f"thrml approach E: JOINT-EBM kv-query (one model, no host hand-off), "
          f"N={args.n}, K={args.k}, beta={args.beta}, backend={jax.default_backend()}")
    print(f"{'cleanup/unbind ratio':>22} {'f_j exact':>10}")
    for lam in [2.0, 3.0, 5.0, 8.0]:
        acc = run(args.n, args.k, args.beta, lam, args.seed)
        tag = "(raw unbind)" if lam == 0.0 else ""
        print(f"{lam:>22.1f} {acc:>10.3f} {tag}")


if __name__ == "__main__":
    main()
