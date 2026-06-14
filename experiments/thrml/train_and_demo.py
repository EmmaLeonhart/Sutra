"""Sutra -> thrml exploration, approach C: TRAINABLE couplings (the constrain-train
link).

A2 HAND-DERIVED the AND gadget's couplings. This demo LEARNS them: a 3-spin
fully-visible Ising (a, b, z) is trained by contrastive divergence
(thrml.estimate_kl_grad) on the 4 valid AND triples {(0,0,0),(0,1,0),(1,0,0),
(1,1,1)}, with NO hand-derived weights. After training, clamp a,b and sample z;
if z = a&b, the op was learned, not engineered -- the bridge to Sutra's
"every operation trainable" vision.

MEASURED: after training, per-(a,b) modal z exact = a&b, vs the chance 0.5 of an
untrained model; plus the learned weights printed (compare to the A2 gadget).

Run:  python experiments/thrml/train_and_demo.py [--steps 120 --lr 0.2]
"""
from __future__ import annotations

import argparse

import jax
import jax.numpy as jnp

from thrml import SpinNode, Block, SamplingSchedule, sample_states
from thrml.models import (IsingEBM, IsingSamplingProgram, IsingTrainingSpec,
                          hinton_init, estimate_kl_grad)

# 4 valid AND triples (a, b, z=a&b) as bits.
_AND_DATA = jnp.array([[0, 0, 0], [0, 1, 0], [1, 0, 0], [1, 1, 1]], dtype=jnp.int32)


def train(steps, lr, beta, batch, seed):
    a, b, z = SpinNode(), SpinNode(), SpinNode()
    nodes = [a, b, z]
    edges = [(a, b), (a, z), (b, z)]
    biases = jnp.zeros((3,))
    weights = jnp.zeros((3,))
    free_blocks = [Block([a]), Block([b]), Block([z])]   # negative-phase: all free
    sched_pos = SamplingSchedule(n_warmup=0, n_samples=1, steps_per_sample=0)
    sched_neg = SamplingSchedule(n_warmup=20, n_samples=10, steps_per_sample=2)
    # data tiled to the batch
    reps = batch // 4
    data = jnp.tile(_AND_DATA, (reps, 1)).astype(jnp.bool_)   # (batch, 3)
    key = jax.random.key(seed)
    for step in range(steps):
        model = IsingEBM(nodes, edges, biases, weights, jnp.array(beta))
        spec = IsingTrainingSpec(model, [Block(nodes)], [], [], free_blocks,
                                 sched_pos, sched_neg)
        key, k1, k2 = jax.random.split(key, 3)
        init_free = hinton_init(k1, model, free_blocks, (data.shape[0],))
        gw, gb, *_ = estimate_kl_grad(k2, spec, nodes, edges, [data], [], [], init_free)
        weights = weights - lr * gw      # descend KL
        biases = biases - lr * gb
    return nodes, edges, biases, weights


def evaluate(nodes, edges, biases, weights, beta, seed):
    a, b, z = nodes
    model = IsingEBM(nodes, edges, biases, weights, jnp.array(beta))
    prog = IsingSamplingProgram(model, [Block([z])], clamped_blocks=[Block([a, b])])
    sched = SamplingSchedule(n_warmup=80, n_samples=120, steps_per_sample=3)
    key = jax.random.key(seed)
    hits = 0
    for av in (0, 1):
        for bv in (0, 1):
            key, ki, ks = jax.random.split(key, 3)
            init = [jax.random.bernoulli(ki, 0.5, (1,))]
            samp = sample_states(ks, prog, sched, init, [jnp.array([av, bv], bool)],
                                 [Block([z])])
            zhat = int(jnp.mean(jnp.asarray(samp[0]).astype(jnp.float32)) > 0.5)
            hits += int(zhat == (av & bv))
    return hits / 4


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--steps", type=int, default=120)
    ap.add_argument("--lr", type=float, default=0.2)
    ap.add_argument("--beta", type=float, default=1.0)
    ap.add_argument("--batch", type=int, default=64)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    nodes, edges, biases, weights = train(args.steps, args.lr, args.beta,
                                          args.batch, args.seed)
    acc = evaluate(nodes, edges, biases, weights, args.beta, args.seed + 1)
    print(f"thrml approach C: LEARNED AND gate (CD training, no hand-derived weights), "
          f"{args.steps} steps, backend={jax.default_backend()}")
    print(f"  learned biases (a,b,z): {[round(float(x),2) for x in biases]}")
    print(f"  learned weights (ab,az,bz): {[round(float(x),2) for x in weights]}")
    print(f"  post-training z=a&b exact: {acc:.3f}   (untrained ~0.5)")


if __name__ == "__main__":
    main()
