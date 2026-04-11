/// similarity/main.ak — entry point for the `similarity` project in
/// the embedding-pipeline example solution.
///
/// This project depends on the `corpus` project and computes a
/// cosine similarity between a query vector and the corpus'
/// reference vectors. In the v1 solution system dependency
/// resolution only validates the edge; cross-project name lookup
/// (importing `corpus`'s `Corpus()` function) is not yet wired
/// through the compiler's name resolver, so this file defines
/// its own basis vectors for now. A future revision will import
/// from the dependency.

function fuzzy SimilarityScore(vector query) {
    vector cat = basis_vector("cat");
    return similarity(query, cat);
}

function.SimilarityScore(basis_vector("dog"));
