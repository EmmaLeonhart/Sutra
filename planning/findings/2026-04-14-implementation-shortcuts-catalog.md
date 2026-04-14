## Implementation shortcuts in the Sutra and fly-brain pipelines, as of 2026-04-14

**Audience:** Emma, future sessions. **Not** the papers. Per CLAUDE.md, shortcuts
are reported to the user and recorded here, not written into paper bodies. The
papers state design intent; this file states where the implementation falls short
of that intent.

This file replaces the implementation-confession paragraph in
`sutra-paper/paper.md` §3.4 that was added in commit `ce1fce1` and is being
reverted alongside this catalog.

---

### 1. `t_true` is a seeded random direction, not a substrate-fit centroid

- **Spec / paper claim:** `t_true` is the substrate-fitted *canonical truth
  direction*, fit during empirical initiation by embedding a curated set of
  canonically-true propositions and taking the unit-normalized centroid
  (§3.4 / `planning/sutra-spec/04-defuzzification.md`).
- **Implementation:** `fly-brain/vsa_operations.py` constructs `t_true` from
  `numpy.random.RandomState(seed=hash("__RESERVED_TRUE__"))` and unit-normalizes.
  This is a reserved random direction, not a centroid of anything.
- **Why this matters:** the spec says `is_true(v) = cos(v, t_true)` measures
  semantic truth. With a random `t_true` the value is uncorrelated with truth —
  it's just a stable hash that any program can share. The construction works as
  a single canonical constant but does not realize the *meaning* the spec
  attaches to it.
- **What's needed to close it:** an embedding-space backend that fits `t_true`
  to a curated true-proposition centroid on a non-broken substrate (GTE-large /
  BGE-large / Jina-v2 — *not* mxbai). Connectome backend can keep a reserved
  direction with a separate justification, since "centroid of true propositions"
  is not a thing the connectome substrate has.
- **Reviewer impact:** the v9_post1601 Gemini review specifically flagged this
  as the "massive assumption" of the paper. The ce1fce1 attempt to be honest
  about it in the paper body was the wrong move — the fix is to make the
  implementation match the design intent, not to publish the gap.

### 2. The §6.6 "80/80" decision number is from the old hemibrain MB, not Shiu

- **Paper claim (current §6.6):** "80/80 decisions, σ=0" on the four-program
  conditional, hemibrain MB (140 PN → 1,882 KC), n=5 seeds.
- **Newer measurement available:** the same algorithm on the Shiu whole-brain
  LIF (138,639 neurons, 15M synapses, real FlyWire v783 W) gives **155/160
  (96.9%)** at n=10 seeds. The window-sweep finding from this morning
  (`planning/findings/2026-04-14-shiu-conditional-window-sweep.md`) confirms
  the residual is structural codebook collision on bad seeds, not integration
  noise.
- **Why this matters:** the Sutra paper is silently citing the easier
  (small-MB-only) number. The fly-brain paper already updated to Shiu 155/160
  in its abstract. The Sutra paper §6.6 has not.
- **What's needed to close it:** rewrite §6.6 to lead with the Shiu number,
  drop "80/80 σ=0", report the measured 96.9% honestly.

### 3. MBON readout is ridge regression, not dopamine-gated plasticity

- **Paper framing (fly-brain):** the readout layer "uses a learned linear map
  from KC firing patterns to output vectors, fitted via ridge regression — the
  same shape of computation a real MBON performs via dopamine-gated plasticity."
- **What this elides:** ridge regression has access to held-out training labels
  and minimizes squared error globally. Dopamine-gated plasticity is a local
  Hebbian rule keyed to a reinforcement signal. They produce a linear map; the
  *means* of producing it are completely different. Reviewer 1606 con #2
  flagged this directly.
- **Why this matters:** the "MBON does the matching" claim downstream of this
  is doing real work in the paper — if the matching is actually ridge regression
  on KC activity vectors, the substrate's contribution shrinks to "produces the
  KC patterns we then classify with sklearn."
- **What's needed to close it:** either (a) implement an actual local plasticity
  rule (anti-Hebbian on KC→MBON gated by a reinforcement signal) and report
  whatever number that gives, or (b) be explicit in the paper that the readout
  is fitted offline and the substrate's role is the KC encoding only.

### 4. "Empirical initiation" is not implemented for `t_true`

