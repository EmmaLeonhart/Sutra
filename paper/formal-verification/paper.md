# Verifying a Neuro-Symbolic Substrate by Reduction to Tensor Normal Form

---

## Abstract

Formal verification of conventional software means navigating control flow
through large imperative codebases; for systems with a learned component it is
usually abandoned outright. We argue that **Sutra**, a typed purely-functional
language whose compiled forward pass *is* a tensor-op graph, changes the shape of
the problem for the non-learned part of a system. Every Sutra program
β-reduces to a **tensor normal form (TNF)**: one fused tensor-op graph over a
frozen substrate. Crucially, the construct that makes conventional verification
expensive — the branch — disappears: `if/else` reduces to a **single
three-valued-Kleene polynomial**, Lagrange-interpolated and exact on the
{−1, 0, +1} truth grid, and each loop to a bounded soft-halt recurrence. Because
branches are polynomials rather than forks, the path set does not explode; and
because semantically equivalent programs reduce to the same graph, verifying the
**trusted base** — kernel roles and named critical programs — reduces from
imperative-path enumeration to **discharging a finite set of closed-form
obligations over a small, fixed set of tensor graphs.**

We make this precise as three per-construct obligation families (contract /
branch-range / termination), and we ground the claim that the reduced form is
faithfully computable on the empirics already measured for the substrate:
rotation binding decodes bundles at 100% accuracy through width *k* = 8 on four
frozen embedding substrates (where the Hadamard baseline has collapsed to
2.5–7.5%), with a reversibility round-trip of 1.5 × 10⁻¹⁵; and a downstream OS
(Yantra) runs full arithmetic — operator selection included — bit-exact through
its kernel (18/18; 1024/1024 symbol round-trips at max |err| = 0.0). We are
explicit about the boundary: this covers the **non-AI** trusted base, per
published contract, not the whole running system and not anything riding on a
learned weight. The polynomial-obligation checker is specified here, not yet
built. The contribution is a verification *framework and reduction*, and the
argument that the reduction is real rather than rhetorical.

---

## 1. Introduction

Two facts are usually taken to be in tension. (i) Critical systems want formal
guarantees about their trusted base. (ii) Useful systems increasingly contain
learned components, which resist formal guarantees. The common resolution is to
verify neither — the imperative trusted base is too large to verify cheaply, and
the learned part is given up on, so the whole stack ships on testing alone.

Sutra offers a different decomposition. It is a typed, purely functional language
whose compiler β-reduces an entire program — primitives, control flow, string
I/O — to a single fused tensor-op graph over a frozen embedding substrate
(`paper/paper.md`). We call that reduced artefact the program's **tensor normal
form (TNF)**. Our claim is narrow and structural:

> For the **non-learned** trusted base, reduction to TNF turns verification from
> control-flow path enumeration into algebra over a small fixed set of tensor
> graphs.

This does not make the learned parts safe. It makes them *separable*: the
boundary between "reduces to a checkable tensor graph" and "depends on a learned
weight" is syntactically visible, so the trusted base can be verified while the
learned part is quarantined behind contracts and monitoring.

**Contributions.**
1. **The reduction** (§2): why TNF is a normal form and not constant folding,
   and why equivalence on the reduced graph is algebra.
2. **The obligation framework** (§3): three per-construct obligation families —
   contract, branch-range, termination — that a checker would discharge. The
   branch-range family (§3.2), built on **three-valued polynomial Kleene logic**,
   is the one that removes path explosion: branches become closed-form
   polynomials, not forks, so the cost of conditionals stops being exponential.
3. **The faithfulness evidence** (§4): the measured substrate exactness that
   makes the reduction meaningful rather than rhetorical, including a downstream
   OS computing bit-exactly through its kernel.
4. **The boundary** (§5): a precise statement of what is *not* covered, in the
   DO-178C-shaped framing of a real certification effort.

We claim a framework and a reduction, not a certified system. §5 is as load-
bearing as §2.

## 2. Tensor normal form as a normal form

A TNF is not a constant-folded version of an otherwise-conventional program.
There is no residual program underneath it. In a neural network the weights are
matrices and the forward pass is chained matmuls; nobody calls that an
optimization of some more primitive program, because the matrices *are* the
computation. Sutra does the same for arbitrary programs: compilation produces the
weight/rotation structure, and execution is the forward pass.

