# Axons

> **First cut.** The axon as a Sutra concept is under-specified relative to
> the rest of the language. This doc captures the user's expressed position
> as of 2026-05-07; the rest of the design space is marked as open
> questions inline (and indexed in `open-questions.md`).

## What an axon is

An **axon** is a structured embedding: a fixed-width vector whose contents
are produced by **rotation binding** over a known **codebook of roles**.

```
axon = bundle( bind(R_subject, F_alice),
               bind(R_action,  F_send),
               bind(R_object,  F_message_42) )
```

`R_*` are unit-norm rotation operators (one per role, drawn from a
codebook fixed at compile time). `F_*` are fillers — vectors that may
themselves come from an embedding model, a Sutra-compiled symbol, or
another axon. All of these are the same shape, which is what lets an
axon's fillers be other axons without a type ladder.

This is the same `bind` / `unbind` / `bundle` primitives the rest of the
spec defines (see `binding.md`, `operations.md`). An axon is not a new
primitive; it is the user-facing name for a particular *use* of those
primitives — a role/filler bundle whose role set is part of the axon's
type.

## Why axons, not records or structs

A program could in principle pass a Python dict, a flat tuple, or a
serialized JSON blob between functions. Sutra's position is that the
right unit is the axon. Three properties carry that argument:

1. **Composable without parsing.** Two axons combine into a third by
   bundling. No serialization, no schema validation, no version
   negotiation at the boundary. The receiver decodes the role it needs
   by `unbind(role, axon)`.
2. **Differentiable end-to-end.** Gradients flow through `bind` /
   `bundle` exactly the way they flow through any other tensor
   operation. A computation that crosses many function calls remains
   one smooth function.
3. **Same shape as model inputs.** A model that consumes embeddings is
   already prepared to consume axons. An LLM activation residual, an
   embedding-model output, and a structured Sutra return value are all
   the same kind of tensor.

These three together are the user's reason for treating axons as the
*currency* of Sutra: in 95% of programs, a `.su` function takes an axon
and returns an axon.

## Hardware-linked monad framing

The user's framing for axons is *"kind of like monads in Haskell, a bit,
but extremely hardware-linked."* The analogy is hedged on purpose — this
is a thinking aid, not a theoretical claim that axons are monads in the
category-theory sense.

What the analogy is pointing at:

- A Haskell monad like `IO` encapsulates effect: the effect happens
  outside the language, the monad gives a structured way to compose
  those effects. The monad's structure is independent of what hardware
  is underneath.
- A Sutra axon encapsulates structure too — every value has the same
  shape, every operation is the same kind of tensor op, and a function
  that takes an axon and returns one composes the same way regardless
  of what the role/filler positions mean.

The "hardware-linked" part is where the analogy breaks. In Haskell, the
fact that `IO` ultimately talks to a disk is invisible to a program
manipulating `IO Int`. In Sutra, the role operators *are* the keys —
possessing the rotation operator `R_x` is the only way to read or write
the `x` slot of an axon. When a downstream system (the OS in Yantra,
hardware drivers, IO surfaces) ties a role to a physical resource, the
role doesn't *represent* that resource symbolically — it *is* the
operator the runtime uses to talk to it. There's no separate handle.

This is the property that makes axons load-bearing for downstream
systems work, and it is the property that distinguishes axons from
"records that happen to be vectors."

> **Open question.** What does "hardware-linked" cash out to inside the
> Sutra language proper, vs. what is purely a downstream concern of the
> system that hosts a Sutra runtime? Today the user's position is the
> mid-position — Sutra defines what a role/operator is, downstream
> systems decide which roles are tied to which physical resources — but
> the boundary has not been worked through end-to-end.

## Roles are operators, not labels

A role in Sutra is not a string key. It is a unit-norm rotation matrix.
You don't "have a name for the slot"; you have *the only key that opens
the slot*.

This means:

- A function that does not have `R_x` in its scope cannot read or write
  the `x` slot of an axon, because the operator is the unbinder.
- Capability transfer happens by bundling the operator (or a derived
  child operator) into another axon and handing the receiving axon to
  another part of the program. This is the same machinery that does
  ordinary axon construction, used reflectively.
- "Revoking" a role amounts to rotating the parent operator; child
  copies decode to noise.

The Sutra spec defines this mechanism. Whether and how a host system
exposes role transfer as a security primitive (process isolation,
sandboxing, capability revocation) is the host's call — Yantra's
`08-security-and-isolation.md` is one such design.

## Axon types

A type for an axon is a contract about *which roles are expected to be
bound* on entry and exit. A type signature looks like:

```
ProcessFoo : { R_input_query, R_caller_ctx } -> { R_response, R_provenance }
```

Read: "this function reads roles `R_input_query` and `R_caller_ctx` from
its input axon and writes roles `R_response` and `R_provenance` into
its output axon."

The compiler can statically check that the body only reads roles
guaranteed by the input type and only writes roles its output type
promises. This is structural typing on a vector — the "type" is which
rotation slots are populated, with what fillers, drawn from what
codebooks.

> **Open question.** How tightly does the surface syntax need to mirror
> the type signature shown above? Today there is no surface form for
> declaring an axon type. Candidates include record-shaped declarations
> (`type Foo = { R_x: vector, R_y: vector }`), inline annotations on
> functions, and inferred-only typing. See `types.md` for the broader
> typing question.

## Constraints

- **Fixed-width state per program.** A program's value at any instant
  is one axon (plus the program itself). The width is part of the
  program's compile-time configuration. This is what makes a downstream
  scheduler able to know in advance how much GPU it owes the program.
- **No higher-order axons (yet).** Sutra today does not bind programs
  *as* fillers — a program can pass an embedding *of* a program, but
  not a program-as-axon that another program can apply. Lifting this
  is research-grade.
- **Crosstalk grows with codebook depth.** Nesting too many bind/bundle
  layers in a single axon eventually degrades decoding. A program that
  needs more compositional depth than the substrate supports gets
  noisy output, not a clean error. The depth limit is substrate-
  dependent.

## Error handling across axon boundaries

> **Open question.** Sutra does not yet specify how an error propagates
> through a chain of axon-passing functions. Two candidates:
>
> - **Error as a sentinel filler in a status role.** The output type
>   carries a status role (`R_status`), the body writes a "failure"
>   filler into it, downstream functions decode it.
> - **Error as a special-shape axon.** A separate axon type for errors,
>   distinguished from normal axons by which role set is bound.
>
> Both are workable. The user has not picked one. Today error handling
> in Sutra is whatever the program's author writes by hand.

## Open questions

(Also indexed in `open-questions.md`.)

- Default axon width. Embedding models vary (768, 1024, 4096). Pick one
  and force converters at substrate boundaries, or carry width as part
  of the axon's type?
- Should every axon carry an explicit provenance role by default?
  Useful for debugging and downstream alignment monitors, but it costs
  a codebook entry and adds compile-time overhead to every program.
- One global codebook with namespaced roles, vs. per-program (or
  per-tenant) codebooks that share a hashing convention. Affects
  isolation guarantees and link-time costs.
- How `R_x`-style role notation maps onto Sutra surface syntax. The
  examples in this doc use `R_*` and `F_*` as a thinking shorthand;
  the actual `.su` source today writes roles as identifiers without
  the prefix.
- Whether role-as-operator transfer should have a first-class surface
  form (a "give role" / "receive role" syntax) or stay implicit in
  bundling.
- What downstream-system properties (OS-level capability transfer,
  hardware-link semantics, IO surfaces) the Sutra spec should
  *constrain* vs. *leave to the host*. Today the boundary is
  unstated.
