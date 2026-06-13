"""Sutra -> thrml exploration, attempt #5: a composed program -- VSA key-value query.

Composes the two CLEAN ops onto one record: bind/unbind (#3, exact) + cleanup
(#1, associative memory). This is the `role_filler_record` pattern -- an actual
multi-op Sutra program running on the thermodynamic sampler, not a single op.

Data (compile-time, like a codebook): K role/filler bit-registers; the stored
record  M = sign( sum_k r_k (x) f_k )  (bundle of bound role-filler pairs).

Query role j, ON THE SUBSTRATE, in two staged sampling runs (host hand-off
between stages = the legitimate orchestrator/readout boundary):
  Stage 1 (unbind): clamp M and r_j, 3-body factor M_i r_j_i u_i = +1 -> sample
    u = M (x) r_j  (a NOISY f_j: the j term gives f_j, other pairs add crosstalk).
  Stage 2 (cleanup): Hebbian associative memory over the filler codebook, init = u
    -> relaxes to the nearest stored filler = f_j.

MEASURED: exact recovery of f_j vs (a) the raw unbind u (no cleanup) and (b)
chance. The gap (cleanup vs raw) is the value the composition adds.

Run:  python experiments/thrml/kv_store_demo.py [--n 12 --k 2 --beta 4]
"""
from __future__ import annotations

import argparse

import jax
import jax.numpy as jnp

from thrml import SpinNode, Block, SamplingSchedule, sample_states
from thrml.block_sampling import BlockGibbsSpec
from thrml.factor import FactorSamplingProgram
from thrml.models import (IsingEBM, IsingSamplingProgram, hinton_init,
                          SpinEBMFactor, SpinGibbsConditional)

_SD = {SpinNode: jax.ShapeDtypeStruct((), jnp.bool_)}


def unbind(M_bits, r_bits, n, beta, seed):
    """Substrate stage 1: sample u with the 3-body factor enforcing u = M (x) r."""
    M_nodes = [SpinNode() for _ in range(n)]
    r_nodes = [SpinNode() for _ in range(n)]
    u_nodes = [SpinNode() for _ in range(n)]
    factor = SpinEBMFactor([Block(M_nodes), Block(r_nodes), Block(u_nodes)],
                           beta * jnp.ones((n,)))
    free_blocks = [Block([nd]) for nd in u_nodes]
    spec = BlockGibbsSpec(free_blocks, [Block(M_nodes + r_nodes)], _SD)
    prog = FactorSamplingProgram(spec, [SpinGibbsConditional() for _ in u_nodes],
                                 [factor], [])
    k = jax.random.key(seed)
    kinit, ksamp = jax.random.split(k, 2)
    clamp = jnp.concatenate([M_bits, r_bits]).astype(bool)
    init = [jax.random.bernoulli(kk, 0.5, (1,)) for kk in jax.random.split(kinit, n)]
    sched = SamplingSchedule(n_warmup=100, n_samples=200, steps_per_sample=3)
    samp = sample_states(ksamp, prog, sched, init, [clamp], [Block(u_nodes)])
    bits = (jnp.mean(jnp.asarray(samp[0]).astype(jnp.float32), axis=0) > 0.5)
    return bits.astype(jnp.int32)  # u bits (modal)


def cleanup(u_bits, codebook_pm1, n, beta, seed):
    """Substrate stage 2: Hebbian associative memory over the filler codebook,
    initialised at u; relaxes to the nearest stored filler."""
    w = (codebook_pm1.T @ codebook_pm1).astype(jnp.float32) / n
    w = w - jnp.diag(jnp.diag(w))
    iu = jnp.triu_indices(n, k=1)
    nodes = [SpinNode() for _ in range(n)]
    edges = [(nodes[int(i)], nodes[int(j)]) for i, j in zip(iu[0], iu[1])]
    model = IsingEBM(nodes, edges, jnp.zeros((n,)), beta * w[iu], jnp.array(beta))
    free_blocks = [Block([nd]) for nd in nodes]
    prog = IsingSamplingProgram(model, free_blocks, clamped_blocks=[])
    k = jax.random.key(seed)
    init = [u_bits[i].reshape((1,)).astype(bool) for i in range(n)]  # init AT u
    sched = SamplingSchedule(n_warmup=150, n_samples=200, steps_per_sample=4)
    samp = sample_states(k, prog, sched, init, [], [Block(nodes)])
    bits = (jnp.mean(jnp.asarray(samp[0]).astype(jnp.float32), axis=0) > 0.5)
    return bits.astype(jnp.int32)


def run(n, K, beta, seed):
    key = jax.random.key(seed)
    kf, kr = jax.random.split(key, 2)
    fillers = 2 * jax.random.bernoulli(kf, 0.5, (K, n)).astype(jnp.int32) - 1
    roles = 2 * jax.random.bernoulli(kr, 0.5, (K, n)).astype(jnp.int32) - 1
    M = jnp.sign(jnp.sum(roles * fillers, axis=0))      # bundle of bound pairs
    M = jnp.where(M == 0, 1, M)                          # break ties to +1
    M_bits = ((M + 1) // 2)

    clean_hits = raw_hits = 0
    for j in range(K):
        u_bits = unbind(M_bits, ((roles[j] + 1) // 2), n, beta, seed * 10 + j)
        u_pm1 = 2 * u_bits - 1
        fhat = cleanup(u_bits, fillers, n, beta, seed * 10 + j + 100)
        fhat_pm1 = 2 * fhat - 1
        clean_hits += int(jnp.all(fhat_pm1 == fillers[j]))
        raw_hits += int(jnp.all(u_pm1 == fillers[j]))
    return clean_hits / K, raw_hits / K


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=12)
    ap.add_argument("--k", type=int, default=2)
    ap.add_argument("--beta", type=float, default=None)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    betas = [args.beta] if args.beta is not None else [2.0, 4.0, 6.0]
    print(f"thrml VSA key-value query (compose unbind + cleanup): N={args.n}, "
          f"K={args.k} pairs, backend={jax.default_backend()}")
    print(f"{'beta':>5} {'cleanup-exact':>14} {'raw-unbind':>11} {'chance':>10}")
    chance = 1.0 / (2 ** args.n)
    for b in betas:
        # average over a few records for a stable number
        cl = rw = 0.0
        R = 4
        for s in range(R):
            c, r = run(args.n, args.k, b, args.seed + s)
            cl += c; rw += r
        print(f"{b:>5.1f} {cl / R:>14.3f} {rw / R:>11.3f} {chance:>10.2e}")


if __name__ == "__main__":
    main()
