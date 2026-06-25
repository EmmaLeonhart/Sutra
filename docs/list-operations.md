# List operations

Sutra has a first-class `list<T>` and the higher-order operations you expect — `map`, `filter`, `concat` — all **immutable**: each builds a *new* list and never mutates its input. That immutability is not a stylistic choice; it is what lets list operations sit cleanly on the substrate, where values are built, not edited in place.

## The call names are `array_*`

The operations are spelled `array_concat`, `array_map`, `array_filter` (plus `array_length` and `array_get` for reading results). The bare `map` and `filter` spellings are unavailable as call names because `map` is a **type keyword** — `map<K, V>` is the content-addressed codebook type you have already seen in the retrieval examples. So the list ops take the `array_` prefix to stay unambiguous.

| Operation | Meaning |
|---|---|
| `array_concat(a, b)` | new list — `a`'s elements, then `b`'s |
| `array_map(f, xs)` | new list — `f` applied to each element |
| `array_filter(pred, xs)` | new list — the elements where `pred` is true |
| `array_length(xs)` | number of elements |
| `array_get(xs, i)` | element `i` |

## Functions are values

`array_map` and `array_filter` take a **first-class function value** — either a named function or an inline arrow. A predicate passed to `array_filter` returns a `fuzzy` (a Sutra truth value), not a host boolean.

```c
function int dbl(int x)      { return x * 2; }
function fuzzy gt_one(int x) { return x > 1; }

// Named function passed to map; build [1,2,3,4] first, then double each.
function list<int> concat_then_double() {
    var joined = array_concat([1, 2], [3, 4]);
    return array_map(dbl, joined);        // -> [2, 4, 6, 8]
}

// Inline arrow function value.
function list<int> map_with_arrow() {
    return array_map((int x) => x * 10, [1, 2, 3]);   // -> [10, 20, 30]
}

// Predicate keeps the elements greater than one.
function list<int> keep_big() {
    return array_filter(gt_one, [1, 2, 3]);   // -> [2, 3]
}
```

This is the full program [`examples/list_ops.su`](https://github.com/EmmaLeonhart/Sutra/blob/main/examples/list_ops.su). It compiles and runs end-to-end on the PyTorch backend; the test `tests/test_list_ops.py` reads each result back through `array_length` / `array_get` and checks it against the values above.

## Immutability in practice

```c
var xs = array_concat([1, 2], [3, 4]);   // xs = [1,2,3,4]
var ys = array_map(dbl, xs);             // ys = [2,4,6,8]
// xs is still [1,2,3,4] — array_map built a new list, it did not touch xs.
```

Every operation returns a fresh list; the inputs are never modified. Chaining is just nesting: `array_filter(pred, array_map(f, xs))`.

## What runs where

The list itself is a **binding array** on the substrate — a real tensor structure, built and read with substrate operations. The element *transform* runs wherever the element type runs: with `int` elements at the current runtime configuration the per-element arithmetic is host-scalar, so `array_map(dbl, …)` folds the doubling on the host while the list structure lives on the substrate. With number-vector elements the transform is substrate work. The list API is the same either way.

These operations are implemented on the canonical **PyTorch** backend (`codegen_pytorch.py`). The deprecated numpy backend implements only `array_length` / `array_get`, not the higher-order ops.

## Keyed collections: `dict<K, V>`

`list<T>` is the *ordered* collection. For a *keyed* one, Sutra has the built-in
rotation-hashmap **`dict<K, V>`** — `m[key] = value` to store, `m[key]` to read, lowering
to the stdlib `hashmap_*` operations. Unlike a list, a whole dict is a **single
accumulator vector** (storage is `O(d)`, not `O(n)`), and a read recovers signal plus a
little noise, so you clean it up at the call site. The [Memory page](memory.md) explains
the mechanism and shows the `dict<K, V>` surface syntax end to end.

## Related

- [Memory without control flow](memory.md) — the keyed `dict<K, V>` hashmap and how rotation-binding storage works.
- [Operations and operators](operators.md) — the full primitive reference.
- [Primitive classes](primitive-classes.md) — the built-in types, including `map<K, V>`.
