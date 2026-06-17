# The axon model (Yantra-side notes)

> **Authoritative axon spec lives in Sutra**, at
> `Sutra/planning/sutra-spec/axons.md`. Axons are a Sutra concept;
> Yantra uses axons because Sutra has them. This file holds only the
> Yantra-OS-specific design notes that build on top of the Sutra spec —
> read the Sutra spec first.
>
> Anything below that contradicts the Sutra spec is wrong here, not
> there. Open the Sutra spec and update this file.

## What an axon is (one-line refresher)

A fixed-width vector produced by rotation binding over a codebook of
roles — `bundle( bind(R_subject, F_alice), bind(R_action, F_send), … )`.
The full definition, the role-as-operator story, and the open spec
questions are all in `Sutra/planning/sutra-spec/axons.md`.

In Yantra, *every* `.su` file is, in 95% of cases, a function
`(Axon) -> Axon`. The whole OS is what you get when you wire a few
hundred of those together.

## Why axons are the right unit of IPC

The Sutra spec gives the general argument (composable without parsing,
differentiable end-to-end, same shape as model inputs). For Yantra
specifically, those three properties cash out as:

- The IPC graph is one smooth tensor function. Training across process
  boundaries is not a special case.
- A model that consumes embeddings is already prepared to consume what
  another process emits. JEPA's predicted latents, an LLM's activation
  residual, and a `read_file()` syscall result are all the same kind
  of tensor.
- No serializer / deserializer pair sits between processes. A receiver
  decodes the role it needs by `unbind`.

## Capability transfer at the OS level

The Sutra spec defines that roles are operators, not labels — possessing
the rotation operator is the only way to read or write the slot. Yantra
turns that into a security mechanism:

- **Process isolation.** A process is bound to a set of roles. Roles it
  doesn't possess decode any axon's slot to noise.
- **Sandboxing.** Hand a child process a smaller codebook (or a
  derived child codebook) and it can only operate on that subset.
- **Revocation.** Rotate the parent operator; child copies of the
  derived operator decode to noise. Existing axons in flight that
  carried the revoked role become unreadable in that slot.

Mechanism details, threat-model, and crosstalk analysis live in
`08-security-and-isolation.md`.

## Filesystem bridge

The conventional filesystem returns axons to processes via syscalls.
The notation below is **informal documentation of what keys each
syscall expects on its input axon and produces on its output axon** —
it is not a compile-time type contract. Per the Sutra spec, axons
have no declared schema; the compiler does dataflow analysis but
does not type-check key sets. Yantra documents call shapes this way
for human readers, the same way a man page documents `read(2)`.

```
read_file  : { R_path } -> { R_bytes_axon, R_metadata_axon }
write_file : { R_path, R_payload_axon } -> { R_status }
```

`R_bytes_axon` carries the file's contents as either:

- a literal embedding produced by an embedding model
  (`nomic-embed-text`, `mxbai-embed-large`, `ESM-2`, …) when the file
  is meant to be consumed semantically, or
- a Sutra-compiled axon that decodes losslessly to bytes when the file
  is meant to be consumed exactly (executables, configs, binary blobs).

Which mode applies is part of the file's metadata, not the syscall's
job. See `05-filesystem-bridge.md`.

## Yantra-specific constraints on axons

These are tightenings of what the Sutra spec leaves open:

- **Fixed width is mandatory in Yantra, not optional.** The Sutra spec
  treats default axon width as an open question. For Yantra to schedule
  GPU allocation under load, the axon width per process must be known
  at install time — it goes in the program's install manifest. Within
  Yantra, "carry width as part of the type" is not the chosen path.
- **Crosstalk depth caps are surfaced as runtime errors, not silent
  degradation.** The Sutra spec acknowledges crosstalk grows with
  codebook depth. Yantra commits to detecting depth-cap violations at
  runtime and surfacing them as errors, so a process gets a clean
  rejection instead of garbled output.

## Yantra-specific open questions

(General axon open questions live in `Sutra/planning/sutra-spec/open-questions.md`
and `Sutra/planning/sutra-spec/axons.md`.)

- Should every axon at the OS layer carry a provenance role by default,
  even when the underlying program doesn't request one? Useful for the
  alignment monitor (`10-ai-native-interface.md`); costs a codebook
  entry per process.
- Per-tenant codebooks vs. one global codebook with namespaced roles.
  This is a real partitioning question for multi-tenant deployments
  and the answer will differ between defense / aerospace targets and a
  hypothetical consumer-grade Yantra.
