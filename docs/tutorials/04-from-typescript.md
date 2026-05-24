# 04 — From TypeScript and JavaScript

Sutra's surface syntax is TypeScript-shaped on purpose — `function`, `class`, `&&` / `||`, string and numeric literals all read the same way. Because the syntactic distance is small, a typed core of TypeScript — and JavaScript treated as untyped TypeScript — can be **transpiled** into Sutra automatically. This tutorial takes three small programs from `.ts` all the way to running Sutra, and shows where the substrate starts to show through.

## What you'll learn

- How to install and run the TypeScript → Sutra transpiler (`ts2su`)
- How everyday TypeScript constructs map onto Sutra — strings, `Math.*`, loops
- Why `Math.pow(2, 10)` doesn't come back as exactly `1024`, and why that's the point

## Install

```bash
pip install sutra-dev[runtime,ts]
```

That single install gives you two command-line tools:

- `ts2su` — TypeScript / JavaScript → Sutra (`.su`)
- `sutrac` — validate, compile, and run Sutra

The `runtime` extra pulls in PyTorch so `sutrac --run` can execute the compiled module. The examples below use strings and numbers, which encode directly on the substrate — no embedding server needed. (Programs that embed *natural-language text* additionally need a local Ollama server; these don't.)

## 1. A function

Start with `greet.ts`:

```typescript
function greet(): string {
    return "hello";
}

function main(): number {
    return greet().length;
}
```

Transpile it:

```bash
ts2su greet.ts          # writes greet.su
```

The generated `greet.su` (header comment elided):

```c
function String greet() {
    return String.make_string("hello");
}
function int main() {
    return greet().string_length();
}
```

Two mappings to notice:

- A TypeScript `string` literal becomes `String.make_string(...)`. A Sutra `String` is a codepoint array encoded on synthetic axes of a vector — not a host string.
- `.length` becomes the `string_length()` method.

Now run it:

```bash
sutrac --run greet.su
# tensor(5., device='cuda:0')
```

The result is `5` — the length of `"hello"`. Every Sutra value is a tensor; the device is `cuda:0` if you have a GPU and `cpu` otherwise, but the value is the same.

## 2. Where the substrate shows through: `Math`

Sutra has `Math.*` intrinsics that line up with TypeScript's, so the transpiler passes them straight through. Take `math.ts`:

```typescript
function rooted(n: number): number {
    return Math.sqrt(n);
}

function powered(base: number, exponent: number): number {
    return Math.pow(base, exponent);
}

function main(): number {
    return powered(2, 10);
}
```

Transpile and run:

```bash
ts2su math.ts
sutrac --run math.su
# tensor(1023.2264, device='cuda:0')
```

`Math.pow(2, 10)` is `1024` — but Sutra returns **`1023.23`**. That is not a bug; it is the design. Sutra's `Math.pow` does not call a host math library. It evaluates *on the substrate* through interpolated lookup tables — `pow(a, b) = exp(b · log(a))` over stored `exp` / `log` tables — so the result carries the substrate's approximation error. Sutra is fuzzy-by-default: exact arithmetic is the special case, not the assumption. See [Numeric math](../numeric-math.md) for how numbers live in the substrate and [Operations and operators](../operators.md) for how the transcendentals are built.

## 3. A loop becomes a substrate cell

The most interesting transformation is control flow. Sutra has no host-side `while` or `for` over data values — every program lowers to straight-line tensor work. So the transpiler hoists C-style loops into Sutra's **declared-loop** form. Take `for.ts`:

```typescript
function sum_to(n: number): number {
    let sum = 0;
    for (let i = 0; i < n; i++) {
        sum += i;
    }
    return sum;
}

function main(): number {
    return sum_to(10);
}
```

`ts2su for.ts` produces (header elided):

```c
while_loop _loop_0(i < n, int i = 0, int n = 0, int sum = 0) {
    sum = sum + i;
    i = i + 1;
}

function int sum_to(int n) {
    slot int sum = 0;
    slot int i = 0;
    slot int _i_l0 = i;
    slot int _n_l0 = n;
    slot int _sum_l0 = sum;
    loop _loop_0(i < n, _i_l0, _n_l0, _sum_l0);
    i = _i_l0;
    n = _n_l0;
    sum = _sum_l0;
    return sum;
}
```

The `for` loop has been lifted into a top-level `while_loop` **declaration** — a first-class loop function whose parameters are the recurrent state (`i`, `n`, `sum`). At the call site, that state is passed as `slot` variables and copied back after the loop returns. This is Sutra's loops-as-RNN-cells model: the body is one cell evaluation, and the whole loop unrolls to a fixed-length tensor-op chain with a soft-halt mask. Validate it:

```bash
sutrac for.su
# ok: 1 file(s) validated, 0 diagnostics
```

The structural transformation — `for` to a substrate-resident declared loop — is the headline. The [Loops](../loops.md) page covers the runtime model the unrolled cell executes on.

## What maps, and what doesn't yet

The transpiler ships valid Sutra for a typed core of the language:

- **Maps cleanly today:** functions (incl. arrow-as-`const`), `string` and string concatenation, `Math.*`, numeric operators, `while` / `for` / `do-while` → declared loops, `async` / `await` / `Promise<T>`, interfaces and type aliases (erased), discriminated unions, enums, and module imports.
- **Untyped JavaScript** is read as untyped TypeScript: values with no type annotation become `JavaScriptObject`, the fallback runtime. Such files transpile, but the `JavaScriptObject` runtime is still being built, so untyped programs don't run end-to-end yet — add type annotations to stay on the fast path.
- **Out of scope:** `eval`, prototype mutation, runtime-loaded code, array-method chaining (`.map` / `.filter`), template literals, and regex. These belong to the dynamic edge of JavaScript; the transpiler rejects them rather than faking them.

For the complete per-feature surface, see the [TypeScript → Sutra mapping](../typescript-to-sutra.md) reference.

## Read next

- [TypeScript → Sutra mapping](../typescript-to-sutra.md) — the full per-feature reference, with a status matrix.
- [Loops](../loops.md) — the declared-loop / RNN-cell model the `for` example compiles into.
- [Numeric math](../numeric-math.md) — why substrate arithmetic is approximate.
