"""Sutra -> thrml exploration, approach B (corrected): MIN-ENERGY ground-state
decode of the proper-gadget 2x2 multiplier.

B1 (staged annealing) failed due to a marginal-mode-carry bug. This is the clean
approach-B test: the multiplier is built from PROPER gadgets (AND/XOR/eq), so the
correct product is the STRICT global energy minimum. So a single WARM run (which
mixes and visits the answer, best-of-S=1.0 at beta=1.5) + a MIN-ENERGY decode
should return the answer with NO verifier -- the contrast to the ADDER (#4c) where
min-energy FAILED because the soft carry encoding had spurious lower-energy states.

Energy is computed from the known gate structure (sigma = 2*bit-1):
  AND(i1,i2,o) energy = -0.25 si1 -0.25 si2 +0.5 so +0.25 si1 si2 -0.5 si1 so -0.5 si2 so
  XOR(x,y,z)   energy = - sx sy sz
  eq(p,q)      energy = - sp sq
(the beta scale is constant across samples, dropped for argmin.)

MEASURED: min-energy exact product vs modal-exact vs best-of-S, over all 16 pairs.

Run:  python experiments/thrml/groundstate_demo.py [--beta 1.5 --reps 4]
"""
from __future__ import annotations

import argparse

import jax
import jax.numpy as jnp

from thrml import Block, SamplingSchedule, sample_states
from thrml.block_sampling import BlockGibbsSpec
from thrml.factor import FactorSamplingProgram
from thrml.models import SpinGibbsConditional

from multiplier_demo import build, _SD


def _and_e(i1, i2, o):
    return (-0.25 * i1 - 0.25 * i2 + 0.5 * o + 0.25 * i1 * i2
            - 0.5 * i1 * o - 0.5 * i2 * o)


def energy(S):
    """S: dict name->spin array (S,). Total multiplier-circuit energy per sample."""
    e = _and_e(S["a0"], S["b0"], S["w"]) + _and_e(S["a1"], S["b0"], S["x"]) \
        + _and_e(S["a0"], S["b1"], S["y"]) + _and_e(S["a1"], S["b1"], S["z"]) \
        + _and_e(S["x"], S["y"], S["c1"]) + _and_e(S["z"], S["c1"], S["c2"])
    # XOR weight is NEGATIVE (z=x^y <=> prod sigma=-1), so energy term = +prod.
    e += +(S["x"] * S["y"] * S["p1"]) + (S["z"] * S["c1"] * S["p2"])   # XOR
    e += -(S["p0"] * S["w"]) - (S["p3"] * S["c2"])                     # eq
    return e


_FREE = ["w", "x", "y", "z", "c1", "c2", "p0", "p1", "p2", "p3"]


def run(beta, reps, seed):
    inputs, free, prod, factors = build(beta)
    free_blocks = [Block([nd]) for nd in free]
    spec = BlockGibbsSpec(free_blocks, [Block(inputs)], _SD)
    prog = FactorSamplingProgram(spec, [SpinGibbsConditional() for _ in free],
                                 factors, [])
    sched = SamplingSchedule(n_warmup=200, n_samples=250, steps_per_sample=5)
    key = jax.random.key(seed)
    emin = modal = best = 0; trials = 0
    for a in range(4):
        for b in range(4):
            for _r in range(reps):
                trials += 1
                ab = [a & 1, (a >> 1) & 1, b & 1, (b >> 1) & 1]
                clamp = jnp.array(ab, bool)
                key, ki, ks = jax.random.split(key, 3)
                init = [jax.random.bernoulli(k, 0.5, (1,))
                        for k in jax.random.split(ki, len(free))]
                obs = [Block([nd]) for nd in free]
                samp = sample_states(ks, prog, sched, init, [clamp], obs)
                S = {nm: 2 * jnp.asarray(samp[i]).reshape(-1).astype(jnp.int32) - 1
                     for i, nm in enumerate(_FREE)}
                for k, nm in enumerate(["a0", "a1", "b0", "b1"]):
                    S[nm] = jnp.full_like(S["w"], 2 * ab[k] - 1)
                pbits = jnp.stack([(S[p] + 1) // 2 for p in ["p0", "p1", "p2", "p3"]], 1)
                ints = (pbits * (2 ** jnp.arange(4))).sum(axis=1)
                E = energy(S)
                got_e = int(ints[int(jnp.argmin(E))])
                vals, counts = jnp.unique(ints, return_counts=True)
                got_m = int(vals[int(jnp.argmax(counts))])
                emin += int(got_e == a * b)
                modal += int(got_m == a * b)
                best += int(bool(jnp.any(ints == a * b)))
    return emin / trials, modal / trials, best / trials


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--beta", type=float, default=1.5)
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    em, mo, be = run(args.beta, args.reps, args.seed)
    print(f"thrml approach B (min-energy ground-state decode) 2x2 multiplier: "
          f"beta={args.beta}, {args.reps} reps x 16 pairs, backend={jax.default_backend()}")
    print(f"  min-energy: {em:.3f}   modal: {mo:.3f}   best-of-S: {be:.3f}   "
          f"chance: {1/16:.4f}")


if __name__ == "__main__":
    main()
