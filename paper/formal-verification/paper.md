# Reducing Control Flow to Tensor Algebra: Verifying the Non-Learned Trusted Base of a Neuro-Symbolic Substrate

---

## Abstract

Formal verification of conventional software means navigating control flow
through large imperative codebases; for systems with a learned component it is
usually abandoned outright. We show that **Sutra**, a typed purely-functional
language, changes the shape of the problem for the non-learned part of a system,
because its compiler turns an entire program — primitives, control flow, string
I/O — into a single fused **tensor-op graph** over a frozen substrate, and that
graph *is* the program's semantics (as a neural network's weights are its
computation), not a residual to be interpreted. The construct that makes
conventional verification expensive — the branch — does not survive into the
graph: `if/else` compiles to a **single three-valued-Kleene polynomial**,
Lagrange-interpolated and exact on the {−1, 0, +1} truth grid, and each loop to a
bounded soft-halt recurrence. Verifying the **trusted base** — kernel roles and
named critical programs — therefore becomes algebra over a small fixed set of
tensor graphs rather than enumeration of control-flow paths.

We make this precise as three per-construct obligation families — contract,
branch-range, termination — and we give **mechanical checks for all three**,
running on the real compile-and-execute substrate: Kleene-gate exactness (worst
error 0.0 across the truth grid), connective range-soundness (a closed-form proof
that outputs lie in [−1, +1] over the whole fuzzy domain), and loop termination
(bounded, monotone halt), plus the kernel-enforced read/write confinement half of
the contract obligation. We further give a **decision procedure for program
equivalence over the Kleene-logic fragment**: a checker extracts each expression's
polynomial via the compiler's own lowering and decides whether two programs
compile to the same tensor graph by the polynomial identity `expand(p₁ − p₂) = 0`,
for arbitrary nesting depth. This separates two notions that are usually
conflated — compiling to the same graph versus being logically equivalent — and
we exhibit distributivity as a clean witness that the former is strictly stronger.

The reduction is meaningful because the substrate computes the compiled graph
exactly, which we establish with measured results restated in full here (§4):
rotation binding decodes bundles at 100% accuracy through width *k* = 8 on four
frozen embedding substrates where the Hadamard baseline has collapsed to 2.5–7.5%,
with a bind/unbind round-trip of 1.5 × 10⁻¹⁵; and a downstream GPU-native OS
(Yantra) runs full arithmetic — operator selection included — bit-exact through
its kernel (18/18 dispatch cases and 1024/1024 symbol round-trips at |err| = 0.0).
The scope is the non-learned trusted base, per published contract; §5 states it
precisely and §6 positions the work against neural-network verification, SMT for
nonlinear arithmetic, partial evaluation, and vector-symbolic architectures.

---

## 1. Introduction

Two facts are usually taken to be in tension. (i) Critical systems want formal
guarantees about their trusted base. (ii) Useful systems increasingly contain
learned components, which resist formal guarantees. The common resolution is to
verify neither — the imperative trusted base is too large to verify cheaply, and
the learned part is given up on, so the whole stack ships on testing alone.

Sutra offers a different decomposition. It is a typed, purely functional language
whose compiler reduces an entire program — primitives, control flow, string I/O —
to a single fused tensor-op graph over a frozen embedding substrate. The claim is
narrow and structural:

> For the **non-learned** trusted base, compiling the program to a tensor-op graph
> turns verification from control-flow path enumeration into algebra over a small
> fixed set of tensor graphs.

This does not make the learned parts safe. It makes them *separable*: the
boundary between "compiles to a checkable tensor graph" and "depends on a learned
weight" is syntactically visible, so the trusted base can be verified while the
learned part is quarantined behind contracts and monitoring.

**Contributions.**
1. **The reduction** (§2): why the compiled tensor-op graph is the program's
   semantics rather than a constant-folded residual or a deep-learning
   computation-graph optimization, and why equivalence on it is algebra.
2. **The obligation framework with mechanical checks** (§3): three per-construct
   obligation families — contract, branch-range, termination — each with a check
   that runs on the substrate. The branch-range family (§3.2), built on
   **three-valued polynomial Kleene logic**, is the one that removes path
   explosion: branches become closed-form polynomials, not forks.
3. **An equivalence decision procedure for the Kleene fragment** (§2): deciding
   same-graph by polynomial identity, distinguished from logical equivalence,
   with distributivity as a witness.
4. **The faithfulness evidence** (§4): measured substrate exactness — including a
   downstream OS computing bit-exactly through its kernel — restated self-
   containedly here.

