// C-style `for (init; cond; incr) body` — the most common loop shape
// in TS. Desugared by the transpiler to `init; while (cond) { body;
// incr; }` to reuse the while-loop lowering. A `continue` in the body
// would skip the increment with this desugar, but `continue` isn't
// supported in the lowering anyway.

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
