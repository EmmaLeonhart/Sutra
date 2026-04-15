# Program structure

## Files and entry point

A Sutra program lives in one or more `.su` files. The entry point
is the `main` function — the same convention C / Go / Rust use.

The `.su` files currently in `examples/` and elsewhere in the repo
are **accepted as reasonable examples of how a Sutra program is
written**. The deprecated spec (`planning/sutra-spec-deprecated/`)
was largely wrong, but the `.su` source files themselves were
written against the compiler and real programs, so they are closer
to ground truth for surface syntax than the deprecated spec was.

There is not a hidden second layer of file organization: it is
`.su` source + the project manifest described below.

## `meru.toml` — project manifest

Each Sutra **project / solution** carries a `meru.toml` file
(literally `M-E-R-U` + `.toml`) that describes the runtime
configuration the project needs. This file exists because Sutra
programs are **not fully architecture-independent** — which
substrate a program runs on affects what primitives are available
and how they perform.

The manifest records things like:

- What embedding space the program is using.
- Whether the program uses a database.
- Whether the program uses logits.
- Other substrate / runtime configuration the compiler and runtime
  need to know about.

A project on a different substrate will need a different
`meru.toml`; the same `.su` source may or may not run unchanged
depending on how substrate-specific it is.

## Architecture-independence

Sutra is **somewhat** architecture-independent — more so for
programs that only use the core vector operations, less so for
programs that lean on substrate-specific features (a specific
embedding space, a specific database, logits from a specific
model). The user's position is that architecture-independence is
a **spectrum**, not a binary property, and the design should not
force either extreme.

## Open questions

- Exact schema of `meru.toml` — what fields are required, what
  fields are optional, what are the defaults.
- How is substrate-incompatibility detected and reported? At
  compile time via `meru.toml` mismatch? At runtime when a
  primitive isn't available?
- Is there a per-file import system, or are all `.su` files in a
  project compiled as a single unit?
- What is the directory layout of a project? Does `meru.toml` sit
  at the root of the project, alongside `.su` files, or elsewhere?
- Multiple-entry-point programs (libraries, tools with subcommands)
  — do they each have a `main`, or is that a single-entry-point
  assumption?
