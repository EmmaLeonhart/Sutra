# Defuzzification: `is_true` and `defuzzify`

```
is_true(x)               → fuzzy in [0, 1]            // one-shot polarization
defuzzify(x)             → fuzzy in [0, 1]            // default = 10 iterations
defuzzify(x, iters)      → fuzzy in [0, 1]            // explicit iteration count
```

The mechanism for *polarizing* fuzzy computation. **Defuzzification never returns a crisp 0/1.** It sharpens the fuzzy state along a target axis — concentrating the mass — while keeping the result a fuzzy quantity that is still a vector and still differentiable. There is no "extract a crisp answer" step in Sutra. Downstream consumers that want a definite answer compare the polarized fuzzy against a threshold (default 0.5 per §26 single-option `select`); the threshold is a *consumer* choice, not a property of the polarization.

`is_true(x)` does one polarization step. `defuzzify(x)` is the user-facing entry point — it iterates `is_true` ten times by default, which is "a lot of polarization" in the sense that the fuzzy mass is sharply concentrated, but the output is still fuzzy. `defuzzify(x, iters)` gives explicit control. `defuzzify(x, 1) == is_true(x)`.

The mechanism is the same in both cases: a **matrix derived from the vector itself** (see "The Truth-Extraction Matrix" below) is repeatedly applied. Each application polarizes more; none binarizes.

> **Recurring correction:** Earlier versions of this spec described `is_true` as "extracting crisp answers." That framing is wrong and has caused repeated confusion. The output of `is_true` and `defuzzify` is a fuzzy quantity. Polarization ≠ binarization. The §26 spec move (dropping `gate` for `select` / `select else`) depends on this — there is no commit primitive in Sutra because defuzzification is differentiable, and it is differentiable because the output stays fuzzy.

Open design question: does iterated polarization converge toward 1.0 (certainty attractor), oscillate, or have more complex fixed-point behavior? The answer likely depends on the operator definition and may itself be a tunable parameter. The 10-iteration default is provisional — chosen because it is "a lot" without committing to a specific convergence model.

This is a first-class language concern, not a library afterthought. "How polarized is this?" is always a valid question in Sutra.

## The Truth-Extraction Matrix

The proposed mechanism for `is_true` is a **matrix derived from the vector itself**. Given a vector `v`, there exists a matrix `M(v)` such that:

```
M(v) * v = t
```

where `t` is the truth vector — a canonical vector representing "true" in the embedding space.

The matrix `M(v)` is not a single global matrix. It is **derived from `v`** — it encodes "what does truth mean for this particular vector / this region of the space." Different vectors in different parts of the space will produce different truth-extraction matrices, because what it means for something to be true depends on what the something *is*.

### Equality via Truth Vectors

Once you can extract a truth vector from any vector, you can **evaluate equalities**:

```
is_equal(a, b) = similarity(M(a) * a, M(b) * b)
```

Two vectors are "equal" if their truth-extraction matrices map them to the same (or similar) truth vector. This is more nuanced than raw cosine similarity between `a` and `b` — it asks "are these the same *in terms of what they assert*?" rather than "are these close in embedding space?"

### Recursive Refinement

Recursive application works by repeatedly applying the truth extraction:

```
t_1 = M(v) * v                    # first-order truth
t_2 = M(t_1) * t_1                # second-order: "how true is it that this is true?"
t_3 = M(t_2) * t_2                # third-order refinement
...
```

Each application re-evaluates the truth of the previous result using a matrix derived from that result. The intuition: the first application asks "is this true?", the second asks "is my assessment of truth reliable?", the third asks "is my reliability assessment reliable?", and so on.

The key question is convergence behavior:
- **Fixed-point convergence:** The sequence `t_1, t_2, t_3, ...` converges to a stable truth value. This is the desirable case — recursive application "locks in" to a confident answer.
- **Oscillation:** The sequence alternates between values. This would indicate the truth assessment is unstable for this vector — itself useful information (it means the proposition is genuinely ambiguous).
- **Divergence:** The sequence explodes. This would indicate a pathological region of the space where truth extraction doesn't work — a substrate defect that should be caught by integrity checking.

### Mathematical Plausibility

This is essentially saying that truth is a **learned linear projection** specific to each vector's neighborhood in the embedding space. The matrix `M(v)` can be thought of as:

- A rotation that aligns `v` with the truth axis
- A projection onto the subspace where truth/falsehood is discriminable
- A learned transformation that captures "what would need to be true about the world for `v` to be true"

Since `M` is derived from `v`, this is a nonlinear operation overall (even though each individual application is a matrix multiply). The nonlinearity comes from the dependence of `M` on its input — this is what gives recursive application its refining power rather than just being repeated linear projection.

The exact mechanism for deriving `M(v)` from `v` is an open design question. Candidates:
- **Learned neural network:** A small network that takes `v` and outputs the matrix entries
- **Geometric derivation:** Construct `M` from `v`'s position relative to known reference vectors
- **Decomposition-based:** Use the structure of `v` (its bindings and bundles) to analytically construct the appropriate truth projection
