# Defuzzification: `is_true`

```
is_true(x)           → scalar in [0, 1]
is_true(is_true(x))  → refined confidence
```

The mechanism for extracting crisp answers from fuzzy computation. `is_true` takes a vector and returns a truth value (similarity to a reference "true" vector, or magnitude, or some learned function).

Recursive application (`is_true(is_true(x))`) allows dialing in confidence at arbitrary granularity. Open design question: does this converge toward 1.0 (certainty attractor), oscillate, or have more complex fixed-point behavior? The answer likely depends on the operator definition and may itself be a tunable parameter.

This is a first-class language concern, not a library afterthought. "How true is this?" is always a valid question in S2.
