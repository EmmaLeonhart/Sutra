// Expected error: AKA0110 - `|>` pipe-forward operator not supported.
// The spec explicitly forbids it; use nested calls or method chains.

function vector Bad(vector a, vector b) {
    return embed("cat") |> Blend(b) |> Normalize;
}
