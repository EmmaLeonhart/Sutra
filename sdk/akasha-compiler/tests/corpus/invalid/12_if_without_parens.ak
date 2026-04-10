// Expected error: AKA0100 - `(` required after `if`.
// Per the spec, conditionals are TypeScript-style and always use parens.

function void Bad(bool x) {
    if x {
        return;
    }
}