§5 states the boundary; §6 positions the work in the literature.

## 2. The compiled tensor-op graph

Sutra's compiler emits, for each program, a fused tensor-op graph over a frozen
embedding substrate: compilation produces the weight/rotation structure, and
execution is the forward pass. The graph is the program's semantics in the same
sense that a neural network's weights are its computation — there is no residual
program underneath waiting to be interpreted.

This distinguishes the compiled graph from three neighbours it is easy to confuse
it with. **Against the specialization spectrum** — constant propagation, partial
evaluation / Futamura projections (Futamura 1971), multi-stage programming (Taha
& Sheard 2000) — those transforms remove known subexpressions from a program that
still runs in a conventional operational model; here there is no conventional
model left to run in. **Against symbolic execution** — which enumerates path
conditions through an interpreter and suffers exactly the path explosion we
remove — the compiled graph has no path set to enumerate: a conditional is a
single polynomial, not a branch in an execution tree. **Against deep-learning
graph optimization** (operator fusion, XLA-style rewriting) — those preserve a
graph that already exists; here the graph *is* the program's semantics, produced
by compilation from source, and the verification question is about that
semantics, not about speeding up an existing tensor program.

The verification-relevant consequence: equivalence checking moves onto the
compiled graph as **algebraic comparison**, not a traversal of possible
executions.

**A decision procedure for the Kleene-logic fragment.** For programs built from
the Kleene connectives (`&&`, `||`, `!`, nested to any depth) we decide
equivalence outright. A checker (`fv_obligation_checker.py`) extracts each
expression's polynomial by running the compiler's own inliner pass — not a
hand-copied formula — and walking the lowered arithmetic into a polynomial, then
decides whether two programs **compile to the same graph** by the polynomial
identity `expand(p₁ − p₂) = 0`. This is exact and decidable regardless of nesting
depth (it is polynomial identity testing, evaluated symbolically). The checker
also decides the weaker **logical** equivalence — agreement on the {−1, 0, +1}ⁿ
Kleene grid — and reports both, refusing (rather than guessing) on any term
outside the polynomial fragment, such as a comparison or a runtime intrinsic.

These two notions are not the same, and separating them is a result in its own
right. De Morgan, commutativity, and double negation compile to *identical*
polynomials — same graph. **Distributivity does not:** `a ∧ (b ∨ c)` and
`(a ∧ b) ∨ (a ∧ c)` agree at all 27 grid points (they are logically equivalent)
but compile to *different* polynomials off-grid. So "compiles to the same graph"
is strictly stronger than "logically equivalent"; the graph comparison decides a
well-defined sublattice of logical equivalences, and the checker decides exactly
which side of that line any given pair falls on.

## 3. The obligation framework

Verifying the trusted base concentrates into three closed-form obligation
families, one per Sutra construct that survives into the compiled graph. All three
have a mechanical check that runs on the real compile-and-execute pipeline.

**3.1 Contract obligations.** Each trusted program carries an *axon-typed
contract*. An **axon** is a structured embedding — a single vector carrying named
role→filler slots via rotation binding (the VSA operations of §4) — so a
program's typed interface is "the set of named roles it reads and writes." The
contract names the input roles the program may read, the output roles it may
write, and its status conditions. For program `p` with contract `C`, the
obligation is that `p`'s compiled graph reads only `C.read_roles`, writes only
`C.write_roles`, and that the role-to-role function it computes is the one `C`
specifies. The compiler already emits the static read/write key sets
(`AXON_KEYS_READ`, `AXON_KEYS_BOUND`) that seed the role half of this obligation.

The **read/write confinement** part is **discharged at the kernel** (the
downstream OS): a program can only emit on roles in its `write_roles`
(capability-checked at routing) and is delivered only axons on roles in its
`read_roles`, with no cross-role leakage — mechanically tested (three kernel
tests, including a two-role read-isolation check). The **role-to-role function**
part is **discharged for the Kleene-logic fragment**: when a contract states the
intended function as a reference expression, "does the implementation compute it?"
is exactly `reduces_to_same_graph(implementation, reference)` (§2) — decided
exactly, any depth. (Demonstrated: a NAND contract `!(a&&b)` is satisfied by the
De Morgan implementation `!a||!b` and correctly rejects a NOR implementation.) The
remaining open part is soundness of the static `AXON_KEYS` analysis against the
keys a program touches at runtime, which needs runtime key-usage instrumentation.