The distinction from the classical specialization spectrum — constant
propagation, partial evaluation (Futamura projections), staging — is
**ontological, not quantitative**. Those transforms remove known subexpressions
from a program that still runs in a conventional model; TNF collapses the model
itself into linear algebra, leaving nothing un-folded to fall back on.

The verification-relevant consequence: **semantically equivalent programs reduce
to the same graph** (modulo trivial differences). Equivalence checking on the
reduced graph is therefore algebraic normalisation, not a traversal of possible
executions — the single move that converts the verification problem.

## 3. The obligation framework

Reduction concentrates all verification load into three closed-form families,
one per Sutra construct that survives into the TNF.

**3.1 Contract obligations (from β-reduction).** Each trusted program carries an
axon-typed contract: the input roles it may read, the output roles it may write,
and its status conditions. For program `p` with contract `C`, the obligation is
that `TNF(p)` reads only `C.read_roles`, writes only `C.write_roles`, and that
the role-to-role function it computes is the one `C` specifies. The compiler
already emits the static read/write key sets (`AXON_KEYS_READ`,
`AXON_KEYS_BOUND`) that seed the role half of this obligation.

**3.2 Branch-range obligations (from polynomial Kleene logic).** This family
carries most of the weight, because branches are what make conventional
verification expensive: each `if/else` doubles the path set, so a trusted base
with *b* branches presents up to 2ᵇ paths — the state-space explosion that
imperative verification has to fight. Sutra removes the branch as a control-flow
object. Source `if/else` reduces to a **single polynomial** that interpolates
between the branch values on a fuzzy truth value; the connectives are the
**three-valued Kleene** operators (`and`, `or`, `not`, the t-norms) realised as
**Lagrange-interpolated polynomials exact on the 3×3 Kleene grid** over
{−1 = false, 0 = unknown, +1 = true}, branchless and smooth (hence gradient-
compatible) off the grid.

Two consequences matter for verification. First, **branchlessness collapses the
path set**: a branch is no longer a fork to enumerate but a polynomial whose
value the truth-axis scalar determines, so the obligation is a closed-form bound
on that polynomial's range and sign over [−1, +1] — a polynomial extremum/root
problem, not a path walk. Second, **three-valued rather than Boolean is the right
logic for a substrate that mixes exact symbolic and uncertain learned signals**:
the middle value (unknown) is first-class, so the verifier reasons about
"undetermined" directly instead of forcing a premature Boolean collapse, while
the crisp true/false cases stay bit-exact because the interpolation is exact on
the grid. A finite nine-point check (the polynomial reproduces the Kleene table
at {−1, 0, +1}²) anchors the smooth form to the discrete logic it stands in for.

**This grid-exactness obligation is now discharged mechanically** (the first FV
obligation to move from stated to checked). A test compiles the real pipeline —
parse → inline the polynomial → simplify → tensor-op codegen → runtime — and
evaluates `&&`, `||`, `!` at all nine grid points on the substrate, asserting
the Kleene strong-logic table (and = min, or = max, not = negate on the
antipodal encoding). Measured: **worst |error| = 0.0** across the grid — exact,
not approximate. The polynomials checked are the ones the compiler emits:
`a&&b = (a+b+ab−a²−b²+a²b²)/2`, `a||b = (a+b−ab+a²+b²−a²b²)/2`, `!a = −a`.

The same grid saturation makes selection exact in practice: a sufficiently
sharpened softmax `select` is a *true* one-hot, because `exp(−k)` underflows to
exactly 0 (float32 for modest `k`; far below ulp in float64), so unselected
branches are multiplied by exact zero rather than a small residue — the mechanism
behind the bit-exact operator dispatch in §4.3.

**3.3 Termination obligations (from soft-halt loops).** Each loop is a bounded
recurrence `state ← R · state` with a fixed-width state vector and a halt cell.
Termination reduces to "the halt signal is monotone within bounded steps,"
discharged per loop — far smaller than proving an arbitrary `while` terminates.

