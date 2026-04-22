# Open question: Surface syntax for binding-kind choice

## The question

Sutra has two binding kinds — **semantic** (learned-matrix bind,
`R @ filler` where R is fit from embedding pairs, acting in the
semantic subspace) and **rotation** (2D-Givens rotation into an
allocated slot of the synthetic subspace, for opaque variable
storage and array positions). See `planning/sutra-spec/binding.md`.

**How does a `.su` program tell the compiler which kind to use?**
The spec commits to *"the choice is visible to the programmer"*
and *"the compiler does not guess from context"* — but the actual
source-level syntax is not yet chosen.

## What we currently do

Nothing yet. Existing examples declare `vector r_name =
basis_vector("role_name");` and every `bind(role, filler)` call
compiles to sign-flip (which is retired as a design kind; see the
2026-04-21 findings note). There is no source-level way to say
"this is a semantic role" vs "this is a rotation-bound variable."
The migration off sign-flip onto rotation binding (STATUS.md queue
item 4) needs this syntax settled first.

## Why this is load-bearing

- The compiler must know the kind at **compile time** to do the
  right thing. Semantic bind requires a matrix-fitting step from
  paired training data (empirical-initiation phase). Rotation bind
  requires allocating a synthetic-subspace 2D plane to the slot.
  A single `bind(role, filler)` call site is ambiguous without a
  declaration.
- The programmer must know the kind when **writing** the code,
  because picking the wrong kind is a type error in program design
  (rotation bind on a relational role misses the meaning; semantic
  bind on a variable-storage slot is overkill and smears the value
  through semantic space).
- Getting the syntax wrong early propagates: every example, every
  doc, every compiler error message downstream has to be rewritten
  if we change how roles are declared. So it's worth getting
  right the first time.

## Candidates

### Candidate A — Keyword prefix on a shared declaration

```
semantic role located_in_country = learned_from("cities.tsv");
rotation role r_name = slot();
```

Two keywords (`semantic`, `rotation`) before a shared `role`
declaration. Explicit, greppable, impossible to misread. But
calling a rotation-bound *variable* a "role" feels wrong — it's
a variable, not a relation. Verbose on the common case.

### Candidate B — Different declaration keywords for different kinds

```
role located_in_country = learned_from("cities.tsv");  // semantic
var r_name : vector;                                     // rotation-bound
var x : fuzzy = +0.7;                                    // rotation-bound bool
var[16] slots : vector;                                  // rotation-bound array
```

`role` reserved for semantic relations; `var` for rotation-bound
storage. Matches standard programming intuition: `var` is the
familiar variable declaration from every imperative language, and
`role` is the Sutra-distinctive meaning-carrying binding primitive.
Pedagogically clean — a new reader learns "var is storage, role is
a learned relation" and the rest follows. Array / sequence
positions get a natural `var[N]` extension.

### Candidate C — Inferred from the right-hand-side constructor

```
role located_in_country = learned_from("cities.tsv");  // semantic
var r_name = slot();                                    // rotation-bound
```

The compiler picks the kind based on what constructor the RHS
calls: `learned_from(...)` → semantic; `slot()` or similar → rotation-bound.
This is essentially a less-strict variant of B — same forms, but
you could theoretically use either declaration keyword and the
RHS would tell. Risk: relies on the reader knowing the constructor
vocabulary.

### Candidate D — Type annotation as a parameter

```
role<semantic> located_in_country = learned_from(...);
role<rotation> r_name = slot(...);
```

Kind is a type parameter on `role`. Consistent with Sutra's
existing `map<vector, string>` generic-like syntax. But
`role<rotation>` reads oddly — a rotation-bound variable isn't
really "a role" in any sense, it's storage. The parameter-on-role
framing forces the rotation-bound kind into the role vocabulary.

### Candidate E — Uniform declaration, kind chosen at bind site

```
role X = ...;
bind_semantic(X, filler);
bind_rotation(X, filler);
```

Rejected — violates the "visible at declaration" commitment and
allows the same role to be used in both kinds, which is incoherent
given the two kinds act on different subspaces.

## Tradeoffs

