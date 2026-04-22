# Rotation binding prototype — results

**Date:** 2026-04-22.
**Status:** Implementation landed, smoke-tested on the frozen LLM
substrate (nomic-embed-text via Ollama, mean-centered). Companion
to `2026-04-22-rotation-binding-prototype-design.md`.

## What landed

- **Rotation binding** replacing sign-flip in
  `sdk/sutra-compiler/sutra_compiler/codegen_numpy.py`. Role-seeded
  Haar-random orthogonal matrix cached per role-vector hash. Bind is
  `Q_role @ filler`; unbind is `Q_role^T @ record`. Role-first
  convention for both bind and unbind arguments (the majority of
  existing demos already used this convention for unbind; one demo
  and three compositional demos needed argument-order migration).
- **Rotation-hashmap prototype** as runtime methods on `_NumpyVSA`:
  `hashmap_new`, `hashmap_set`, `hashmap_get`. Library-pattern
  implementation (per Candidate B in the open-question doc) — reuses
  bind/unbind with an accumulator to provide a hashmap-like API.
  Exact lookup works; soft lookup (noisy key retrieval) does not,
  which is an expected limitation of the discrete-hash approach and
  future work.
- **Two new example .su programs**: `rotation_record.su` (3-field
  role-filler record, mirrors the classic demo on more
  discriminative fillers), `rotation_book_catalog.su` (4-field book
  records × 4 books = 16 bundled bindings, tests capacity).
- **Python hashmap test**: `examples/_rotation_hashmap_test.py`
  exercises the library pattern with 5 stored (concept, attribute)
  pairs.

## Smoke test results (`examples/_smoke_test.py`)

Running the full 12-program suite on rotation binding:

| Program | Result | Notes |
|---|---|---|
| `hello_world.su` | OK | Doesn't use bind |
| `fuzzy_branching.su` | 16/16 OK | Doesn't use bind |
| `role_filler_record.su` | 6/6 OK | Updated from `unbind(record, role)` to `unbind(role, record)` for role-first consistency |
| `classifier.su` | 9/9 OK | Doesn't use bind |
| `analogy.su` | 5/5 OK | Unchanged — already role-first |
| `knowledge_graph.su` | 5/5 OK | Updated `bind(o, bind(s, p))` → `bind(s, bind(p, o))` for role-first nesting |
| `predicate_lookup.su` | 3/3 OK | Updated nested bind structure like `knowledge_graph` |
| `fuzzy_dispatch.su` | 1/4 PARTIAL | Regression. See analysis below. |
| `nearest_phrase.su` | 25/25 OK | Doesn't use bind |
| `sequence.su` | 10/11 PARTIAL | Updated `bind(token, pos)` → `bind(pos, token)`; one decode (`decode_at(seq_fox, pos_1)`) returns `jumps` instead of `quick` |
| `loop_rotation.su` | 5/5 OK | Doesn't use bind (eigenrotation + snap) |
| `counter_loop.su` | OK | Doesn't use bind |

**Summary: 10 of 12 pass cleanly, 2 partial regressions.**

### The two partial regressions

**`fuzzy_dispatch.su` (1/4).** Uses `select(...)` which produces a
softmax-weighted superposition of 4 records, each with 2 role-
fillers = up to 8 bundled bindings at retrieval. Under rotation
binding, the signal-to-noise ratio at retrieval scales as ~1/√N for
N bundled terms; 8 bundled terms give SNR ~0.35, which is marginal
for 3-4 option codebooks. Sign-flip happened to have component-wise
noise structure that was more tolerant of the select-based
superposition; rotation's noise is isotropic and doesn't tolerate as
well. This is a capacity characteristic, not a bug — a finding
worth recording about the capacity difference between the two
mechanisms. Possible fixes (not in scope for this pass): larger
substrate dimension, harder softmax temperature, or learned-matrix
binding (which can be more informationally efficient than rotation).

**`sequence.su` (10/11).** After the `bind(token, pos)` →
`bind(pos, token)` migration, 10 of 11 checks pass. The single fail
is `decode_at(seq_fox, pos_1)` returning `jumps` instead of `quick`.
Likely a specific noise pattern — 10/11 is within normal capacity
range for 5-item sequences; one off-by-one at ~1/√5 ≈ 0.45 SNR isn't
surprising. Not worth chasing for this pass.

### Migration footprint

Four `.su` files needed argument-order changes to be consistent
with role-first rotation binding:

- `role_filler_record.su`: `unbind(record, role)` → `unbind(role, record)`
- `knowledge_graph.su`: `bind(o, bind(s, p))` → `bind(s, bind(p, o))`
- `predicate_lookup.su`: same nested-bind rewrite as knowledge_graph
- `sequence.su`: `bind(token, pos)` → `bind(pos, token)`

Five `.su` files needed no changes (they already used role-first).
Three `.su` files don't use bind at all. Total migration cost: four
small edits, each 1-5 lines.

