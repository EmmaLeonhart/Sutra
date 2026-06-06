// Explicit if/else returning bare-atom branches — exercises the
// _lower_statement if_statement defuzz-blend path. Regression guard for
// the `* (atom)` → CastExpr parser ambiguity (fixed 2026-06-05).

function maxi(a: number, b: number): number {
    if (a >= b) {
        return a;
    } else {
        return b;
    }
}

function main(): number {
    return maxi(5, 3);
}
