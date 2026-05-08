// Untyped JavaScript: every value gets the JavaScriptObject fallback
// type on the Sutra side. Mixed numeric / non-numeric usage stays
// dynamic — the JS `+` operator handles strings, numbers, and
// type coercion.

function double_or_concat(x) {
    return x + x;
}

function main() {
    return double_or_concat(7);
}
