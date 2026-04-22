# Rotation binding prototype — design decisions

**Date:** 2026-04-22.
**Status:** Design note for the first-pass implementation. Captures
the compromises taken to get rotation binding running on the real
frozen LLM embedding space without blocking on the full
extended-state-vector design.

## The target

Replace the sign-flip bind in `sdk/sutra-compiler/sutra_compiler/
codegen_numpy.py` (lines 171-175) with rotation binding, using the
nomic-embed-text frozen LLM substrate that's already wired up. Keep
the existing demo programs (`role_filler_record.su`, `analogy.su`,
`knowledge_graph.su`, `predicate_lookup.su`) passing. Prototype a
rotation-hashmap. Deliver this in a single implementation pass
rather than blocking on the full extended-state-vector spec.

## The compromise: rotation in the semantic subspace, for now

The 2026-04-21 design (see
`2026-04-21-extended-state-and-rotation-binding.md`) commits to:

- State vector split as `[semantic | synthetic]`.
- Rotation binding acts on a dedicated synthetic subspace with 2D
  Givens planes per slot → **zero cross-talk by construction**.
- Semantic binding (learned matrices) acts on the semantic subspace.

Implementing that properly requires threading the subspace split
through embedding, bind, bundle, unbind, similarity, snap, and
every example program. It's a multi-session refactor.

**This prototype instead does rotation binding in the same 768-d
nomic embedding subspace that sign-flip currently operates on.**
The role vector seeds a Haar-random orthogonal matrix; bind is
`Q_role @ filler`; unbind is `Q_role^T @ bound`. Cached per role
hash so repeated bind/unbind calls reuse the rotation matrix.

**Honest caveat: cross-talk stays at 1/√d statistical, not zero.**
Because the rotation's planes aren't structurally segregated from
the content-bearing directions of the LLM embedding, bundled-and-
retrieved noise has the same magnitude as under sign-flip. For
the existing 3-4 item records in the demo programs, 1/√d ≈ 3.6%
noise is tolerable — classification by nearest-cosine-match still
works. For larger bundles or more demanding retrieval, the zero-
cross-talk advantage of the dedicated-subspace design would start
to matter and this prototype would not be enough.

**Why this prototype is still net-positive over sign-flip:**

1. **Continuous parameter space.** A rotation is any element of
   SO(768); sign-flip is limited to diagonal ±1 matrices (a finite
   set of size 2^768). This matters for the rotation-hashmap use
   case, where you want keys hashed to continuous angles rather
   than discrete sign patterns.
2. **Magnitude preservation.** Rotations preserve L2 norm exactly;
   sign-flip happens to too, but rotations compose cleanly and
   behave well under mean-centering, which is what the substrate
   requires (see
   `2026-04-22-magnitude-preservation-as-substrate-requirement.md`).
3. **Upgrade path.** Once the extended-state-vector design lands,
   rotation binding upgrades from "role-seeded Haar rotation on
   semantic dims" to "2D Givens plane in dedicated synthetic dim
   allocated at compile time" — same bind signature, same
   unbind inverse, just different subspace. The prototype doesn't
   build an architecture we'd have to tear out.
4. **Composition with learned-matrix bind later.** When learned-
   matrix bind lands (deferred past 2026-04-29 per user priority),
   it'll operate on the same 768-d space; rotation and learned-
   matrix bind will then coexist in a shared substrate, which
   pressure-tests the "two kinds can operate on the same state"
   claim.

## Scope of this prototype pass

**In:**

- Swap `bind`/`unbind` in `codegen_numpy.py` to rotation binding.
  Keep `bundle` as sum-and-normalize.
- Role-seeded Haar rotation, cached by role hash. Hash uses the
  float64 bytes of the role vector for determinism.
- Runtime methods on `_NumpyVSA` for a rotation hashmap
  (`hashmap_new`, `hashmap_set`, `hashmap_get`) — library-pattern
  implementation per Candidate B in
  `planning/open-questions/rotation-hashmap-as-language-feature.md`.
  Accessed from Python test scripts, not yet wired into the .su
  language surface.
- 2-4 new example .su files exercising rotation bind on semantic
  vectors (record round-trip, multi-field records, sequence/
  association tasks).
- Smoke test against existing and new .su programs.

**Explicitly out of scope for this pass:**

