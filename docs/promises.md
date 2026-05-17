# Promises and async/await

`async`, `await`, and `Promise<T>` are first-class Sutra vocabulary — not stdlib helpers, not TypeScript imports. The language has them natively. They look the way they look in JavaScript and TypeScript because there's no reason to invent a new spelling for the same idea, and because programs written in TS-style with promises mostly run as-is in Sutra.

What makes them work is a **two-stage beta-reduction** at compile time. The same program is rewritten twice on the way to the substrate:

1. **Stage 1**: `async` and `await` get rewritten into explicit `Promise<T>` construction with `.then()` / `.catch()` chains. Pure surface rewriting. No substrate concerns.
2. **Stage 2**: each `Promise<T>` value gets rewritten into a `while_loop` whose halt vector has two channels — `fulfilled` and `rejected`. This is the substrate-bottom step. From here on, the program is a tail-recursive RNN cell running on the GPU.

The point of doing it in two stages, instead of going from `async/await` straight to a loop, is that the **middle stage is itself useful**. You can write `new Promise(executor)` directly when that fits your program. You can pass `Promise<T>` values around, store them, return them. The Promise is a real concept the language understands, not just a transient compiler artifact.

---

## The progression, in three boxes

For each of the worked examples below, the leftmost box is what the user wrote (or what TypeScript users would recognise). The middle box is what stage 1 produces — still Sutra source, but with no `async` or `await` keywords left, just explicit `Promise<T>` calls. The rightmost box is what stage 2 produces — a declared `while_loop` that runs on the substrate.

### Example 1 — single await on a fetched value

<div markdown="1">
<table>
<tr>
<th width="33%">Stage 0 — what you write (async / await)</th>
<th width="33%">Stage 1 — Promise construction</th>
<th width="33%">Stage 2 — substrate while_loop</th>
</tr>
<tr>
<td markdown="1">

```c
async function Promise<vector>
    fetch_label(vector q)
{
    vector raw =
        await network_lookup(q);
    return argmax_cosine(
        raw, [a, b, c]
    );
}
```

</td>
<td markdown="1">

```c
function Promise<vector>
    fetch_label(vector q)
{
    return network_lookup(q)
        .then(vector raw -> {
            return Promise.resolve(
                argmax_cosine(
                    raw, [a, b, c]
                )
            );
        });
}
```

</td>
<td markdown="1">

```c
while_loop fetch_label_body(
    !arrived(in.raw_response)
        && !in.rejected,
    axon in,
    slot vector result : vector
) {
    pass in, result;
}

function Promise<vector>
    fetch_label(vector q)
{
    axon in =
        network_lookup_axon(q);
    slot vector result : vector =
        zero_vector();
    loop fetch_label_body(
        in, result
    );
    vector clean = argmax_cosine(
        in.raw_response, [a, b, c]
    );
    return promise_fulfilled(clean);
}
```

</td>
</tr>
</table>
</div>

The leftmost box is what the programmer types. The rightmost box is what runs on the GPU. The middle box never appears in the user's source code — but it's a real Sutra program in its own right, and you can write it directly if you want to.

### Example 2 — two chained awaits

<div markdown="1">
<table>
<tr>
<th width="33%">Stage 0 — async / await</th>
<th width="33%">Stage 1 — Promise construction</th>
<th width="33%">Stage 2 — substrate while_loop</th>
</tr>
<tr>
<td markdown="1">

```c
async function Promise<vector>
    pipeline(vector q)
{
    vector a =
        await stage_one(q);
    vector b =
        await stage_two(a);
    return b;
}
```

</td>
<td markdown="1">

```c
function Promise<vector>
    pipeline(vector q)
{
    return stage_one(q)
        .then(vector a -> {
            return stage_two(a)
                .then(vector b -> {
                    return Promise
                        .resolve(b);
                });
        });
}
```

</td>
<td markdown="1">

```c
// Two declared loops, one
// per await. The second
// runs after the first
// resolves; the second's
// input axon is gated on
// the first's resolved
// value.
while_loop pipeline_step1(
    !arrived(in1.value)
        && !in1.rejected,
    axon in1,
    slot vector a : vector
) { pass in1, a; }

while_loop pipeline_step2(
    !arrived(in2.value)
        && !in2.rejected,
    axon in2,
    slot vector b : vector
) { pass in2, b; }
```

</td>
</tr>
</table>
</div>

Sequential awaits chain into a sequence of declared loops, one per await. As an optimisation pass, sequential awaits gating on independent inputs may fuse into a single multi-channel loop — that's a future optimisation, not a correctness requirement.

