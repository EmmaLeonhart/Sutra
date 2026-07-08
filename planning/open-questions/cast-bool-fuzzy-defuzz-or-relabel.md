# Is `(bool) fuzzy` a free relabel or an implicit defuzzification?

## The question

When cast lowering shipped (2026-07-07, `types.md` § "The shipped lowering table"), `(bool) f`
on a fuzzy value was implemented as a **free relabel** — same truth-axis value, only the static
type changes; polarization to ±1 stays the explicit `defuzzy(f)` / `is_true` surface. But the
corpus fixture `sdk/sutra-compiler/tests/corpus/valid/07_casts.su` carried an older comment
claiming the opposite convention: "`(bool)` on a fuzzy performs defuzzy — it's the one
cross-type cast the spec allows because it's really a recursive is_true." (Comment updated to
the shipped semantics; this doc preserves the fork.)

## What we do now and why

Relabel. Reasons: (a) `types.md` § Casting makes relabel the DEFAULT and requires projection
casts (the defuzz kind) to be explicit; (b) an implicit defuzz inside a cast would hide a real
transformation (iterated polarizer) behind syntax that elsewhere costs nothing; (c) `if (f)`
already thresholds the truth axis, so the relabel changes no branch behaviour; (d) `defuzzy` /
`defuzzify_trit` exist precisely as the explicit polarizer surface.

## Why the other side has force

The corpus comment's framing came from somewhere: `bool` in the spec carries a defuzz-counter
design (types.md § open questions), which suggests bool-ness is *earned by defuzz steps*, not
just labeled. If bool is "a fuzzy that has been defuzzed at least once," then `(bool) f`
silently minting a bool without a defuzz step breaks that invariant.

## What would close it

Emma's call on what `bool` MEANS: a label on the truth axis (relabel is right) or a
defuzz-count-carrying refinement type (the cast should either defuzz or be rejected). If the
defuzz-counter design lands, revisit `(bool)` lowering in the same change.
