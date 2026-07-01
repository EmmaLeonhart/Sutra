# Verifying Sutra as an Execution Environment on a Probabilistic Substrate: Per-Contract Convergence and Closed-Form Obligations for a Compiled Functional Language

---

## Abstract

We verify **Sutra** — a typed, purely functional language — as a fixed
**execution environment**: an instruction-set architecture whose *non-learned*
trusted base (kernel roles and named critical programs, behaviour fixed at compile
time) runs on a substrate that is, on its second compile target, genuinely
**probabilistic** — a sampler that *settles into* the answer rather than computing
it deterministically. The claim is narrow and per-contract; we do not claim to
verify a learned component or a whole running system. The substrate being
probabilistic, the load-bearing question is **convergence** — does the language,
*as it runs*, reach the answer? — and that is the spine of this paper.

Two convergence results carry it. (i) On the deterministic tensor-op target, each
loop's linear core `state ← R · state` is a discrete-time system whose
**Z-transform poles** decide convergence; measured on the real emitted rotation
(dim 868), all poles lie on the unit circle (spectral radius 1.00000000, `R`
orthogonal), so the core is marginally stable and termination is discharged by the
soft-halt gate, not by spectral decay. (ii) On the second, **energy-based** target,
the per-gadget obligation becomes a finite **ground-state** question; we give
Lean-machine-checked proofs that the gadgets' correct outputs are the strict global
energy minima and that the single-gadget Gibbs sampler converges to its unique
stationary measure (ergodicity, reversibility, stationarity, uniqueness, and the
two-state mixing rate, all mechanised), and we **measure** the continuous-time,
multi-state convergence on the machine-checked AND-gadget energy: the master-ODE
generator's Gibbs measure is stationary and reversible, the full eight-state chain
has a positive spectral gap (`γ = 0.0397` at `β = 1`), and the law's
total-variation decay matches that gap (ratio 1.0000). For the general
multi-state case we additionally **machine-check the structural chain** — for any
finite reversible kernel, the transition operator is self-adjoint in the
$\pi$-weighted inner product (`applyP_selfAdjoint`), a scalar Dirichlet/Rayleigh
gap implies a one-step $L^2(\pi)$ contraction (`applyP_gap_contraction`, the
numerical-radius = operator-norm step, via polarization + Cauchy–Schwarz, no
spectral theorem), and that contraction implies geometric $L^2(\pi)$ decay
(`geometric_convergence`), all `sorry`-free — so that what remains a *measurement*,
explicitly not a Lean proof, is narrowed to the multi-state gap **value**
(`γ = 0.0397`) for the concrete kernel and the continuous-time/continuous-space
limits, not the gap⇒convergence implication itself.

The supporting machinery is a reduction: Sutra's compiler turns an entire program
(primitives, control flow, string I/O) into a single fused **tensor-op graph**,
and that graph *is* the program's semantics, as a neural network's weights are its
computation. The branch, the construct that makes conventional verification
expensive, does not survive into the graph — `if/else` compiles to a **single
three-valued-Kleene polynomial** exact on the {−1, 0, +1} grid — so verifying the
trusted base becomes algebra over a small fixed set of graphs rather than
control-flow path enumeration (§§2–3). We discharge three per-construct obligation
families (contract, branch-range, termination) with mechanical checks on the real
substrate, and give a **decision procedure for program equivalence** over the
Kleene-plus-integer-arithmetic fragment (polynomial identity, exact or poly-time
Schwartz–Zippel; §2). Substrate faithfulness is measured (§4): rotation binding
decodes bundles at 100% through width *k* = 8 (≥99% through *k* = 32 on the 768-d
substrate) where the Hadamard baseline collapses to 2.5–7.5%, round-trip
1.5 × 10⁻¹⁵. The compiled integer-arithmetic dispatch runs exactly within the
IEEE-754 exact-integer range — **classical bit-exactness on the *deterministic*
target, a supporting precision measurement, not the paper's claim** (§4.3). The
substrate's own exactness notion is different and is *not* a deterministic bypass:
it is **p-bit-exactness** — on the probabilistic target the sampler settles into a
stationary distribution concentrated on the strict-minimizer ground state, so the
exact answer *is* the unique minimum the dynamics reach. Exactness and convergence
are then one claim on one spine (§7): the gadget ground states are the strict
minimizers (Lean-proven) and the reversible sampler converges to the measure on
them. §5 states the scope
(non-learned trusted base only), §6 positions the work, and §8 is a brief note on a
separate, weaker empirical layer — a compile-and-run-against-ground-truth suite for
the source-language frontends — explicitly not conflated with the formal results.

---

## Background

Sutra is a typed, purely functional programming language whose compiler lowers an
entire program to a single fused tensor-op graph over a frozen embedding substrate.
There is no bytecode or interpreter beneath the graph: compilation produces a
weight-and-rotation structure, and running the program is the forward pass through
it, in the same sense that a trained neural network's weights are its computation.
The substrate is a high-dimensional vector space supplied by a frozen pretrained
embedding model (nomic-embed-text by default), extended with a small block of
synthetic axes that carry the real and imaginary parts of numbers, a truth
coordinate, and string-encoding flags.

The primitives the graph is built from come from Vector Symbolic Architectures, also
called hyperdimensional computing: binding composes a role with a filler, bundling
superposes several vectors into one, and cleanup decodes a noisy superposition back
to its nearest stored item (Plate 1995; Gayler 2003; Kanerva 2009). Sutra uses these
as its data-structuring layer: a record is a bundle of role-filler bindings, a string
is a synthetic-axis-encoded array of codepoints, and a number lives on the synthetic
number axis. Control flow is expressed without host branching: a conditional becomes a
polynomial blend over a three-valued truth grid, and a loop becomes a bounded
soft-halt recurrence.

A system built on this substrate has two parts with different epistemic status. The
frozen embedding model is a learned, opaque component; its internal semantics are not
verified, only its interface. Everything the compiler emits above it, the program's
control flow, arithmetic, string handling, and role structure, is non-learned: a fixed
tensor graph determined entirely by the source. This paper concerns the verification
of that non-learned trusted base, and the contracts that quarantine the learned
component behind it. The reader needs no familiarity with the embedding model's
training; the claims are about the compiled graph, which is the same object whether the
substrate is nomic-embed-text or another frozen model of the same dimension.

---

## 1. Introduction

Two facts are usually taken to be in tension. (i) Critical systems want formal
guarantees about their trusted base. (ii) Useful systems increasingly contain
learned components, which resist formal guarantees. The common resolution is to
verify neither: the imperative trusted base is too large to verify cheaply, and
the learned part is given up on, so the whole stack ships on testing alone.

Sutra offers a different decomposition. It is a typed, purely functional language
whose compiler reduces an entire program (primitives, control flow, string I/O)
to a single fused tensor-op graph over a frozen embedding substrate. The claim is
narrow and structural:

> For the **non-learned** trusted base, compiling the program to a tensor-op graph
> turns verification from control-flow path enumeration into algebra over a small
> fixed set of tensor graphs.

This does not make the learned parts safe. It makes them *separable*: the
boundary between "compiles to a checkable tensor graph" and "depends on a learned
weight" is syntactically visible, so the trusted base can be verified while the
learned part is quarantined behind contracts and monitoring.

**Contributions.** The spine is convergence — verifying the language *as it runs*,
on a substrate whose second target is probabilistic; the reduction and the
closed-form obligations are the supporting machinery that makes that question
tractable.

