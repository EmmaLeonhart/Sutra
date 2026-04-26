# Prior art — VSA Turing completeness via Cartesian closedness

**Date opened:** 2026-04-25.
**Status:** Reference list. Captures the citations from
`chats/vsa-cartesian-closedness.md` so they're in a normal repo
location before that chat is deleted. Should be folded into a
formal prior-art audit if/when the Sutra paper needs to argue its
own Turing-completeness story.

## Why this exists

The argument that Sutra (and VSA more broadly) can express
Turing-complete computation has been made via different routes in
the recent literature. None of these papers are cited in the
current `planning/sutra-spec/` or in any active paper draft, but
the ones below are the most recent and direct treatments. They
sit in deprecated spec under
`planning/sutra-spec-deprecated/{09-lambda-calculus.md,10-turing-completeness.md}`
plus the chat that produced this doc.

## Core papers

### Flanagan et al. 2024 — "Hey Pentti, We Did It!: A Fully Vector-Symbolic Lisp"

- **Venue:** Society for Mathematical Psychology / ICCM 2024.
- **Extended preprint:** arXiv:2510.17889 (October 2025).
- **What it does:** Encodes the five Lisp 1.5 elementary functions,
  lambda expressions, and auxiliary functions as a VSA program.
  Argues that demonstrating a VSA encoding of Lisp is equivalent to
  showing VSAs are **Cartesian closed**, which by Curry–Howard–Lambek
  makes them equivalent to Turing-complete recursively enumerable
  languages. Reference implementation uses Holographic Reduced
  Representations (HRRs).
- **Honest gap:** The Cartesian closedness claim is invoked
  programmatically (cites nLab) rather than derived from VSA axioms.
  Encoding relies on a cleanup memory whose status as "part of the
  algebra" vs "external oracle" is left ambiguous. Strict
  Turing-completeness needs unbounded computation; VSAs operate in
  fixed-dimensional spaces. Closer to a strong constructive
  demonstration with categorical framing than a rigorous mechanical
  proof.

### Flanagan et al. 2025 — "Hey Pentti, We Did (More of) It!"

- **arXiv:2511.08767** (November 2025).
- **What it does:** Extends the VSA Lisp interpreter with residue
  arithmetic via Frequency-domain HRRs (FHRRs) and Residue
  Hyperdimensional Computing (RHC), adding integer-arithmetic
  primitives. Treats the Cartesian-closedness result from the prior
  paper as established and builds on it.

### Companion category-theory paper

- **arXiv:2501.05368** (January 2025) — "Developing a Foundation of
  Vector Symbolic Architectures Using Category Theory."
- **What it does:** Notes that the intersection of VSAs and category
  theory was almost entirely unexplored as of early 2025 (a literature
  search yielded only twelve results). Proposes generalizing from
  vectors to **co-presheaves** and describes VSA operations as right
  Kan extensions of the external tensor product.

### Kleyko et al. IEEE survey

- The older IEEE survey of VSAs as a computing framework. Demonstrates
  universality by encoding systems known to be Turing-complete inside
  a VSA. Highlights "computing in superposition" as the distinguishing
  feature that sets VSAs apart from conventional computing. Pre-dates
  the categorical framing — universality is sketched via Turing-machine
  simulation rather than via CCC structure.

### Smolensky 1990 — Tensor Product Representations

- The foundational treatment of variable binding in a vector /
  connectionist setting. §3.1 (unbinding) and §3.7.2 (LISP binary-tree
  operations as linear maps on the tensor product space) are the
  parts directly relevant to VSA lambda calculus / beta reduction.
  Smolensky uses tensor products rather than circular convolution; the
  theoretical foundation for variable binding lives here.

### Lambek & Scott 1986 — *Introduction to Higher-Order Categorical Logic*

- Foundational reference for the **Curry–Howard–Lambek** correspondence
  (typed lambda calculus ↔ Cartesian closed categories ↔ intuitionistic
  logic). Cited by Flanagan et al. but not derived from there. The
  primary mathematical reference if a Sutra paper needs to ground
  its Turing-completeness story in CCC semantics rather than via
  Turing-machine simulation.

### Kolmogorov–Arnold representation theorem (KART)

- Hilbert's 13th-problem result, formalized by Arnold and Kolmogorov:
  any continuous bounded multivariate function can be expressed as a
  finite composition of univariate functions, composed via addition.
  No multivariate function is truly "irreducible."
- **Liu & Tegmark 2024** (KAN — Kolmogorov-Arnold Networks) brought
  the theorem back into ML practice by replacing fixed activation
  functions on nodes with learnable spline-parameterized activation
  functions on edges. The KAN paper sidesteps KART's worst-case
  pathology — that the inner univariates can be non-smooth or fractal
   — by restricting the family to splines.
- **Why this is in the Sutra prior-art audit:** KART is the theoretical
  justification for Sutra's "compile every continuous math function to a
  tensor op" strategy. The decomposition into univariates is what makes
  the compilation strategy uniform: log, sqrt, sin, exp are all in KART
  normal form trivially (they're already univariate), and any continuous
  function is reachable in principle. The compiler picks an
  approximation tier (Chebyshev polynomial / lookup table / CORDIC) and
  emits the tensor op; the precision contract from `atman.toml`'s
  `[math]` section sets the polynomial degree or table resolution.
  See `docs/numeric-math.md` § "Transcendental functions" and
  `todo.md` § "Compile-time math function approximation."

## How beta reduction features in this story

In the categorical reading, beta reduction corresponds to
composition of morphisms via the evaluation map
`eval: (A ⇒ B) × A → B` in a Cartesian closed category. A VSA
realizes this structure to the extent that bind / bundle / unbind
faithfully implement those morphisms — but **unbinding in a VSA is
approximate** (recovers a vector close to the original, not equal),
so what you actually get is a "fuzzy CCC" where the triangle
identities hold only up to ε. The cleanup memory projects each
intermediate result back onto a discrete codeword, which keeps
errors from accumulating across iterated beta reductions.

So the VSA / lambda-calculus isomorphism is real at the level of
representational structure but breaks at operational semantics
unless cleanup is counted as part of the algebra. Beta reduction
is the operation where this gap shows up most clearly — not the
*limiting factor*, but the place the approximation cost is
visible.

## What this is not

This is a **citation list**, not a Sutra design doc. The
Sutra-specific Turing-completeness argument hasn't been formally
written down anywhere in the current spec, and these references
shouldn't be treated as Sutra's claim — they're just the relevant
prior art the Sutra story would need to reckon with if/when that
formalization happens.