| Candidate | Visible at decl? | Greppable? | Natural words? | Pedagogy? | Future-kind-friendly? |
|-----------|------------------|------------|----------------|-----------|----------------------|
| A (keyword prefix) | yes | yes | "rotation role" awkward | okay | adds a word per kind |
| **B (different keyword)** | **yes** | **yes** | **clean** (`var` / `role`) | **best** | adds a word per kind |
| C (inferred from RHS) | implicit | partial | clean | okay — readers need to know RHS | RHS constructors multiply |
| D (type annotation) | yes | yes | `role<rotation>` odd | so-so | extends cleanly |
| E (per-site) | no | at call site | confusing | bad | easy but wrong |

## Recommendation: Candidate B

**Use `role` for semantic bindings and `var` for rotation-bound
variables.**

Why:

- **Pedagogical clarity.** `var x = 3` reads the same in every
  imperative language on Earth; a new reader has no friction. `role`
  is the one new vocabulary term they need to learn, and it's
  reserved for the Sutra-distinctive thing (semantic relations).
  Two keywords, each doing one job.
- **Maps onto what each kind actually is.** Rotation-bound things
  really are variables — mutable-looking slots whose stored value
  can be reassigned. Semantic-bound things really are roles —
  relations that carry meaning. The vocabulary follows the design,
  not the other way around.
- **Greppable and visible at declaration.** `grep '^role '` and
  `grep '^var '` find the two kinds distinctly. No reader has to
  trace the RHS constructor to see what kind a binding is.
- **Array / sequence positions slot in naturally** as `var[N]`.
  Canonical axes (truth, etc.) don't need a new keyword — they're
  language-level constants, not user declarations.
- **The evangelism argument** (see CLAUDE.md and the user's notes
  on VSA being a small, neglected field): Sutra is likely a primary
  entry point for new readers. Every syntactic choice that reduces
  friction pays compounding returns on adoption.

The one cost is that `role` becomes a narrow, Sutra-specific
vocabulary term. That's acceptable — the whole language is
Sutra-specific, and `role` is a clean handle on the innovation.
The loose English sense of "role" (as in "role-filler binding")
still roughly matches — learned relations *are* roles in the
classical VSA sense — so it's not jarring vocabulary.

## What resolving this looks like

If the user agrees with B:

- Update `planning/sutra-spec/binding.md` with a "Surface syntax"
  section naming `role` and `var` as the declaration forms.
- Pick the concrete syntax for `learned_from(...)` and `slot()`
  (or whatever the RHS constructors are called).
- Update the three demo programs (`hello_world`, `fuzzy_branching`,
  `role_filler_record`) to use `var` instead of the current
  `vector r_name = basis_vector(...)` pattern. The demos don't use
  learned-matrix binding today, so `role` declarations will come
  with new semantic-binding demos.
- Update `sdk/sutra-compiler/` to accept the new declaration forms.
- Move this doc out of `open-questions/` — it becomes the spec
  section on surface syntax.

If the user prefers a different candidate, the writeup in
`binding.md` follows the chosen form instead.

## What we don't know

1. **What does the semantic-role RHS constructor look like?**
   `learned_from("file.tsv")` is a placeholder — the actual
   constructor depends on how training data is passed and how the
   empirical-initiation phase is triggered. See
   `planning/sutra-spec/binding.md` §"Semantic binding" — still
   open there too.
2. **What does the rotation-bound RHS constructor look like?**
   `slot()` as a placeholder; could be `var x : vector;` (no RHS
   at all — just a declaration that allocates a synthetic-subspace
   slot) or `var x = <initial value>;` or something else. Open.
3. **Initialization semantics for `var`.** Does `var x : vector`
   start at zero on the truth axis (i.e. neither true nor false),
   or at some designated sentinel? Probably zero — but worth
   specifying.

These are small open questions downstream of the keyword choice;
they don't block B.

## Prior-art audit pending

The surface-syntax choice is language-design territory that
doesn't strongly overlap with VSA literature. The relevant priors
are from type-system and declaration-syntax design (Haskell type
classes, Rust traits, OCaml modules, Scala implicits, Swift
declarations). A sweep of those before publishing the language spec
is on the todo list. Dev-level work proceeds without the audit;
publication-level framing waits for it.