**3.2 Branch-range obligations (from polynomial Kleene logic).** This family
carries most of the weight, because branches are what make conventional
verification expensive: each `if/else` doubles the path set, so a trusted base
with *b* branches presents up to 2ᵇ paths. Sutra removes the branch as a
control-flow object. Source `if/else` compiles to a **single polynomial** that
interpolates between the branch values on a fuzzy truth value; the connectives are
the **three-valued Kleene** operators (`and`, `or`, `not`, the t-norms) realised
as **Lagrange-interpolated polynomials exact on the 3×3 Kleene grid** over
{−1 = false, 0 = unknown, +1 = true}, branchless and smooth (hence gradient-
compatible) off the grid.

Two consequences matter. First, **branchlessness collapses the path set**: a
branch is a polynomial whose value the truth-axis scalar determines, so the
obligation is a closed-form bound on that polynomial's range and sign over
[−1, +1] — a polynomial extremum problem, not a path walk. Second, **three-valued
rather than Boolean is the right logic for a substrate that mixes exact symbolic
and uncertain learned signals**: the middle value (unknown) is first-class, so the
verifier reasons about "undetermined" directly, while crisp true/false stays
bit-exact because the interpolation is exact on the grid.

**Grid-exactness is discharged mechanically.** A test compiles the real pipeline —
parse → inline the polynomial → simplify → tensor-op codegen → runtime — and
evaluates `&&`, `||`, `!` at all nine grid points on the substrate, asserting the
Kleene strong-logic table (and = min, or = max, not = negate on the antipodal
encoding). Measured: **worst |error| = 0.0** across the grid. The polynomials
checked are the ones the compiler emits: `a&&b = (a+b+ab−a²−b²+a²b²)/2`,
`a||b = (a+b−ab+a²+b²−a²b²)/2`, `!a = −a`.

**Range-soundness is discharged in closed form.** What soundness requires is that
the connectives never produce an out-of-range truth value anywhere in [−1, +1]².
We prove this with a polynomial range-bounder (`fv_poly_bound.py`) that computes
the exact global extrema of a polynomial over an axis-aligned box by the
compact-domain extremum argument — the extrema lie at stationary points of the
restriction to some face of the box, so the candidate set is the box corners and
the edge-interior and interior gradient-zero points, solved and evaluated in exact
(rational/algebraic) arithmetic. On the three connectives it returns **exact range
[−1, +1]** — a proof, not a sampled min/max. To ensure the bound applies to *what
the compiler emits*, the test first cross-checks the symbolic polynomial against
the substrate on the {−1, 0, +1}² grid (which uniquely determines a
degree-≤2-per-variable polynomial) plus off-grid points (agreement to 6 × 10⁻⁸),
then bounds. (`test_fv_poly_obligation_checker.py`; grid-exactness:
`test_fv_kleene_grid_exactness.py`.)

The same grid saturation makes selection exact: a sufficiently sharpened softmax
`select` is a *true* one-hot, because `exp(−k)` underflows to exactly 0 (in
float32 for modest `k`, far below ulp in float64), so unselected branches are
multiplied by exact zero — the mechanism behind the bit-exact operator dispatch
in §4.3.

**3.3 Termination obligations (from soft-halt loops).** Each loop is a bounded
recurrence `state ← R · state` with a fixed-width state vector and a halt cell.
Termination reduces to "the halt signal is monotone within bounded steps,"
discharged per loop — far smaller than proving an arbitrary `while` terminates.

This is discharged structurally and observably. Structurally the emitted loop is
`for _t in range(max_iters)` (bounded by construction) with
`halted = min(halted + halt, 1)` and `halt = sigmoid(·) ≥ 0` (monotone, capped at
1; on saturation `state = (1−halted)·cand + halted·state` freezes). Observably on
the torch substrate: a non-converging loop runs to the bound and stops
(`iters_active = 9.998/10`, never exceeding `max_iters`); a converging loop is
**exactly frozen** across unroll depth — its state at `T=20` equals its state at
`T=10`, **diff = 0.0**. (`test_fv_termination.py`.)

**Tooling.** Off-the-shelf SMT solvers target Boolean and linear arithmetic, not
the polynomial obligations the compiled graph produces; §6 discusses where
nonlinear solvers such as dReal fit. The per-construct discharges above use
concrete finite methods: grid-exactness is a nine-point evaluation;
range-soundness is a closed-form critical-point bound; termination is structural
plus a saturation observation; equivalence is symbolic polynomial identity.

