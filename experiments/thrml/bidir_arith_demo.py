"""Sutra -> thrml exploration, approach A (sample-and-verify), demo A1:
BIDIRECTIONAL arithmetic on ONE energy model.

#4c established sample-and-verify: encode an op as constraint factors, sample,
keep the sample satisfying the relations (the program, not the answer). This demo
generalizes it and shows the property that makes energy-based / thermodynamic
computing different from the feed-forward PyTorch path: the SAME factor graph runs
the computation in BOTH directions just by changing which register is clamped.

  factors (the n-bit ripple-carry adder, a+b=s):
    parity  s_i = a_i^b_i^c_i      -> 4-body  prod(sigma_a,sigma_b,sigma_cin,sigma_s)=+1
    carry   c_{i+1}=MAJ(a_i,b_i,c_i) -> three pairwise  -J sigma_cout(sigma_a+sigma_b+sigma_cin)

  ADD:       clamp a, b, c0=0  -> sample s (and carries)  -> verify -> read sum
  SUBTRACT:  clamp a, s, c0=0  -> sample b (and carries)  -> verify -> read b = s-a

MEASURED: exact-match of the freed register via sample-and-verify, vs chance.

Run:  python experiments/thrml/bidir_arith_demo.py [--n 4 --beta 2 --trials 24]
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


def adder_nodes_factors(n, beta, J=1.0):
    a = [SpinNode() for _ in range(n)]
    b = [SpinNode() for _ in range(n)]
    s = [SpinNode() for _ in range(n)]
    c = [SpinNode() for _ in range(n + 1)]
    cin, cout = c[:n], c[1:]
    w = beta * J * jnp.ones((n,))
    factors = [
        SpinEBMFactor([Block(a), Block(b), Block(cin), Block(s)], w),
        SpinEBMFactor([Block(cout), Block(a)], w),
        SpinEBMFactor([Block(cout), Block(b)], w),
        SpinEBMFactor([Block(cout), Block(cin)], w),
    ]
    return dict(a=a, b=b, s=s, c=c), factors


def sample_free(nodes, factors, clamp_map, free_nodes, beta, seed):
    """clamp_map: {node: bit}; free_nodes: list of the rest. Returns the samples
    for ALL of a,b,s,c as bit arrays (S, .)."""
    clamped_nodes = list(clamp_map.keys())
    clamp_vals = jnp.array([clamp_map[nd] for nd in clamped_nodes], dtype=bool)
    free_blocks = [Block([nd]) for nd in free_nodes]
    spec = BlockGibbsSpec(free_blocks, [Block(clamped_nodes)], _SD)
    prog = FactorSamplingProgram(spec, [SpinGibbsConditional() for _ in free_nodes],
                                 factors, [])
    k = jax.random.key(seed)
    kinit, ksamp = jax.random.split(k, 2)
    init = [jax.random.bernoulli(kk, 0.5, (1,))
            for kk in jax.random.split(kinit, len(free_nodes))]
    sched = SamplingSchedule(n_warmup=300, n_samples=200, steps_per_sample=5)
    obs = [Block(nodes["a"]), Block(nodes["b"]), Block(nodes["s"]), Block(nodes["c"])]
    samp = sample_states(ksamp, prog, sched, init, [clamp_vals], obs)
    return [jnp.asarray(x).astype(jnp.int32) for x in samp]  # a,b,s,c bits (S,.)


def verify_pick(a_s, b_s, s_s, c_s, n):
    """Among samples, keep those satisfying the adder relations; return the index
    of one, or -1. (sigma = 2*bit-1.)"""
    sa = 2 * a_s - 1; sb = 2 * b_s - 1; ss = 2 * s_s - 1; sc = 2 * c_s - 1
    scin, scout = sc[:, :n], sc[:, 1:]
    ok_par = jnp.all(sa * sb * scin * ss == 1, axis=1)
    ok_car = jnp.all(scout == jnp.sign(sa + sb + scin), axis=1)
    ok = ok_par & ok_car
    return (int(jnp.argmax(ok)) if bool(jnp.any(ok)) else -1)


def to_int(bits):
    return int(jnp.sum(bits * (2 ** jnp.arange(bits.shape[0]))))


def run(n, beta, trials, seed):
    nodes, factors = adder_nodes_factors(n, beta)
    add_hits = sub_hits = sub_valid = 0
    key = jax.random.key(seed)
    for t in range(trials):
        key, ka, kb = jax.random.split(key, 3)
        av = jax.random.randint(ka, (n,), 0, 2)
        bv = jax.random.randint(kb, (n,), 0, 2)
        a_int, b_int = to_int(av), to_int(bv)

        # ADD: clamp a, b, c0=0; free s, c1..cn
        clamp = {**{nodes["a"][i]: int(av[i]) for i in range(n)},
                 **{nodes["b"][i]: int(bv[i]) for i in range(n)},
                 nodes["c"][0]: 0}
        free = nodes["s"] + nodes["c"][1:]
        a_s, b_s, s_s, c_s = sample_free(nodes, factors, clamp, free, beta, seed * 7 + t)
        idx = verify_pick(a_s, b_s, s_s, c_s, n)
        if idx >= 0:
            sum_bits = jnp.concatenate([s_s[idx], c_s[idx, n:n + 1]])
            add_hits += int(to_int(sum_bits) == a_int + b_int)

        # SUBTRACT: clamp a, s(full = b_int+a_int), c0=0; free b, c1..c_{n-1}
        full = a_int + b_int                      # the sum we will clamp
        sbits = jnp.array([(full >> i) & 1 for i in range(n + 1)])  # n+1 bits
        clamp = {**{nodes["a"][i]: int(av[i]) for i in range(n)},
                 **{nodes["s"][i]: int(sbits[i]) for i in range(n)},
                 nodes["c"][0]: 0, nodes["c"][n]: int(sbits[n])}
        free = nodes["b"] + nodes["c"][1:n]       # b and the internal carries
        a_s, b_s, s_s, c_s = sample_free(nodes, factors, clamp, free, beta, seed * 13 + t)
        idx = verify_pick(a_s, b_s, s_s, c_s, n)
        if idx >= 0:
            sub_valid += 1
            sub_hits += int(to_int(b_s[idx]) == b_int)   # b = full - a
    return add_hits / trials, sub_hits / trials, sub_valid / trials


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=4)
    ap.add_argument("--beta", type=float, default=2.0)
    ap.add_argument("--trials", type=int, default=24)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    add, sub, sv = run(args.n, args.beta, args.trials, args.seed)
    chance = 1.0 / (2 ** args.n)
    print(f"thrml bidirectional arithmetic (one model, sample-and-verify): "
          f"N={args.n}-bit, beta={args.beta}, {args.trials} trials, "
          f"backend={jax.default_backend()}")
    print(f"  ADD   (clamp a,b -> s):  exact {add:.3f}   chance {chance:.4f}")
    print(f"  SUB   (clamp s,a -> b):  exact {sub:.3f}   (verify-found {sv:.3f})")


if __name__ == "__main__":
    main()
