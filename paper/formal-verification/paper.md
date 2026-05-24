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
branches are polynomials rather than forks, the path set does not explode — at a
cost we quantify rather than hide: the per-branch polynomial grows in *size* with
branch-nesting depth (§3.4). Verifying the **trusted base** — kernel roles and
named critical programs — reduces from imperative-path enumeration to
**discharging a finite set of closed-form obligations over a small, fixed set of
tensor graphs**, with program equivalence handled by algebraic rewriting of the
reduced graphs (a fixed set of *sound* rewrites — constant-folding, zero-
absorption, CSE — that canonicalises the equivalences it covers, not yet a
complete decision procedure).

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
learned weight. **Three obligation families already have working mechanical
checks** that run on the substrate — Kleene-gate exactness (worst error 0.0
across the truth grid), connective range-soundness (outputs provably in [−1, +1]
over the whole fuzzy domain), and loop termination (bounded + monotone halt) —
plus the kernel-enforced role-isolation half of the contract obligation. The
*general* polynomial-obligation checker that would discharge an arbitrary
obligation is specified but not yet built; what is built is the per-construct
discharge for each family above. The contribution is a verification *framework
and reduction with its first obligations mechanically discharged*, an explicit
account of the costs (§3.4) and the boundary (§5), and the argument that the
reduction is real rather than rhetorical.

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

The verification-relevant consequence: equivalence checking moves onto the
reduced graph as **algebraic rewriting**, not a traversal of possible executions.
Concretely, the compiler's simplifier applies a fixed set of *sound* rewrites —
each an exact algebraic identity or soundness-preserving structural match (no
approximate rewrites): `a − a → 0` and zero-absorption, arithmetic constant
folding (`x + 0 → x`, …), a displacement-addition bundle rewrite, and common-
subexpression elimination. Two programs that differ only by equivalences this
rewrite set captures reduce to the **same** graph, so checking *those*
equivalences is algebra, not path enumeration.

**Honest scope (this answers a fair reviewer objection).** This is *not* a claim
that the simplifier is a complete decision procedure for program equivalence: it
is a confluent rewrite set with *documented non-rewrites* (e.g. it does not
materialise composite rotations), so there exist equivalent programs it does not
collapse to an identical graph. A complete canonical form is future work; what we
claim, and what the rewrite set delivers, is that equivalence checking is *moved
into algebra over the reduced graph* and is exact for the rewrites it implements.
The §3.2/§3.3 obligation discharges below do not depend on full canonicalisation —
they bound and check individual reduced graphs directly.

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

The **read/write confinement** part of this obligation is **discharged at the
kernel** (the downstream OS): a program can only emit on roles in its
`write_roles` (capability-checked at routing) and is delivered only axons on
roles in its `read_roles`, with no cross-role leakage — mechanically tested
(three kernel tests, incl. a two-role read-isolation check). Two parts remain
open and are the harder ones: that the role-to-role *function* matches `C`
(program correctness, not just confinement), and that the static
`AXON_KEYS_READ`/`BOUND` analysis is *sound* against the keys the program
actually touches. "Confinement discharged" is not "contract obligation done."

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

The **off-grid branch-range obligation is also discharged.** Off the grid the
polynomials interpolate (they do not reproduce min/max exactly there — that is
the intended C^∞ behaviour between grid points); what soundness requires is that
they never produce an out-of-range "truth" value. Measured on a dense sweep of
the continuous fuzzy domain [−1, +1]²: the connective outputs stay in
**[−1.000000, +1.000000]** — no over/undershoot anywhere. So the connectives are
valid truth-axis operations across the whole domain, not just at the grid. (Both
checks: `sdk/sutra-compiler/tests/test_fv_kleene_grid_exactness.py`.)

The same grid saturation makes selection exact in practice: a sufficiently
sharpened softmax `select` is a *true* one-hot, because `exp(−k)` underflows to
exactly 0 (float32 for modest `k`; far below ulp in float64), so unselected
branches are multiplied by exact zero rather than a small residue — the mechanism
behind the bit-exact operator dispatch in §4.3.

**3.3 Termination obligations (from soft-halt loops).** Each loop is a bounded
recurrence `state ← R · state` with a fixed-width state vector and a halt cell.
Termination reduces to "the halt signal is monotone within bounded steps,"
discharged per loop — far smaller than proving an arbitrary `while` terminates.

**This obligation is discharged**, structurally and observably. Structurally the
emitted loop is `for _t in range(max_iters)` (bounded by construction, no
unbounded `while`) and `halted = min(halted + halt, 1)` with `halt = sigmoid(·)
≥ 0` (monotone non-decreasing, capped at 1; on saturation `state =
(1−halted)·cand + halted·state` freezes). Observably (torch substrate): a
non-converging loop runs to the bound and stops (`iters_active = 9.998/10`,
never exceeding `max_iters` — bounded, no hang); a converging loop is **exactly
frozen** across unroll depth — its state at `T=20` equals its state at `T=10`,
**diff = 0.0** — so the monotone cumulative halt, once saturated, holds. Check:
`sdk/sutra-compiler/tests/test_fv_termination.py`.

