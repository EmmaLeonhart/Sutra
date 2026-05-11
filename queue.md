# Sutra — Work Queue

**This file is a queue, not a state snapshot.** It lists what is
being worked on right at this moment. Finished work lives in
`git log` and `planning/findings/`; longer-horizon work lives in
`todo.md`.

See CLAUDE.md §"Workflow Rules" for how queue.md and the task tool
stay in sync.

---

## Active

### 1. Promises and async/await — partially shipped, two pieces still open

Un-postponed 2026-05-09. Per the user, every TypeScript construct
should be expressible in Sutra (modulo architectural violations);
`async`, `await`, and `Promise<T>` are essential to that goal. They
are **first-class Sutra vocabulary** — not stdlib helpers, not TS
imports — with a **two-stage beta-reduction** at compile time:

```
async function    (sugar over)
   ↓
Promise<T>        (sugar over)
   ↓
while_loop with two-channel halt vector  (substrate primitive)
```

Spec: `planning/sutra-spec/promises.md` (canonical) +
`docs/promises.md` (website with three-box visualisation). Original
voice-conversation that drove the design:
`planning/exploratory/promises-design-conversation.md`.

#### What works today

- **Surface syntax fully reserved.** `async function`, `await expr`,
  and `Promise<T>` parse cleanly and validate without errors. Lexer
  has `KW_ASYNC` / `KW_AWAIT`; `Promise` is a contextual primitive
  type name like `vector` or `dict`.
- **Stage-1 desugar — two simple shapes compile + run end-to-end:**
  - *Pure return*: `async function Promise<T> f() { return e; }` →
    `function Promise<T> f() { return Promise.resolve(e); }`
  - *Thin wrapper*: `async function Promise<T> f() { return await e; }`
    → `function Promise<T> f() { return e; }`
  Implemented in `sdk/sutra-compiler/sutra_compiler/promise_desugar.py`.
  Corpus fixture: `tests/corpus/valid/async_promise_desugar.su`.
- **Stdlib `Promise<T>` class** — declared in
  `sdk/sutra-compiler/sutra_compiler/stdlib/promises.su` with
  `resolve`, `reject`, `isFulfilled`, `isRejected`, `isPending`,
  `value`, `reason` as static intrinsics. Loader sees them.
- **TS transpiler integration** — `async function`,
  `await expr`, and `: Promise<T>` annotations pass through verbatim
  from TypeScript into Sutra. TS fixture
  `sdk/sutra-from-ts/tests/fixtures/async_promise_basic/` lowering
  test green.
- **Codegen rejection on the unsupported shapes** — anything Stage-1
  desugar can't simplify (var-then-return, post-await code,
  try/catch) errors with a helpful pointer at
  `planning/sutra-spec/promises.md`. No silent failures.

Three-box mental model rendered at `docs/promises.md` (live at
`sutralang.dev/promises/` after the next pages-CI run).

#### What's still pending

**All major Stage-2 + Stage-3 (try/catch, first-class fns, loop-
bodied awaits) shipped 2026-05-09.** Promises now expose every
JavaScript-style operation we need:

- `Promise.resolve(v)` / `Promise.reject(r)` constructors
- `Promise.isFulfilled`, `Promise.isRejected`, `Promise.isPending`
  state inspectors
- `Promise.value(p)` / `Promise.reason(p)` value extractors
- `Promise.await_value(p)` loop-bodied await — substrate-equivalent
  of the while_loop spinning on `isPending`, with a 100-iteration
  soft-halt timeout for the no-external-I/O case
- try/catch with polarized `AXIS_PROMISE_REJECTED` blend (single-
  return blocks, both branches evaluated)
- First-class function values (`function f` parameter type)
- Stage-1 desugar covering every JS-style async/await shape that
  doesn't need closures

**Three small remaining items, all in `todo.md`:**
- Closure capture in arrow functions (top-level fn refs work; local-
  capture lambdas need scope-resolution work).
- Container method dispatch (`Array.map`, `Promise.then`,
  `Promise.all`, `Promise.race`) — straight stdlib additions, not
  blocked on language work.
- Multi-statement try/catch bodies (need slot hoisting like loops).

#### Phase tracker

| # | Phase | Status |
|---|---|---|
| 1 | Spec — `promises.md` two-stage layering | ✅ |
| 2 | Lexer + parser + AST + codegen rejection | ✅ |
| 3 | Stage-1 desugar — two simple shapes | ✅ first cut |
| 3+ | Stage-1 — full coverage (needs first-class fns) | 🚧 blocked |
| 4 | TS transpiler pass-through | ✅ |
| 5 | Stdlib `Promise<T>` class declaration | ✅ |
| 6 | Stage-2 lowering — `Promise<T>` → `while_loop` | ✅ runtime methods + Promise.await_value loop-bodied intrinsic |
| 8 | try/catch via polarized AXIS_PROMISE_REJECTED blend | ✅ |
| 9 | First-class function values | ✅ |
| 7 | Fixtures — try/catch, multi-await, propagation | partial (2 corpus + 1 TS) |

---

