# Axons

> **Second cut, 2026-05-07.** This replaces the morning's first cut
> with the user's expanded position from later the same day. The
> surface API resembles a hash map *syntactically*, but axons are
> not hash maps — they're a bundle of named variables (closer to a
> Haskell-monad-style structuring construct than a runtime dict).

## What an axon actually is

An axon is **a bundle of named variables that gets passed as a single
value**. Think of it as a structured environment, or a control object
that carries the named values one piece of code wants to hand to
another. The user's tightest framing: *"an axon is just a collection
of defined objects — they're a bundle of variables and control
objects. They look like hash maps superficially, but they aren't.
They're closer to what Haskell monads are."*

### No declared schema

There is no compile-time declaration of which keys an axon contains.
There is one `Axon` class, with no type parameter; an axon value is
just a bundle of whatever the program added to it. The compiler does
not track "axon A has declared keys X, Y, Z." There is no
`interface FooAxon { x: int; y: int }`. There is no
`Axon<{x: int, y: int}>`.

The only thing the compiler tracks is **dataflow**: which keys the
receiving code reads, and which keys the producing code writes. That
analysis drives the lazy evaluation rule below, but it is not a
type-system feature — there is no error class for "this function
returns an axon missing the `cat` key." A function that reads a key
that was never added gets whatever the substrate produces from
unbinding a slot that was never bound (typically noise; see
§"Behavior on missing key" in the open questions).

This is what the user means by *"axons do not exist at compile time
[as schemas]."* Each axon is a runtime value (the materialized
bundle); at the type level it is just `Axon`, with no further
structure.

### Like a Haskell monad

The closest existing-language analogy the user has reached for is
Haskell monads. The point of the analogy is:

- A Haskell `IO` value isn't a compile-time-known structured object
  with declared internal fields; it's a value that flows through
  monadic composition, with no schema you can interrogate. Likewise
  for `Maybe`, `State`, or anything else in the `Monad` type class.
- A Sutra axon flows through axon-passing functions the same way.
  The function takes an axon, possibly reads some keys, possibly
  writes some keys, and returns an axon. Composition is just
  function composition. There is no axon-shape contract that the
  type system enforces.

The analogy isn't a category-theory claim. Sutra is not asserting
that axons satisfy the monad laws. It is recording how the user
thinks axons should *feel* to program against: a way to carry
structure through code, not a typed container with a fixed schema.

### Axons are not hash maps

This needs stating up front because the surface API in the next
section looks hash-map-shaped and the temptation to treat axons as
dicts will be permanent.

A hash map's defining operation is **runtime input → runtime output**:
you give it a key value computed at runtime, it returns the
corresponding stored value. That operation does not exist on axons.
There is no axon equivalent of:

```
String s = compute_key();
Object v = my_hash_map.get(s);    // hash map: legal
Object v = my_axon.item(s);       // axon: NOT a thing the language does
```

The string in `a.item("cat")` is **a compile-time identifier**, not a
runtime key. It is closer to the field name in `a.cat` than to a
hash-map lookup — the two forms compile to the same operation, and
both are field access on a compile-time-known name. The quote marks
in the string-form exist for ergonomic / transpilation reasons (a
transpiler can emit `a.item("varname")` mechanically without parsing
identifier rules), not because there's a runtime key resolution
happening.

A handful of consequences fall directly out of "no runtime key
lookup":

- No iteration over an axon's contents. There is no `for (k in a)`,
  no `keys()`, no `entries()`, and there will not be.
- No dynamic membership test. `a.has("cat")` where the key is
  computed at runtime is not a thing.
- No size query. `a.length` is not a thing — the runtime doesn't
  carry a registry of which names have been added.
- No key-set comparison between axons. Two axons aren't compared by
  their materialized key sets at runtime.

These restrictions are what **enables** the lazy evaluation rule
below. A real hash map could not be lazy-across-boundaries, because
the receiver could ask "what keys do I have" and force materialization
of everything. An axon is closed enough at compile time that the
compiler can prune the whole graph of unreferenced names safely.

