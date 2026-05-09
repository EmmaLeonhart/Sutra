// Multi-function fixture: locks down the composition of features
// that landed across the session — interface + Axon-typed param +
// if-implicit-else + while loop with multiple body statements +
// function-call-in-expression-context + let-as-slot.

interface Range { lo: number; hi: number }

function clamp(value: number, r: Range): number {
    if (value < r.lo) return r.lo;
    return value;
}

function sum_clamped(arr_size: number, max: number): number {
    const r: Range = { lo: 0, hi: max };
    let total = 0;
    let i = 0;
    while (i < arr_size) {
        total = total + clamp(i, r);
        i = i + 1;
    }
    return total;
}

function main(): number {
    return sum_clamped(10, 5);
}