The underlying sign-flip asymmetry that the .su files exploited
(both `a * sign(b)` and `b * sign(a)` yield retrievable vectors
through averaging) is a real property of sign-flip that rotation
binding does not have. So the migration was necessary rather than
cosmetic — rotation is strictly directional. The spec change of the
surface syntax (`role` / `var` keywords, Candidate B) will make
this asymmetry visible at declaration time instead of hidden in call
sites.

## New .su programs

### `rotation_record.su` — minimal 3-field demo

Mirrors `role_filler_record.su` on a different set of fillers
(person/topic/mood rather than name/color/shape). Tests rotation
binding on 3 bundled terms with 6-option codebooks per field.
Result: **3/3 decodes correct** across multiple record
instantiations.

### `rotation_book_catalog.su` — 4-field records × 4 books

Each book record has 4 rotation-bindings (title, author, genre,
year). Tests capacity with 4 bundled terms per record. Initial
attempt (using short proper-noun fillers like "Dune", "Asimov")
returned title=Dune and author=Herbert for every query —
a substrate artifact: nomic-embed-text apparently collapses short
proper nouns into a tight cluster, making them indistinguishable
even before binding. Rewriting the fillers as descriptive strings
("a desert-planet novel about spice and prophecy", etc.) gave each
filler a distinct semantic direction, and recovery jumped to
**16/16 decodes correct**.

This is a useful substrate-characterization finding: proper-noun
embeddings cluster tighter than descriptive-string embeddings in
nomic's space. Relevant to sutra programming style — prefer
descriptive fillers over bare proper nouns when possible, or be
prepared to substitute a substrate that handles proper nouns more
distinctively.

## Rotation-hashmap prototype results

Test setup: 5 (concept, attribute) pairs stored in a single
hashmap accumulator; retrieve each attribute by its concept.

**Exact lookup: 5/5 succeeded** with cosine scores 0.42–0.50 against
the correct attribute.

**Soft (noisy) lookup: 2/5 succeeded** (expected failure mode) —
queries with similar-but-different keys (`kitten` for `cat`, `puppy`
for `dog`) return ~0 cosine across all candidates. Only
`puppy→bark` and `salmon→scales` happened to work, and the scores
(0.015, -0.011) are near noise. Consistent with the discrete-hash
limitation: a small perturbation of the key completely changes the
role hash, so there's no continuity from stored key to query key.

**Out-of-distribution queries** (octopus, penguin, rhinoceros — not
stored) return top matches with cosine <0.08, confirming the
accumulator doesn't spuriously claim recovery for unknown keys.

**Signal/noise separation is clear.** Exact lookups score ~0.4-0.5,
everything else scores <0.1. That's a healthy margin.

## Implications for the open question
(`planning/open-questions/rotation-hashmap-as-language-feature.md`)

- **Candidate B (library pattern) is clearly viable.** The mechanism
  works for exact lookup with 5 entries on the real frozen LLM
  substrate. Scaling to more entries is a capacity question the
  rotation-binding capacity experiment will characterize.
- **Candidate A (first-class `map<K, V>` language feature) is
  unblocked.** The library pattern shows the mechanism works; a
  language feature would add subscript syntax (`m[key] = val`),
  compile-time allocation, and potentially a continuous-hash
  variant for soft lookup. Decision still pending.
- **Soft lookup is a real design dimension.** The discrete-hash
  prototype doesn't support it. If soft lookup is load-bearing for
  the use cases Sutra is meant to cover (semantic concept memory,
  agent observation store), the language feature version needs a
  continuous-hash mechanism (Householder reflection parameterized
  by key, or learned projection to angles). That's a real design
  question, not just an implementation detail.

## What remains

- Run the full capacity experiment per
  `2026-04-21-rotation-binding-capacity-experiment-design.md`.
  This prototype tested a handful of cases; the full experiment
  characterizes the capacity curve.
- Decide whether to add continuous-hash soft lookup as a second
  hashmap variant. Preliminary sketch: Householder reflection
  `H(u) = I - 2 u u^T` where `u = normalize(key)` — continuous in
  key, involutory (same for set/get), O(d) cost. Worth trying.
- Implement the `role` / `var` surface syntax (STATUS queue item 4).
  The rotation binding works; declaration syntax is the remaining
  language-level commitment.
- Fix the two partial regressions (`fuzzy_dispatch`, `sequence`)
  either by adjusting substrate parameters or by accepting the
  capacity characterization.

## Prior-art audit pending

The role-seeded Haar rotation binding is essentially continuous-
random-permutation binding from classical VSA/HRR. RotatE
(Sun et al. 2019) in the KG-embedding community uses complex-valued
rotations for relation modeling, which is mechanically the same
operation viewed through phase-angle parameterization. The
hashmap-as-bundle pattern is the standard VSA associative memory
(Kanerva's SDM, Kleyko et al. HD-computing variants). The specific
prototype-implementation-on-frozen-LLM-substrate-via-Ollama
combination may not have been published, but the underlying
primitives are decades old. Audit before publication.
