# Machine-checked λ₂ / gap VALUE for the concrete 8-state single-spin-flip Gibbs kernel

**Status: OPEN — named, NOT green-lit (Emma).** Do not start without her go; see `queue.md`
§ "FV PAPER" (the whole FV-paper disposition is NEEDS-DECISION and this is its only remaining leg).

## The question

`applyP_gap_contraction` (`fv-lean/mathlib/Convergence.lean:346`, CI-green 2026-06-30) closes
*gap ⇒ geometric decay* with the spectral gap `γ` as a **scalar Rayleigh hypothesis**: for
mean-zero `h`, `|⟨Ph,h⟩_π| ≤ (1−γ)‖h‖²_π`. What is NOT machine-checked is the **value** of that
gap for the literal 8-state single-spin-flip kernel: the measured `γ = 0.0397` is currently an
*input* the theorem is instantiated with, not a number Lean derives from the matrix entries.
The open item is a machine-checked `λ₂`/eigenvalue (or equivalent Rayleigh) bound computed FROM
the concrete kernel entries, discharging the hypothesis instead of assuming it.

## What we currently do and why

The FV paper states `γ = 0.0397` as a measurement (DEVLOG 2026-07-04) and keeps the Lean claim
conditional on the Rayleigh hypothesis. This is honest and the paper's "not claiming" section
covers it; the paper reached Accept (v96) on this framing.

## What we know about the route

A per-edge conductance bound **cannot work**: it can't see the zeros between non-neighbouring
states (single-spin-flip kernels have `P_{st} = 0` for Hamming distance > 1), so it degrades to
a vacuous bound. The named viable route is the **canonical-paths comparison method** (route each
pair `s→t` through a Hamming path, bound congestion), which yields a `λ₂` bound from the matrix
entries. Building that comparison machinery in Lean/Mathlib is the actual work — it is a real
formalization project, not an assembly step.

## What would close it

Either (a) Emma green-lights the leg → build canonical-paths in `fv-lean/mathlib/`, verified via
`fv-lean-mathlib-ci` (local Windows hits MAX_PATH — iterate via branch pushes), nothing counts
until `lean` accepts with no `sorryAx`; or (b) Emma declares the FV paper finished as-is → the
measured `γ` stays a documented measurement and this dossier is retired as
won't-do-unless-reopened.
