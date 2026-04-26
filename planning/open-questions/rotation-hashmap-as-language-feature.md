# Open question: rotation-hashmap as a language feature

## The question

A rotation-hashmap is a hashmap whose lookup mechanism is **rotation
binding with a hash-to-angle function**: given a key-vector, hash it
to a point on a k-torus (a vector of k angles in [0, 2π)), use
those angles as the rotation parameters to store / retrieve an
associated value.

**Should Sutra have this as a first-class language feature, a
library pattern, or neither?**

The three options:

1. **First-class language feature.** Dedicated declaration form
   (`map<K, V>` or similar), compiler allocates hash directions and
   synthetic-subspace storage region at compile time, runtime does
   the rotation/bundle/retrieval primitively. Syntax has subscript
   access: `m[key] = value; x = m[key]`.
2. **Library pattern.** Users can compose the primitive
   rotation-binding + hash-projection machinery themselves to build
   a hashmap-like structure, but the language doesn't privilege it.
   Stays a community-maintained pattern.
3. **Don't include.** Sutra programs do record-and-field style
   access (one rotation slot per known field name) and don't need
   a runtime-keyed associative structure.

## What we currently do

Nothing — the idea surfaced in the 2026-04-21 session and hasn't
been implemented or committed. Existing demos use static record
fields (`r_name`, `r_color`, `r_shape`), which are compile-time
known keys, not runtime vector keys. There is no associative
structure over arbitrary semantic vectors in the current compiler
or spec.

The mechanically-closest artifact is the `FILLER_NAME` lookup in
`examples/role_filler_record.su`:

```
map<vector, string> FILLER_NAME = {
    f_alice:  "alice",
    ...
};
```

But that's compiled to a Python dict keyed by object identity —
it's not a rotation hashmap, it's just a host-language dict.

## Why this is load-bearing

If Sutra is going to handle real programs (not just toy demos), it
needs **some** way to associate runtime-computed keys with values.
Three concrete pressures:

- **Semantic memory.** Recognize a thing, retrieve what you know
  about it. The thing is a semantic vector (possibly noisy); the
  "what you know" is another semantic vector or a fuzzy scalar.
  This is exactly what a rotation-hashmap does natively: hash the
  recognized vector to angles, extract via inverse rotation.
- **Agent-style programs.** Store observations keyed by context;
  retrieve by context at decision time. The keys are contexts
  (semantic vectors), not compile-time names.
- **General programs that don't know their keys at compile time.**
  Any meaningful extension of the language beyond single-pass
  record manipulation will hit this. Without an associative
  structure, Sutra is effectively a calculator.

The counter-pressure: maybe these cases are better handled by a
host-language dict (as `FILLER_NAME` currently is), and Sutra
itself stays a pure vector-arithmetic language that the host
orchestrates. That's option 3 and it's defensible.

## Candidate A — First-class feature

### Sketch

A new declaration kind alongside `role` and `var`:

```
map<vector, vector> concept_memory;   // allocates a rotation-hashmap
concept_memory[cat_vec]       = cat_whiskers_vec;
concept_memory[dog_vec]       = dog_bark_vec;
result = concept_memory[noisy_cat_vec];    // fuzzy-recovers cat_whiskers_vec
```

### What the compiler does

1. Allocate a dedicated synthetic-subspace region of some size
   (say, `N_hash` synthetic dimensions, enough to support `k`
   rotation planes for the hash) for this hashmap.
2. Allocate or learn `k` hash directions — unit vectors in the
   semantic subspace that the key will be projected onto to get
   the `k` angles. Random projections give LSH-style behavior;
   learned projections give key-distribution-aware spreading.
3. Generate runtime code:
   - **Assign `m[key] = value`:** hash `key` to `(θ_1, ..., θ_k)`,
     apply the corresponding rotation to `value` within the
     hashmap's synthetic region, add the bound result to the
     hashmap's running bundle (superposition).
   - **Read `m[key]`:** hash `key` to angles, apply inverse
     rotation to the hashmap's bundle, extract and clean up.

### What this buys

