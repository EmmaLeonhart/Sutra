# No null in Sutra

**Opened:** 2026-04-23 (session that added `unknown`).
**Status:** Design position stated by user; not yet enforced in the
implementation. Captured so the "why" doesn't get lost when the
compile-time check eventually lands.

## The position

> The entire concept of something being null doesn't exist in this
> language. Null would be solely a compilation-time thing, because
> your code can't compile if you have null. It would be solely a
> compilation-time thing.

Null is not a runtime value. There is no `null` keyword producing
`null` values in expressions, no null-checks on dereferences, no
null-coalescing operator. Sutra's ground state is "a vector in the
extended-state layout," not "a pointer that may or may not point to
something."

This is not "null is rarely useful." It is "null doesn't exist."

## Why the language can afford this

Sutra's primitive values are all **vectors** in the extended-state
layout (see `planning/findings/2026-04-21-extended-state-and-rotation-
binding.md` and the "primitive classes" addendum in
`literals-and-auto-embedding.md`). A vector always has a
representation — zero-filled if nothing more is known. "Absent"
values that would be null in other languages already have a natural
representative in Sutra:

- A fuzzy / bool / trit without a value: the neutral point on the
  truth axis — `unknown`. Zero coordinate, not a null pointer.
- An int / float without a value: zero on the number axis. Same
  story.
- A vector without a value: the zero vector.

The neutral point IS the value. There is nothing to stand in for
"we don't have one yet" other than the zero/neutral representative
— and that representative is meaningful, not a sentinel.

## What happens when a programmer declares but doesn't assign

The question the user raised:

> Yes, you can have a situation where you declare the name of a
> variable and then later on use it in the code. I'm not going to
> say you can't do that. I think it's sensible that you'd be able
> to do it. It's just that, in that situation, the code is just
> not going to compile unless you later on declared it to something.

So the compile-time contract is: **every variable must be assigned
before its first read.** This is an initialize-before-use check,
enforced statically. The compiler refuses a program where a
variable's value is read along a path where no assignment precedes
it. The error is at compile time; no runtime "uninitialized" value
escapes into the substrate.

This is distinct from "null-check" languages in two ways:

1. The check is static, not runtime. A program either compiles or
   it doesn't. No `NullPointerException` class of error exists at
   runtime.
2. The default value — when a variable is assigned but the
   programmer chose a neutral starting point — is the semantically
   meaningful neutral for that type (`unknown` on the truth axis,
   `0` on the number axis, zero-vector on a vector slot). Not a
   sentinel.

## The imperative-style tension the user flagged

> You can't really, but it feels very imperative. I might even be
> able to talk you out of doing it because it's so imperative.
> Sorry, I might block it because it is so imperative. I don't
> think you could do this in an imperative style. Imperative style
> assigns something a different value at a different point.
> Basically, all this would just be that you're not actually
> meaningfully changing it. You're not changing a pointer or memory
> location at all when you do this; you're just doing this stuff.

The user's own hesitation here is about the `var x; … x = foo;`
*pattern* — declaring a name without an initializer and assigning
later. That pattern reads as imperative mutation even if Sutra's
underlying model is functional. Two interpretations:

- **A. Allow it.** A variable is just a name. `var x;` binds the
  name without a value. `x = foo;` is the next binding of `x` to
  `foo`. Not really "mutation" — it's rebinding, same as in any
  language with let-rebinding semantics. Compiler enforces
  initialize-before-use.
- **B. Block it.** The pattern is too visually imperative; Sutra
  should require `var x = <initial_value>;` at declaration time.
  Gets rid of the uninitialized case entirely, at the cost of
  forcing the programmer to pick a neutral (`unknown`, `0`, etc.)
  up front.

User leaned toward blocking (B) — "I might even be able to talk
you out of doing it because it's so imperative" — but left the
door open. The decision isn't made yet.

## What the current implementation does

The current parser / validator allows `var x : TYPE;` (uninitialized
var-colon form) for vector / fuzzy / bool / int / scalar / trit /
luk, emitting a zero-of-the-type as the default. This is the
reading that option A would accept and that option B would forbid.

No initialize-before-use check exists yet — a program that reads
from an uninitialized variable along some path will currently
compile and run with the type's default value. If the decision goes
to option B, the `var x : TYPE;` form gets a deprecation warning
and eventually an error.

## Candidate resolutions

- **A. Keep `var x : TYPE;` + add initialize-before-use check.**
  The permissive path. The uninitialized-var syntactic form
  continues to exist; the check makes sure no un-assigned variable
  is ever read.
- **B. Forbid `var x : TYPE;` without an initializer.** The
  restrictive path. Every declaration must carry an initializer.
  No `null`-shaped corner of the language at all.
- **C. Compromise: allow it, but require the programmer to assign
  `unknown` or a type-appropriate neutral explicitly.** So
  `fuzzy f = unknown;` is fine; `fuzzy f;` is not.

C is close to B in spirit but shifts the burden from "the syntax
forbids this" to "the programmer must name what the neutral is."
Neither implemented nor blocked yet; the current behavior is option
A minus the initialize-before-use check.

## What this doesn't preclude

- Dict/map lookup returning an "absent" signal. That's not null;
  it's a discriminated-union result (`Option<V>` in other
  languages, or a pair-of-vectors convention in Sutra). Separate
  question.
- User-defined classes that model absence explicitly. If someone
  writes an `Optional<T>` class, they can have explicit `present`
  / `absent` states. That's their class's semantics, not a
  language-level null.

## Pointers

- Related: `planning/open-questions/zero-as-explicit-neutrality.md`
  (why the neutral point is a first-class value, not a degenerate
  form of anything).
- Related: `planning/open-questions/literals-and-auto-embedding.md`
  §"Primitive classes" (why every value is a vector, so "absent"
  has a natural representative rather than requiring a null
  sentinel).
- Current var-colon handling: `codegen_flybrain.py:_translate_var_decl`
  around line 451.
