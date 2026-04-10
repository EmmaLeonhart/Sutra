// Expected error: AKA0002 - unterminated string literal.
// The lexer should emit the error and the parser should recover.

function string Bad() {
    return "this string never closes;
}