Discharging §3.2 needs a bespoke checker: off-the-shelf SMT solvers target
Boolean and linear arithmetic, not the polynomial obligations TNF produces.
Building and qualifying that checker is the bulk of the remaining work and is
**not done**.

## 4. Faithfulness: the reduction is computed exactly

A reduction to algebra is only worth anything if the substrate computes the
reduced form *exactly*. Three measured results show it does.

**4.1 Bundle decoding.** Rotation binding decodes bundles at **100% accuracy
through width *k* = 8** on four frozen substrates spanning two modalities (three
text encoders — nomic-embed-text, all-minilm, mxbai-embed-large — and the ESM-2
protein model), where the textbook Hadamard product has already collapsed
(2.5% on mxbai-embed-large, 7.5% on all-minilm) (`paper/paper.md` §3.2).

**4.2 Reversibility.** The rotation round-trip is at the floating-point noise
floor: mean `‖unbind(R, bind(R, x)) − x‖ = 1.5 × 10⁻¹⁵` across all four
substrates.

**4.3 Exactness through a real trusted base.** A downstream GPU-native OS
(Yantra) runs full arithmetic expressions on the Sutra substrate through its
kernel — operator *selection* included, decided on the substrate by a saturated
`select` (§3.2) rather than a host branch — and recovers results **bit-exact
within the float32 exact-integer range** (18/18 operator-dispatch cases at
|err| = 0.0, including the 2²⁴ boundary), with 1024/1024 distinct symbols round-
tripped through the kernel router at max |err| = 0.0. This is the §3.1 contract
property in miniature: the reduced graph computes exactly what the source
denotes, end-to-end through a kernel.

These are existence results for exactness, not a proof that every TNF is exact;
they establish that the reduction's premise holds on the substrates and programs
measured.

## 5. What this does and does not buy — the boundary

The reduction buys the *shape* of a certification effort, DO-178C-style: a fixed
image and fixed critical-program set (Plan); axon-typed contracts (Requirements);
Sutra source whose TNFs are the designs (Design); mechanical proofs that TNFs
meet contracts plus discharged polynomial obligations (Verification artefacts);
an append-only capability/admission log (Trace); and the compiler in scope for
qualification with its TNF output — not the source — as the artefact under review
(Tooling assurance).

It does **not** buy the following, and saying so is part of the method:

- **No whole-system proof.** Equivalence-as-algebra applies to the contract
  surface of *individual* programs whose TNFs are individually tractable. It does
  not dissolve state-space explosion across a running system; no real system has
  a closed-form whole-system proof and we claim none.
- **No verification of the learned parts.** Anything that invokes an embedding
  model or depends on a learned weight is outside the trusted base. It gets
  bounded behaviour, capability discipline, provenance, and runtime monitoring.
  The reduction makes the learned parts *quarantinable*, not *safe*.
- **No certified artefact today.** The architecture is verification-friendly;
  the proofs are an ongoing project and the polynomial-obligation checker is not
  built. A certified configuration would be per-customer, per-mission.

## 6. Related work

TNF sits beyond the classical specialization spectrum (§2): constant propagation,
partial evaluation / Futamura projections, and staging all leave a residual
program in a conventional model, whereas TNF collapses the model into linear
algebra. The certification framing follows DO-178C's plan/requirements/design/
verification/trace structure. The substrate primitives are vector-symbolic
architectures (binding, bundling, cleanup); Sutra's contribution there, on which
this work rests, is that rotation binding remains exact through bundle widths
where the standard Hadamard binding has collapsed (`paper/paper.md`).

## 7. Conclusion

Reducing the non-learned trusted base to a tensor normal form changes formal
verification from imperative-path enumeration into algebra over a small fixed set
of tensor graphs, with the verification load concentrated into three closed-form
obligation families. The premise — that the reduced form is computed exactly —
is borne out by the measured substrate exactness, including a downstream OS that
computes bit-exactly through its kernel. The work that remains is the bespoke
polynomial-obligation checker and the per-program discharge; the contribution
here is the reduction and the framework, with an explicit boundary around the
learned parts the method deliberately does not touch.

---

*Companion spec (obligations stated for implementation):
`planning/sutra-spec/formal-verification.md`. Substrate empirics:
`paper/paper.md`. Downstream OS verification surface: Yantra `paper/paper.md` §4.*
