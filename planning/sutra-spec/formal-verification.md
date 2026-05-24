# Formal verification — the rules

**Status: framework (the "rules"), 2026-05-24.** This is the canonical,
agent-facing spec of what formal verification *means* for Sutra and what
obligations it imposes. The clawRxiv write-up is `paper/formal-verification.md`;
this file is the ground truth it must not contradict (CLAUDE.md §"If spec and
implementation disagree, stop and resolve it explicitly").

It is a framework, not a finished proof. Most of the obligations below are
*stated* here; *discharging* them mechanically is the ongoing project. Saying
otherwise would be exactly the fake this repo forbids.

## The one claim

> A Sutra program β-reduces to a **tensor normal form (TNF)**: a single fused
> tensor-op graph over a frozen substrate. So verifying the trusted base is
> *discharging a finite set of closed-form obligations over a small, fixed set
> of tensor graphs* — algebra on the reduced form — rather than navigating
> control flow through imperative code.

Everything else is the structure that makes that claim precise and the honest
boundary of where it stops.

## What TNF is (and is not)

TNF is not constant folding applied to an otherwise-conventional program. There
is no residual program underneath: the matrices **are** the computation, the way
a neural network's weights are the computation and not an optimization of it.
The difference from constant propagation / partial evaluation / staging is
**ontological, not quantitative** — TNF collapses the computational model into
linear algebra, so there is no "un-folded" version to fall back to. See
`planning/exploratory/tnf-vs-constant-folding-explanation.md`.

The consequence that matters for verification: **semantically equivalent
programs reduce to the same graph** (modulo trivial differences), so equivalence
checking on the reduced graph is algebra, not a control-flow traversal.

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
  the contract surface of *individual* programs whose TNFs are individually
  tractable. It does not wave away state-space explosion across a whole running
  system. No real system has a closed-form whole-system proof; we do not promise
  one.

## The three reduction pillars (where the obligations come from)

### Pillar 1 — β-reduction to TNF

A Sutra program reduces to a canonical fused tensor-op graph.

- **Obligation (equivalence):** `TNF(p₁) ≡ TNF(p₂)` is decided by algebraic
  normalisation of the two graphs, not by exploring executions.
- **Obligation (contract):** for a program `p` with axon-typed contract `C`,
  show `TNF(p)` reads only `C.read_roles`, writes only `C.write_roles`, and that
  the role-to-role map it computes matches `C`. The static read/write key sets
  the compiler already emits (`AXON_KEYS_READ` / `AXON_KEYS_BOUND`) are the
  starting evidence for the role obligations.

### Pillar 2 — polynomial Kleene logic for branches

What looks like `if/else` in source becomes, after reduction, a **polynomial
that interpolates between branches on a fuzzy truth value**. The Kleene
connectives are Lagrange-interpolated polynomials, **exact on the {−1, 0, +1}
truth grid** and Cᵒᵒ elsewhere — closed-form expressions whose range, sign, and
derivatives are symbolically tractable per branch.

- **Obligation (branch range/sign):** for each reduced branch polynomial, bound
  its range and sign on the truth-axis domain — a closed-form question, not a
  path enumeration.
- **Saturation note:** the same polynomial/transcendental saturation that makes
  branches exact at the grid is what makes the `select` dispatch exact in
  practice — `exp(−k)` underflows to exactly 0 in float32 for modest `k`, so a
  sharpened softmax `select` is a *true* one-hot (off-branches ×0), not a blend.
  Downstream evidence: Yantra's calculator selects its operator this way,
  18/18 bit-exact (`../Yantra/apps/calc/switch.su`).
- **Tooling:** off-the-shelf SMT solvers target Boolean / linear arithmetic;
  discharging these polynomial obligations needs a bespoke checker. Shipping it
  is part of what compiler qualification costs. **Not built.**

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
- **Design:** the Sutra source, whose **TNFs are the designs**.
- **Verification artefacts:** mechanical proofs that the TNFs satisfy the
  contracts; polynomial obligations discharged by the bespoke checker.
- **Trace:** every capability grant and admit/evict in an append-only log.
- **Tooling assurance:** the compiler is in scope for qualification; the
  artefact under review is its **output (the TNF)**, not the source.

## Non-claims (the discipline — keep this section honest)

- Sutra is **not** formally verified today. The architecture is
  verification-friendly; the proofs are an ongoing project, most not started.
- The polynomial-obligation checker **does not exist** yet.
- FV covers the **non-AI trusted base only**, per individual contract, not the
  whole running system and not anything that rides on a learned weight.
- If a later result contradicts anything here, stop and resolve it (fix the
  impl or update this doc) — do not let the paper and this spec drift.

## Cross-references

- `planning/exploratory/tnf-vs-constant-folding-explanation.md` — TNF ontology.
- `planning/sutra-spec/equality-and-defuzzification.md` — truth axis, Kleene,
  defuzzification (the saturation that makes branches/`select` exact).
- `planning/sutra-spec/control-flow.md` — loops and conditionals.
- `paper/paper.md` §3 — the measured substrate empirics cited above.
- Yantra `paper/paper.md` §4 — the downstream OS-level verification surface this
  language-level framework feeds.