The cleanest one-line framing the user has given is: **axons are just
variables — they look like hash maps but they're really control
objects.** Treat them that way and the rest of the design falls out.

## The surface API

The user-facing API resembles a dict in *syntax*, even though the
operational semantics aren't dict semantics:

```
Axon a = new Axon();
a.add("cat", cat);
Cat c = a.item("cat");
```

The accessor is **`item`**, not `get`. `item` is settable, so it works
on the left-hand side too:

```
a.item("i") = a.item("i") + 1;
a.item("i")++;                 // sugar for the line above
```

Property-style access — `a.cat` — is preferred where it's ergonomic and
the key is statically known. The compiler is allowed to lower
property-style access to the same `item` mechanism; programs should not
depend on the two forms being observably distinct.

There is deliberately no `get` method. The user has flagged `get` as
unintuitive and it should not appear in any code-gen path or stdlib
shim.

### The mutating-looking syntax is sugar; the compiler usually elides the axon entirely

The surface API *looks* imperative — `add`, `item(k) = ...`,
`item(k)++` — but that appearance is **ergonomic sugar**. The
mental model "every mutation produces a new axon" overstates what
actually happens. The truthier model:

> When you write `a.item("pi") += 1`, the compiler treats it as
> SSA-style renaming on the underlying variable. The "old" `pi`
> becomes some `pi_2` internally. **No new axon is constructed
> unless an axon actually has to cross a function or loop boundary.**

Inside a function body, between loop-iteration boundaries, there
isn't really an axon at all. There are just variables. The
`a.item(k)` syntax lets you address those variables through the
axon's name as a syntactic convenience (essential for transpiling
imperative languages where everything is variable mutation), but
the compiler sees through the surface and operates on the
underlying values.

The original axon — the one any other reference still points to —
is unchanged. This is the same shape as a state monad in a
functional language: the *appearance* of mutation, achieved
through threading values forward, with the compiler fusing the
chain at compile time so no intermediate axon is materialized.

Stating this rule directly: **axons are completely un-imperative
aside from the ergonomics.** Don't take the imperative-looking
surface as license to assume there is a mutable hash map
underneath. There isn't. Treat `a.item(k) = v` the way Haskell
would treat a state-monad update — a step in a functional
computation, not a write to a memory cell, and very often not even
a new value construction.

The reason the surface is sugared at all is to make transpiling
side-effect-heavy languages (C, JS) tractable. Hand-written Sutra
can stay closer to the value-passing form without losing anything
semantically.

### Axons appear in exactly four positions

A consequence of "axons are compile-time-elided unless a boundary
crossing forces them" is that axons can meaningfully appear in
only four positions in a program:

