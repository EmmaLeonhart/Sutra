// Math.* transcendentals — TS source. The transpiler passes these
// through verbatim because Sutra has matching `Math.foo` static
// intrinsics; the Sutra codegen routes them to `_VSA.foo` which
// evaluates via the substrate-pure interpolated-lookup-table path
// (planning/findings/2026-05-10-interpolated-lookup-table-works.md).
// Out-of-range inputs raise SutraMathOverflow.
//
// Fixture sticks to integer-typed inputs because TS `number` lowers
// to Sutra `int` by default in the transpiler today; floating-point
// type inference for `number` is a known follow-on. The runtime
// math intrinsics accept either — the int annotation is just the
// surface-level Sutra type, the underlying _VSA.exp / log / pow / sqrt
// always operate on float values.

function rooted(n: number): number {
    return Math.sqrt(n);
}

function powered(base: number, exponent: number): number {
    return Math.pow(base, exponent);
}

function main(): number {
    // pow(2, 10) ≈ 1024 (within float32 + lookup-table tolerance).
    return powered(2, 10);
}
