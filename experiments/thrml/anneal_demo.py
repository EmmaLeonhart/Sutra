"""Sutra -> thrml exploration, approach B: ground-state encoding + ANNEALING.

The contrast to approach A (sample-and-verify). The 2x2 multiplier (A3) is built
from proper gadgets (AND/XOR/eq), so the correct product IS the strict global
energy minimum -- but a FIXED beta cannot decode it by mode: cold beta freezes in
local minima (best-of-S 0.25), warm beta mixes but the distribution is spread
(modal 0). ANNEALING resolves this: start WARM to mix into the global-min basin,
then COOL to concentrate the distribution onto it -- so a plain MODAL decode hits
the answer, NO verifier needed.

Implementation: staged sampling. For each beta in an increasing schedule, rebuild
the multiplier program at that beta and initialise the free spins from the
previous (warmer) round's modal state; read the modal product after the coldest
round.

RESULT (2026-06-14): this staged version FAILS -- annealed modal-exact 0.000 vs
fixed beta=4.0 0.062 (both ~ chance). The bug is instructive: it carries the
per-node MARGINAL MODE of the warm round as the cold init, but the marginal mode
of a spread (warm) distribution is NOT a coherent state in the answer's basin, so
the cold round freezes from near-random. Proper annealing needs a within-chain
beta schedule (thrml's SamplingSchedule does not expose per-step beta) or carrying
a single low-energy COHERENT state. The principled ground-state decode for the
proper-gadget multiplier is MIN-ENERGY over a warm run (the answer is the strict
global min there -- unlike the adder's soft encoding where min-energy failed, #4c)
-- that is the next approach-B variant. Kept as a measured negative result.

Run:  python experiments/thrml/anneal_demo.py [--reps 2]
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


def _program(beta):
    inputs, free, prod, factors = build(beta)
    free_blocks = [Block([nd]) for nd in free]
    spec = BlockGibbsSpec(free_blocks, [Block(inputs)], _SD)
    prog = FactorSamplingProgram(spec, [SpinGibbsConditional() for _ in free],
                                 factors, [])
    return prog, free, prod


def _modal_free(prog, prod, free, clamp, init, key, n_samp=120, warm=100):
    sched = SamplingSchedule(n_warmup=warm, n_samples=n_samp, steps_per_sample=4)
    obs = [Block(prod)] + [Block([nd]) for nd in free]
    samp = sample_states(key, prog, sched, init, [clamp], obs)
    pbits = jnp.asarray(samp[0]).astype(jnp.int32)                # (S,4)
    free_modal = [(jnp.mean(jnp.asarray(samp[1 + i]).astype(jnp.float32)) > 0.5)
                  .reshape((1,)) for i in range(len(free))]       # carried init
    pw = 2 ** jnp.arange(4)
    ints = (pbits * pw).sum(axis=1)
    vals, counts = jnp.unique(ints, return_counts=True)
    return int(vals[int(jnp.argmax(counts))]), free_modal


def run_annealed(schedule, reps, seed):
    exact = 0; trials = 0
    key = jax.random.key(seed)
    progs = [_program(b) for b in schedule]   # one program per beta
    for a in range(4):
        for b in range(4):
            for _r in range(reps):
                trials += 1
                clamp = jnp.array([a & 1, (a >> 1) & 1, b & 1, (b >> 1) & 1], bool)
                key, ki = jax.random.split(key)
                _, free0, _ = progs[0]
                init = [jax.random.bernoulli(k, 0.5, (1,))
                        for k in jax.random.split(ki, len(free0))]
                got = 0
                for prog, free, prod in progs:        # warm -> cold
                    key, ks = jax.random.split(key)
                    got, init = _modal_free(prog, prod, free, clamp, init, ks)
                exact += int(got == a * b)
    return exact / trials


def run_fixed(beta, reps, seed):
    prog, free, prod = _program(beta)
    exact = 0; trials = 0
    key = jax.random.key(seed)
    for a in range(4):
        for b in range(4):
            for _r in range(reps):
                trials += 1
                clamp = jnp.array([a & 1, (a >> 1) & 1, b & 1, (b >> 1) & 1], bool)
                key, ki, ks = jax.random.split(key, 3)
                init = [jax.random.bernoulli(k, 0.5, (1,))
                        for k in jax.random.split(ki, len(free))]
                got, _ = _modal_free(prog, prod, free, clamp, init, ks)
                exact += int(got == a * b)
    return exact / trials


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", type=int, default=2)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    schedule = [1.5, 4.0]   # warm (mix into the basin) -> cold (concentrate)
    print(f"thrml approach B: annealed ground-state decode of the 2x2 multiplier, "
          f"{args.reps} reps x 16 pairs, backend={jax.default_backend()}")
    fixed = run_fixed(4.0, args.reps, args.seed)
    ann = run_annealed(schedule, args.reps, args.seed)
    print(f"  fixed beta=4.0   modal-exact: {fixed:.3f}")
    print(f"  annealed {schedule}  modal-exact: {ann:.3f}   chance: {1/16:.4f}")


if __name__ == "__main__":
    main()
