# Sutra as a numerical / finance language, not just an AI language

**Date opened:** 2026-04-28.
**Status:** Parking lot for positioning material harvested from the
KART chats triage. Not a commitment that Sutra targets these markets
— the technical contributions are real (compile-time math
approximation, type-system units, batch-as-tensor-multiply) but the
go-to-market choice is downstream of when/whether the paper lands.

This is a sister doc to `sutra-paper-draft.md`. The paper draft owns
the *technical* novelty story; this doc owns the *target audience* and
*comparison* story. They cite each other but stay separated so the
paper doesn't get cluttered with market-strategy material.

## The pitch in one paragraph

Sutra is an AI-adjacent language, but the same compiler architecture
that makes it work for AI happens to make it a serious numerical /
finance language too. Compile-time math approximation with a TOML
precision contract, units of measure as ordinary types (not a bolted-
on compiler feature), and portfolio-scale batching as a single tensor
multiply are all things F# and Julia don't do — not because they
chose not to, but because their compiler architectures don't admit
them.

## The math comparison

### Julia

Julia's whole bet is "JIT compile at runtime to make dynamic
numerical code fast." It calls into `libopenlibm` for transcendentals
(a portable libm) and gets correctly-rounded double precision. There
is no "give me 6 digits and go fast" option — you always get full
libm precision at full libm cost. `BigFloat` exists for arbitrary
precision (slower, not faster) but no fast/lossy direction.

**Sutra contrast:** precision is a compile-time architectural
decision. The user picks `1e-3` for game work or `1e-12` for physics
in `atman.toml`, the compiler emits a Chebyshev polynomial of the
appropriate degree as a tensor op, and the result is deterministic,
auditable, and runs on the same substrate as the rest of the program.
Julia is fast dynamic numerical code; Sutra is compiled mathematical
computation native to the same substrate as ML models.

### F#

F# is essentially "C# with nicer syntax and pattern matching" — its
numeric story is whatever .NET's BCL gives you, which is IEEE 754 and
the system math library. There is no special compilation story for
math, no tensor awareness, nothing. F# is genuinely not hard to
compete with on this axis.

**The harder competitor is Julia, not F#.** F# is a positioning
target because of *where* it's used (.NET-bound finance shops) more
than because of *what* it does technically.

## The finance angle

F# is widely used in quant finance for:

- Quantitative modeling — derivative pricing, risk calculations
- Domain-specific DSLs for financial instruments
- Type-safe units of measure (compile-time `Dollar` vs `Euro`)
- Interop with the .NET ecosystem banks already run on

Sutra hits two finance pain points harder:

1. **Precision contracts for regulatory audit.** Finance often needs
   to know exactly what precision a calculation ran at, for
   regulatory and audit reasons. F# / Julia hide this behind libm.
   Sutra exposes it as a compile-time TOML setting — the precision
   is auditable from `atman.toml`, not reverse-engineered from
   library version notes.
2. **Batch-as-tensor-multiply over portfolios.** A pricing function
   compiles to a matrix; a portfolio is a vector of instruments;
   pricing the portfolio is one matrix-vector multiply. Monte Carlo
   over thousands of paths is one batched matmul. The data-parallel
   shape that finance batches naturally have lines up with what the
   compiler emits.

The compiled tensor operation is also more inspectable and
deterministic than a JIT-compiled libm call chain — relevant for
audit trails.

The institutional reality: finance runs on Windows .NET out of
*inertia*, not because it's good. That's a weakness in F#'s position,
not a moat.

## Units of measure as ordinary types

F# has units of measure as a bolted-on compiler feature — somewhat
magical, separate from the rest of the type system. They erase at
runtime (purely a compile-time fiction in the IL), so you get the
safety but can't reflect on units, can't serialize them meaningfully,
can't use them as runtime entities.

In Sutra, units of measure fall out of the type system you already
have. `Dollar` is just a type, `Euro` is just a type, and adding a
`Dollar` to a `Euro` is a type error the same way any other type
mismatch is. They compose:

- `Dollar` — a scalar
- `Portfolio<Dollar>` — a vector of dollar-denominated positions
- A pricing function `Bond<Dollar>` → `PresentValue<Dollar>` —
  compiles to a matrix

No special "units" concept needed. The types *are* the units. And
because Sutra's types are real classes (not erased annotations), the
units survive into runtime — serializable, reflectable, real.

### Currency stdlib design (sketch)

A `Currency` base class in the stdlib gives subclasses inherited
financial semantics:

- `Dollar + Dollar` → `Dollar`. Same-currency arithmetic works
  through the inherited `Number` operators.
- `Dollar + Euro` → **type error**. Cross-currency arithmetic is
  rejected at compile time — there is no implicit exchange rate.
- Conversion goes through an explicit `ExchangeMatrix<Dollar, Euro>`:

      exchange : ExchangeMatrix<Dollar, Euro> -> Dollar -> Euro

  Mathematically a one-entry scalar multiply, but the type
  signature forces the conversion to be visible in source — exactly
  what a financial auditor wants to see.
- Portfolios compose the same way:

      Portfolio<Dollar> + Portfolio<Dollar>          // fine
      Portfolio<Dollar> + Portfolio<Euro>            // type error
      normalize(Portfolio<Dollar>, Portfolio<Euro>,
                ExchangeMatrix)                      // explicit

This isn't special-casing. `Currency` defines `+` to require
matching type parameters — a normal generic constraint. Everything
else falls out from the tensor hierarchy as normal. The standard
library story is: `Currency` gives you the financial semantics,
`Number` gives you the math, `Tensor` gives you the operations, and
you pick where in that hierarchy your domain concept lives.

**Implementation status** (2026-04-28): the `Currency` stdlib base
class is gated on user-class operator support landing first. Today
operators are defined on primitive classes only (see
`planning/sutra-spec/types.md` § "Classes exist — but only at
compile time" and `todo.md` § "[Pre-YC] Ontology — make the class
system real"). When user classes can carry operator implementations
that subclasses inherit, `Currency` is the canonical demo of the
ontology working end-to-end — same hook as the F# units-of-measure
replacement story above.

## Who Julia / F# can't serve well

The audience that Sutra's compiler architecture serves naturally:

- People who need **deterministic compile-time guarantees** about
  what computation runs (regulatory, embedded, safety-critical).
- People deploying to **GPU / TPU** where you want everything in
  tensor land already.
- People who want **explicit precision contracts** rather than
  whatever-libm-gives-you.
- **AI-adjacent work** where data is already in hyperdimensional
  space and switching representations to "do math" is wasteful.

That's a coherent, defensible niche. It is not "worse Julia" — it's
a different thing.

## What this doc is not

- A commitment that Sutra targets finance specifically.
- A commitment that the F# / Julia comparison goes in any paper.
- A roadmap.

It is harvested positioning material kept out of the paper draft so
the paper draft can stay focused on technical novelty. If Sutra
eventually gets a "use cases" section in the paper or a "who is this
for" page on the docs site, this is where the language for those
sections starts.
