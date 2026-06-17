# Verification story

## What we can verify, and what we can't

A blunt division of the system:

- The non-AI parts (kernel, init, file system bridge, capability check,
  resource manager, browser engine, transpiler outputs of finite
  programs) are **formally verifiable**. Sutra's beta-reduced tensor
  normal form, polynomial Kleene logic, and tail-recursive loops give
  much cleaner proof obligations than a typical C++/Rust kernel.
- The AI parts (any embedding-model invocation, any process whose
  semantics depend on a learned weight matrix) are **not formally
  verifiable** in the strict sense, and we shouldn't pretend otherwise.
  They get bounded behavior guarantees (input/output type contracts,
  norm bounds, capability discipline) and runtime monitoring.

This is the accurate version of the pitch. It is also enough to be
attractive to defense and aerospace, because most of what they
critically depend on lives on the verifiable side, and the AI side is
quarantined behind axon-typed contracts.

## What makes the non-AI side easy to verify

The combination of three Sutra design choices does the work:

1. **Beta reduction to a tensor-op graph.** Sutra programs reduce to
   a fused tensor-op graph that is the program's semantics. Two programs
   that are semantically equivalent reduce to the same graph (modulo trivial
   differences). This means equivalence checking is algebra, not
   traversal.

2. **Polynomial Kleene logic for "branches".** What looks like an
   `if/else` in source is, after reduction, a polynomial that smoothly
   interpolates between the branches based on a fuzzy truth value.
   That polynomial is a closed-form expression — you can reason about
   its value range, its sign, its derivatives. Symbolic reasoning is
   tractable.

3. **Tail-recursive loops as soft-halt RNN cells.** Each loop is a
   bounded recurrence. The runtime's halt cell decides termination.
   Termination proofs reduce to "the halt signal is monotone within
   bounded steps", which is a much smaller obligation than proving an
   arbitrary while-loop terminates.

Together these take "verify a kernel" from "navigate millions of lines
of imperative C" to "discharge a finite set of polynomial obligations
over a known tensor graph."

## DO-178C-style argument structure

For an aerospace certification audience the argument structure looks
roughly like:

- **Plan**. Yantra ships a fixed kernel image plus a fixed set of
  critical processes. Their manifests are published. No runtime code
  loading affects this set.
- **Software requirements**. Each kernel role and critical process has
  an axon-typed contract (input roles, output roles, status conditions).
- **Design**. The kernel and critical processes are written in Sutra.
  Their compiled tensor-op graphs are the designs.
- **Code**. The Sutra source.
- **Verification artefacts**. Mechanical proofs that the tensor normal
  form satisfies the contracts. Polynomial-logic obligations
  discharged by an SMT solver or similar.
- **Trace**. Every capability the kernel grants, every admit/evict the
  resource manager performs, written to an append-only log.
- **Tooling assurance**. The Sutra compiler is itself in scope for
  qualification. Its output (normal form) is the artefact under
  review, not the source.

This is the *shape* of a real certification effort. We are not
shipping a certified Yantra v1; we are shipping something whose
architecture is friendly to certification when the time comes.

## The AI-side story

Embedding models, alignment monitors, and any process that bakes
learned weights into its behavior cannot be formally verified. What
they can have:

- **Bounded contracts**. Outputs live in a known axon shape. Norms are
  bounded. Roles that the contract promises to populate, are populated.
- **Capability discipline**. The AI process gets only the axons its
  manifest says it can read. It cannot read process state from
  elsewhere.
- **Provenance roles** (see `02-axon-model.md`). Every axon an AI
  process emits carries a provenance role that downstream consumers
  can use to decide trust level.
- **Runtime monitoring**. The alignment-pacemaker pattern (see
  `10-ai-native-interface.md`) sits between AI processes and any
  user-visible output, watching for known failure modes.

Crucially, the AI parts do not sit on the verified critical path. A
defense customer running Yantra on a sensor box can use AI for
classification while the actual control loop is provably safe.

## What the verifier sees

If a certification body asks "show me the entire trusted base", the
answer is:

- The bootloader (small C program, transpiled from a Sutra description
  ideally).
- The Sutra runtime (tensor-op executor, GPU memory arenas, halt
  cells).
- The kernel program (axon router, capability check, resource manager
  hooks).
- The init system (the small TS program that admits the boot service
  set).
- The critical-process manifests and Sutra source.

Total surface area is small. The fact that everything above the
bootloader is the same language with the same algebraic semantics is
the win — there is no "Linux + Rust microservices + Python control
plane" to triangulate across.

## What we are not claiming

- **Yantra is not a certified system out of the box.** A certified
  configuration is per-customer, per-mission, and is the user's job to
  obtain. We provide the artefacts that make that effort feasible.
- **Yantra is not formally verified end-to-end today.** The architecture
  is verification-friendly. The actual proofs are an ongoing project,
  most of which has not started yet.
- **Yantra does not make AI safe.** It makes AI *quarantinable* — the
  unsafe parts are bounded, contracted, and monitored. That is not the
  same as safe.

## Open questions

- **Compiler qualification.** The Sutra compiler has to be in scope for
  certification eventually. What does that look like? Self-hosted
  bootstrap with a verified microcompiler at the bottom?
- **Embedding-model identity attestation.** A swappable embedding model
  is a trust hole. We probably need a signature on every model bundle
  the bridge accepts.
- **Polynomial-logic toolchain.** Mature tooling exists for
  Boolean/linear logic. Polynomial Kleene with the specific
  fuzzy-interpolation Sutra uses is more bespoke. We may need to ship
  our own SMT-style backend.