Discharging §3.2 needs a bespoke checker: off-the-shelf SMT solvers target
Boolean and linear arithmetic, not the polynomial obligations TNF produces. The
methodology is *not* "feed it to an SMT solver and hope." For the obligations we
discharge here it is concrete and finite: grid-exactness is a nine-point
evaluation; range-soundness is a bound on a low-degree polynomial over a box,
obtained by checking the finite set of critical points (box corners plus interior
stationary points where the gradient vanishes) — closed-form, not search; loop
termination is structural plus a saturation observation. The *general* checker
that would discharge an arbitrary reduced-graph obligation is the bulk of the
remaining work and is **not built**.

**3.4 The cost: expression size and numerical stability.** Removing the branch as
a control-flow object is not free, and the honest accounting matters. We trade
**path** explosion for **expression-size** growth. Conventional verification
faces up to 2ᵇ paths in the number of branches *b*; the polynomial encoding has
*no* path set, but a conditional whose guard is itself a conditional composes a
degree-2(-per-variable) polynomial into another, so the polynomial *degree* can
grow with branch-**nesting depth** *d* (roughly 2ᵈ without intervention). The two
explosions are in different parameters: *b* (total branch count) versus *d*
(nesting depth), and in practice *d ≪ b* — most branches are shallow — so the
trade is usually favourable, but it is a trade, not a free lunch. There is a real
mitigation native to the substrate: **defuzzification** (`is_true`/`snap`) between
nesting levels polarises a value back toward the {−1, 0, +1} grid, which caps the
degree that propagates into the next level rather than letting it compound; the
cost is then paid in defuzz iterations instead of degree. **Numerical stability:**
we have *measured* exactness for the single connectives (worst error 0.0 on the
grid, range in [−1, +1]) and for full arithmetic through a downstream kernel (§4),
but the float behaviour of *deeply nested, un-defuzzified* high-degree
compositions is **not yet characterised** — quantifying it (and the degree at
which conditioning degrades) is open work, flagged here rather than waved past.

## 4. Faithfulness: the reduction is computed exactly

A reduction to algebra is only worth anything if the substrate computes the
reduced form *exactly*. Three measured results show it does. The protocol and
full tables are in the Sutra language paper; we restate enough here that this
paper stands on its own.

**4.1 Bundle decoding.** Protocol: for each bundle width *k*, bind *k*
role–filler pairs by rotation, superpose (bundle) them into one vector, and
decode each filler by unbind + nearest-codebook (argmax-cosine); accuracy is the
fraction recovered, 10 trials per width. Result: rotation binding decodes at
**100% accuracy through width *k* = 8** on four frozen substrates spanning two
modalities — three text encoders (nomic-embed-text, all-minilm, mxbai-embed-large)
and the ESM-2 protein model — where the textbook Hadamard (element-wise) binding
has already collapsed at *k* = 8 (2.5% on mxbai-embed-large, 7.5% on all-minilm).
The point for verification: the bundle/bind/unbind primitives the TNF is built
from recover their inputs exactly at the widths the trusted base uses.

**4.2 Reversibility.** A single bind+unbind cycle returns the input at the
floating-point noise floor: mean `‖unbind(R, bind(R, x)) − x‖ = 1.5 × 10⁻¹⁵`
across all four substrates — i.e. the rotation is invertible to machine epsilon,
so a reduced graph built from binds/unbinds does not silently lose information.

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
obligation families. This is not only a reduction on paper: **three of the
families already have working, measured mechanical checks** — Kleene-gate
exactness (worst error 0.0), connective range-soundness (outputs in [−1, +1]),
and loop termination — plus the kernel-enforced role-isolation half of the
contract obligation. The premise that the reduced form is computed exactly is
borne out by the measured substrate exactness, including a downstream OS that
computes bit-exactly through its kernel. What remains is the *general* polynomial-
obligation checker (the per-construct discharges exist; the arbitrary-obligation
tool does not), the harder halves of the contract obligation (function
correctness, static-key soundness), and characterising the numerical cost of deep
branch-nesting (§3.4). The contribution is the reduction, the framework, and its
first obligations discharged — with an explicit boundary around the learned parts
the method deliberately does not touch.

---

*Companion spec (obligations stated for implementation):
`planning/sutra-spec/formal-verification.md`. Substrate empirics:
`paper/paper.md`. Downstream OS verification surface: Yantra `paper/paper.md` §4.*
