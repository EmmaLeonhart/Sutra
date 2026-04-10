// Expected error: AKA0103 - `var` combined with explicit type.
// The syntax-decisions doc is explicit: never `var vector x`.

function void Bad() {
    var vector x = embed("cat");
}