- **Extended state vector.** No `[semantic | synthetic]` split.
  Rotation lives in the same 768-d space as semantic content.
  Recorded as follow-up work.
- **Language-surface hashmap.** `map<K, V>` as a .su declaration
  form stays the open question; this pass tests the mechanism via
  Python calls to the runtime.
- **Learned-matrix binding.** Deferred per user priority until
  after the Anthropic grant application (~2026-04-29).
- **`role` / `var` declaration keywords.** Surface syntax decision
  is committed in the spec but not yet implemented in the parser.
  Existing examples keep their `vector r_name = basis_vector(...)`
  declarations; rotation binding is the new underlying mechanism
  regardless of declaration syntax.
- **Canonical truth axis.** Spec only; no runtime support yet.
- **Sign-flip bridge.** Sign-flip is being fully retired from the
  codegen in this pass, not kept as a fallback. If existing demos
  break on rotation, we fix rotation (or report the result), not
  re-enable sign-flip.

## Rotation-hashmap mechanism (library pattern)

Implemented as methods on `_NumpyVSA`:

- `hashmap_new()` returns a zero vector (the accumulator).
- `hashmap_set(acc, key_vec, val_vec)` returns a new accumulator
  equal to `acc + rotate(val_vec, key_vec)`. Key vector is hashed
  (same mechanism as bind roles) to derive a rotation matrix; the
  value is rotated by that matrix and added to the running
  accumulator. Bundle is sum-without-normalize (normalization
  would interfere with capacity accounting across many writes).
- `hashmap_get(acc, key_vec)` returns the value extracted by
  inverse rotation: `Q_key^T @ acc`. Caller handles cleanup
  (argmax-cosine against a candidate codebook, or raw vector).

Soft lookup falls out for free: if the query key is noisy, `Q_key`
is close to `Q_stored_key`, so `Q_key^T @ Q_stored_key` is close
to identity, and the retrieved value is close to the stored one.
The quality of "close" depends on how continuous the
role-to-rotation map is — in this prototype, hash-based seeding
makes the map discontinuous (small key perturbations produce
different rotations), which *kills* soft lookup. That's a
limitation of the prototype that the full design (learned
projection → continuous angles) would fix.

**Prototype fallback: for soft lookup to work, the hashmap will
use a continuous hash** — project the key onto k random unit
vectors, use the projections as angles for k 2D Givens rotations
in random plane pairs. This way a small key perturbation produces
small angle changes, and soft lookup works.

## Expected results

- **Record round-trip (`role_filler_record.su`, etc.):** should
  pass. 3-field records with 1/√d cross-talk have healthy margin.
- **Larger bundles (`knowledge_graph.su`, `predicate_lookup.su`):**
  should pass but with tighter margins. If a test that passed under
  sign-flip fails under rotation, that's a finding worth recording,
  not a reason to back off.
- **Hashmap soft lookup:** at small N (say, 4-8 stored items) with
  distinctive semantic keys, retrieval should work with noisy
  queries. At larger N, capacity limits kick in. The capacity
  experiment from `2026-04-21-rotation-binding-capacity-experiment-
  design.md` is the full characterization; this pass tests only a
  handful of cases.

## Prior-art audit pending

The role-seeded Haar-random rotation binding approach has clear
prior art — this is essentially the "random permutation binding"
of classical HRR/HDC, generalized to continuous rotation. Plate
(1995), Kanerva's HDC, Frady & Sommer on fractional power encoding
all touch this. Before publication, the specific seeding-from-role-
vector mechanism and the hashmap-via-continuous-projection design
need to be checked against the HDC associative-memory literature
(Kleyko et al., Ge & Parhi) and against knowledge-graph-embedding
literature that explicitly uses rotation (RotatE, Sun et al. 2019
— RotatE's `h * r ≈ t` with complex-valued rotations is very close
to what we're doing here, and this is the second "TransE/VSA
should be the same thing" data point).

**RotatE deserves a dedicated callout.** Sun et al.'s RotatE paper
explicitly treats KG relations as rotations in complex-valued
embedding space, which is the same mechanism as Sutra's rotation
binding with a phase-angle interpretation. Like TransE, it sits in
the KG-embedding community but uses a VSA-style primitive. The
unification story (TransE/VSA aren't different traditions) is even
stronger once RotatE is in the picture.
