// if-then-return followed by a trailing return — exercises the
// _lower_function_body implicit-else defuzz-blend path (the second of
// the two if/else lowering sites). Regression guard for the
// `* (atom)` → CastExpr parser ambiguity (fixed 2026-06-05).

function maxi(a: number, b: number): number {
    if (a >= b) {
        return a;
    }
    return b;
}

function main(): number {
    return maxi(5, 3);
}
