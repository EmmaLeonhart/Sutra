# Axon value-slot birthday collision — the "CI flake" is a real capacity defect (2026-07-15)

## One line

Two axon keys whose per-key permutations map AXIS_REAL to the same synthetic slot both read
back the PAIR'S SUM; with `synthetic_dim=100` and 10 keys that happens with p≈0.37 per seed
set, and the seed set varies by platform — so the test passes locally by luck and fails on CI
runners legitimately.

## The evidence chain (all measured)

1. CI failures (`test_axon_op_cache_under_cap_never_evicts`): tree→11.0 (=4+7 machine),
   house→13.0 (=5+8 mountain), and the transformers-backend probe locally: go→9.0 (=2+7
   machine). Always EXACT pair sums, both keys of the pair affected. Runs 29386156802,
   29387477961, 29388981344 (0.17.1-pinned — server version falsified as cause).
2. Model digest identical local/CI (`0a109f42…`); all 10 embedding byte-hashes DISTINCT on the
   failing CI run; pairwise cosine matrix identical to local (max +0.6128 machine/mountain).
   Embeddings are healthy — collapse hypothesis falsified.
3. Mechanism: `_axon_op_for` = blockdiag(Q_sem, P_perm). The value written by
   `axon_add(axon, key, len)` lives on AXIS_REAL in the synthetic block; separation between
   keys' values comes ONLY from P_perm — a `RandomState(role_hash ^ 0xA50AF00D)` permutation
   of `synthetic_dim` slots. `axon_item` unpermutes with the key's own perm and reads
   AXIS_REAL. If perm_A and perm_B send AXIS_REAL to the same slot j, the bundle holds
   a+b at j and BOTH keys read a+b. Verified locally: at runtime_dim=256 (dim=356,
   synthetic_dim=100) the 10 keys map to slots 70,51,21,14,89,75,64,94,74,53 — injective,
   hence local green.
4. Birthday bound: P(collision, 10 keys) = 1−∏(1−i/d): d=100 → 0.372; d=256 → 0.163;
   d=64 → 0.523. The observed CI failure rate (3 of 4 runs) is consistent with runner
   heterogeneity re-drawing seeds (embedding bytes differ per CPU microarch → role_hash
   differs → different permutation per platform).

## Why this matters beyond the test

Any axon-as-record with k keys has p≈k²/2d chance that two fields ALIAS each other's scalar
values on a given platform — silently, deterministically for that platform. This is a
correctness bound on the axon record design, not a test-hygiene issue. The test is a true
positive and must not be weakened, xfail'd (it XPASSes locally — strict xfail can't express
platform-dependent truth), or re-keyed to dodge the draw.

## Fix directions (design fork — Emma's call, substrate semantics)

a. **Collision-check + salt-retry at build**: when an axon build sees the key set, detect
   AXIS_REAL slot collisions and re-derive the colliding key's perm with an incremented salt
   until injective. Deterministic given the key set; keeps the design; cache key becomes
   (role_hash, salt). Readback needs the same salt — trivially available for axon_item calls
   that pass the key string, but changes the "operator is a pure function of the key alone"
   property.
b. **Grow the synthetic block**: reduces p (d=1024 → p≈0.04 for 10 keys) but never eliminates;
   silent aliasing remains possible at any scale.
c. **Give the value semantic-block support too** (bind the scalar through Q, not just P_perm):
   separation then comes from near-orthogonal rotations in the big block — collisions become
   graded crosstalk (measurable, small) instead of exact aliasing. Bigger semantic change.
d. Something else Emma prefers — she designed the axon machinery.

## Status

CI compiler suite is legitimately red on affected runners until a direction is chosen.
Non-gating probe (`experiments/axon_key_crosstalk_probe.py` + CI step) stays in place — it
now prints slot assignments' upstream inputs (embedding hashes) every run.
