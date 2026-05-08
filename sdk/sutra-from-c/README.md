# sutra-from-c

Transpile a restricted subset of C source into [Sutra](https://sutralang.dev) (`.su`) source.

## Status: skeleton

This package currently has no transpilation logic. The CLI wires up but reports `not yet implemented` and returns a non-zero exit code. See `DESIGN.md` for the planned approach and the open questions blocking implementation.

The transpiler is part of [Sutra's strategic queue](https://github.com/EmmaLeonhart/Sutra/blob/master/queue.md). It is downstream of the [axon spec](https://github.com/EmmaLeonhart/Sutra/blob/master/planning/sutra-spec/axons.md), which is itself a first cut — both files need to stabilize before the transpilation rules can lock in.

## Why a C → Sutra transpiler

Two reasons:

1. **Strategic.** Yantra (the planned Sutra-based OS) requires that existing C code can participate. A transpiler from a restricted C subset gives that path without rewriting C code by hand.
2. **Pragmatic.** A working transpiler is a forcing function on the Sutra-side axon model — until you have to lower a struct into an axon, the axon spec's open questions can stay open. The transpiler will pin them down.

## Planned scope (subset of C accepted)

Read `DESIGN.md` for the full plan. In one paragraph: a translation-unit-at-a-time pass that lowers ANSI C minus the preprocessor and minus inline asm. Structs lower to axons (each field becomes a role). Function pointers lower to axons too. The output is `.su` source that compiles cleanly through `sutra-compiler`.

## Install

Once published:

```bash
pip install sutra-from-c
c2su path/to/file.c
```

The CLI does not currently produce output — it reports `not yet implemented`.

## License

Apache-2.0. See `LICENSE`.
