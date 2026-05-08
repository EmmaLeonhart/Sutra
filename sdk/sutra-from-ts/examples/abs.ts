// Demonstrate if/else lowering: "strong defuzz then select."
// `if (x < 0) return -x;` followed by `return x;` collapses to
// `return select(is_true(x < 0), -x, x);`.

function abs(x: number): number {
    if (x < 0) return -x;
    return x;
}

function main(): number {
    return abs(-7);
}