- **Native soft lookup.** Similar semantic keys hash to similar
  angles, so querying with a noisy version of a stored key
  recovers the associated value approximately. This is the
  cardinal advantage over bit-hash or name-keyed lookup.
- **Fits the extended-state-vector design cleanly.** Hashmap
  storage lives in a dedicated slice of the synthetic subspace,
  structurally orthogonal to semantic content and to other
  hashmaps. No cross-talk with the rest of the program.
- **Language-primitive retrieval is on-substrate.** The whole
  read/write cycle is rotation + bundle + cleanup, all of which
  the substrate already has. No host-side dict, no serialization
  across the semantic/substrate boundary.
- **Composes with learned-matrix bind.** The stored *values* can
  themselves be semantic vectors, which can be operated on by
  learned role matrices — unlike a bit-keyed hashmap where the
  values are opaque.

### What this costs

- **Synthetic-subspace budget.** Each hashmap eats a chunk of the
  synthetic subspace. A program with many hashmaps, or hashmaps
  with many keys, may outgrow the budget.
- **Capacity is finite.** Stored bundle accumulates; eventually
  reading a stored key returns too-noisy output. Needs a
  capacity analysis analogous to the rotation-binding capacity
  experiment.
- **Hash direction choice is substrate-dependent.** Random
  directions are simple and interpretable but give poor spread
  when keys are distributed non-uniformly (e.g. lots of close-
  together concept vectors). Learned directions are better but
  add another empirical-initiation step at compile time.

## Candidate B — Library pattern

### Sketch

Users compose existing primitives. Conceptually:

```
// User-defined rotation hashmap using only role/var primitives
var[K_HASH] hash_directions : vector;    // filled with random directions
var hashmap_state : vector;              // bundle accumulator

function assign(var key, var val) {
    angles = [hash_directions[i] @ key for i in 0..K_HASH];
    rotated = rotate_by_angles(val, angles);
    hashmap_state = hashmap_state + rotated;
}

function lookup(var key) -> vector {
    angles = [hash_directions[i] @ key for i in 0..K_HASH];
    recovered = inverse_rotate_by_angles(hashmap_state, angles);
    return cleanup(recovered);
}
```

### What this buys

- **Zero new compiler work** beyond what's already needed for
  rotation binding.
- **Experimentation space.** Users can prototype different hash
  schemes, different capacity allocations, different cleanup
  procedures, without modifying the language.
- **Honest about capacity/hash choice being substrate-specific.**
  No language commitment to "this is the one true hashmap."

### What this costs

- **Boilerplate.** Every program that wants hashmaps rewrites the
  same ~20-line pattern.
- **No compiler-level cross-talk prevention.** User code might
  accidentally reuse synthetic-subspace dimensions that collide
  with the hashmap. A first-class feature would allocate
  exclusively; a library pattern has to trust the user.
- **Harder to teach.** "Here's how to build a hashmap out of
  rotations" is a lot more to explain to a new reader than
  "here's the hashmap syntax."
- **Harder to analyze.** A language with first-class hashmaps
  lets the compiler reason about them (e.g., is the capacity
  adequate for the number of assigns seen statically?). A
  library hashmap is opaque to the compiler.

## Candidate C — Don't include

### Sketch

Sutra programs handle associative lookup via host-language dicts
(the current `map<K, V>` in examples is already this). The
language stays a pure compositional-vector-arithmetic language;
anything needing runtime-keyed storage goes through the host.

### What this buys

- **Smallest language.** No new primitive, no new syntax, no new
  capacity analysis.
- **Forces clarity on what Sutra is for.** If Sutra is specifically
  the vector-arithmetic core and the host handles everything else,
  the scope is clean.

### What this costs

- **Off-substrate semantics.** Host dicts don't respect the
  substrate model — the lookup isn't "on the substrate," the keys
  are bit-compared rather than rotation-decoded, no soft lookup.
  Any future substrate without a host (e.g. a neuromorphic target)
  wouldn't have host dicts as an option at all.
- **Limits what programs can express.** Agent-style programs,
  semantic memory, anything context-driven becomes awkward.

## Tradeoffs summary