1. **The input of a function** (the parameter).
2. **The output of a function** (the return).
3. **The start of a loop iteration** (the loop's input state).
4. **The end of a loop iteration** (the loop's output state, which
   becomes the next iteration's input).

These four positions are not really four distinct things — they
collapse to one. **A loop is a mini-function that doesn't have
its own file**, with a recurring-network shape that explicitly
passes information in a circle. Position (3) is the loop's
input; position (4) is the loop's output, which feeds back into
position (3) for the next iteration. So axons exist at *function
boundaries*, full stop, where "function" is read broadly enough
to include the implicit self-recursive mini-function that a loop
becomes after lowering.

Anywhere else, the axon is **syntactic salt**: you can write code
that constructs an axon and adds entries to it and never returns
it or feeds it to a loop, but the compiler erases the axon
entirely. The local variables you set on it become ordinary
variables in scope; the axon-object itself never materializes.

This is not a restriction the language enforces with an error —
you can write the salt and it compiles — but stylistically and
performance-wise it adds nothing. Idiomatic Sutra constructs
axons only when an axon actually has to cross one of these
boundaries.

## No generics; per-entry class tags

`Axon` is a single non-generic class. There is no `Axon<Cat>`. Values
inside an axon can be of any type — the carrier is monomorphic.

What axons *do* support is a **per-entry class tag**: each stored
value carries an indication of what class it was at the time of
insertion. So when you `a.add("cat", c)` where `c : Cat`, the entry
remembers it was a `Cat`, and `a.item("cat")` can give back a `Cat`
(rather than a bare `vector` you have to cast). The user has flagged
that this matters — *"the class is important"* — but axons are not
*limited* by class. You can put anything in any entry; the tag is a
suggestion to the type system about what to expect coming back out,
not a constraint on what can go in.

This is the same shape as Java's `Map<String, Object>` enriched with
runtime-class info: the carrier is monomorphic, the values are
heterogeneous, and there is enough metadata at the entry level for
retrieval to give back something better than `Object`.

> **Open question.** Exact mechanics of the per-entry tag — runtime
> cast vs. compile-time-erased static check; how strict the
> "suggestion" is (warn on mismatch, error on mismatch, silent?);
> whether the tag is a class-level identity or a richer structural
> shape. The user has resolved that tags exist; the form they take
> is still open.

## Why bundle-of-variables, not a record or a real hash map

A program could in principle pass values through a declared record
type (Java struct, Haskell record, TS interface) or through a real
runtime hash map. Sutra picks neither, and the bundle-of-variables
shape gives it three properties that the alternatives don't:

1. **Composable without parsing.** Two axons combine into a third by
   bundling. No serialization, no schema validation, no version
   negotiation. The receiver decodes the key it needs by `item("cat")`.
   A declared record can't compose two records of different declared
   shapes; an axon can.
2. **Differentiable end-to-end.** Gradients flow through `add` and
   `item` exactly the way they flow through any tensor operation. A
   computation that crosses many function calls remains one smooth
   function. A real hash map breaks differentiability at every
   lookup.
3. **Same shape as model inputs.** A model that consumes embeddings
   is already prepared to consume what an `item` call extracts. An
   LLM's activation residual, an embedding-model output, and a Sutra
   structured return value are the same kind of tensor.

These three are the user's reason for treating axons as the *currency*
of Sutra: in 95% of programs, a `.su` function takes an axon and
returns an axon.

## How axons are stored on the substrate

Underneath the surface API, an axon is a fixed-width vector produced
by **rotation binding** over a codebook of roles:

```
axon = bundle( bind(R_cat, F_cat),
               bind(R_dog, F_dog),
               bind(R_mouse, F_mouse) )
```

The string key (`"cat"`) maps at compile time to a unit-norm rotation
operator (`R_cat`); the stored value (`cat`) is the filler. Insertion
is `bundle + bind`; retrieval is `unbind`; the compile-time simplifier
folds chains into cached matrices.

This is the same `bind` / `unbind` / `bundle` machinery `binding.md`
and `operations.md` define. The surface API is a thin user-facing
layer over those primitives — `add` lowers to `bundle + bind`, `item`
lowers to `unbind`, both running as substrate tensor ops.

The user-facing surface should not require thinking about the
rotation operators directly. They are an implementation detail that
comes back into view only when the program does something the
substrate operations don't directly support — e.g. capability
transfer, cross-codebook composition, or low-level inspection.

## Lazy evaluation across boundaries

**Only the keys referenced in the receiving code are materialized.**

```
function getCat(axon a) {
    return a.item("cat");
}
```

If a caller hands `getCat` an axon with a million keys, the wire and
the substrate computation only carry the `"cat"` entry. The other
999,999 fillers are never bundled, never bound, never read. The
compiler does this analysis at the function (and program) boundary:
it sees which keys the receiving code references and prunes the rest
from the materialized axon.

This is the rule that makes axons workable as IPC currency. A program
can publish a giant structured state — the equivalent of
all-of-systemd's view of the world — and a downstream consumer pays
only for the slice it actually reads. Conceptually:

```
axon out = systemd.publish_state();    // 10,000-key state
screen.consume(out);                   // screen reads the 4 keys it needs
                                       // → only those 4 cross the boundary
```

> **Open question.** How far the lazy analysis propagates. Through a
> single function call: clearly yes. Through nested axon-valued
> entries (an axon that contains another axon): unclear. Across a
> dynamic-dispatch boundary where the receiving code isn't visible at
> compile time: probably not, but the failure mode (over-materialize
> conservatively, or refuse to compile) is unspecified.

## Axons as loop carriers

This is the load-bearing use case for the C / TypeScript transpilers.
A side-effect-heavy loop like

```c
int sum = 0;
for (int i = 0; i < 10; i++) {
    sum += i;
}
```

cannot stay in its imperative shape on a Sutra substrate — Sutra has
no host-side mutation, no host-side `for`. The transpiler lowers it to
a tail-recursive function whose state is an axon:

```
function axon loop_body(axon a) {
    if (a.item("i") >= 10) return a;
    a.item("sum") = a.item("sum") + a.item("i");
    a.item("i") = a.item("i") + 1;
    return loop_body(a);
}

Axon state = new Axon();
state.add("sum", 0);
state.add("i", 0);
state = loop_body(state);
int total = state.item("sum");
```

The pattern is intentionally heavy-handed: **every variable referenced
inside the loop body becomes an axon entry**. The loop body's mutations
become `item(key) = ...` assignments on the axon. The axon is threaded
through the tail call as the loop's state vector. This is the user's
"cheat way of doing tail recursion" — a smarter analysis can prune
variables that don't escape the loop, but the dumb form is enough to
get a working translation, and it's robust to side effects the
analyzer might not catch.

When working in idiomatic Sutra (not transpiled), programs typically
destructure axons promptly rather than threading them through long
chains. The fat-axon-as-loop-state pattern is specifically a
transpilation accommodation for languages where everything mutates.

## Axons as function I/O

The general case generalizes the loop pattern. A Sutra function
typically takes an axon and returns one:

```
function axon process(axon input) {
    Cat c = input.item("subject");
    String r = input.item("response");
    Axon out = new Axon();
    out.add("status", "ok");
    out.add("payload", make_payload(c, r));
    return out;
}
```

Functions composed this way build up larger environments by extending
or replacing axons as they go. The bundle-of-variables shape keeps
each function's local contract local — what keys it reads, what keys
it writes — without forcing a single global record type that every
function has to agree on.

## Axons correspond to memory points

When an axon crosses a process or program boundary, it corresponds
pretty directly to an actual addressable region: the bundle that
encodes the materialized keys at that boundary. The fact that
"materialized" is determined by the receiver's lazy analysis (above)
means the *size* of that region is set by what the receiver reads,
not by what the sender stuffed in.

This is the property that load-bearing downstream systems (Yantra
above all) lean on. A scheduler can know in advance how much GPU
each axon-passing call costs, because the axon's materialized width is
a function of the receiver's compiled code, not a function of dynamic
runtime decisions.

## The hardware-linked-monad framing

The user's framing for axons in this conversation has been *"kind of
like monads in Haskell, a bit, but extremely hardware-linked."* The
analogy is hedged on purpose — this is a thinking aid, not a
category-theoretic claim that axons are monads.

What the analogy is pointing at:

- A Haskell monad like `IO` encapsulates effect; the effect happens
  outside the language and the monad gives a structured way to
  compose those effects. The monad's structure is independent of what
  hardware is underneath.
- A Sutra axon encapsulates structure too — every value has the same
  shape, every operation is the same kind of tensor op, and a
  function that takes an axon and returns one composes the same way
  regardless of what the keys mean.

The "hardware-linked" part is where the analogy breaks. In Haskell,
the fact that `IO` ultimately talks to a disk is invisible to a
program manipulating `IO Int`. In Sutra, when a downstream system
ties a key to a physical resource, the key's underlying rotation
operator *is* the operator the runtime uses to talk to it — there's
no separate handle. Possessing the operator is the only way to read
or write the slot. That's where the hardware link sits, even though
the user-facing surface is just `add` / `item` calls.

The user has emphasized this hardware-correspondence as one of the
two defining properties of axons (the other being that they are
*completely un-imperative aside from the ergonomics*): **axons are
one of the most literal things in Sutra that corresponds to a
physical part of the computer.** The `add` / `item` surface is a
user-facing convenience; what those calls compile to is operations
on a vector that, at the wire and substrate boundary, is real,
addressable, and physically realized.

> **Open question.** What "hardware-linked" cashes out to inside the
> Sutra spec proper, vs. what is purely a downstream concern of the
> system that hosts a Sutra runtime (Yantra). Today the boundary is
> unstated.

## Constraints

- **Fixed width per program.** A program's axon-valued state at any
  instant fits a fixed bundle width set at compile time. The width
  goes in the program's compile-time configuration. This is what
  lets a downstream scheduler know in advance how much GPU it owes
  the program — the answer doesn't depend on which keys the program
  inserts at runtime.
- **No higher-order axons (yet).** Sutra today does not bind programs
  *as* values inside an axon — a program can store an embedding *of*
  a program, but not a program-as-axon-entry that another program
  can apply. Lifting this is research-grade.
- **Crosstalk grows with codebook depth.** Nesting too many bind /
  bundle layers in a single axon eventually degrades decoding. A
  program that needs more compositional depth than the substrate
  supports gets noisy retrieval, not a clean error. The depth limit
  is substrate-dependent.

## Error handling across axon boundaries

> **Open question.** Sutra does not yet specify how an error
> propagates through a chain of axon-passing functions. Two
> candidates:
>
> - **Sentinel filler in a status key.** The output type carries a
>   `"status"` key, the body writes a "failure" filler into it,
>   downstream functions decode it and branch.
> - **Error-shaped axon.** A separate axon "shape" for errors,
>   distinguished from normal axons by which keys are populated.
>
> Both are workable. The user has not picked one. Today error
> handling in Sutra is whatever the program's author writes by hand.

## Open questions

(Also indexed in `open-questions.md`.)

Resolved in this cut:
- ~~Surface accessor~~: **`add` / `item`, no `get`. `item` is settable.
  Property-style access (`a.cat`) where ergonomic.**
- ~~Generics~~: **None. Axon is a single non-generic class; values are
  heterogeneous.**
- ~~Whether the surface is dict-like or record-like~~: **neither — a
  bundle of named variables / control object. Looks dict-shaped
  syntactically; isn't a hash map (no runtime input→output lookup),
  isn't a declared record (no compile-time schema).**
- ~~Whether axons are lazy across boundaries~~: **yes. Only referenced
  keys materialize.**
- ~~Whether the appearance of mutation is real~~: **no. The
  imperative-looking syntax is sugar; the compiler usually elides the
  axon entirely (treats `item(k) = v` as SSA-style variable rename).
  A new axon only materializes when one actually has to cross a
  function or loop boundary.**
- ~~Whether axons can appear anywhere in code~~: **no — meaningfully
  only at four positions: function input, function output, loop start,
  loop end. Anywhere else is syntactic salt that the compiler erases.**
- ~~Whether per-entry class tags exist~~: **yes — the user has resolved
  that axons store class info per entry as a suggestion to the type
  system. Mechanics still TBD (see open below).**

Still open:
- How the per-entry type tag is represented and resolved (runtime cast
  vs compile-time-erased static check, with what failure mode).
- How far the lazy analysis propagates (through nested axons, across
  dynamic dispatch).
- What "hardware-linked" cashes out to inside the Sutra spec vs. in
  downstream systems.
- Default axon width — single fixed width vs. width-as-part-of-the-
  program-configuration.
- How property-style access (`a.cat`) lowers when the key is *not*
  statically known. (For statically-known keys: same as `item("cat")`.
  For dynamically-computed keys: probably an error, but unspecified.)
- Behavior on missing key: compile error for statically-known-missing,
  runtime error, or noise-decoded value? Likely depends on whether
  the substrate has a probe for "this role was never bound."
- Whether `Axon` is a new built-in class added to the surface, vs. a
  special syntactic form. Either is workable but they have different
  ergonomics for class-related features (inheritance, methods).
- Whether role-as-operator transfer should have a first-class surface
  form, or stay implicit in the `add` mechanism.