**Range-soundness scales to arbitrary depth by composition.** The closed-form
critical-point bound gives the exact range of a single connective; the *composed*
polynomial of a deeply nested expression is high-degree and bounding it directly
is expensive. We do not need to: each connective is proven to map [−1, +1]ᵏ into
[−1, +1] (its exact range *is* [−1, +1]), so any expression built solely from the
connectives, over truth-axis inputs in [−1, +1], has range within [−1, +1] **by
induction on the expression tree** — independent of nesting depth and degree. The
check (`range_sound_by_composition`) verifies an expression is such a composition
(refusing if it uses a non-connective operator), and decides range-soundness for
arbitrarily deep nestings instantly. So the equivalence procedure (degree-
insensitive polynomial identity) and range-soundness (degree-insensitive
composition) both scale; the closed-form bounder remains the exact tool for the
per-connective lemma they rest on.

## 4. Faithfulness: the reduction is computed exactly

A reduction to algebra is worth something only if the substrate computes the
compiled graph *exactly*. This is not a circular assumption about an opaque
substrate, and it is worth being precise about why.

**The substrate operations are formally-defined VSA operations with algebraic
laws.** Bind, unbind, and bundle — the primitives the compiled graph is built
from — are vector-symbolic-architecture operations, not ad-hoc tensor code. A
recent category-theoretic foundation defines VSA binding and bundling as right Kan
extensions of the external tensor product, which reduce to the element-wise
operations implementations use (Shaw, Furlong, Anderson & Orchard 2025); the
holographic-reduced-representation algebra (Plate 1995) gives their laws — binding
is **invertible** (`unbind(R, bind(R, x)) = x`) and bundling is a **linear
superposition** whose decodable capacity grows with dimension (Frady, Kleyko &
Sommer 2018; Kleyko, Rachkovskij, Osipov & Rahimi 2023). So the obligations the
verifier discharges are algebra over operations that *have* a formal algebra; what
is left to establish empirically is narrower and non-circular: how exactly a given
**frozen embedding substrate** realises those laws. ("Frozen" = a pretrained
embedding model whose weights are fixed and never updated — e.g. nomic-embed-text
at 768 dimensions; Sutra binds and bundles *in that fixed space* rather than
learning a new one.) The three results below are that realisation — the
invertibility law to machine epsilon, and exact decode within capacity at the
widths the trusted base uses — measured, with protocols restated here so the paper
stands on its own.

**4.1 Bundle decoding.** Protocol: for each bundle width *k*, bind *k* role–filler
pairs by rotation, superpose (bundle) them into one vector, and decode each filler
by unbind + nearest-codebook (argmax-cosine), 10 trials per width. Result:
rotation binding decodes at **100% accuracy through width *k* = 8** on four frozen
substrates spanning two modalities — three text encoders (nomic-embed-text,
all-minilm, mxbai-embed-large) and the ESM-2 protein model — where the textbook
Hadamard (element-wise) binding has already collapsed at *k* = 8 (2.5% on
mxbai-embed-large, 7.5% on all-minilm). The point of *k* = 8 is not a capacity
ceiling — it is the **comparison width at which the standard baseline fails while
rotation binding does not**; capacity itself grows with dimension per the
references above. For verification what matters is narrower: the bundle/bind/unbind
primitives the compiled graph is built from recover their inputs exactly at the
small, fixed widths the trusted base actually uses (a kernel role's axon carries a
handful of named slots, not hundreds).

**4.2 Reversibility.** A single bind+unbind cycle returns the input at the
floating-point noise floor: mean `‖unbind(R, bind(R, x)) − x‖ = 1.5 × 10⁻¹⁵`
across all four substrates — the rotation is invertible to machine epsilon.

**4.3 Exactness through a real trusted base.** A downstream GPU-native OS (Yantra)
runs full arithmetic expressions on the Sutra substrate through its kernel —
operator *selection* included, decided on the substrate by a saturated `select`
(§3.2) rather than a host branch — and recovers results **bit-exact within the
float32 exact-integer range** (18/18 operator-dispatch cases at |err| = 0.0,
including the 2²⁴ boundary), with 1024/1024 distinct symbols round-tripped through
the kernel router at max |err| = 0.0. Within the exact-integer range the
arithmetic is integer-valued and the saturated `select` multiplies off-branches
by *exact* zero, so these are not tolerance-band results: the measured |err| is
0.0 and reproduces across runs on the measured platform. This is the §3.1 contract
property in miniature: the compiled graph computes exactly what the source
denotes, end-to-end through a kernel.

These are existence results for exactness on the substrates and programs measured,
which is what the reduction's premise requires.

## 5. Scope

