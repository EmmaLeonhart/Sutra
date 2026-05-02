# Paper title brainstorm

**Source:** Emma 2026-05-01.

The current title is *"Sutra: A Programming Language for
Vector-Symbolic Computation in Vector Embedding Spaces."* Emma
flagged it as redundant ("Vector" twice) and not capturing the
moving parts of what Sutra actually does. Too many parts to fit in
one title; goal here is to pick one that reads as the most
load-bearing claim and lets the abstract handle the rest.

## The pipeline the title is trying to summarize

Per Emma's reframing, Sutra is fundamentally a journey:

1. **Ergonomic functional surface** — `.su` source looks like
   TypeScript / Java; familiar operators, classes, loops as
   declared functions, polynomial fuzzy logic.
2. **Beta reduction (compile-time function expansion)** — every
   operator and stdlib call inlines until the program is a
   straight-line algebraic expression over VSA primitives.
3. **Beta normal form** — the residual after β-reduction. Reads
   like VSA in C-ish Polish notation: `bundle(bind(role, filler),
   bind(role, filler))` etc.
4. **Tensor normal form** — algebraic reduction of the β-normal
   form to a fused matmul / element-wise / nonlinear tensor-op
   graph. *Recurrent tensor normal form* generalizes for loops:
   the cell body is in TNF and the recurrence is a top-level
   operator.
5. **GPU execution as a neural network** — the compiled tensor
   graph runs on PyTorch (CUDA when available); structurally
   indistinguishable from an inference-mode neural network with
   user-defined ops.

The title needs to evoke at least the unique part of this — most
likely (2)→(4)→(5), the "lambda calculus → tensor graph → GPU"
spine. (1) is true of any HLL; (3) is an intermediate detail.

## Candidate titles

Grouped by foreground emphasis. Each has a short rationale.

### A. Compilation-pipeline framing (Emma's lean: "lambda calculus to neural network")

1. **Sutra: Compiling Lambda Calculus to a Neural Network**
   - Most direct phrasing of what Emma actually said.
   - "Lambda Calculus" cues the formal-PL audience; "Neural
     Network" cues the ML audience. Bridge is the headline.
   - Risk: ML readers might expect "trained the neural network"
     and need to be redirected by the abstract.

2. **Sutra: From Beta Reduction to Tensor Normal Form**
   - Names the actual compilation strategy. Strong with
     PL-theory readers.
   - Risk: "Tensor Normal Form" is our own coinage — readers
     don't know what it is from the title alone.

3. **From Lambda Calculus to GPU Tensor Graphs: The Sutra Language**
   - Concrete on both endpoints. "GPU Tensor Graphs" is what
     readers actually picture.
   - Slightly long.

4. **Sutra: A Functional Language That Compiles to Tensor Normal Form**
   - Foregrounds the language-design angle.
   - Conservative; doesn't say *what target* the TNF runs on.

### B. Substrate-as-architecture-target framing

5. **Sutra: Programming the Embedding Space as a Tensor Architecture**
   - Names the §1.4 framing (substrate-as-arch-target).
   - Less catchy; "architecture" overloaded.

6. **Compiling for Embedding Spaces: The Sutra Language and Tensor Normal Form**
   - Two-clause structure; both ideas land but the title is
     long.

### C. Vector-Symbolic / VSA framing (closest to current title)

7. **Sutra: Vector-Symbolic Programming on Frozen LLM Substrates**
   - Tight rephrasing of the current title without the doubled
     "Vector". Drops the compilation story.
   - Easy default if we don't want a bigger reframe.

8. **A Programming Language for Vector-Symbolic Computation Compiled to Tensor Graphs**
   - Adds the compilation half to the existing framing.

### D. Provocative / catchy

9. **A Compiler from Lambda Expressions to Recurrent Neural Networks**
   - Drop "Sutra" entirely from the title; let the language name
     live in the byline.
   - Loud; might attract more attention but less self-locating.

10. **Programs Without Branches: Sutra and the Tensor Normal Form**
    - Foregrounds the substrate-purity / no-control-flow claim.
    - "Without Branches" is technically inaccurate (loop driver
      has a Python `while True` + break) but the load-bearing
      claim — no branches inside any operation — is true.

11. **The Tensor Normal Form: A Programming Language as a Frozen Neural Substrate**
    - Lead with the contribution; "Sutra" relegated to the abstract.
    - Also loud.

## Recommendations

Two finalists emerge:

- **#1 ("Compiling Lambda Calculus to a Neural Network")** if the
  pitch is to a broad audience and the goal is a memorable claim.
  Closest to what Emma said out loud.

- **#2 ("From Beta Reduction to Tensor Normal Form")** if the
  pitch is to PL/compiler people. Strongest on the actual
  technical contribution, weakest on cross-audience appeal.

A hybrid like **"Sutra: Compiling Lambda Calculus to Tensor Normal
Form on a Neural Substrate"** captures both endpoints but is
heavy.

## What the title should NOT try to do

- List every contribution. Polynomial fuzzy logic, rotation
  binding, soft-halt RNN cells, end-to-end differentiability —
  all great, but each is one paragraph in the abstract, not a
  word in the title.
- Use both "Vector" and "Symbolic" together. Either say "Vector-
  Symbolic" once or rephrase. The doubled "Vector ... Vector
  Embedding" was the original problem.
- Use Sutra-specific neologisms ("tensor normal form") without
  tying them to something familiar in the same line.

## Decision

Deferred to Emma. Open question: which finalist (1 or 2) reads
best, and whether to lead with "Sutra:" or push the language name
to the byline.