1. **Convergence — the spine** (§3.3, §7): the two pieces that verify the language
   *as it runs*, not just as an algebraic object. The loop's linear core
   `state ← R · state` is a discrete-time system whose **Z-transform poles** decide
   convergence (measured: the emitted rotation is marginally stable, so termination
   is the halt gate's job, not spectral decay); and the energy-based target's
   sampler is a continuous-time Markov jump process whose **master-equation
   spectral gap** decides convergence (the discrete-time chain's ergodicity,
   stationary measure, uniqueness and two-state rate are **Lean-machine-checked**;
   the full multi-state gap and the continuous-time decay are **measured, not
   Lean-proved** — the gadget chain has a positive gap and the law decays at exactly
   that rate). These are the stochastic-ODE / Z-transform tools the probabilistic
   substrate calls for.
2. **The reduction** (§2, supporting): why the compiled tensor-op graph is the
   program's semantics rather than a constant-folded residual or a deep-learning
   computation-graph optimization, and why equivalence on it is algebra — the move
   that turns the trusted base into a small fixed set of checkable graphs.
3. **The obligation framework with mechanical checks** (§3, supporting): three
   per-construct obligation families (contract, branch-range, termination), each
   with a check that runs on the substrate. The branch-range family (§3.2), built on
   **three-valued polynomial Kleene logic**, removes path explosion: branches become
   closed-form polynomials, not forks.
4. **An equivalence decision procedure for the Kleene fragment** (§2, supporting):
   deciding same-graph by polynomial identity, distinguished from logical
   equivalence, with distributivity as a witness.
5. **The faithfulness evidence** (§4, supporting): measured substrate results —
   rotation-binding capacity and reversibility — with exact integer-arithmetic
   dispatch as a supporting precision measurement (it is bought by routing *around*
   the probabilistic codebook, so it is not the paper's claim), restated
   self-containedly here.

The framing is narrow: this verifies Sutra as a fixed **execution environment** —
kernel roles and named critical programs — running on a substrate that is, on its
second target, genuinely **probabilistic**, and per-contract, not as a whole-system
or learned-component proof. §§2–6 develop the supporting reduction and obligation
framework on the deterministic tensor-op target; **§7** is where the spine takes its
cleanest form, on the energy-based probabilistic target, where the obligation
becomes a ground-state question and the sampler's convergence is machine-checked
(discrete) and measured (continuous-time, multi-state). §5 states the boundary; §6
positions the work in the literature; **§8** is a deliberately *weaker* empirical
(compile-and-run) check of the source-language frontends, explicitly not conflated
with the formal guarantees above.

## 2. The compiled tensor-op graph (supporting machinery)

*§§2–6 are the supporting machinery: the reduction and the closed-form obligations
that make the convergence question of §3.3 and §7 tractable. They are developed on
the deterministic tensor-op target; the spine — convergence on the probabilistic
substrate — is §7.*

Sutra's compiler emits, for each program, a fused tensor-op graph over a frozen
embedding substrate: compilation produces the weight/rotation structure, and
execution is the forward pass. The graph is the program's semantics in the same
sense that a neural network's weights are its computation: there is no residual
program underneath waiting to be interpreted.

This distinguishes the compiled graph from three neighbours it is easy to confuse
it with. **Against the specialization spectrum**: constant propagation, partial
evaluation / Futamura projections (Futamura 1971) and multi-stage programming
(Taha & Sheard 2000) remove known subexpressions from a program that still runs
in a conventional operational model; here there is no conventional model left to
run in. **Against symbolic execution**, which enumerates path
conditions through an interpreter and suffers exactly the path explosion we
remove, the compiled graph has no path set to enumerate: a conditional is a
single polynomial, not a branch in an execution tree. **Against deep-learning
graph optimization** (operator fusion, XLA-style rewriting), those preserve a
graph that already exists; here the graph *is* the program's semantics, produced
by compilation from source, and the verification question is about that
semantics, not about speeding up an existing tensor program.

The verification-relevant consequence: equivalence checking moves onto the
compiled graph as **algebraic comparison**, not a traversal of possible
executions.

**A decision procedure for the polynomial fragment, Kleene logic *and* integer
arithmetic.** The fragment is not limited to the Boolean connectives. For programs built
from the Kleene connectives (`&&`, `||`, `!`) *and* integer arithmetic (`+`, `-`, `*`),
nested to any depth and freely mixed, we decide equivalence outright. A checker
(`fv_obligation_checker.py`) extracts each expression's polynomial by running the
compiler's own inliner pass, not a hand-copied formula, and walking the lowered
arithmetic into a polynomial, then decides whether two programs **compile to the same
graph** by polynomial identity. Two routes decide the *same* notion: an *exact* symbolic
check `expand(p₁ − p₂) = 0`, and a *poly-time* randomized check (Schwartz–Zippel over a
finite field) that scales to deep nestings the exact route cannot reach, §3 quantifies
both and the trade-off. The checker also decides the weaker **logical** equivalence,
agreement on the {−1, 0, +1}ⁿ Kleene grid, and reports both, refusing (rather than
guessing) on any term outside the polynomial fragment, such as a comparison or a runtime
intrinsic.

These two notions are not the same, and separating them is a result in its own
right. De Morgan, commutativity, and double negation compile to *identical*
polynomials, same graph. **Distributivity does not:** `a ∧ (b ∨ c)` and
`(a ∧ b) ∨ (a ∧ c)` agree at all 27 grid points (they are logically equivalent)
but compile to *different* polynomials off-grid. So "compiles to the same graph"
is strictly stronger than "logically equivalent"; the graph comparison decides a
well-defined sublattice of logical equivalences, and the checker decides exactly
which side of that line any given pair falls on. The *arithmetic* side of the fragment
sharpens the picture: arithmetic distributivity `(a + b)·c = a·c + b·c` **is** a
same-graph identity (the two compile to the *same* polynomial), the exact mirror image
of Kleene distributivity, which is not. The same checker decides both, Boolean and
integer-arithmetic equivalence, by the one polynomial-identity test. This has a direct
use beyond the trusted base's own logic: **verifying that a compiler optimization
preserves semantics.** Horner's method `a·x³ + b·x² + c·x + d` and `((a·x + b)·x + c)·x + d`
compile to the *same* graph (the rewrite is sound); constant folding and reassociation
likewise; and an incorrect rewrite, a sign flip `a·x² + b·x + c` vs `a·x² − b·x + c`, is
caught as a *different* graph. The decision procedure is the same; only the inputs change.

## 3. The obligation framework

Verifying the trusted base concentrates into a small set of closed-form
obligation families, one per Sutra construct that survives into the compiled
graph: contracts (§3.1), branches (§3.2), loops (§3.3), and, once the base does
arithmetic the substrate's native float range cannot hold exactly,
digit-array carry propagation (§3.4). Each has a mechanical check that runs on
the real compile-and-execute pipeline.

**3.1 Contract obligations.** Each trusted program carries an *axon-typed
contract*. An **axon** is a structured embedding, a single vector carrying named
role→filler slots via rotation binding (the VSA operations of §4), so a
program's typed interface is "the set of named roles it reads and writes." The
contract names the input roles the program may read, the output roles it may
write, and its status conditions. For program `p` with contract `C`, the
obligation is that `p`'s compiled graph reads only `C.read_roles`, writes only
`C.write_roles`, and that the role-to-role function it computes is the one `C`
specifies. The compiler already emits the static read/write key sets
(`AXON_KEYS_READ`, `AXON_KEYS_BOUND`) that seed the role half of this obligation.

The **read/write confinement** part is **discharged at the runtime kernel**,
the capability-checked axon router that enforces Sutra's role model: a program
can only emit on roles in its `write_roles`
(capability-checked at routing) and is delivered only axons on roles in its
`read_roles`, with no cross-role leakage, mechanically tested (three kernel
tests, including a two-role read-isolation check). The **role-to-role function**
part is **discharged for the Kleene-logic fragment**: when a contract states the
intended function as a reference expression, "does the implementation compute it?"
is exactly `reduces_to_same_graph(implementation, reference)` (§2), decided
exactly, any depth. (Demonstrated: a NAND contract `!(a&&b)` is satisfied by the
De Morgan implementation `!a||!b` and correctly rejects a NOR implementation.) The
**key-soundness** part, that the static `AXON_KEYS` analysis matches the keys a
program touches at runtime, is **discharged by opt-in runtime key-usage
instrumentation**: the runtime's axon read/bind methods record, when enabled, the
key of each access (a string by name; a non-string, statically-unnamable key as
`<dynamic>`), and soundness is the set inclusion `runtime_keys ⊆ AXON_KEYS`. The
check is non-vacuous: a program touching only its statically-collected keys is
sound, while a read or bind of an uncollected key, or any `<dynamic>` key, is
caught. (The instrumentation is off by default, so it adds nothing to the
compiled hot path; it is a monitoring recorder around the substrate ops. The
check witnesses the executed paths; a path-coverage argument or a key-level
manifest would make it exhaustive rather than execution-witnessed.) With role
confinement (kernel), function-correctness (Kleene fragment), and key-soundness
all in hand, the contract obligation of §3.1 is discharged rather than half-done.

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
[−1, +1], a polynomial extremum problem, not a path walk. Second, **three-valued
rather than Boolean is the right logic for a substrate that mixes exact symbolic
and uncertain learned signals**: the middle value (unknown) is first-class, so the
verifier reasons about "undetermined" directly, while crisp true/false stays
bit-exact because the interpolation is exact on the grid.

**Grid-exactness is discharged mechanically, as a codegen-correspondence
check, not a math-discovery claim.** A degree-≤2-per-variable polynomial
interpolated through the nine {−1, 0, +1}² grid points hits those nine points
exactly by construction; that piece is Lagrange interpolation, not a result.
What the check verifies is something distinct and load-bearing: that the
polynomial the *compiler actually emits* at the end of `parse → inline →
simplify → tensor-op codegen → runtime` agrees with the spec polynomial on the
grid. A typo or rewrite-pass bug in the codegen, a stray sign, a missing
`a²b²` term, a constant folded the wrong way, would show up as a non-zero
grid error even though Lagrange interpolation as a method is untouched. So
"worst |error| = 0.0 across the grid" is a regression guard against codegen
drift, asserting that the chain ending at the substrate's tensor ops still
produces the spec connectives. Measured value reported as the empirical
discharge of the check, not as a mathematical discovery. The polynomials
checked are the ones the compiler emits: `a&&b = (a+b+ab−a²−b²+a²b²)/2`,
`a||b = (a+b−ab+a²+b²−a²b²)/2`, `!a = −a`.

**Range-soundness is discharged in closed form.** What soundness requires is that
the connectives never produce an out-of-range truth value anywhere in [−1, +1]².
We prove this with a polynomial range-bounder (`fv_poly_bound.py`) that computes
the exact global extrema of a polynomial over an axis-aligned box by the
compact-domain extremum argument, the extrema lie at stationary points of the
restriction to some face of the box, so the candidate set is the box corners and
the edge-interior and interior gradient-zero points, solved and evaluated in exact
(rational/algebraic) arithmetic. On the three connectives it returns **exact range
[−1, +1]**, a proof, not a sampled min/max. To ensure the bound applies to *what
the compiler emits*, the test first cross-checks the symbolic polynomial against
the substrate on the {−1, 0, +1}² grid (which uniquely determines a
degree-≤2-per-variable polynomial) plus off-grid points (agreement to 6 × 10⁻⁸),
then bounds. (`test_fv_poly_obligation_checker.py`; grid-exactness:
`test_fv_kleene_grid_exactness.py`.)

The same grid saturation makes selection exact: a sufficiently sharpened softmax
`select` is a *true* one-hot, because `exp(−k)` underflows to exactly 0 (in
float32 for modest `k`, far below ulp in float64), so unselected branches are
multiplied by exact zero, the mechanism behind the bit-exact operator dispatch
in §4.3.

**3.3 Termination obligations (from soft-halt loops).** Each loop is a bounded
recurrence `state ← R · state` with a fixed-width state vector and a halt cell.
Termination reduces to "the halt signal is monotone within bounded steps,"
discharged per loop, far smaller than proving an arbitrary `while` terminates.

We are explicit about what this is and is not, since "all loops are bounded" can
read as a sidestep. It is a deliberate **language design choice**, and one that
has been made *visibly* at the surface syntax level, Sutra distinguishes two
forms with two purposes:

- **`loop (cond)` / `while_loop`** (this section): a bounded soft-halt
  recurrence over a fixed-width state vector. Termination obligation applies,
  discharges as described below, and the trusted base is composed exclusively
  of this form.
- **`recur(...)`** (non-halting; Sutra's explicit non-halting-loop primitive,
  shipped in this work's reference implementation): an *explicitly non-halting*
  loop, used for UI tick-loops, event-driven recurrences carrying substrate
  state across iterations, and other cases where the program *should* run
  forever. `recur` does not pose a termination obligation because it asserts
  non-termination as its declared semantics. The trusted base does not use
  `recur`; programs that do are outside the scope of the FV agenda by
  construction (and the obligation framework reports this without an attempt
  to prove a property the form does not claim).

Naming both forms explicitly addresses the natural worry that "Sutra bans
unbounded loops" is a sidestep: the language design **separates** the cases
rather than collapsing them, so the absence of an unbounded `while` in the
trusted-base fragment is a meaningful scope claim, not a missing feature.
With this split, what §3.3 covers is bounded recurrences specifically. **We do
not claim a novel attack on the halting problem, and the by-construction nature is
the point, not a hidden circularity**: by *excluding* the undecidable case
(unbounded `while`) from the trusted-base fragment, and reporting, rather than
silently accepting, any program that uses the non-halting `recur`, we are left
with a fragment on which a *decidable* obligation remains. That obligation is not
vacuous: for each bounded soft-halt loop one must still check that the halt signal
is **monotone** and **crosses its threshold within the bound** (rather than the
loop running to the bound every time), which is a real mechanical check on the
emitted recurrence, not an assumption. The contribution here is the clean
*separation* that turns the trusted base's loops into a checkable fragment, plus
that convergence check, not a claim to decide termination of arbitrary programs.
It is a real, useful property for a trusted base, a kernel role must not hang,
but it is **not** functional correctness, which is a separate obligation (§3.1,
discharged for the Kleene fragment) and not subsumed by termination.

This is discharged structurally and observably. Structurally the emitted loop is
`for _t in range(max_iters)` (bounded by construction) with
`halted = min(halted + halt, 1)` and `halt = sigmoid(·) ≥ 0` (monotone, capped at
1; on saturation `state = (1−halted)·cand + halted·state` freezes). Observably on
the torch substrate: a non-converging loop runs to the bound and stops
(`iters_active = 9.998/10`, never exceeding `max_iters`); a converging loop is
**exactly frozen** across unroll depth, its state at `T=20` equals its state at
`T=10`, **diff = 0.0**. (`test_fv_termination.py`.)

**The convergence criterion made principled: the loop's poles.** The structural-
plus-observational discharge above is a consequence of a sharper fact about the
loop's *linear core*, which the **Z-transform** names exactly. The recurrence
`state ← R · state` is a discrete-time linear time-invariant system; its one-sided
Z-transform is `X(z) = (z·I − R)⁻¹ · z · x₀`, so the system's **poles** — the roots
of `det(z·I − R)` — are precisely the **eigenvalues of `R`**. The standard
discrete-time stability classification reads straight off the poles relative to the
unit circle: all `|λ| < 1` gives geometric decay to a fixed point (termination from
the linear dynamics alone); `|λ| = 1` with the on-circle poles *semisimple* gives a
bounded, norm-preserving orbit with no decay; any `|λ| > 1` diverges and fails the
bounded-state premise the whole obligation rests on. This is decidable on the
*actual emitted operator*: a checker (`fv_loop_convergence.analyze_loop_recurrence`,
exposed as `fv.analyze_loop_recurrence`) computes the eigenvalues of the `R` the
loop runs and classifies the regime. Measured on the emitted bind rotation
(dim 868): **all 868 poles lie exactly on the unit circle, spectral radius
1.00000000, with `R` orthogonal** (hence normal, so the on-circle poles are
genuinely semisimple, not defective) — *marginally stable*. The
verification-relevant reading is sharp: the linear core neither decays nor grows,
so termination is **not** a property of the recurrence — it is discharged entirely
by the soft-halt gate above. The Z-transform makes precise *which* mechanism does
the work, and the same check rules out the only way the linear core could break the
obligation: a pole outside the unit disk, which would let the state blow up before
the gate can fire. (`fv_loop_convergence.py`, `test_fv_loop_convergence.py`, 6/6;
the substrate cross-check measures the eigenvalues of the real emitted rotation.)

**Tooling.** Off-the-shelf SMT solvers target Boolean and linear arithmetic, not
the polynomial obligations the compiled graph produces; §6 discusses where
nonlinear solvers such as dReal fit. The per-construct discharges above use
concrete finite methods: grid-exactness is a nine-point evaluation;
range-soundness is a closed-form critical-point bound; termination is structural
plus a saturation observation plus a Z-transform pole-location check on the loop
operator; equivalence is symbolic polynomial identity.

**Range-soundness scales to arbitrary depth by composition, the bounder is NOT
on the critical path for depth.** This is worth stating directly, because the
natural worry is that deep nesting produces a high-degree polynomial the
closed-form bounder cannot handle. It does, and we do not bound it. The
closed-form critical-point bound gives the exact range of a *single* connective;
the *composed* polynomial of a deeply nested expression is high-degree and
bounding it directly is expensive — measured, the exact box bound completes a
single connective in ≈0.1 s but does not finish even a depth-2 composition
(`(a && b) || c`) within 30 s, because the critical-point box search blows up the
moment degree and arity climb past one connective. We do not need to: each
connective is proven to
map [−1, +1]ᵏ into
[−1, +1] (its exact range *is* [−1, +1]), so any expression built solely from the
connectives, over truth-axis inputs in [−1, +1], has range within [−1, +1] **by
induction on the expression tree**, independent of nesting depth and degree. The
check (`range_sound_by_composition`) verifies an expression is such a composition
(refusing if it uses a non-connective operator), and decides range-soundness for
arbitrarily deep nestings instantly. So the equivalence procedure (degree-
insensitive polynomial identity) and range-soundness (degree-insensitive
composition) both scale; the closed-form bounder remains the exact tool for the
per-connective lemma they rest on.

**The composition argument is structural, not numerical, substrate noise is a
separate concern, addressed in §4.** A reasonable critique is that VSA
operations accumulate noise at increasing bundle width, so the per-connective
lemma (range = [−1, +1] exactly) is "leaky" once the connectives are realised
on a real substrate. That critique conflates two layers that are deliberately
kept separate. The composition argument here is *about the polynomial*: given
the inputs of each connective are in [−1, +1], the output of the polynomial
the connective lowers to is in [−1, +1], a closed-form fact about the
polynomial, independent of how it's executed. Whether the substrate computes
that polynomial *faithfully* (within machine epsilon, or bit-exactly under the
integer-exact-range conditions named in §4.3) is a separate, measured question.
The two layers stack: §3.3 says the *abstract* range is sound for any depth;
§4 (esp. §4.1's capacity curve and §4.3's bit-exact dispatch) says the
*substrate* realises that abstract range to documented precision within the
trusted-base usage envelope. Conflating them would let either layer's
limitations contaminate the other's claim; keeping them separate is what lets
each layer's argument be precise.

**Cost of the equivalence check, and a poly-time decision procedure that scales.**
The *exact* identity check `expand(p_a − p_b) == 0` is expensive, and we name why
plainly: the Kleene lowering duplicates operands (`a && b` expands to a formula that
mentions `a` and `b` several times), so the *inlined* arithmetic, and `sympy.expand`
of it, is exponential in nesting depth, before any cancellation. Measured on the same
`extract_truth_polynomial` pipeline the checker uses (balanced Kleene trees, var pool 3;
`experiments/randomized_pit_scaling.py`): depth 1 → **6 monomials**, depth 2 → **312**,
depth 3 → **infeasible** (`expand` killed after 30 s). This is the wall reviewers
correctly flagged.

The wall is not intrinsic to deciding equivalence, only to deciding it by *expansion*.
We add a **randomized identity test (Schwartz–Zippel)** that decides the same notion in
polynomial time. Instead of distributing the polynomial, it evaluates the difference
`p_a − p_b` at random points of a finite field `F_p` (`p = 2^61 − 1`), applying each
connective's closed-form truth polynomial to its operands' *values* on the *original,
un-inlined* expression tree, one number per node, **O(tree size) per trial**, no
duplication, no `expand`. It is sound one-sided: any nonzero evaluation is an **exact
disproof** with a witness point, and all-zero over `k` trials certifies identity with
false-positive probability `≤ (deg / (p−1))^k`. Measured on the same trees (32 trials):

| nesting depth | leaves | `expand` (exact) | randomized PIT |
|--------------:|-------:|:-----------------|---------------:|
| 3  | 8     | infeasible (> 30 s) | 0.003 s |
| 6  | 64    | infeasible          | 0.017 s |
| 8  | 256   | infeasible          | 0.039 s |
| 10 | 1 024 | infeasible          | 0.152 s |
| 12 | 4 096 | infeasible          | **0.822 s** |

So the procedure decides at **depth 12 (4 096 leaves) in under a second** what expansion
cannot do at depth 3, with verdicts agreeing with the exact check wherever the exact check
still terminates (De Morgan, commutativity, distributivity, and absorption are
cross-checked in `test_fv_general_checker.py`). The connective formulas the evaluator
applies are verified against the compiler's own inliner
(`test_kleene_connective_formulas_match_inliner`), so the randomized check decides the
*same* polynomial as `reduces_to_same_graph`, not a drift. The trade-off: the
exact check is certain when it terminates; the randomized check trades that for a
quantified, negligible error (at depth 12 the bound is `(1.7×10⁷ / 2^61)^32 ≈ 10^−360`).
The degree grows ≈ `4^depth`, so beyond ~depth 30 a larger prime or CRT over several
primes restores the margin, unnecessary for any realistic nesting. Full data:
a companion finding in the repository (with the original expansion-cost table).

**3.4 A fourth shape: digit-array carry propagation.** Once the trusted base does
arithmetic the substrate's native float range cannot hold exactly (arbitrary-
precision integers as a fixed-width digit array), the same finite reasoning lifts
to a fourth obligation shape. The `digit_array_add` intrinsic does radix-`r`
addition entirely in tensor ops (pairwise sum, floor-division carry extraction, an
`N`-step shift-and-propagate; no `.item()`, no host scalar branch). *Range-
soundness* is a step-indexed invariant — every digit stays in `[0, r)` and every
carry in `{0, 1}`, preserved across each propagation step (the maximal `d_new = r`
is the "9 + 1" cascade) — a closed-form fact about the arithmetic in the spirit of
the §3.2 bound. *Termination* is structural: the runtime is `for _step in
range(n)` over the digit-array *width*, not a data-dependent value, so it halts in
exactly `n` steps. Shipped bit-exact on nine worked cases
(`experiments/bigint_worked_example.py`); the full obligations, proofs, and spec
are in the repository. Not yet covered: signed digit arrays, and expressing these
bounds in the §3.2 polynomial-Kleene style rather than step-indexed induction (a
wiring task, not a new result).

## 4. Faithfulness: the reduction is computed exactly

A reduction to algebra is worth something only if the substrate computes the
compiled graph *exactly*. This is not a circular assumption about an opaque
substrate, and it is worth being precise about why.

**The substrate operations are formally-defined VSA operations with algebraic
laws.** Bind, unbind, and bundle, the primitives the compiled graph is built
from, are vector-symbolic-architecture operations, not ad-hoc tensor code. The
holographic-reduced-representation algebra (Plate 1995) gives their laws, binding
is **invertible** (`unbind(R, bind(R, x)) = x`) and bundling is a **linear
superposition** whose decodable capacity grows with dimension (Frady, Kleyko &
Sommer 2018; Kleyko, Rachkovskij, Osipov & Rahimi 2023). So the obligations the
verifier discharges are algebra over operations that *have* a formal algebra; what
is left to establish empirically is narrower and non-circular: how exactly a given
**frozen embedding substrate** realises those laws. ("Frozen" = a pretrained
embedding model whose weights are fixed and never updated, e.g. nomic-embed-text
at 768 dimensions; Sutra binds and bundles *in that fixed space* rather than
learning a new one.) The three results below are that realisation, the
invertibility law to machine epsilon, and exact decode within capacity at the
widths the trusted base uses, measured, with protocols restated here so the paper
stands on its own.

**4.1 Bundle decoding, accurate well beyond *k* = 8, not just at it.** Protocol:
for each bundle width *k*, bind *k* role–filler pairs by rotation, superpose
(bundle) them into one vector, and decode each filler by unbind +
nearest-codebook (argmax-cosine), 10 trials per width. The headline result is the
**measured capacity curve**, not a single-point claim at *k* = 8:

|   *k* | nomic (768-d) | mxbai (1024-d) | all-minilm (384-d) |
|------:|--------------:|---------------:|-------------------:|
|     2 |        100.0% |         100.0% |             100.0% |
|     4 |        100.0% |         100.0% |             100.0% |
|     8 |        100.0% |         100.0% |             100.0% |
|    16 |        100.0% |          98.8% |              92.5% |
|    24 |        100.0% |          95.8% |              76.2% |
|    32 |         99.1% |          85.3% |              66.9% |
|    48 |         93.3% |        (mem)\* |              42.3% |

\*mxbai *k* = 48 hit a memory-allocator error during Haar-QR matrix
construction on this configuration; reported as missing data rather than
guessed.

Read the table directly: **rotation binding stays at or above 99% accuracy
through *k* = 32 on the 768-d substrate, and 95% through *k* = 24 on the 1024-d
substrate.** Capacity grows with dimension exactly as the VSA literature
predicts (Plate; Frady, Kleyko & Sommer). This is *not* a method whose ceiling
is *k* = 8. That is the *comparison width* where the textbook Hadamard
(element-wise) binding has already collapsed (2.5% on mxbai-embed-large,
7.5% on all-minilm) while rotation binding holds. Hadamard never exceeds 95%
on any substrate even at *k* = 2, and is below 50% by *k* = 48 on all three.
Beyond text, the same protocol gives 100% through *k* = 8 on the ESM-2 protein
model, where Hadamard is similarly collapsed at modest widths, the property
is substrate-independent within the dense-encoder family.

The capacity curve's roll-off at large *k* does **not** undercut the verification
claim, because the two concern different objects. Bundling capacity is a property of
VSA *associative memory*, how many items survive superposition, and that lossy,
graceful-degradation regime is **not part of the trusted base** and is **not what the
obligations verify**; the verified object is the compiled arithmetic/control graph,
whose exactness (§4.3) is bit-level integer dispatch, independent of how many items a
bundle could hold. What verification needs from bundling is narrower than maximum
capacity: the bundle/bind/unbind primitives the compiled graph is built from recover
their inputs exactly at the small, fixed widths the trusted base actually uses (a
kernel role's axon carries a handful of named slots, not hundreds). The trusted-base
widths are typically ≪ 8, and the curve shows the primitives work accurately at
order-of-magnitude more capacity than that requirement, so the measured roll-off is
reported headroom, not a crack in the exactness it is sometimes misread as
contradicting.
(10 trials per *k*; the full table including signal cosines and the Hadamard
comparison is a companion finding in the repository.)

**4.2 Reversibility.** A single bind+unbind cycle returns the input at the
floating-point noise floor: mean `‖unbind(R, bind(R, x)) − x‖ = 1.5 × 10⁻¹⁵`
across all four substrates, the rotation is invertible to machine epsilon.

**4.3 Exactness of the compiled arithmetic dispatch (classical, deterministic
target).** The bit-exactness in this subsection is *classical* bit-exactness on the
deterministic tensor-op target — a property of *Sutra's compilation*, not of any
application, and deliberately distinct from the **p-bit-exactness** that is the
substrate's headline notion (defined at the end of this subsection and carried by
the §7 convergence spine). Two kernel-free demos
in this repository exercise it with no OS, kernel, or router in the loop, each
compiles a `.su` source and calls its substrate entry point directly. In
`demos/calc`, the operator is *selected on the substrate* from its character's
codepoint (`string_char_at` + a softmax-saturated `select`, §3.2) rather than by
a host dispatch table, and the arithmetic runs on the substrate in float64 (exact
integers to 2⁵³): **11/11 expressions evaluate exactly** against an exact-rational
oracle, **6/6** inexact or unparseable inputs are *refused* rather than
approximated, and **7/7** result strings are decomposed exactly on the substrate.
In `demos/echo`, a string rides a single rotation binding into an axon and back,
**bit-exact on 5/5 round-trips** down to runtime dimension 16. Both run at small
width, `demos/calc` at the audited floor of `runtime_dim = 8`, with no
`basis_vector` calls so the semantic codebook is unused, so the exactness is the
dispatch's, not an artifact of high dimension. Reproduce in-repo:
`python -m pytest demos/calc demos/echo` (32/32, measured on torch + CUDA with
nomic-embed-text). The property follows from the lowering, so it holds for any
Sutra program that compiles arithmetic the same way.

The usual "bit-exact on GPU" objection — float32 non-determinism from reduction
reordering — does not bite: the dispatch is element-wise ops plus one saturated
`select`, with no many-element reductions, and every intermediate is an
exactly-representable integer below 2⁵³, so each result is bit-identical regardless
of order (off-branches are multiplied by exact `0.0`). The scope is precise —
integer-valued computation in the exact range, not arbitrary float pipelines; the
soft-halt `sigmoid` is transcendental and deliberately outside it.

This is **classical bit-exactness on the *deterministic* target, and it is a
supporting precision measurement, not the paper's claim.** It is bought precisely
by routing arithmetic through the synthetic number axes and avoiding the
probabilistic semantic codebook (zero `basis_vector` calls, `runtime_dim = 8`); it
says the dispatch is faithful where the substrate is used deterministically. We
flag it as classical bit-exactness deliberately, because the headline exactness
notion for this paper is a *different* one and must not be conflated with it.

**The substrate's exactness notion is p-bit-exactness, not classical
bit-exactness.** On the probabilistic (energy-based / p-bit) target the substrate
does not deterministically compute the answer; it *samples*, settling into a
stationary distribution. "Exact" there cannot mean "the float pipeline reproduces a
bit pattern" — it means the distribution the sampler settles into is concentrated on
the exact answer: the strict global energy minimum *is* the correct output, so as
the sampler converges its mass goes to the right state and nowhere else. We call
this **p-bit-exactness** — exactness in distribution on a probabilistic bit
substrate. It is *not* bought by routing around the codebook; it is exactly the
property the §7 convergence chain establishes — the gadget ground states are the
strict minimizers (Lean-proven, §7.1), and the reversible sampler converges to the
stationary measure that places all its mass there (self-adjointness → spectral gap →
geometric decay, §7.2). So the exactness claim and the convergence claim are the
*same* claim on the probabilistic substrate, viewed once as "the right answer is the
unique minimizer" and once as "the dynamics reach it." The deterministic
bit-exactness above is the easy, classical case; p-bit-exactness on the probabilistic
target is the representative one, and it is the spine of §7.

**4.4 Dispatch-level discharge is necessary, not sufficient.** Confirming that
every operation dispatches to a substrate primitive (no host scalar branch, no
`float()` extraction inside an op, no Python control flow on a substrate value) is
necessary but not sufficient for the faithfulness §4 needs. Three further
measurements separate "every op dispatched correctly" from "the substrate carries
the claimed signal," each having caught a silent failure in a substrate-purity
audit of downstream programs:

- **Dimension audit** — `runtime_dim` must match what the source needs. A program
  with no `basis_vector` calls uses no semantic-codebook capacity, so its dimension
  can drop from the 768 + 100 default to a small fraction with no change in output;
  downstream apps ran at the full 768-d for weeks (~96× over-dimensioned) despite
  zero `basis_vector` calls until the audit cut them.
- **State-locus audit** — a "recurrent" claim requires the state vector to survive
  across steps *on the substrate*, not in a host variable extracted between calls.
  Counter/toggle/font-cycle demos were mislabelled RNNs until the audit reclassified
  them as stateless substrate functions in a host loop (the fix: a real substrate
  `loop`, §3.3).
- **Signal-separation audit** — a substrate classifier must show a positive
  `gap = min(positive-class) − max(negative-class)`. An initial font-glyph encoding
  dispatched every op correctly yet had LIT/UNLIT cosines overlapping at every
  dimension 16–256 (negative gap); the corrected encoding ships with a measured
  positive gap.

§4.1's capacity table is itself a signal-separation report and §4.3's |err| = 0.0
its strongest form; we name all three because they apply across the trusted base,
and treating dispatch-level cleanliness as the full claim is the silent failure
mode.

**4.5 A worked failure: a syntactic check is not a semantic guarantee.** The
repository ships a CI leak sweep that re-emits every user `.su` program and greps
for banned host-readout patterns (`float()`/`.item()` on a substrate tensor, host
`for`/`if` on a scalar). It is green across 67 programs — but it missed a leak in
the runtime *prelude* itself: `_TorchVSA.eq` computed cosine similarity with a live
autograd chain and then returned `make_truth(float(cos.item()))`, severing the
graph. It survived because the sweep reads emitted user programs, not the prelude
class. The leak surfaced from a program-level measurement, not the syntactic check:
a constrain-train experiment that made `==`'s output depend on a trainable
parameter failed `loss.backward()` ("does not have a grad_fn") because the chain
ended inside `eq`. The fix is a substrate-pure scatter (`out[truth_axis] = cos`,
`cos` kept as a 0-D tensor; numerics identical, autograd preserved), and the sweep
gained a second pass over the prelude under a method-level allowlist of legitimate
host↔substrate boundaries. The lesson is structural: a syntactic audit discharges a
syntactic claim, but substrate faithfulness is semantic, so the program-level
measurements (here an end-to-end differentiability probe) are what catch what grep
cannot. A companion experiment confirms the substrate carries autograd cleanly once
the leak is closed: `defuzz β` trains a `beta` parameter inside `defuzzify_trit`
end-to-end through the compiled graph (3 seeds, baseline loss ≈ 0.21 → ≈ 0.01;
`experiments/defuzz_gain_adjustment.py`).

## 5. Scope

The reduction buys the *shape* of a certification effort, DO-178C-style: a fixed
image and fixed critical-program set (Plan); axon-typed contracts (Requirements);
Sutra source whose compiled graphs are the designs (Design); mechanical proofs
that the graphs meet contracts plus discharged polynomial obligations
(Verification artefacts); an append-only capability/admission log (Trace); and the
compiler in scope for qualification with its compiled-graph output, not the
source, as the artefact under review (Tooling assurance).

The scope is bounded in three ways. The method covers the **non-learned** trusted
base: anything that invokes an embedding model or depends on a learned weight is
outside it, and gets bounded behaviour, capability discipline, provenance, and
runtime monitoring rather than a proof, the reduction makes the learned parts
*quarantinable*, not *safe*. Equivalence-as-algebra and the obligation checks
apply to the **contract surface of individual programs** whose compiled graphs are
individually tractable, not to a closed-form whole-system proof. And a certified
configuration is per-customer and per-mission; the present contribution is the
framework, the reduction, and the discharged obligations.

**The frozen substrate is a foundational trust assumption, not a verified
property, and that is the same posture every formally-verified system has had
to take.** A formally-verified C compiler trusts the CPU's IEEE-754 unit; a
verified OS trusts the silicon's MMU; a verified bytecode interpreter trusts the
machine that runs it. Sutra trusts the **frozen-substrate semantic mapping**:
that `embed("cat")` returns a particular vector and that that vector's
relationships to other embeddings have whatever properties the substrate
provides. We do not prove the semantic mapping is correct, that would require
verifying the pretrained embedding model itself, which is the learned-component
verification problem we explicitly *do not* claim to solve. What we do claim:
once the substrate is fixed (a particular pretrained model at particular weights,
say nomic-embed-text at the published checkpoint), the *algebra over those
embeddings*, bind, unbind, bundle, similarity, the polynomial connectives,
behaves as our §3 obligations specify, measured to the precision §4 documents.
The trust boundary is named: substrate-vector identity is foundational;
everything built on top is verified or quarantined. Conflating "the substrate is
trusted" with "the system is unverified" misreads where the boundary is, in the
same way that "the CPU is trusted" does not invalidate the verified-compiler
above it.

## 6. Related work

**Neural-network verification.** A large line verifies properties of *learned*
networks: Reluplex (Katz et al. 2017) and its successor Marabou (Katz et al.
2019) extend SMT to ReLU networks; abstract-interpretation systems such as AI2
(Gehr et al. 2018) and α,β-CROWN (Wang et al. 2021) bound network outputs over
input regions. Our posture is orthogonal and complementary: rather than verify the
learned network, Sutra verifies the **non-learned trusted base** by reduction and
*quarantines* the learned part behind contracts, the two could compose, with
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

**Arithmetic-circuit compilation (cryptography).** Compiling a program's
control flow into a polynomial arithmetic circuit is a well-studied technique
in zero-knowledge proofs and verifiable computation: Pinocchio (Parno, Howell,
Gentry & Raykova 2013) compiles C-like programs into quadratic arithmetic
programs over a finite field; Groth16 (Groth 2016) gives a succinct
preprocessing-SNARK over the resulting QAP; libsnark, ZoKrates, and Circom are
the practical compiler frontends. The mechanism is similar to ours, surface
control flow becomes polynomial, but the *purpose* is different: ZK-SNARKs
compile in order to *prove* program execution succinctly to a verifier without
revealing inputs; we compile in order to *verify* program properties by closed-
form algebra on the same graph the substrate runs. The cost surfaces also
differ: ZK-SNARKs pay setup + proof time + verifier time per execution and the
field is finite (mod p); we pay polynomial-identity / range-bounding wall once
per equivalence check and the field is the reals embedded in IEEE-754. The
shared ancestor is "compile branches into a polynomial circuit"; the
divergence is what you do with the resulting polynomial.

**Vector-symbolic architectures.** The substrate primitives are VSA/HRR
operations, binding, bundling, cleanup (Plate 1995; Gayler 2003; Kanerva 2009),
and they have a formal foundation we rely on rather than reinvent: the
holographic-reduced-representation algebra (Plate 1995) gives binding and bundling
their laws, and the capacity of bundling, how many superposed items decode
correctly as a function of dimension, is characterised in the VSA literature
(Frady, Kleyko & Sommer 2018; Kleyko, Rachkovskij, Osipov & Rahimi 2023). Our use of this is in §4: the
obligations are algebra over operations with formal laws, and the measured result
this work rests on is that *rotation* binding stays exact through bundle widths
where the standard Hadamard binding collapses. The three-valued Kleene polynomial
encoding of branches as a verification lever is, to our knowledge, new.

**Certification.** The plan/requirements/design/verification/trace framing follows
DO-178C, the avionics software-assurance standard, adapted so the artefact under
review is the compiler's tensor-graph output rather than imperative source.

## 7. The probabilistic substrate: verifying an energy-based compile target (the spine)

*This is the spine of the paper. The supporting machinery of §§2–6 was developed on
the deterministic target; here it reaches its cleanest form on a substrate that is
genuinely probabilistic, and the load-bearing question becomes convergence — does
the sampler reach the answer? The discrete-time picture is **Lean-machine-checked**;
the continuous-time, multi-state convergence is **measured, not Lean-proved**, and
labeled as such throughout.*

The verification of §§2–6 is over the deterministic PyTorch tensor-op target.
Sutra's second compile target is genuinely **probabilistic**: an energy-based model
sampled on thermodynamic, probabilistic-bit hardware (a sparse grid of p-bits doing
block-Gibbs sampling, the kind Extropic is building). There a Sutra value is a
register of spins, an operation is a *factor* (a local energy term), and the answer
is the configuration the sampler *settles into* — the ground state of the gadget's
energy — rather than a value computed deterministically. Verifying it means proving
a property of the energy landscape, and proving that the sampler *converges* to it.
This is the substrate that matches Sutra's fuzzy-by-default premise, and the
direction the verification work is moving.

The §3 reduction carries over: turning verification into a small fixed set of
finite obligations on the compiled object is target-agnostic, and on the
energy-based target it takes its cleanest form, a finite **ground-state** question
— *"is the arithmetically-correct output the global minimum of the gadget's
energy?"* — because a lowest-energy decode is exact precisely when it is. The same
obligations would certify the computation on any sampler that minimizes the same
energy.

This is a finite question for each gadget (the spins range over $\{-1,+1\}$), and
finite questions are exactly where machine-checked proof is cheapest. We give Lean
4 proofs (core only, no `mathlib`) that the energy-based gadgets the backend emits
have their correct output as the **strict global energy minimum**, every theorem
sorry-free, depending only on `[propext, Quot.sound]`:

- the derived **AND** gadget (biases and pairwise couplings), its output `a ∧ b`
  is the unique energy minimiser;
- the 3-body **XOR/parity** gadget, `x ⊕ y` is the unique minimiser, which pins
  the *sign* of the factor (the opposite sign silently encodes XNOR, a bug we hit
  empirically and the proof now excludes);
- the 1-bit **full adder**, sum `a ⊕ b ⊕ cin` (a 4-body parity factor) and carry
  `MAJ(a,b,cin)` (a pairwise factor) are jointly the strict minimiser for all
  inputs, so **integer addition's ground-state decode is provably exact**. A
  multiplier is these gates composed, so its correctness follows from theirs.

**How the gadget proofs compose to a circuit, machine-checked in general.** A complete
arithmetic circuit is gadgets *wired together*, one gadget's output spin is another's
input, and on the energy-based target wiring is **addition of energies**: the circuit's
energy is the sum of its gadget energies over the shared spin register. Composition of
the ground-state proofs is a sum-of-minimized-terms argument, and we prove it *in
general* (`Composition.lean`, core Lean, no `sorry`): for any finite list of penalty
terms over a shared state, if a state `s₀` minimizes every term and every other state
makes at least one term strictly larger at `s₀`, then `s₀` is the **strict** global
minimum of the sum (`strict_global_min_of_terms`). Each gadget's `_strict` theorem
supplies exactly these two hypotheses, its energy is uniquely minimized at its correct
local output, so a circuit assembled only from verified gadgets inherits a correct
strict global minimum from its parts, **for any number of gadgets, with no monolithic
re-proof**. This converts the composition methodology from an informal argument into a
machine-checked theorem. One subtlety the proof makes precise: a gadget's *raw* energy is
not a constant-zero-at-correct quantity (its minimum value varies with the inputs), so the
terms that compose are the gadgets' **proper penalties**, each raw energy shifted by its
own strict minimum, so it is `0` when the gadget is satisfied and `> 0` otherwise. We
machine-check the lemma applied to a concrete *two-gate* circuit, a 3-input AND built from
two AND gadgets wired on a shared spin (`and3_circuit_strict_min`), whose correct output
is the strict global energy minimum for every input, discharged from the two gadget
penalties via the general lemma rather than a re-proof of the composite. We further
machine-check a *heterogeneous* instance, a half-adder whose two penalties are a XOR
gadget (sum) and an AND gadget (carry) over the shared inputs (`half_adder_strict_min`),
confirming the composition lemma is gadget-type-agnostic rather than specific to a single
gadget. The 2×2 multiplier
(AND + XOR + adder) is the larger worked gate instance, and the general lemma certifies the
pattern at any size.

We also begin on *reachability*. The single-site (Glauber) block-Gibbs chain on
the AND gadget's $\{-1,+1\}^3$ state space is machine-checked **irreducible**
(every state reaches every state, the configuration cube is connected, and every
Glauber move has positive probability at finite $\beta$) and **aperiodic** (every
state has a self-loop, the conditional resampling a spin to its current value).
Irreducibility and aperiodicity are *exactly* the hypotheses the classical
fundamental theorem of finite Markov chains requires for a unique stationary
distribution $\pi$ and convergence to it from any start. We additionally prove
that for **any** strictly-antitone weight, and the Boltzmann weight
$w(E)=e^{-\beta E}$ is strictly antitone for every $\beta>0$, the strict
energy-minimiser is the strict unique **mode** of $\pi$. So the finite chain
converges (classical theorem, hypotheses now mechanised) to a stationary
distribution whose unique mode is the arithmetically-correct answer.

A second, `mathlib`-backed layer pins the stationary object itself, over the reals.
We machine-check (i) a general lemma that reversibility (detailed balance
$\pi(s)P(s,t)=\pi(t)P(t,s)$) of any finite row-stochastic kernel implies $\pi$ is
stationary; (ii) that the gadget's Gibbs kernel with the *real* Boltzmann weights
$e^{-\beta E}$ is reversible with respect to the Gibbs measure, so that measure is
stationary; and (iii) two-state Perron–Frobenius **uniqueness** of the stationary
distribution. With the irreducibility/aperiodicity above, this is the full
reversible-chain picture: a positive, irreducible, reversible finite chain has a
*unique* stationary distribution, and it is the Gibbs measure.

Each proof is a finite case analysis discharged by `omega` after a Boolean split
(integer `decide` does not reduce in the kernel here). These same gadgets were
independently *measured* to compute correctly at ~100% on the real sampler, and
the AND gadget was even *re-learned* from data by contrastive divergence,
recovering the hand-derived couplings, so measurement, learning, and proof agree
on the same energy landscape.

**What is now machine-checked, including the rate.** We have machine-checked the
gadget energies are *correct*; the finite chain's ergodicity hypotheses (irreducible,
aperiodic) and Gibbs **mode**; and, over the reals with `mathlib`, detailed
balance, stationarity of the Gibbs measure, and its uniqueness. The **mixing rate**
(*how fast* the chain reaches that unique stationary measure, the $t\to\infty$
total-variation / spectral-gap statement) is now mechanised too, for the two-state
clamped-decode chain the gadget inhabits. The transition matrix's second eigenvalue
$\lambda_2 = 1 - P_{f\to t} - P_{t\to f}$ is the per-step contraction factor: one step
multiplies the deviation from the stationary $\pi$ by exactly $\lambda_2$
(`two_state_step_contraction`), so after $n$ steps it is $\lambda_2^n$ times the
initial deviation (`two_state_geometric_mixing`) and the total-variation distance
decays as $|\lambda_2|^n$ (`two_state_tv_mixing`). Instantiated for the gadget's own
single-site Gibbs kernel, which fully resamples the spin, $\lambda_2 = 0$ exactly
(`gibbs_lambda2_zero`): the chain reaches the Gibbs measure in a *single* step
(`gibbs_mixes_in_one_step`; spectral gap $=1$). All `[propext, Classical.choice,
Quot.sound]`, no `sorry`. So the full *discrete-time* convergence picture for the
gadget chain (the gadgets *correct*, the chain *ergodic with the right unique
stationary Gibbs measure*, and the two-state *rate*) is machine-checked.

**The continuous-time, multi-state convergence, measured.** The Lean layer leaves
two pieces open: the *general multi-state* spectral gap (only the two-state clamped
decode is mechanised) and the *continuous-time* (Langevin/SDE) limit. We close them
*numerically* — a measurement on the real gadget energy, not a machine-checked
proof, and we mark the status as exactly that. The continuous-time limit of
single-site block-Gibbs is a Markov jump process whose law obeys the master
equation (the Kolmogorov-forward / Fokker–Planck ODE) $\dot p = Q^{\mathsf T} p$,
the distribution-level statement of the Langevin dynamics. Building the heat-bath
generator $Q$ on the machine-checked AND-gadget energy $E4$, the checker
(`fv.analyze_sampler_convergence`) measures: the Gibbs measure is **stationary**
($\lVert \pi^{\mathsf T} Q\rVert_\infty = 1.4\times10^{-17}$) and **reversible**
(detailed-balance violation $4.2\times10^{-22}$), the generator's spectrum is real
$\le 0$, and the full **eight-state** chain has a strictly positive **spectral gap
$\gamma = 0.0397$** at $\beta=1$ — so the law converges exponentially, for the
multi-state chain, not only the two-state case. Integrating the master ODE from a
worst-case start, the total-variation distance to $\pi$ decays at a **measured rate
$0.0397$, matching the spectral gap to ratio $1.0000$** — the gap *is* the
continuous-time convergence rate, confirmed on the trajectory. The clamped-decode
chain's stationary mode is the correct AND output for all four inputs.
(`fv_sampler_convergence.py`, `test_fv_sampler_convergence.py`, 6/6.)

**The multi-state convergence, exposed as Lean structure (two machine-checked legs).**
Two general-finite-state legs of the multi-state gap are now machine-checked, on an
explicit structure we state here in full so the proof is legible from the paper, not just
named. Fix a finite state space — a `Fintype S` — and read observables as vectors
$f:S\to\mathbb R$. The *kernel* is a row-stochastic matrix $P:S\times S\to\mathbb R$
($\sum_t P_{st}=1$) that is *reversible* with respect to the Gibbs vector $\pi$: detailed
balance $\pi_s P_{st}=\pi_t P_{ts}$. The transition operator acts as
$(Pf)_s=\sum_t P_{st}f_t$ (`applyP`), and the relevant geometry is the $\pi$-weighted inner
product $\langle f,g\rangle_\pi=\sum_s \pi_s f_s g_s$ (`innerPi`) with squared norm
$\lVert f\rVert_\pi^2=\langle f,f\rangle_\pi$. On exactly this structure:

1. **Reversibility ⇒ self-adjointness.** $\langle Pf,g\rangle_\pi=\langle f,Pg\rangle_\pi$
   for an arbitrary finite $S$ (`GibbsMultiState.applyP_selfAdjoint`), together with
   stationarity $\sum_s\pi_s P_{st}=\pi_t$ (`applyP_stationary`) — so the spectrum is real
   and the gap $\gamma=1-\lambda_2$ is well-defined. Pure finite-sum algebra from detailed
   balance, with no spectral-theory import.
2. **Scalar Rayleigh gap ⇒ one-step contraction.** If the self-adjoint form obeys the
   *scalar* Dirichlet/Rayleigh gap $\lvert\langle Ph,h\rangle_\pi\rvert\le(1-\gamma)\lVert
   h\rVert_\pi^2$ on the mean-zero subspace, then $P$ contracts the squared $\pi$-norm by
   $r=(1-\gamma)^2$ in one step: $\lVert Pf\rVert_\pi^2\le(1-\gamma)^2\lVert f\rVert_\pi^2$
   (`SutraConvergence.applyP_gap_contraction`). This is the numerical-radius = operator-norm
   step for a self-adjoint operator, proved *elementarily* off the reversibility foundation —
   real polarization ($4\langle Pf,g\rangle_\pi=\langle P(f{+}g),f{+}g\rangle_\pi-\langle
   P(f{-}g),f{-}g\rangle_\pi$), the parallelogram law, and the Cauchy–Schwarz discriminant
   argument (instantiate $g=t\!\cdot\!Pf$ for all $t$ and read off the discriminant of the
   resulting nonnegative quadratic) — with **no** finite-dimensional spectral theorem.
3. **Gap ⇒ geometric convergence.** Feeding leg 2's one-step contraction ($r=(1-\gamma)^2<1$)
   into the induction gives $\lVert P^n f\rVert_\pi^2\le r^n\,\lVert f\rVert_\pi^2$ —
   geometric decay to the stationary mean (`SutraConvergence.geometric_convergence`). The
   chain preserves the $\pi$-mean (`applyP_preserves_piMean`), so the mean-zero subspace the
   contraction lives on is $P$-invariant and the induction goes through.
4. **The Z-transform pole is the contraction rate — loop and Gibbs are one theorem.** The
   energy sequence $a_n=\lVert P^n f\rVert_\pi^2$ has generating function
   $G(z)=\sum_n a_n z^n$; comparison with the geometric series (no spectral theorem) gives
   that $G(z)$ is summable exactly for $r\!\cdot\! z<1$, i.e. the **Z-transform pole sits at
   $z=1/r$: the pole radius equals the contraction rate $r$** (`energy_gen_summable`), and at
   $z=1$ the total deviation-energy $\sum_n a_n$ is finite when $r<1$ — the chain settles
   (`energy_summable_of_contraction`). The deterministic loop is the SAME
   statement at the boundary $r=1$: for an orthogonal (π-isometry) $R$ the energy is constant,
   so $G(z)=\lVert f\rVert_\pi^2\sum_n z^n$ converges iff $z<1$ — the pole lies exactly on the
   unit circle (`loop_energy_gen_summable`), marginal stability, termination by the halt gate.
   So the loop ($r=1$, poles on $|z|=1$) and Gibbs ($r=(1-\gamma)^2<1$, pole inside) are
   instances of one Z-transform theorem; only the pole radius, $=r$, changes — exactly the
   substrate table below.

All four legs are `[propext, Classical.choice, Quot.sound]`, no `sorry`, and CI-checked on
`ubuntu-latest` (`fv-lean/mathlib/GibbsMultiState.lean` and `Convergence.lean`; the
`fv-lean-mathlib-ci.yml` job runs `lake build` over all three mathlib-layer libraries on
every change to them). This is the self-adjoint → gap → decay chain named in §1, now
machine-checked end to end **from a scalar Rayleigh gap to geometric decay**, and the same
convergence recast once more as a **Z-transform pole = contraction rate** identity that puts
the deterministic loop and the Gibbs chain under one theorem — a scalar gap number in, a
machine-checked operator-norm contraction, geometric-decay rate, and pole-radius identity out.
The gap *value* $\gamma=0.0397$ is the measured input that instantiates the scalar hypothesis.

The composition itself is machine-checked, not merely asserted: because leg 2 delivers the
contraction only on the mean-zero subspace (the stationary direction is norm-preserving, so an
all-observables contraction would be false), the iteration that reaches leg 3 is the mean-zero
form `geometric_convergence_meanZero`, which keeps every iterate mean-zero via
`applyP_preserves_piMean` (`iterP_piMean_zero`). And leg 2's Rayleigh hypothesis is not always
an external input: for a concrete reversible **two-state** kernel it is *discharged from the
matrix entries* — `twoState_rayleigh_eq` proves $\langle Pf,f\rangle_\pi=(1-P_{01}-P_{10})\lVert
f\rVert_\pi^2$ on the mean-zero subspace (the second eigenvalue $\lambda_2=1-P_{01}-P_{10}$,
computed by two-term algebra, no spectral theorem), and `twoState_geometric_decay` chains it
through legs 2–3 to a fully-closed $\lVert P^n f\rVert_\pi^2\le(\lambda_2^2)^n\lVert f\rVert_\pi^2$
with **no measured input**. So the Rayleigh hypothesis is demonstrably dischargeable, not vacuous.

For the *general* multi-state case the gap is now reduced to a **Poincaré/Dirichlet bound**, with
no finite-dimensional spectral theorem. The $\pi$-Dirichlet form
$\mathcal{E}(f)=\tfrac12\sum_{s,t}\pi_s P_{st}(f_s-f_t)^2$ satisfies
$\mathcal{E}(f)=\lVert f\rVert_\pi^2-\langle f,Pf\rangle_\pi$ (`dirichlet_eq`), so
$\langle Pf,f\rangle_\pi=\lVert f\rVert_\pi^2-\mathcal{E}(f)$
(`innerPi_rayleigh_eq_dirichlet`); a Poincaré inequality $\mathcal{E}(f)\ge\gamma\lVert f\rVert_\pi^2$
on the mean-zero subspace together with laziness ($\langle Pf,f\rangle_\pi\ge0$) then yields the full
two-sided Rayleigh gap and hence geometric decay $\lVert P^n f\rVert_\pi^2\le((1-\gamma)^2)^n\lVert
f\rVert_\pi^2$ (`gap_of_poincare_lazy`, `geometric_decay_of_poincare_lazy`) — all `sorry`-free, CI-checked.
This is a reusable engine parameterized by the Poincaré constant $\gamma$: a concrete chain closes
end to end by supplying $\gamma$ from the elementary per-edge form.

The conductance route is exercised end to end on a genuine **multi-state** chain: for the
lazy-uniform kernel on any finite state space (stay w.p. $1-\varepsilon$, else jump uniformly),
every off-diagonal edge weight equals $\varepsilon/n^2$, so the complete-graph Dirichlet identity
$\sum_{s,t}(f_s-f_t)^2=2n\sum f_s^2-2(\sum f)^2$ (`sum_sq_diff`) and the per-edge bound
(`dirichlet_raw_ge_of_min_edge`) give the Poincaré constant $\gamma=(\varepsilon/n^2)\cdot n^2
=\varepsilon$ (`unif_poincare`), and `lazyUnif_geometric_decay` closes $\lVert P^n f\rVert_\pi^2\le
((1-\varepsilon)^2)^n\lVert f\rVert_\pi^2$ — an $n$-state chain, $\gamma$ **computed from the matrix
entries**, no measured input and no spectral theorem (all `sorry`-free, CI-checked). This is the
multi-state analogue of the two-state instance; it does not use the eight-state Gibbs kernel, whose
exact $\gamma=0.0397$ remains a transcendental measurement.

What remains genuinely open, named not claimed: (i) discharging the Rayleigh hypothesis the
same way for the specific **eight-state Gibbs** kernel — a per-edge (Cheeger/conductance) lower bound on
$\gamma$ for that operator (the general Poincaré$\Rightarrow$decay engine, the two-state case, and a
closed-form multi-state instance are done; the eight-state $\gamma=0.0397$ is still taken as the
measured input, its exact eigenvalue being transcendental); and (ii) the continuous-*space* overdamped
Langevin diffusion $dX=-\nabla U\,dt+\sqrt{2/\beta}\,dW$ on a relaxed energy. (Proofs: `fv-lean/`, core, no `mathlib`,
and `fv-lean/mathlib/` for the reversibility/stationarity/uniqueness/rate layer; the
measured continuous-time analysis: `fv_sampler_convergence.py`; the host/sampled
hardware mapping: the companion findings.)

## 8. Source-language frontends: empirical end-to-end verification

The verification in §§3–7 is *formal*: closed-form obligation discharge (§3–§4)
and machine-checked Lean proofs (§7). This is a **brief complementary note**, not
a co-equal contribution, on a **separate and weaker** assurance layer we are
careful not to conflate with the formal results. Beyond hand-written Sutra, the
language is also a compile *target* reached from several source languages by
research lowering passes, **not complete or production compilers, a claim we
explicitly do not make.** Those passes are verified **empirically, by end-to-end
test, not by proof**: the bar is **compile-AND-run against ground truth**. A
fixture is a small source program with a known result; the pass lowers it to
Sutra, the §2 compiler lowers that to the tensor-op graph, the graph runs on the
substrate, and the decoded output is compared to the source language's own answer
, a wrong number is a *failure*, not a pass. The fixture suite measures the
*breadth of verification-relevant constructs* that reach the §3 target
(conditionals/`match` → the §3.2 branch polynomial; the recursion forms → bounded
substrate loops; algebraic data → structured axons), not any language's full
surface.

**What this does and does not establish.** It establishes that, on the inputs in
the suite, each lowering preserves the source semantics through to a substrate
run, a regression-grade, executable check that the pass emits *correct* Sutra. It
does **not** establish a formal proof that a lowering is correct for all inputs,
nor a complete compiler for any language; we make neither claim, and this layer
must not be read as extending the §3–§4 obligations or the §7 Lean proofs to the
frontends. The relationship to the formal layer is one-directional: because every
pass emits *ordinary* Sutra and the §2 compiler is the only component that lowers
to tensors, the lowered program inherits the *target-level* trusted-base
properties of §§3–4 exactly as a hand-written one does; what is *not* inherited,
and is supplied here only empirically, is assurance about the **lowering step
itself**. Formal verification of that step (a verified frontend, in the CompCert
(Leroy 2009) sense) is outside scope, and we name the present assurance as exactly
what it is: empirical, not formal.

## 9. Conclusion

The spine of this paper is **convergence** — verifying Sutra as an execution
environment *as it runs* on a substrate whose second target is genuinely
probabilistic. On the deterministic target the loop's linear core is marginally
stable (Z-transform poles on the unit circle, **measured**), so termination is the
soft-halt gate's job; on the energy-based target the sampler converges to its unique
stationary Gibbs measure (**Lean-machine-checked** in the discrete, two-state case;
**measured** for the multi-state continuous-time gap). The reduction and the
closed-form obligations below are the supporting machinery that makes that
convergence question tractable.

Compiling the non-learned trusted base to a tensor-op graph turns formal
verification from imperative-path enumeration into algebra over a small fixed set
of tensor graphs, with the load concentrated into three closed-form obligation
families. All three have mechanical checks that run on the substrate:
Kleene-gate exactness (worst error 0.0), connective range-soundness (a closed-form
proof of outputs in [−1, +1]), and loop termination — together with the
kernel-enforced confinement half of the contract obligation and a decision
procedure for program equivalence over the Kleene-logic fragment that separates
same-graph from logical equivalence. The premise that the substrate computes the
compiled graph faithfully is borne out by the measured results of §4. The
reduction, framework, and discharged obligations are the contribution; extending
the equivalence decision procedure beyond the Kleene fragment, and building the
general checker that discharges an arbitrary reduced-graph obligation, are the road
ahead on the deterministic target.

The same framework is target-agnostic, and §7 carries it to the **probabilistic**
energy-based target, where the obligation collapses to a finite **ground-state**
question and the substrate matches Sutra's fuzzy-by-default premise. There the
gadgets' ground-states are machine-checked correct, and the single-gadget Gibbs
sampler is machine-checked to converge to its unique stationary Gibbs measure
(ergodicity in core Lean; reversibility, stationarity, and uniqueness over the
reals in `mathlib`; the two-state mixing rate mechanised — spectral gap 1, so it
mixes in one step). Beyond that, the *continuous-time, multi-state* convergence is
now **measured** on the real gadget energy: the master-equation generator's Gibbs
measure is stationary and reversible, the full eight-state chain has a positive
spectral gap ($\gamma=0.0397$ at $\beta=1$), and the law's total-variation decay
matches that gap (ratio $1.0000$). What remains is to lift that measurement to a
*machine-checked* multi-state proof and to the continuous-space Langevin diffusion
— verifying the language as it genuinely runs on a probabilistic substrate, which
is where this line of work is headed.

---

## References

de Moura, L. and Bjørner, N. (2008). Z3: An Efficient SMT Solver. In *Tools and Algorithms for the Construction and Analysis of Systems (TACAS)*.

Frady, E. P., Kleyko, D. and Sommer, F. T. (2018). A Theory of Sequence Indexing and Working Memory in Recurrent Neural Networks. *Neural Computation*, 30(6).

Futamura, Y. (1971). Partial Evaluation of Computation Process: An Approach to a Compiler-Compiler. *Systems, Computers, Controls*, 2(5). Reprinted in *Higher-Order and Symbolic Computation*, 12(4), 1999.

Gao, S., Kong, S. and Clarke, E. M. (2013). dReal: An SMT Solver for Nonlinear Theories over the Reals. In *International Conference on Automated Deduction (CADE)*.

Gayler, R. W. (2003). Vector Symbolic Architectures Answer Jackendoff's Challenges for Cognitive Neuroscience. In *Joint International Conference on Cognitive Science (ICCS/ASCS)*.

Gehr, T., Mirman, M., Drachsler-Cohen, D., Tsankov, P., Chaudhuri, S. and Vechev, M. (2018). AI2: Safety and Robustness Certification of Neural Networks with Abstract Interpretation. In *IEEE Symposium on Security and Privacy (S&P)*.

Groth, J. (2016). On the Size of Pairing-Based Non-interactive Arguments. In *Advances in Cryptology (EUROCRYPT)*.

Kanerva, P. (2009). Hyperdimensional Computing: An Introduction to Computing in Distributed Representation with High-Dimensional Random Vectors. *Cognitive Computation*, 1(2).

Katz, G., Barrett, C., Dill, D. L., Julian, K. and Kochenderfer, M. J. (2017). Reluplex: An Efficient SMT Solver for Verifying Deep Neural Networks. In *Computer Aided Verification (CAV)*.

Katz, G., Huang, D. A., Ibeling, D., Julian, K., Lazarus, C., Lim, R., Shah, P., Thakoor, S., Wu, H., Zeljić, A., Dill, D. L., Kochenderfer, M. J. and Barrett, C. (2019). The Marabou Framework for Verification and Analysis of Deep Neural Networks. In *Computer Aided Verification (CAV)*.

Kleyko, D., Rachkovskij, D. A., Osipov, E. and Rahimi, A. (2023). A Survey on Hyperdimensional Computing aka Vector Symbolic Architectures. *ACM Computing Surveys*, 55(6).

Leroy, X. (2009). Formal Verification of a Realistic Compiler. *Communications of the ACM*, 52(7).

Parno, B., Howell, J., Gentry, C. and Raykova, M. (2013). Pinocchio: Nearly Practical Verifiable Computation. In *IEEE Symposium on Security and Privacy (S&P)*.

Plate, T. A. (1995). Holographic Reduced Representations. *IEEE Transactions on Neural Networks*, 6(3).

RTCA (2011). *DO-178C: Software Considerations in Airborne Systems and Equipment Certification.*

Taha, W. and Sheard, T. (2000). MetaML and Multi-stage Programming with Explicit Annotations. *Theoretical Computer Science*, 248(1–2).

Wang, S., Zhang, H., Xu, K., Lin, X., Jana, S., Hsieh, C.-J. and Kolter, J. Z. (2021). Beta-CROWN: Efficient Bound Propagation with Per-neuron Split Constraints for Neural Network Robustness Verification. In *Advances in Neural Information Processing Systems (NeurIPS)*.

---

*Reproducibility. The compiler, the obligation checker, the Lean 4 proofs, and the
scripts that produce every measured number reported here are in the project
repository; each result is regenerated by a named test or experiment, and the
substrate-leak sweep and proof checks run under continuous integration.*
