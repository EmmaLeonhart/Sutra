# sutra-from-ts

Transpile a typed core of TypeScript — and JavaScript treated as untyped TypeScript — into [Sutra](https://sutralang.dev) (`.su`) source.

## Status: skeleton

This package currently has no transpilation logic. The CLI wires up but reports `not yet implemented` and returns a non-zero exit code. See `DESIGN.md` for the planned approach and the open questions blocking implementation.

The transpiler is part of [Sutra's strategic queue](https://github.com/EmmaLeonhart/Sutra/blob/master/queue.md). It is downstream of the [axon spec](https://github.com/EmmaLeonhart/Sutra/blob/master/planning/sutra-spec/axons.md), which is itself a first cut — both files need to stabilize before the transpilation rules can lock in.

## Why a TypeScript → Sutra transpiler

Two reasons:

1. **Strategic.** Yantra (the planned Sutra-based OS) requires that existing TypeScript and JavaScript code can participate. A transpiler from a typed-core TS subset gives that path without rewriting code by hand. Sutra's surface syntax already looks TypeScript-flavored (functions, classes, `&&` / `||`, string and numeric literals), so the syntactic distance is small.
2. **Pragmatic.** TypeScript and Sutra share the structural-typing-on-records mindset. Lowering TS interfaces and classes to Sutra axons is a forcing function on the Sutra-side axon model, similar to what the C transpiler does for structs.

JavaScript is treated as TypeScript with type annotations stripped — the transpiler reads `.js` and `.ts` uniformly. Untyped values become `vector` in Sutra (the bottom of Sutra's typing surface) with no implicit narrowing.

## Planned scope

Read `DESIGN.md` for the full plan. In one paragraph: a single-file pass that handles the typed core (interfaces, classes, functions, narrowing) and rejects the dynamic edges (`eval`, prototype mutation, untyped `any` chains) with clear errors. The output is `.su` source that compiles cleanly through `sutra-compiler`.

## Install

Once published:

```bash
pip install sutra-from-ts
ts2su path/to/file.ts
ts2su path/to/file.js   # treated as untyped TS
```

The CLI does not currently produce output — it reports `not yet implemented`.

## License

Apache-2.0. See `LICENSE`.