- **Paper claim (§4.2 of Sutra paper):** the compiler probes a target
  embedding space, fits correction matrices, and outputs a substrate-specific
  mapping. This is presented as the language's compilation strategy.
- **Implementation reality:** the empirical-initiation framework exists for
  per-embedding-model binding capacity tests (see §6.3 cross-substrate table),
  but `t_true` specifically does not go through it — it is constructed from a
  reserved hash regardless of substrate (#1).
- **Why this matters:** §3.4 and §4.2 imply `t_true` is *output* of empirical
  initiation. It is not. This is the same gap as #1, viewed from the
  compiler-strategy angle.

### 5. Eigenrotation loops sometimes accumulate `R^i v₀` on the host

- **Spec (§03):** `loop (condition)` iterates `state ← R · state` *on the
  substrate* — every step is a substrate forward pass, not a host matmul.
- **Implementation reality:** several `fly-brain/real_rotation_*.py` variants
  iterate the rotation on numpy at the host and only run prototype matching
  on the substrate. This is documented in the fly-brain paper §Result 3
  (the "rotation runs in host numpy and termination runs on the real
  hemibrain MB" pipeline, 20/20 + 30/30).
- **Why this matters:** when results from a host-iterated rotation are
  reported without that caveat, the claim "eigenrotation runs on the
  connectome" is overstated. The fly-brain paper actually does this honestly
  in the current draft (it labels the host-iterated pipeline as such and
  retracts the substrate-iteration claim). The shortcut to watch for is in
  *future* sessions accidentally re-asserting "rotation on the connectome"
  from the host-iterated numbers.
- **Status:** the negative result was correctly captured in
  `planning/findings/2026-04-13-cx-ring-attractor-no-direction-discrimination.md`
  and the EPG-no-recurrence finding. The shortcut is the gap, not the
  reporting of the gap.

### 6. `select`'s normalizer is clipped-cosine + sum-normalize, not softmax

- **Spec (§26):** `select(scores, options) = Σ softmax(scores)_i · options_i`.
- **Implementation reality:** `fly-brain/fuzzy_conditional.py` and
  `fly-brain/shiu_conditional.py` use `max(0, cos)` then sum-normalize, because
  the substrate can drive that cheaply and exponentials are more expensive.
- **Why this matters:** both produce convex combinations of options, so the
  4-way conditional results are not invalidated. But the spec calls one thing
  and the implementation does another, and §26 explicitly flagged this as an
  open spec question rather than picking a side. The papers don't call this
  out at all.
- **What's needed to close it:** either (a) decide softmax is normative and
  approximate it on the substrate with a documented justification, or
  (b) update §26 to make clipped-cosine + sum-normalize the spec, with
  softmax as an alternative.

### 7. §6.6 of the Sutra paper still describes polar-decomposition `Q` as
"iteration on the connectome"

- **Status in fly-brain paper:** retracted (Result 3 in the fly-brain paper
  explicitly retracts this and reports the negative EPG-drive result).
- **Status in Sutra paper:** §6.6 last paragraph still says "Iteration
  compiles to eigenrotation … `Q` is the polar-decomposition nearest-orthogonal
  matrix to a real FlyWire v783 slice … `‖W − Q‖_F / ‖W‖_F = 0.983`" — and
  reports the substrate-only 9/10 at k=3 alongside the host-iterated 20/20+30/30
  without the retraction. The two papers disagree about the same operation.
- **Why this matters:** if the fly-brain paper retracts it as a substrate
  operation and the Sutra paper still cites it, the second one is publishing
  a claim the first one withdrew.
- **What's needed to close it:** either drop §6.6 from the Sutra paper entirely
  (the pre-mortem in `2026-04-14-sutra-paper-pre-mortem.md` argues for this),
  or align it with the fly-brain paper's retraction.

---

## How to use this catalog

When a future session is editing either paper:

1. Read this file before claiming any of the operations above are working
   "on the substrate" or "as the spec describes."
2. If you fix a shortcut (close the spec/impl gap), delete that entry and add
   a one-line note to the commit message that the shortcut was closed.
3. If you discover a new shortcut, add it here with the same structure
   (claim / implementation / why-it-matters / what's-needed). Do not put it
   in the paper.
4. If a reviewer flags something that turns out to be on this list, that's
   the reviewer correctly catching a gap we already knew about — fix the
   implementation, do not publish the gap.

The rule: papers state design intent with substrate-honest measurements.
Shortcuts live here.
