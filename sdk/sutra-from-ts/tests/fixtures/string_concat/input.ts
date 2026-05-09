// String concatenation: `string + string` lowers to
// `String.string_concat(a, b)` (a Sutra static intrinsic added in
// stdlib/strings.su 2026-05-08). The runtime walks the codepoint
// axes and copies them into a fresh String vector.

function greet(name: string): string {
    const hello: string = "hello, ";
    return hello + name;
}

function main(): string {
    return greet("world");
}