| Candidate | Compiler work | On-substrate? | Soft lookup? | Expressive? |
|---|---|---|---|---|
| A (first-class) | Large | Yes | Yes | Yes |
| B (library) | Small | Yes (user-built) | Yes (user-built) | Yes but verbose |
| C (don't include) | None | No (host dict) | No | Limited |

## What we don't know

1. **How often does a realistic Sutra program need associative
   lookup on runtime-computed keys?** If rarely, (C) with an
   occasional host-dict escape hatch is fine. If frequently, (A)
   pays for itself. The honest answer depends on what programs
   people actually write, which we don't know yet because Sutra
   is too young.
2. **What's the practical capacity of a rotation-hashmap?**
   Capacity depends on hash dimensionality `k`, noise levels at
   read time, and key distribution. Needs an experiment analogous
   to the rotation-binding capacity experiment (see
   `planning/findings/2026-04-21-rotation-binding-capacity-experiment-design.md`).
3. **Random vs. learned hash directions.** Random is simpler but
   worse on clustered keys; learned is better but adds compile-
   time complexity. Unclear which dominates empirically.
4. **Does soft lookup compose correctly?** If stored values are
   themselves compositional vectors that will be operated on by
   role matrices downstream, does the rotation-hashmap noise
   propagate cleanly or destroy the downstream compositional
   structure?
5. **Does the hash have to be deterministic?** For some agent-like
   uses, a stochastic hash (different runs hash the same key
   differently) might actually be desirable — but that complicates
   the "pure Sutra program" framing.
6. **Key type.** Semantic vectors are the obvious case, but should
   integer keys also be allowed? Fuzzy keys? What about keys that
   are themselves records (rotation-bundle structures)?

## What resolving this looks like

- **If we go with A (first-class):**
  - Add a section to `planning/sutra-spec/binding.md` for rotation
    hashmap as a third binding-adjacent construct (or its own
    section, since it's higher-level than a bind).
  - Pick surface syntax. `map<K, V> name;` is the natural form,
    matching existing demo conventions.
  - Design the compiler allocation for hash directions and storage
    region.
  - Run a capacity experiment to set default sizes.
  - Update compiler (`sdk/sutra-compiler/`) to accept and generate
    hashmap code.
- **If we go with B (library):**
  - Add an example `.su` program (`examples/rotation_hashmap.su`?)
    that demonstrates the pattern.
  - Document the pattern in tutorial material.
  - No spec work required; no compiler work required beyond
    rotation-binding-proper being implemented.
- **If we go with C (don't include):**
  - Document explicitly in `planning/sutra-spec/program-structure.md`
    that runtime-keyed associative lookup is delegated to the host.
  - Leave this doc as a resolved-but-not-adopted record so future
    sessions know the question was considered.

## Prior-art audit pending

Rotation-hashmap in the specific form proposed (hash semantic
vector → k angles → rotation binding → bundle storage) has
candidate priors that need actual checking:

- **Fractional Power Encoding** (Plate, Frady & Sommer, Sussillo-
  adjacent work). Continuous-valued rotations for encoding
  scalars in HD representations. Closest mechanical prior, but
  typically framed as "encode a scalar input as a rotation," not
  "use a hash-to-angle for a hashmap." Worth checking whether
  the hashmap-style usage has been stated.
- **Locality-Sensitive Hashing** (Indyk & Motwani 1998 and
  descendants; Datar et al. on angular LSH). Random-projection
  hashing for approximate nearest-neighbor search. Different
  purpose but same "project key onto random direction, derive
  hash" move.
- **Kleyko et al.** on hash operations in hyperdimensional
  computing. Likely overlaps substantially with this proposal;
  first stop for the audit.
- **Associative memory in HD computing** (Kanerva's SDM; FLASH;
  various "resonator networks" work). Mechanically different but
  similar purpose.

The user's working assumption is that rotation-hashmap-with-
continuous-hash-on-semantic-vector-keys is genuinely
under-explored because the field is small; plausible, but the
audit needs to be done before publication. Dev-level decisions
(whether to include this in the language) proceed without the
audit.
