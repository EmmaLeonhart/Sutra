# JavaScript primitives as subclasses of Sutra primitives

**Surfaced:** 2026-05-10
**Reporter:** Emma — final message of the 2026-05-10 session on JSO
operator overrides.

## The position

Emma's clarification of the JavaScript-compatibility model:

> *"the JavaScript primitives, how I guess I'd probably say for our
> case, we'd have a class that is a JavaScript object, but then
> we'd also have a class that's like a JavaScript primitive, and
> then the JavaScript primitive will then have all the individual
> JavaScript things inherit from them, or I don't know, no, I
> think it'll probably be better for there to be like a JavaScript
> integer that inherits from our integer class and stuff like that,
> but on those things we have object, we have like the operators,
> we have it, so there's a distinction between the two things… a
> JavaScript integer or JavaScript number, JavaScript string, etc.,
> they'd be sub-subclasses of our own classes but they function a
> bit differently and they have JavaScript operators on them."*

The shape:

```
                Sutra primitives
                /     |       \
              int   String   bool   ...
              /       |        \
   JavaScriptInt   JavaScriptString   JavaScriptBool   ...
       (JS-coercive operators)
       (JS-specific behaviors)
```

`JavaScriptObject` continues to exist for **objects** (the
catch-all for typed-as-`any` / structural / opaque values). The
new layer is **per-primitive JavaScript subclasses** with JS-
specific operator overrides on top of Sutra's own primitive
substrate.

## Why this is cleaner than what landed 2026-05-10

The 2026-05-10 JSO overrides (`js_add` with string-concat coercion,
`js_strict_eq`, `js_typeof`, `js_truthy`) all sit on the
`JavaScriptObject` class. That works because the TS transpiler
makes every typed-class extend `JavaScriptObject` and wraps
primitive literals via `JavaScriptObject.wrap(...)`. But it loses
type information:

- `js_typeof("foo")` currently routes through `is_string` to return
  `"string"` — works, but only because the codepoint-array
  marker survived the `.wrap(...)` round-trip. The runtime
  doesn't know "this was statically typed as a string."
- A future `JavaScriptInt + JavaScriptString` could dispatch at
  compile time (statically known both subclasses), routing to the
  string-concat coercion without runtime flag-checks.
- Each primitive subclass can carry its own JS-specific axes /
  layout if needed (e.g. JavaScriptNumber tracking NaN-ness
  explicitly, JavaScriptString tracking immutability).

## What lands first vs what's open

**Already shipped (2026-05-10):**
- `JavaScriptObject` + `wrap` + `js_add` (now coercive) +
  `js_strict_eq` + `js_truthy` + `js_typeof`. These work on any
  value coerced through `.wrap`.

**Not yet shipped, to be done per this design:**
- `JavaScriptInt extends int` (or extends a fuzzy-`Integer` class
  once that exists), with JS-specific overrides: `+` does
  string-concat-if-string-operand, comparison ops handle the
  JS coercion ladder, etc.
- `JavaScriptString extends String`, with `+` doing concat
  unconditionally (JS strings always concat under `+`).
- `JavaScriptBool extends bool` (or `extends fuzzy`), with JS
  truthy/falsy table baked into its coercions.
- `JavaScriptObject` remains for opaque / `any` / object values.
- The TS transpiler chooses the right subclass at lower time
  based on the static type annotation; primitive literals land as
  `JavaScriptInt.wrap(7)` / `JavaScriptString.wrap("hi")` / etc.,
  not generic `JavaScriptObject.wrap(...)`.

**Design questions still open:**
- Which Sutra primitives need a JS subclass at all? `int`, `float`,
  `String`, `bool` are clearly yes. `vector` (for typed arrays)?
  `Character` (single-char string)?
- Where does `null` / `undefined` live? Probably their own
  singleton classes — `JavaScriptNull` / `JavaScriptUndefined`
  with their own truthy/falsy behavior.
- The operator surface duplicates across subclasses: how much can
  the inheritance chain do for us (i.e. `JavaScriptInt` and
  `JavaScriptFloat` both want JS-coercive `+`, can they share a
  `JavaScriptNumber` intermediate class)?
- Migration story for code that uses `JavaScriptObject` today —
  the existing `wrap` / `js_add` shape stays for backward
  compatibility, but new TS transpilations should prefer the
  typed subclasses.

## Not yet blocking

This is a refinement of the JSO override surface, not a new
blocker. The MVP from 2026-05-10 works; refining it into typed
per-primitive subclasses is the next layer when a real TS program
exposes a case the catch-all class can't dispatch correctly.

Open until someone (Emma or a future session) picks up the
implementation; archive when done.
