"""Sutra -> thrml exploration, attempt #4: integer addition (ripple-carry adder).

The real "programs compute" step: does INTEGER ADDITION run on the sampler? An
n-bit ripple-carry adder, expressed entirely as spin factors:

  bit<->spin: v in {0,1} -> sigma = 2v-1.
  sum bit:   s_i = a_i XOR b_i XOR c_i  <=>  a_i XOR b_i XOR c_i XOR s_i = 0
             <=> product(sigma_a, sigma_b, sigma_c, sigma_s) = +1   (4-body parity factor)
  carry:     c_{i+1} = MAJ(a_i, b_i, c_i). For 3 spins MAJ = sign(sigma sum), so
             E = -J * sigma_{c_{i+1}} * (sigma_a + sigma_b + sigma_c)  (three 2-body factors).

Clamp a, b, and carry_0 = 0; free the sum bits and internal carries; block-Gibbs
should relax to the unique satisfying assignment = the binary sum. Output =
[s_0..s_{n-1}, c_n].

MEASURED: decoded sum vs a+b, exact-match rate over random (a,b) pairs, vs the
chance baseline (1 / 2^(n+1)).

Run:  python experiments/thrml/adder_demo.py [--n 4 --beta 5 --trials 40]
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


def build_program(n, beta, J):
    a = [SpinNode() for _ in range(n)]
    b = [SpinNode() for _ in range(n)]
    s = [SpinNode() for _ in range(n)]
    c = [SpinNode() for _ in range(n + 1)]   # carries c_0..c_n
    cin, cout = c[:n], c[1:]                  # carry into / out of each bit
    w = beta * J * jnp.ones((n,))
    factors = [
        SpinEBMFactor([Block(a), Block(b), Block(cin), Block(s)], w),  # parity
        SpinEBMFactor([Block(cout), Block(a)], w),                     # carry: c_out~a
        SpinEBMFactor([Block(cout), Block(b)], w),                     # carry: c_out~b
        SpinEBMFactor([Block(cout), Block(cin)], w),                   # carry: c_out~c_in
    ]
    free_nodes = s + c[1:]                    # sum bits + internal carries (c_1..c_n)
    clamped_nodes = a + b + [c[0]]            # inputs + carry-in 0
    free_blocks = [Block([nd]) for nd in free_nodes]
    spec = BlockGibbsSpec(free_blocks, [Block(clamped_nodes)], _SD)
    prog = FactorSamplingProgram(spec, [SpinGibbsConditional() for _ in free_blocks],
                                 factors, [])
    return prog, free_nodes, s, c


def run(n, beta, trials, seed):
    prog, free_nodes, s_nodes, c_nodes = build_program(n, beta, 1.0)
    schedule = SamplingSchedule(n_warmup=400, n_samples=200, steps_per_sample=6)
    key = jax.random.key(seed)
    exact = 0
    best = 0
    emin = 0
    for t in range(trials):
        key, ka, kb, kinit, ksamp = jax.random.split(key, 5)
        av = jax.random.randint(ka, (n,), 0, 2)   # bits
        bv = jax.random.randint(kb, (n,), 0, 2)
        a_int = int(jnp.sum(av * (2 ** jnp.arange(n))))
        b_int = int(jnp.sum(bv * (2 ** jnp.arange(n))))
        # clamp values: a, b, carry_0=0 ; bit v -> bool (sigma=2v-1, bool=v)
        clamp = jnp.concatenate([av, bv, jnp.zeros((1,), jnp.int32)]).astype(bool)
        init_free = [jax.random.bernoulli(k, 0.5, (1,))
                     for k in jax.random.split(kinit, len(free_nodes))]
        samples = sample_states(ksamp, prog, schedule, init_free, [clamp],
                                [Block(s_nodes), Block(c_nodes)])
        s_samp = jnp.asarray(samples[0]).astype(jnp.int32)   # (S, n) bits
        c_samp = jnp.asarray(samples[1]).astype(jnp.int32)   # (S, n+1)
        # Decode each sample to an integer (s_0..s_{n-1}, then c_n as MSB) and take
        # the MODE over samples — per-bit averaging can yield an inconsistent
        # bit pattern that is no single valid sample.
        pw = 2 ** jnp.arange(n + 1)
        per = jnp.concatenate([s_samp, c_samp[:, n:n + 1]], axis=1)  # (S, n+1)
        ints = (per * pw).sum(axis=1)                                # (S,)
        truth = a_int + b_int

        # Min-energy decode: the correct sum is the unique global min of the
        # adder Hamiltonian, so rank the drawn samples by energy (a pure readout,
        # no use of `truth`) and return the lowest. sigma = 2*bit-1.
        sa, sb = 2 * av - 1, 2 * bv - 1                  # (n,)
        ss = 2 * s_samp - 1                              # (S, n)
        sc = 2 * c_samp - 1                              # (S, n+1)
        scin, scout = sc[:, :n], sc[:, 1:]               # (S, n)
        e_par = (sa * sb * scin * ss).sum(axis=1)        # parity term per sample
        e_car = (scout * (sa + sb + scin)).sum(axis=1)   # carry term per sample
        energy = -(e_par + e_car)                        # (S,) lower = better
        got_e = int(ints[int(jnp.argmin(energy))])

        vals, counts = jnp.unique(ints, return_counts=True)
        got = int(vals[int(jnp.argmax(counts))])
        exact += int(got == truth)                  # modal decode
        best += int(bool(jnp.any(ints == truth)))   # did ANY sample hit it?
        emin += int(got_e == truth)                 # min-energy decode
    return exact / trials, best / trials, emin / trials


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=4)
    ap.add_argument("--beta", type=float, default=None)
    ap.add_argument("--trials", type=int, default=40)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    betas = [args.beta] if args.beta is not None else [2.0, 4.0, 6.0, 8.0]
    chance = 1.0 / (2 ** (args.n + 1))
    print(f"thrml ripple-carry adder: N={args.n}-bit, {args.trials} random (a,b) pairs, "
          f"backend={jax.default_backend()}")
    print(f"{'beta':>5} {'modal':>8} {'min-energy':>11} {'best-of-S':>10} {'chance':>9}")
    for b in betas:
        acc, best, emin = run(args.n, b, args.trials, args.seed)
        print(f"{b:>5.1f} {acc:>8.3f} {emin:>11.3f} {best:>10.3f} {chance:>9.4f}")


if __name__ == "__main__":
    main()
