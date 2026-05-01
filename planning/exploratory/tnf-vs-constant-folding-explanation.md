# TNF vs constant folding — the ontological framing

**Saved 2026-05-01 for potential paper §1.2 expansion.** Use only if the
in-flight `1505fb4`/`668429d` reviews validate that defending TNF as a
distinct concept is winning. If neither yields Strong Accept, give up
the novelty claim and either drop §1.2 contribution 2 or rename to
something humbler.

## The spectrum

- **Constant propagation** — specific values known at compile time get
  substituted. The residual program still runs on a conventional
  machine; you just removed some work.
- **Partial evaluation** — some inputs known, others not. You
  specialize the program against the known inputs, producing a residual
  program over the unknown ones. Futamura projections live here. The
  "known" stuff need not be literal constants — it can be program
  structure. But the output is still a program in the same
  computational model.
- **Staging** — explicit compile-time vs runtime annotations; the
  language respects those boundaries (MetaML, Lean `#eval`). Partial
  evaluation made explicit and controlled. Still the same model
  underneath, just with temporal layering.
- **Tensor normal form** — Sutra's regime. Not specializing a program
  against early-known values. Asserting that the normal form of all
  computation is a matrix operation. There is no residual program in
  the conventional sense. The "runtime" *is* matrix multiplication
  on GPU.

## The crisp framing

> Sutra's runtime is matrices.

In a neural network, weights are matrices and forward pass is chained
matmuls. Nobody calls that constant folding even though the weights
are fixed at inference time. The matrices *are* the computation, not
an optimization of it.

Sutra does the same for arbitrary programs. The compilation step
produces the weight structure. Execution is the forward pass. The
reason it doesn't feel like constant folding is that there is no
"un-folded" version of the program lurking underneath — matrix
operations aren't an optimization applied to some more primitive
semantics, they are the ground level.

## The honest concession

In the limiting sense, TNF *is* a form of constant folding: it is the
most constant-folded a program can possibly be. Compile-time work
reduces runtime work, same conceptual family. The difference is
**ontological, not quantitative**: a constant-folding pass removes
specific known subexpressions from an otherwise conventional program;
TNF collapses the entire computational model into the linear algebra,
so there is no "otherwise conventional program" to fold.

## Use this only if

- Either `1505fb4` (TNF specificity + §1.4 architecture) or `668429d`
  (XOR worked example) yields Strong Accept on the in-flight reviews.
- That outcome means the reviewer credits the TNF claim as
  meaningfully different from standard passes.
- In that case, this ontological framing is the deeper defense:
  "matrices are the computation, not the optimization of it."

If neither yields Strong Accept, the TNF claim is being read as
defensive rebranding by the reviewer noise. The right response is to
drop the novelty framing — say "the compiled program is a tensor
pipeline; we use standard compiler passes (constant folding, inlining,
beta reduction) plus rotation precomputation and slot allocation to
get there." No claim of a new normal form.