The reduction buys the *shape* of a certification effort, DO-178C-style: a fixed
image and fixed critical-program set (Plan); axon-typed contracts (Requirements);
Sutra source whose compiled graphs are the designs (Design); mechanical proofs
that the graphs meet contracts plus discharged polynomial obligations
(Verification artefacts); an append-only capability/admission log (Trace); and the
compiler in scope for qualification with its compiled-graph output — not the
source — as the artefact under review (Tooling assurance).

The scope is bounded in three ways. The method covers the **non-learned** trusted
base: anything that invokes an embedding model or depends on a learned weight is
outside it, and gets bounded behaviour, capability discipline, provenance, and
runtime monitoring rather than a proof — the reduction makes the learned parts
*quarantinable*, not *safe*. Equivalence-as-algebra and the obligation checks
apply to the **contract surface of individual programs** whose compiled graphs are
individually tractable, not to a closed-form whole-system proof. And a certified
configuration is per-customer and per-mission; the present contribution is the
framework, the reduction, and the discharged obligations.

## 6. Related work

**Neural-network verification.** A large line verifies properties of *learned*
networks: Reluplex (Katz et al. 2017) and its successor Marabou (Katz et al.
2019) extend SMT to ReLU networks; abstract-interpretation systems such as AI2
(Gehr et al. 2018) and α,β-CROWN (Wang et al. 2021) bound network outputs over
input regions. Our posture is orthogonal and complementary: rather than verify the
learned network, Sutra verifies the **non-learned trusted base** by reduction and
*quarantines* the learned part behind contracts — the two could compose, with
NN-verification bounds feeding the runtime monitors Sutra places at the learned
boundary.

**SMT and nonlinear arithmetic.** The obligations the compiled graph produces are
polynomial, not Boolean or linear, so general-purpose SMT (Z3, de Moura & Bjørner
2008) does not apply directly; solvers for nonlinear real arithmetic such as dReal
(Gao et al. 2013) are the natural backend for the *general* range/equivalence
obligations, while the per-construct obligations here admit the closed-form
critical-point, grid, and polynomial-identity methods of §3.

**Program specialization.** Partial evaluation and the Futamura projections
(Futamura 1971) and multi-stage programming (Taha & Sheard 2000) specialise a
program that still runs in a conventional model; §2 argues the compiled graph is
beyond this spectrum, and beyond symbolic execution and deep-learning graph
optimization.

**Vector-symbolic architectures.** The substrate primitives are VSA/HRR
operations — binding, bundling, cleanup (Plate 1995; Gayler 2003; Kanerva 2009) —
and they have a formal foundation we rely on rather than reinvent: a
category-theoretic account derives binding/bundling as right Kan extensions of the
external tensor product (Shaw, Furlong, Anderson & Orchard 2025), and the capacity
of bundling — how many superposed items decode correctly as a function of
dimension — is characterised in the VSA literature (Frady, Kleyko & Sommer 2018;
Kleyko, Rachkovskij, Osipov & Rahimi 2023). Our use of this is in §4: the
obligations are algebra over operations with formal laws, and the measured result
this work rests on is that *rotation* binding stays exact through bundle widths
where the standard Hadamard binding collapses. The three-valued Kleene polynomial
encoding of branches as a verification lever is, to our knowledge, new.

**Certification.** The plan/requirements/design/verification/trace framing follows
DO-178C, the avionics software-assurance standard, adapted so the artefact under
review is the compiler's tensor-graph output rather than imperative source.

## 7. Conclusion

Compiling the non-learned trusted base to a tensor-op graph turns formal
verification from imperative-path enumeration into algebra over a small fixed set
of tensor graphs, with the load concentrated into three closed-form obligation
families. All three have mechanical checks that run on the substrate —
Kleene-gate exactness (worst error 0.0), connective range-soundness (a closed-form
proof of outputs in [−1, +1]), and loop termination — together with the
kernel-enforced confinement half of the contract obligation, and a decision
procedure for program equivalence over the Kleene-logic fragment that separates
same-graph from logical equivalence. The premise that the compiled graph is
computed exactly is borne out by measured substrate exactness, including a
downstream OS that computes bit-exactly through its kernel. The reduction,
framework, and discharged obligations are the contribution; completing the
contract obligation's function-correctness and key-soundness halves, and extending
the equivalence decision procedure beyond the Kleene fragment, are the road ahead.

---

*Companion spec (obligations stated for implementation):
`planning/sutra-spec/formal-verification.md`. Substrate empirics and protocols:
`paper/paper.md`. Downstream OS verification surface: Yantra `paper/paper.md` §4.*
