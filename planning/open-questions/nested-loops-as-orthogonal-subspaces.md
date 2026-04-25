# Open question: how do nested eigenrotation loops compose?

## The question

`planning/sutra-spec/control-flow.md` and `docs/loops.md` define the
single-loop semantics: `loop(N)` unrolls at compile time, `loop(cond)`
compiles to an eigenrotation `state ← R · state` on the substrate
with a prototype-match termination test. The spec is silent on what
happens when one of those data-dependent loops is **nested inside
another**:

```sutra
loop (outer_cond) {
    state = R_outer · state;
    loop (inner_cond) {
        state = R_inner · state;
    }
}
```

What is the substrate-level meaning of two `loop(cond)` constructs
nested like this? The current compiler accepts the syntax, but the
semantics — what `R_outer` and `R_inner` actually compose into, and
how the inner loop's termination signal returns information to the
outer loop — is undecided.

## What we currently do

Nothing principled. The lowering walks the AST and emits two nested
host-side loops; each inner iteration calls the substrate sequentially.
That's the same "host sequencer threads sequential presentations"
caveat called out in `planning/findings/2026-04-13-audit-rotation-loop-execution-locus.md`,
but compounded — the host now runs the inner sequencer per outer step.

There is no design statement that says where on the substrate the
inner rotation should live relative to the outer rotation, or how
the inner loop's exit value (a vector) should re-enter the outer
loop's state.

## The candidate from the design conversation

The design intuition (recorded only in
`chats/continuous-multiplication-loop-free-computation.md` before
that chat was triaged out): **nested loops are rotations in
orthogonal subspaces of the same state vector**.

Concretely:

- The outer loop rotates in dims `{i, j, k}` of the state vector
  (i.e. `R_outer` is the identity on every other dim).
- The inner loop rotates in dims `{l, m, n}`, disjoint from
  `{i, j, k}`. So `R_inner` is the identity on `{i, j, k}` and on
  every dim outside its own working set.
- Because the working subspaces are orthogonal, `R_outer` and
  `R_inner` commute on the full state vector. Running them in any
  interleaving — outer-first, inner-first, or fully fused
  `R_inner · R_outer` — produces the same result on dims that
  belong to neither, on dims that belong to outer (only `R_outer`
  acts), and on dims that belong to inner (only `R_inner` acts).
- High-D embedding spaces give "enormous orthogonal room," so deep
  nesting is essentially free as long as the per-loop working
  subspaces stay disjoint.
- Cross-loop information flow (e.g. inner termination → outer
  state) happens through an explicit `bind(role, value)` that
  writes into a third subspace — the binding both communicates the
  result and selects which subspace receives it.

If this framing is right, nested loops are not really "nested" in
the host sense. They are the substrate computing
`(R_outer ⊕ R_inner) · state` once, where `⊕` is direct-subspace
sum, and the host's job is just to drive the termination tests
against the appropriate prototype subspaces.

## Why this matters

Three concrete pressures:

- **Substrate honesty.** If the spec says `loop(cond)` is on the
  substrate and the implementation host-sequences nested loops, the
  inner-loop arithmetic *between* substrate calls runs on the host
  every outer step. That's the same host-sequencer caveat that the
  Substrate Rule was supposed to close — multiplied by nesting depth.
- **Compilation.** A spec-level decision lets the compiler fuse
  nested loops into a single substrate call (one composite rotation
  `R_inner · R_outer` plus the appropriate prototype-match for each
  layer). That's a real performance and clarity win, but only safe
  if the orthogonal-subspace claim is enforced — accidental dim
  reuse breaks correctness silently.
- **Cross-subspace communication.** The spec already has `bind` and
  `unbind` as the cross-subspace primitives, but doesn't say whether
  they're the prescribed mechanism for inner-result → outer-state
  flow. Without that, a programmer writing a nested loop has no
  guidance on how to thread an inner result back up.

## What we don't know

1. **Subspace allocation.** Does the compiler statically allocate
   disjoint subspaces per loop scope (using lexical nesting depth)?
   Does the programmer annotate? Or is it a property the simplifier
   discovers from the rotation matrices the user supplied? Each
   answer has different ergonomic and analysis costs.
2. **Termination as an eigenvalue perturbation vs. a separate
   prototype match.** The current spec uses prototype match for
   termination; the design intuition phrased termination as an
   I/O signal that *damps* the rotation (eigenvalue drifts off the
   unit circle). Are these the same thing reframed, or genuinely
   different mechanisms?
3. **Dependency propagation.** If the inner loop's body depends on
   the outer loop's current state — i.e. `R_inner` is itself a
   function of the outer state — the orthogonal-subspaces story
   breaks. How common is this in real Sutra programs we'll write?
   If it's rare, restrict the language; if common, the framing
   needs revisiting.
4. **Capacity.** "Enormous orthogonal room in HDC" is true at d=768
   for a few nested loops. At deep nesting depth, how does the
   subspace budget get consumed, and how is that surfaced to the
   programmer?
5. **Cross-subspace binding back-channel.** Is `bind(outer_role,
   inner_result)` the official mechanism for "inner loop tells
   outer loop what happened"? If yes, we should say that in the
   spec; if no, what's the alternative?

## What resolving this looks like

- Add a "Nested loops" subsection to `planning/sutra-spec/control-flow.md`
  that picks a story (likely orthogonal-subspaces with explicit
  binding for back-channel) and states what is fixed by the spec
  vs. left to the programmer.
- Update the codegen so nested `loop(cond)` constructs allocate
  disjoint working subspaces (or refuse to compile if they can't
  prove disjointness, depending on what the spec ends up requiring).
- Write a `.su` example with at least one real nested loop —
  probably the cleanest test case is two coupled rotations where
  the inner one's termination contributes to the outer's state.
- Once the spec section lands, prune this doc.
