# `x == 0` reads NEUTRAL at runtime — cosine equality is degenerate at the zero vector (2026-07-08)

Round-23 real-program-reach drive. FizzBuzz — the canonical second program — is unwritable:
`(n % 3) == 0` silently returns the truth-axis neutral, every select score ties, and the
string superposition decodes as garbage codepoints.

## Measured (runtime_dim=16, torch backend)

| expression | truth reading |
|---|---|
| `0.0 == 0` (both literals) | **1.0** — but only because preeval CONSTANT-FOLDS it before the substrate is involved |
| `(16 % 3) == 1` (runtime, nonzero) | **1.0** |
| `(15 % 3) == 0` (runtime zero) | **0.0 — NEUTRAL** |

Mechanism: `==` is cosine similarity projected onto the truth axis, and cos(0⃗, v) is 0/‖0‖ —
degenerate. A runtime value that IS zero cannot cosine-match anything, including zero itself.
Zero-testing is the single most common comparison in real programs (divisibility, emptiness,
loop termination), so this is a first-order reach blocker, adjacent to the standing
`<=`/`>=`-ties NEEDS-DECISION (same tanh/cosine family) and the
`zero-as-explicit-neutrality` open question.

## Candidate mechanisms (design needed — `==` is a paper-cited trainable surface, so not a drive-by patch)

1. **Exact zero indicator on the number family:** for number-typed operands, lower `x == 0`
   (and `x == y` generally) through the neural-Unix keystone `relu(1 − |x−y|·k)` on the
   real axis — measured gap 1.0 at integer spacing, no residual, all tensor ops. Keeps
   cosine-`==` for vector/semantic operands.
2. **Euclidean route for the number family** — the `cosine-vs-euclidean` open question's
   territory; magnitude-aware, differentiable, but changes the trained-T story.

Both change the semantics of a shipped trainable surface (the `==` cosine scale T is the one
SHIPPED constrain-train instance), so the choice needs Emma's eyes even though the bug is
unambiguous. Until then: FizzBuzz-class programs have no working zero test.
