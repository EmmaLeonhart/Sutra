"""Sutra -> thrml exploration, attempt #2: content-addressable retrieval from a
clamped partial cue.

Attempt #1 showed the stored bit-register values are the low-energy modes. This
attempt is the actual *use* of the memory: reveal HALF of a stored value's bits
(the cue, held clamped), and let block-Gibbs INFER the other half. If the
substrate computes content-addressable recall, the inferred bits should match the
stored value -- and clamping fixes the sign, resolving the +/-pattern symmetry of
attempt #1.

Mapping: value = N-bit spin register; bundle = Hebbian couplings; query = clamp a
sub-register; recall = block-Gibbs sample_states over the free sub-register.

MEASURED: per-bit accuracy of the inferred half vs the true stored half, averaged
over all stored values as targets, vs a 50% random-fill baseline.

Run:  python experiments/thrml/clamped_retrieval_demo.py [--n 16 --m 3 --beta 4]
"""
from __future__ import annotations

import argparse

import jax
import jax.numpy as jnp

from thrml import SpinNode, Block, SamplingSchedule, sample_states
from thrml.models import IsingEBM, IsingSamplingProgram, hinton_init


def build(n, m, seed):
    key = jax.random.key(seed)
    k_pat = key
    bits = jax.random.bernoulli(k_pat, 0.5, (m, n))
    patterns = 2 * bits.astype(jnp.int32) - 1            # (m, n) +/-1
    w = (patterns.T @ patterns).astype(jnp.float32) / n  # Hebbian
    w = w - jnp.diag(jnp.diag(w))
    iu = jnp.triu_indices(n, k=1)
    return patterns, w[iu], iu


def retrieve(n, m, beta_val, seed):
    patterns, edge_w, iu = build(n, m, seed)
    nodes = [SpinNode() for _ in range(n)]
    edges = [(nodes[int(i)], nodes[int(j)]) for i, j in zip(iu[0], iu[1])]
    model = IsingEBM(nodes, edges, jnp.zeros((n,)), edge_w, jnp.array(beta_val))

    cue_idx = list(range(n // 2))        # revealed (clamped)
    hid_idx = list(range(n // 2, n))     # inferred (free)
    cue_nodes = [nodes[i] for i in cue_idx]
    hid_nodes = [nodes[i] for i in hid_idx]
    clamped_blocks = [Block(cue_nodes)]
    free_blocks = [Block([nd]) for nd in hid_nodes]      # single-site Gibbs
    program = IsingSamplingProgram(model, free_blocks, clamped_blocks)
    schedule = SamplingSchedule(n_warmup=200, n_samples=300, steps_per_sample=5)

    accs = []
    base = []
    for mu in range(m):
        target = patterns[mu]
        k = jax.random.key(seed * 100 + mu + 1)
        k_init, k_samp = jax.random.split(k, 2)
        init_free = hinton_init(k_init, model, free_blocks, ())
        cue_vals = (target[jnp.array(cue_idx)] == 1)     # bool (n/2,)
        state_clamp = [cue_vals]
        samples = sample_states(k_samp, program, schedule, init_free,
                                state_clamp, [Block(hid_nodes)])
        inferred = 2 * jnp.asarray(samples[0]).astype(jnp.int32) - 1  # (S, n/2)
        true_hid = target[jnp.array(hid_idx)]
        accs.append(float(jnp.mean((inferred == true_hid).astype(jnp.float32))))
        base.append(0.5)
    return sum(accs) / len(accs), sum(base) / len(base)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=16)
    ap.add_argument("--m", type=int, default=3)
    ap.add_argument("--beta", type=float, default=None)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    betas = [args.beta] if args.beta is not None else [1.0, 2.0, 4.0, 6.0]
    print(f"thrml clamped-cue retrieval: N={args.n}, M={args.m}, "
          f"cue=first {args.n//2} bits, backend={jax.default_backend()}")
    print(f"{'beta':>5} {'inferred-acc':>13} {'baseline':>9}")
    for b in betas:
        acc, base = retrieve(args.n, args.m, b, args.seed)
        print(f"{b:>5.1f} {acc:>13.3f} {base:>9.3f}")


if __name__ == "__main__":
    main()
