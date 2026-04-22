# Open question: Surface syntax for binding-kind choice

## The question

Sutra has (at least) two first-class binding kinds — **semantic**
(learned-matrix bind, `R @ filler` where R is fit from embedding
pairs) and **structural** (sign-flip bind, `filler * sign(role)`,
for opaque variable storage). See `planning/sutra-spec/binding.md`.

**How does a `.su` program tell the compiler which kind to use for
a given role?** The spec commits to *"the choice is visible to the
programmer"* and *"the compiler does not guess from context"* —
but the actual source-level syntax is not settled.

## What we currently do

Nothing. Every `bind(role, filler)` call in existing examples
compiles to sign-flip, because that's the only implementation. A
role is declared as `vector r_name = basis_vector("role_name");`,
and there's no place in the declaration to say what kind of bind
operation the role participates in.

This is fine for the current three demos (`hello_world`,
`fuzzy_branching`, `role_filler_record`) — their roles genuinely
are opaque storage handles, so sign-flip is correct. It breaks the
moment we add a semantic role like `R_located_in_country`, because
there is no syntax to declare it.

## Why this is load-bearing

- The compiler must know the kind at **compile time** to do the
  right thing. Semantic bind requires a matrix-fitting step from
  paired training data (empirical-initiation phase). Structural
  bind does not. A single `bind(role, filler)` call site is
  ambiguous without a declaration.
- The programmer must know the kind when **writing** the code,
  because picking the wrong kind is a type error in program design
  (semantic bind on an opaque-storage role is overkill; structural
  bind on a relational role misses the meaning). Making the kind
  invisible would hide a real distinction.
- Getting the syntax wrong early propagates: every example, every
  doc, every compiler error message downstream has to be rewritten
  if we change how roles are declared.

## Candidate syntaxes

### Candidate A — Keyword on declaration

```
semantic role located_in_country = learned_from("cities_and_countries.tsv");
structural role r_name = basis_vector("role_name");
```

Two keywords (`semantic`, `structural`) before `role`. Explicit,
greppable, impossible to misread. Verbose on the common case.

### Candidate B — Different declaration forms

```
role located_in_country = learned_from("cities_and_countries.tsv");
handle r_name = basis_vector("role_name");
```

`role` reserved for semantic bind; `handle` (or `slot`, `tag`,
`key`) for structural bind. Short; the two declarations read very
differently. Risk: `role` previously meant "any bind target"; this
narrows its meaning, which may break older examples and docs.

### Candidate C — Inferred from presence of training data

```
role located_in_country = learned_from("cities_and_countries.tsv"); // semantic
role r_name = basis_vector("role_name");                            // structural
```

Same keyword (`role`) in both cases. The RHS form is what tells
the compiler the kind: `learned_from(...)` → semantic; a raw
`basis_vector(...)` or similar → structural. Concise. Risk: the
kind is visible only via the RHS idiom, which is less greppable
than an explicit keyword; also risks feeling "magical" for new
readers.

### Candidate D — Type annotation

```
role<semantic> located_in_country = learned_from(...);
role<structural> r_name = basis_vector(...);
```

Kind is a type parameter on `role`. Consistent with Sutra's
existing `map<vector, string>` generic-like syntax. Allows future
kinds to slot in (`role<sparse>`, `role<attention>`). A little
noisy.

### Candidate E — No keyword; explicit at bind site

```
role located_in_country = ...;
role r_name = ...;

// At bind site:
bind_semantic(located_in_country, city);
bind_structural(r_name, f_alice);
```

Declarations are uniform; the kind is chosen per-call at the bind
site. Maximal flexibility — a single role could participate in both
kinds of bind. Risk: the kind becomes invisible at the declaration,
defeating the "choice is visible at declaration" commitment. Also
allows the same role in two kinds, which is probably incoherent.

## Tradeoffs at a glance

| Candidate | Visible at decl? | Greppable? | Verbose? | Future-kind-friendly? |
|-----------|------------------|------------|----------|----------------------|
| A (keyword prefix) | yes | yes | yes | needs one word per kind |
| B (different keyword) | yes | yes | no | needs one word per kind |
| C (inferred from RHS) | implicit | no | no | RHS idioms multiply |
| D (type annotation) | yes | yes | a bit | yes, cleanly |
| E (per-site) | no | at call site | no | easy but violates the spec |

## What we don't know

1. **Which candidate feels right to the user?** The spec says the
   choice must be visible at the declaration; that rules out E.
   Between A–D the tradeoffs are largely stylistic.
2. **Will there be a third kind soon enough to matter?** If yes,
   D (generic parameter) pays off. If the two kinds are stable for
   a while, A or B is simpler.
3. **How does the `learned_from(...)` side actually look?** Spec
   work pending — see `planning/sutra-spec/binding.md` §"Semantic
   binding." Until this is decided, candidate C (kind inferred
   from RHS) is impossible to evaluate fully.
4. **Is there a default?** If most programs use one kind more than
   the other, the other can carry the keyword and the default stays
   uncluttered (e.g. `role` = semantic by default; `handle` for
   structural — or the reverse). Picking a default is itself a
   stance on what Sutra is for.

## What resolving this looks like

- User picks a candidate (or proposes a different one).
- `planning/sutra-spec/binding.md` gets a "Surface syntax" section
  with the chosen form and at least one example of each kind.
- Compiler adds the new declaration form (`sdk/sutra-compiler/`);
  existing examples either stay on the old form (if backwards-
  compatible) or are ported.
- This doc moves out of `open-questions/` — it becomes part of the
  spec.