### Example 3 — `try` / `catch` on rejection

<div markdown="1">
<table>
<tr>
<th width="33%">Stage 0 — async / await</th>
<th width="33%">Stage 1 — Promise construction</th>
<th width="33%">Stage 2 — substrate while_loop</th>
</tr>
<tr>
<td markdown="1">

```c
async function Promise<vector>
    getOrDefault(vector q)
{
    try {
        return await
            fetch_label(q);
    } catch {
        return default_label;
    }
}
```

</td>
<td markdown="1">

```c
function Promise<vector>
    getOrDefault(vector q)
{
    return fetch_label(q)
        .then(vector v -> {
            return
                Promise.resolve(v);
        })
        .catch(() -> {
            return Promise.resolve(
                default_label
            );
        });
}
```

</td>
<td markdown="1">

```c
// The .catch() chains a
// follow-on loop that
// fires only when the
// upstream loop's
// `rejected` channel
// saturates instead of
// `fulfilled`. The catch
// body's value becomes
// the surrounding
// promise's resolved
// value.
while_loop
    getOrDefault_body(
    !arrived(in.value)
        && !in.rejected,
    axon in,
    slot vector result : vector
) {
    pass in, result;
}
```

</td>
</tr>
</table>
</div>

There's no exception object — Sutra has no `raise` / `throw` primitive. The `catch` block runs unconditionally on rejection of the awaited promise, with no exception variable bound. The rejection reason from the underlying promise is recoverable via the promise's `.reason()` method if needed.

---

## The three states

| Promise state | What the loop is doing | What the halt vector looks like |
|---|---|---|
| Pending | Eigenrotation cycling — the loop is genuinely spinning | Both `fulfilled` and `rejected` channels < 1 |
| Fulfilled | Halt scalar saturated on the success side | `fulfilled ≈ 1`, `rejected ≈ 0`; result axon carries the resolved value |
| Rejected | Halt scalar saturated on the error side | `rejected ≈ 1`, `fulfilled ≈ 0`; result axon carries the rejection reason |

Per the design, **pending is not silence**. JavaScript's pending promises sit passively until callbacks fire; Sutra's pending promises are actively cycling at the substrate level the entire time. Every tick is an emission. This makes Sutra promises *inherently more observable* than JavaScript ones — there's no ambiguity between "still pending" and "silently crashed." If the heartbeat stops, the loop broke; if it's still emitting, the promise is still alive.

---

## I/O at loop boundaries — both ends, both directions

A promise's loop body has axons attached at one or both boundaries. The standard combinations:

| Position | Direction | Use case |
|---|---|---|
| Front of loop | Input | Standard `await` — gate body on input arrival |
| End of loop | Output | Standard `return` — emit resolved value |
| Front of loop | Output | "Starting" event — notify subscribers the loop began |
| End of loop | Input | Continuation — receive a downstream value before final exit |

The substrate doesn't distinguish input axons from output axons mechanically. The "input" / "output" labels are programmer-facing intent; the lowering treats them uniformly. This generality is the reason a single gated-loop primitive in Sutra can express promises, generators, streams, and observables — they're all the same shape underneath.

---

## What happens to plain TypeScript code

Most TypeScript code with promises runs in Sutra mostly as-is. The TS-to-Sutra transpiler converts type annotations (`number` → `int`, `string` → `String`, `Promise<T>` → `Promise<T>`) and lowers a few syntactic differences (template literals, `const`/`let` → typed-local declarations), but `async function`, `await`, and `Promise<T>` pass through verbatim because Sutra has the same vocabulary.

```typescript
// TypeScript source (input.ts)
async function fetchLabel(q: string): Promise<string> {
    const r = await networkLookup(q);
    return r;
}
```

becomes

```c
// Sutra source (transpiled output)
async function Promise<String> fetchLabel(String q) {
    JavaScriptObject r = await networkLookup(q);
    return r;
}
```

— the only meaningful difference is type-annotation positioning (Sutra puts the type before the name, like C; TypeScript puts it after, like Pascal). The async / await / Promise structure is preserved verbatim.

---

## Reference

Full spec — including the lowering rules, rejection-propagation semantics, and the open questions tracked against the implementation — lives at [`planning/sutra-spec/promises.md`](https://github.com/EmmaLeonhart/Sutra/blob/master/planning/sutra-spec/promises.md). The phased implementation plan tracks against [`queue.md`](https://github.com/EmmaLeonhart/Sutra/blob/master/queue.md) item 1.
