# sutra-from-ts

Transpile a typed core of TypeScript — and JavaScript treated as untyped TypeScript — into [Sutra](https://sutra.noldor.tech) (`.su`) source.

## Status: working

The CLI ships valid `.su` output for the **17 fixtures under `tests/fixtures/`**. As of v0.1.0, coverage includes:

- Function declarations (incl. arrow-as-`const`, closure-free capture via param lifting)
- Classes (fields + methods + static + constructors + `new`)
- Interfaces and type aliases (erased; only register "this name is Axon-shaped"), including
  NESTED interfaces — a nested object literal (`{ inner: { v: 8 } }`) builds a nested axon, and
  nested member access (`o.inner.v`) reads through a hoisted `Axon` temp (shipped 2026-06-18)
- Discriminated unions
- `while` / `for` / `do-while` loops hoisted into Sutra `while_loop` decls with auto-detected state vars
- `async` / `await` / `Promise<T>` (uses Sutra's first-class promise vocabulary, shipped 2026-05-13)
- Module imports (`import { X } from "./foo"`) via lower-time inline expansion with diamond dedup
- String concat (`s + t` → `String.string_concat`)
- Primitive arrays
- Enums lowered to TS classes that extend `JavaScriptObject`
- The `JavaScriptObject` runtime for the untyped JS fallback path

Beyond that surface, lower currently rejects (and the compiler warns about) the dynamic edges of the language — `eval`, prototype mutation, untyped `any` chains, runtime-loaded code. See `DESIGN.md` for the full lowering rules.

## Why a TypeScript → Sutra transpiler

Two reasons:

1. **Strategic.** Yantra (the Sutra-based OS) requires that existing TypeScript and JavaScript code can participate, especially for the GUI/browser layer where the userspace is "everything is a browser." A transpiler from a typed-core TS subset gives that path without rewriting code by hand. Sutra's surface syntax already looks TypeScript-flavored (functions, classes, `&&` / `||`, string and numeric literals), so the syntactic distance is small.
2. **Pragmatic.** TypeScript and Sutra share the structural-typing-on-records mindset. Lowering TS interfaces and classes to Sutra axons is a forcing function on the Sutra-side axon model, similar to what the C transpiler will do for structs.

JavaScript is treated as TypeScript with type annotations stripped — the transpiler reads `.js` and `.ts` uniformly. Untyped values become `vector` in Sutra (the bottom of Sutra's typing surface) with no implicit narrowing.

## Install

```bash
# Standalone:
pip install sutra-from-ts

# As an extra of the Sutra dev library (recommended — pulls in the
# compiler too so you can pipe ts2su output straight into sutrac):
pip install sutra-dev[ts]
```

## Use

```bash
# Default: write next to input with .su extension
ts2su path/to/file.ts            # -> path/to/file.su

# .js treated as untyped TypeScript
ts2su path/to/file.js            # -> path/to/file.su

# Override output path
ts2su input.ts -o out/custom.su

# Pipe into the Sutra compiler
ts2su input.ts -o /tmp/x.su && sutrac --emit /tmp/x.su
```

## License

Apache-2.0. See `LICENSE`.
