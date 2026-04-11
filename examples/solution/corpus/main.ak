/// corpus/main.ak — entry point for the `corpus` project in the
/// embedding-pipeline example solution.
///
/// This project declares three named reference vectors that downstream
/// projects (like `similarity`) can look up by name. Each vector is
/// materialized via the `basis_vector` builtin, which registers the
/// name in the substrate's codebook and returns a vector handle.

function vector Corpus() {
    vector cat = basis_vector("cat");
    vector dog = basis_vector("dog");
    vector mouse = basis_vector("mouse");
    return cat;
}

function.Corpus();