### 2. TypeScript → Sutra transpiler — three-item closeout

Core transpiler substantially complete as of 2026-05-08 (14 fixtures
green end-to-end). After **three remaining items** the JavaScript
story is done. Emma 2026-05-10: this is today's slice. Work in this
order:

1. **Interpolated lookup table** (gates `Math.*` shims). ✅
   shipped 2026-05-10 — including trig and hyperbolic. Architecture:
   length-N value tensor + triangle-weight soft-index dot product
   (not VSA-bundled — see
   `planning/findings/2026-05-10-interpolated-lookup-table-works.md`).
   `_VSA.exp` and `_VSA.log` land as substrate-pure intrinsics on
   both backends; `pow` and `sqrt` beta-reduce to those. Trig
   (`sin` / `cos` / `tan`) uses the same lookup architecture with
   input modulo-reduced to (-π, π]. Hyperbolic (`sinh` / `cosh` /
   `tanh`) beta-reduces to `exp`. `Math.PI` and `Math.TAU` land as
   precomputed scalars; `Math.E` beta-reduces live to `exp(1.0)`
   at the call site. Out-of-range inputs raise `SutraMathOverflow`
   (no silent clamp-to-zero). `_TRANSCENDENTALS_DISABLED` is now
   the empty frozenset. Test coverage: math_basic fixture +
   `test_transcendentals.py`.

2. **Module imports** (`import { X } from "./foo"`). ✅ shipped
   2026-05-10. Single fixture (`module_import/`) green for both
   lowering and end-to-end compilation; diamond and circular
   imports terminate cleanly. Inlines imported declarations at the
   top of the importing file's output bracketed by `// --- begin
   module: <spec> ---` markers. Tree-shaking, namespace imports,
   and bare-specifier resolution (NPM packages) deferred. Doc:
   `docs/typescript-to-sutra.md` § Modules.

3. **Multi-program axon passing demo.** ✅ shipped 2026-05-10.
   `examples/multi_program_axon/` — two separately-compiled `.su`
   programs exchange a 5-key axon vector via a numpy `.npy` wire
   format (3600 bytes). Recovery margin checked via host-side cosine
   monitoring; all three reads land closer to bundled fillers than
   to never-bundled decoys (margins +0.20, +0.20, +0.26). Both
   programs share `atman.toml` for embedding-model agreement, which
   is what makes basis vectors line up across the boundary. Lazy
   materialization is *not* yet implemented — the full bundle
   crosses today; an earlier 12-key draft hit the rotation-binding
   capacity wall on cat/dog disambiguation, motivating the
   producer-side pruning pass as the natural follow-on. Finding:
   `planning/findings/2026-05-10-multi-program-axon-passing-works.md`.

Already shipped on the transpiler:
- Functions (incl. arrow-as-const, closure-free capture via param
  lifting), interfaces, type aliases, classes (fields + methods +
  static + constructors + `new`), discriminated unions,
  `this.field`, void instance methods.
- Loops: while / for / do-while hoist into declared `while_loop`
  decls with auto-detected state vars + slot copies + writeback.
- String concat (`s + t` → `String.string_concat`), primitive
  arrays (`T[]`, `arr[i]`, `arr.length`, `[1, 2, 3]`).
- JavaScriptObject runtime (`wrap`, `js_add`) for the untyped JS
  fallback path.
- `async function`, `await`, `Promise<T>` pass-through (added
  2026-05-09 with item 1); first-class function values; try/catch
  via polarized `AXIS_PROMISE_REJECTED` blend; `Promise.await_value`
  loop-bodied intrinsic.
- Sutra-side enabling work that landed alongside: class fields,
  constructor sugar (`new`), value-returning instance methods,
  non-static class loops, operator overloading via inheritance-
  chain dispatch, synthetic-axis equality (Euclidean+tanh).

Long-form treatment of all three remaining items, with reasoning
and cross-references, in `todo.md` §"TS transpiler / Sutra
postponed pieces".

---

## Parked

The C → Sutra transpiler skeleton at `sdk/sutra-from-c/` is parked
(decision 2026-05-08): user no longer views transpiling Linux as a
useful path to OS-level Sutra work. Skeleton stays in tree; do not
delete. See `todo.md` for the parked entry.

Yantra (the OS) is downstream of the TS transpiler — both the
core transpiler (shipped) and the multi-program axon demo
(postponed) are Yantra prerequisites for any real IPC story.
Yantra is its own repo (`../Yantra/`) with its own queue; Sutra's
queue ends at the transpiler.

---

## Pointers

- Longer-horizon agenda: `todo.md`.
- Pinned semantic corrections: `planning/semantic-corrections.md`.
- Deprecated spec (read-only reference): `planning/sutra-spec-deprecated/`.
- New spec dir + meta-failure note: `planning/sutra-spec/README.md`.
- Findings (dated): `planning/findings/`.
- Open design questions: `planning/open-questions/`.
- Hardwired assumptions in the demo path: `examples/todo.md`.
- Devlog (full history): `DEVLOG.md`.
- Yantra (the OS Sutra is being built for): `../Yantra/`.
