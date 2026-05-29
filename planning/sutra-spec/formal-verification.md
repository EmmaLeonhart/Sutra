# Formal verification — the rules

**Status: framework (the "rules"), 2026-05-24.** This is the canonical,
agent-facing spec of what formal verification *means* for Sutra and what
obligations it imposes. The clawRxiv write-up is `paper/formal-verification/paper.md`;
this file is the ground truth it must not contradict (CLAUDE.md §"If spec and
implementation disagree, stop and resolve it explicitly").

It is a framework, not a finished proof. Most of the obligations below are
*stated* here; *discharging* them mechanically is the ongoing project. Saying
otherwise would be exactly the fake this repo forbids.

## The one claim

> Sutra's compiler emits, for each program, a single fused **tensor-op graph**
> over a frozen substrate, and that graph *is* the program's semantics. So
> verifying the trusted base is *discharging a finite set of closed-form
> obligations over a small, fixed set of tensor graphs* — algebra on the compiled
> graph — rather than navigating control flow through imperative code.

> **Terminology (2026-05-24, Emma):** do NOT call this a "tensor normal form"
> (TNF). We have not formally defined a normal form and claiming canonicality we
> have not proven is an overreach that invites "not rigorous" rejections. The
> real, defensible statement is the descriptive one above: the compiler emits a
> tensor-op graph that is the program's semantics. Drop "TNF"/"normal form" from
> outward writing.

## The compiled tensor-op graph

The compiled graph is not constant folding applied to an otherwise-conventional
program. There is no residual program underneath: the matrices **are** the
computation, the way a neural network's weights are the computation and not an
optimization of it. The difference from constant propagation / partial evaluation
/ staging is **ontological, not quantitative** — compilation collapses the
computational model into linear algebra, so there is no "un-folded" version to
fall back to.

The consequence that matters for verification: **equivalence checking on the
compiled graph is algebra, not a control-flow traversal.** Two programs that
compile to the same polynomial graph are decided equal by `expand(p₁ − p₂) == 0`.

**Scope correction (measured 2026-05-24, do not overstate this).** It is *not*
true that every semantically/logically equivalent pair reduces to the *same*
graph. The reduction canonicalises the equivalences that are polynomial
identities (De Morgan, commutativity, double negation — verified), but
**distributivity** `a&&(b||c)` ≡ `(a&&b)||(a&&c)` is a counterexample: the two
agree on the {−1,0,+1} Kleene grid (logically equivalent) yet reduce to
*different* polynomials off-grid. So "reduce to the same graph" is strictly
stronger than "logically equivalent"; the reduction is a sound *partial*
canonicaliser, not a complete decision procedure for logical equivalence. The
general checker decides BOTH notions exactly for the Kleene fragment —
`reduces_to_same_graph` (polynomial identity) and `kleene_equivalent` (grid
agreement). See `planning/findings/2026-05-24-distributivity-not-canonical.md`.

## Scope — what is in and what is out

In scope (the **trusted base**, verifiable in principle):
- The non-AI programs whose behaviour is fixed at compile time: kernel/runtime
  roles, named critical processes, the deterministic primitives (bind, unbind,
  bundle, similarity, the canonical-axis constructors, the four arithmetic ops,
  the `select` dispatch), control flow, and string I/O.
- The property verified is **per-contract**: "each named program satisfies its
  published axon-typed contract (read roles, write roles, status conditions)."

Out of scope (we do **not** claim these — stating it up front is the rule):
- **The AI parts.** Any embedding-model invocation, any program whose semantics
  depend on a *learned* weight matrix, is not verifiable and we do not pretend
  it is. It gets bounded-behaviour guarantees, capability discipline, provenance
  roles, and runtime monitoring instead. FV makes the AI parts *quarantinable*,
  not *safe*.
- **Whole-system closed-form correctness.** Equivalence-as-algebra applies to
  the contract surface of *individual* programs whose compiled graphs are individually
  tractable. It does not wave away state-space explosion across a whole running
  system. No real system has a closed-form whole-system proof; we do not promise
  one.

## The three reduction pillars (where the obligations come from)

### Pillar 1 — reduction to the compiled tensor-op graph

A Sutra program compiles to a fused tensor-op graph that is its semantics.

- **Obligation (equivalence):** whether two programs compile to the same graph is
  decided by algebraic comparison of the two graphs (`expand(p₁ − p₂) == 0`), not
  by exploring executions.
  - **DISCHARGED for the Kleene-logic fragment, 2026-05-24.** The general
    checker (`sutra_compiler/fv_obligation_checker.py`) extracts each
    expression's polynomial via the compiler's own inliner and decides
    `reduces_to_same_graph` by polynomial identity (`expand(p₁ − p₂) == 0`) —
    exact and decidable for arbitrary `&&`/`||`/`!` nestings. It refuses
    (`NonPolynomialResidual`) on anything outside the fragment (comparisons,
    intrinsics), so the boundary is named, not faked. See the scope correction
    above (distributivity) and `tests/test_fv_general_checker.py`.
- **Obligation (contract):** for a program `p` with axon-typed contract `C`,
  show `p`'s compiled graph reads only `C.read_roles`, writes only `C.write_roles`, and that
  the role-to-role map it computes matches `C`. The static read/write key sets
  the compiler already emits (`AXON_KEYS_READ` / `AXON_KEYS_BOUND`) are the
  starting evidence for the role obligations.
  - **Role-isolation (reads-only / writes-only) — DISCHARGED at the kernel,
    2026-05-24.** The downstream Yantra kernel enforces this at admission/routing
    and it is mechanically tested: a process can only emit on roles in its
    `write_roles` (capability check, else `CapabilityError`) and is delivered
    only axons on roles in its `read_roles`, with no cross-role leakage
    (`../Yantra/tests/test_kernel.py`: `test_send_refused_when_sender_lacks_
    write_role`, `test_send_to_unadmitted_role_is_black_hole`,
    `test_fv_role_contract_read_isolation`). So the read/write *confinement* part
    of the contract is verified.
  - **Function-correctness — DISCHARGED for the Kleene fragment, 2026-05-25.**
    That the *role-to-role function* matches `C` is, for a trusted program in the
    Kleene-logic fragment, exactly `reduces_to_same_graph(implementation,
    contract_reference)` — decidable, exact, any depth. Demonstrated in
    `tests/test_fv_general_checker.py::test_contract_function_correctness_kleene_
    fragment`: a correct NAND implementation (De Morgan) passes its contract; NOR
    is caught (not vacuous). **Scope:** covers trusted programs that ARE Kleene
    expressions; a program outside the fragment (echo = identity axon rebind;
    switch.su = arithmetic + select) has its function-correctness covered by its
    own substrate tests, not by this procedure.
  - **Key-soundness — DISCHARGED via runtime key-usage instrumentation,
    2026-05-29.** The static `AXON_KEYS_READ`/`BOUND` sets are now gated against
    the keys a program actually touches at runtime. The PyTorch runtime carries
    opt-in key tracing on `axon_add`/`axon_item` (`_VSA._fv_key_trace`, OFF by
    default so the hot path is untouched — it is a host-side `set.add` of a
    compile-time key string around the substrate op, never inside the tensor
    math). `fv_key_soundness.check_key_soundness` enables the trace, runs the
    program's axon accesses, and checks `runtime_read ⊆ AXON_KEYS_READ` and
    `runtime_bound ⊆ AXON_KEYS_BOUND`. A `str` key is recorded by name; a non-str
    (pre-embedded vector) key the static analysis could not name is recorded as
    `'<dynamic>'`, which is never in the static literal set and so is always an
    escape — catching any program that reaches an axon via a runtime-computed key.
    Non-vacuous (`tests/test_fv_key_soundness.py`, 5/5): a program touching only
    its statically-collected keys is sound; a read of an uncollected key, a bind
    of an uncollected key, and a `'<dynamic>'` vector key are each caught. With
    role-isolation (kernel) + function-correctness (Kleene fragment) + key-
    soundness now all discharged, the §3.1 contract obligation is no longer half-
    done. (Residual: the check is *per-run* over the exercised paths; a
    path-coverage argument or a key-level manifest would make it exhaustive
    rather than execution-witnessed — a sharpening, not an open hole.)

### Pillar 2 — polynomial Kleene logic for branches (the lever that kills path explosion)

This is the pillar that does the most verification work, and it is what
distinguishes Sutra's surface from "the compiled program is just a tensor
pipeline." In conventional verification, **branches are the enemy**: each
`if/else` doubles the path set, and a trusted base with *b* branches has up to
2ᵇ paths to consider — the state-space explosion that makes imperative
verification expensive. Sutra removes the branch as a control-flow object.

What looks like `if/else` in source becomes, after reduction, a **single
polynomial that interpolates between the branch values on a fuzzy truth value**.
The connectives are the **three-valued Kleene** operators (`and`, `or`, `not`,
the t-norms), realised as **Lagrange-interpolated polynomials exact on the
3×3 Kleene grid** over truth values {−1 = false, 0 = unknown, +1 = true}, and
Cᵒᵒ (smooth) off the grid. They are **branchless and gradient-compatible**:
one closed-form expression, no path fork, differentiable everywhere.

Two properties matter for verification, in order:

1. **Branchlessness collapses the path set.** A branch is no longer a fork to
   enumerate; it is a polynomial whose value is determined by the truth-axis
   scalar feeding it. Verifying the branch is bounding *that polynomial*, not
   walking 2ᵏ paths. This is the move that takes the certification surface from
   "navigate exponential control flow" to "discharge a finite set of closed-form
   obligations."
2. **Three-valued, not Boolean, is the right logic for this substrate.** The
   middle value (0 = unknown) is a first-class truth value, so a program that
   mixes exact symbolic signals with uncertain learned ones can *represent*
   "undetermined" instead of being forced to a premature Boolean collapse. The
   verifier reasons about the third value directly; it does not have to pretend
   every predicate is decided. Because the polynomial is **exact on the grid**,
   the crisp cases (true/false) are bit-exact, while the genuinely-fuzzy cases
   stay fuzzy and bounded — both are inside the same closed form.

- **Obligation (branch range/sign):** for each reduced branch polynomial, bound
  its range and sign over the truth-axis domain [−1, +1] — a closed-form
  question (a polynomial extremum/root problem), not a path enumeration.
  - **DISCHARGED for the three connectives, closed-form, 2026-05-24.** The
    bespoke checker's first piece — a polynomial range-bounder over an
    axis-aligned box by the compact-domain extremum argument (corners +
    edge-interior + interior stationary points; exact sympy arithmetic) — is
    built: `sdk/sutra-compiler/sutra_compiler/fv_poly_bound.py`. It proves the
    `&&`, `||`, `!` polynomials have *exact* range [−1, +1] over [−1, +1]²
    (min = −1, max = +1, not sampled). The bound is tied to the *compiled*
    forms: the test first cross-checks the symbolic polynomials against the
    torch substrate on the {−1,0,+1}² grid (which determines a degree-≤2-per-
    variable polynomial) plus off-grid points, then bounds. See
    `sdk/sutra-compiler/tests/test_fv_poly_obligation_checker.py`. This is the
    branch-range obligation for the primitive connectives.
  - **SCALES to arbitrary depth by composition, 2026-05-24.** The composed
    polynomial of a deeply nested expression is high-degree and bounding it
    directly is expensive — but unnecessary. Each connective maps [−1,+1]^k into
    [−1,+1] (its exact range *is* [−1,+1], proven above), so any expression built
    solely from connectives, over truth inputs in [−1,+1], is range-sound by
    induction on the expression tree — degree-insensitive, any depth.
    `range_sound_by_composition` (`fv_obligation_checker.py`) verifies an
    expression is such a composition (refusing on a non-connective operator) and
    decides it instantly, including the deep 4-var case that makes the closed-form
    bounder intractable. So both branch-range (composition) and equivalence
    (polynomial identity) are degree-insensitive; the closed-form bounder is the
    exact tool for the per-connective lemma they rest on.
- **Obligation (grid exactness):** check that each connective polynomial
  reproduces the Kleene truth table *exactly* at the nine grid points
  {−1, 0, +1}², i.e. that the Lagrange interpolation is the intended one. This is
  a finite, decidable check (evaluate at nine points), and it is the formal
  anchor that ties the smooth polynomial back to the discrete logic it stands in
  for.
- **Saturation note:** the same polynomial/transcendental saturation that makes
  branches exact at the grid is what makes the `select` dispatch exact in
  practice — `exp(−k)` underflows to exactly 0 in float32 for modest `k`, so a
  sharpened softmax `select` is a *true* one-hot (off-branches ×0), not a blend.
  Downstream evidence: Yantra's calculator selects its operator this way,
  18/18 bit-exact (`../Yantra/apps/calc/switch.su`).
- **Tooling:** off-the-shelf SMT solvers target Boolean / linear arithmetic;
  discharging these polynomial obligations needs a bespoke checker. Shipping it
  is part of what compiler qualification costs. **First piece built**
  (`fv_poly_bound.py`, the closed-form range-bounder above, discharging the
  branch-range obligation for the connectives); the *general* checker that takes
  an arbitrary reduced-graph obligation and discharges it is still the bulk of
  the remaining work and is **not built**.

### Pillar 3 — tail-recursive loops as soft-halt RNN cells

Each loop is a bounded recurrence `state ← R · state` whose halt cell decides
termination; the state vector is fixed-width across iterations (O(1) state).

- **Obligation (termination):** show the halt signal is **monotone within
  bounded steps** — a far smaller obligation than proving an arbitrary `while`
  terminates, but still discharged *per loop*.

## Why this is credible and not hand-waving — the exact-substrate evidence

The reduction is only meaningful if the substrate actually computes the reduced
form *exactly*. It does, measured (cite these, do not paraphrase):

- **Bundle decoding:** rotation binding decodes at **100% through width k=8** on
  four frozen substrates (three text encoders + ESM-2), where the Hadamard
  product has already collapsed (2.5% / 7.5%). (`paper/paper.md` §3.2.)
- **Reversibility:** rotation round-trip mean
  `‖unbind(R, bind(R, x)) − x‖ = 1.5 × 10⁻¹⁵` (floating-point noise floor).
- **Exact arithmetic through the trusted base:** Yantra runs full arithmetic
  expressions on the substrate through the kernel, operator selection included,
  **bit-exact within the float32 exact-integer range** (calc 18/18; 1024/1024
  symbol fidelity, max |err| = 0.0). This is the contract-surface property in
  miniature: the reduced graph computes exactly what the source denotes.

## The certification-shaped argument (DO-178C-shaped)

The reduction buys a real *shape* for a certification effort (not a certified
system):

- **Plan:** a fixed image + fixed set of critical programs; manifests published;
  no runtime code loading.
- **Requirements:** axon-typed contracts on every role / critical program.
- **Design:** the Sutra source, whose **compiled graphs are the designs**.
- **Verification artefacts:** mechanical proofs that the compiled graphs satisfy
  the contracts; polynomial obligations discharged by the bespoke checker.
- **Trace:** every capability grant and admit/evict in an append-only log.
- **Tooling assurance:** the compiler is in scope for qualification; the
  artefact under review is its **output (the compiled graph)**, not the source.

## Non-claims (the discipline — keep this section honest)

- Sutra is **not** formally verified today. The architecture is
  verification-friendly; the proofs are an ongoing project, most not started.
- The polynomial-obligation checker exists only in part: the closed-form
  range-bounder (`fv_poly_bound.py`) discharges the branch-range obligation for
  the primitive connectives, but the **general** checker — discharge an
  arbitrary reduced-graph obligation — **does not exist** yet.
- FV covers the **non-AI trusted base only**, per individual contract, not the
  whole running system and not anything that rides on a learned weight.
- If a later result contradicts anything here, stop and resolve it (fix the
  impl or update this doc) — do not let the paper and this spec drift.

## FV paper — tasks to a submittable level (the continuation reference, 2026-05-25)

Derived from the recurring clawRxiv review cons (posts 2614→2621, 7× Reject with
consistently positive pros) and from what is measured vs not-yet-built. Ordered
roughly by leverage. Wordsmithing against the AI reviewer has hit diminishing
returns; these are the substantive items (and a human venue is the real target).

1. **k=8 → real capacity evidence (recurring con, needs an experiment, not a
   reword).** The reviewers keep reading k=8 as a low bar. Run bundle-decoding at
   higher widths (k = 16, 32, 64…) on the frozen substrates and report the
   accuracy-vs-k curve + the crossover where rotation binding finally degrades;
   that turns "k=8 where Hadamard collapses" into a capacity characterisation.
   Measured numbers only.
2. **Term-count / PIT complexity, stated honestly (con: "path explosion just
   shifted to polynomial expansion").** Do NOT say path explosion is "removed."
   Characterise the cost precisely: range-soundness + equivalence are
   degree-insensitive via composition / polynomial identity, but the *expanded*
   polynomial's term count can grow; give the bound and when it bites. Pair with
   a measured term-count for a few real reduced programs.
3. **Fragment scope (con: "Kleene fragment too restrictive; no complex data
   structures / stdlib").** Either (a) widen the decided fragment (comparisons,
   arithmetic predicates) toward more of the trusted base, or (b) tighten the
   paper's claim to exactly the fragment covered and state the path to more. Tie
   to the actual trusted-base programs (kernel roles, echo, switch).
4. **Contract key-soundness (the open §3.1 half) — DONE 2026-05-29.** Runtime
   key-usage instrumentation shipped: opt-in `_VSA._fv_key_trace` on
   `axon_add`/`axon_item` + `fv_key_soundness.check_key_soundness` gating
   `runtime_keys ⊆ AXON_KEYS_*` (non-str keys recorded `<dynamic>`, always an
   escape). Non-vacuous, `tests/test_fv_key_soundness.py` 5/5. §3.1 contract
   obligation now fully discharged (role-isolation + function-correctness +
   key-soundness). Residual sharpening: per-run path-coverage → exhaustive.
5. **Termination framing (con: "trivial / bounded loops sidestep").** Decide the
   framing: lean into "bounded-by-design is the point, the content is convergence
   detection" with a sharper convergence result, or scope the claim. Not a
   wordsmith — needs a crisper convergence property.
6. **The citation con is UNFIXABLE here.** The reviewer flags
   `Shaw … 2025, arXiv:2501.05368` as "hallucinated/future-dated" even with the
   arXiv ID — its knowledge cutoff cannot verify a 2025 paper (same pattern as
   the Neural Computers citation). Nothing to change in the paper; note it when
   choosing a venue (a human reviewer resolves it instantly).
7. **General obligation checker (the bulk of the remaining build).** Extract the
   polynomial directly from the emitted graph (not the inliner restatement) and
   discharge an arbitrary reduced-graph obligation — the part still not built.

## Cross-references

- `planning/exploratory/tnf-vs-constant-folding-explanation.md` — compiled-graph
  ontology (the "compiled graph is the semantics, not a constant fold" argument;
  filename predates dropping the "TNF" term).
- `planning/sutra-spec/equality-and-defuzzification.md` — truth axis, Kleene,
  defuzzification (the saturation that makes branches/`select` exact).
- `planning/sutra-spec/control-flow.md` — loops and conditionals.
- `paper/paper.md` §3 — the measured substrate empirics cited above.
- Yantra `paper/paper.md` §4 — the downstream OS-level verification surface this
  language-level framework feeds.
