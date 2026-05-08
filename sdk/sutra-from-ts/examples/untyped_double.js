// Untyped JS: param `x` has no type annotation, so the transpiler
// declares it `JavaScriptObject x`. JavaScriptObject is a near-empty
// stdlib class extending vector — substrate arithmetic on it works
// because vectors support addition.

function double(x) {
    return x + x;
}

function main() {
    return double(21);
}
