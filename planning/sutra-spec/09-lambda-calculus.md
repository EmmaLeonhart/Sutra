# Lambda Calculus Encoding

Sutra's computational universality claim rests on the ability to encode lambda calculus in VSA. This document covers how that encoding works, where it strains, and what it means for Sutra.

## The Mapping

| Lambda Calculus | VSA Encoding |
|---|---|
| Variable `x` | Atomic hypervector (random, high-dimensional) |
| Abstraction `λx.body` | `bind(VAR_role, x) + bind(BODY_role, encode(body))` |
| Application `(f a)` | `bind(FUNC_role, encode(f)) + bind(ARG_role, encode(a))` |
| Variable reference `x` | The atomic vector `x` itself |

Lambda terms are encoded as **trees in superposition**. Each node bundles its role-tagged children:

```
encode(App(f, a)) = bind(FUNC_role, encode(f)) + bind(ARG_role, encode(a))
encode(Lam(x, b)) = bind(VAR_role, encode(x)) + bind(BODY_role, encode(b))
encode(Var(x))    = x    # atomic vector, no further structure
```

To read back a component, unbind with the role vector:

```
unbind(FUNC_role, encode(App(f, a))) ≈ encode(f)    # approximate!
unbind(ARG_role, encode(App(f, a)))  ≈ encode(a)
```

The role vectors (`VAR_role`, `BODY_role`, `FUNC_role`, `ARG_role`) are fixed random vectors chosen at initialization. They act like field names in a struct — binding a role to a filler is like setting a field, unbinding is like reading one.

## The Substitution Problem

Beta reduction — the core computation step of lambda calculus — requires substitution: replace every occurrence of variable `x` in `body` with argument `a`. This is the hard part.

In symbolic lambda calculus, substitution is a tree walk: find every leaf labeled `x`, replace it with `a`. In VSA, the problem is fundamentally different: occurrences of `x` are not localized in the superposed vector. The variable `x` is bound into the structure at encoding time and cannot be found by scanning — it's entangled with the roles and other fillers.

**This is equivalent to the binding problem in cognitive science.** How do you update one slot of a distributed representation without corrupting the others? Strategies explored:

1. **Cleanup memory approach:** Decode the entire tree back to symbolic form, perform substitution symbolically, re-encode. This works but defeats the purpose — you're leaving vector space to do the hard part.

2. **Depth-aware mapping:** Encode binding depth as part of the role vector (e.g., `bind(VAR_role, bind(DEPTH_2, x))`). Substitution becomes: unbind at the target depth, rebind with the new value. Noise compounds with depth.

3. **Fixed-point / resonance:** Define substitution as a constraint satisfaction problem — the reduced form is an attractor in vector space. Iterate the operation until the representation stabilizes. Elegant but convergence is not guaranteed.

4. **Sequential tree rebuilding:** Walk the tree layer by layer, rebuilding each level with the substitution applied. Requires snap-to-nearest between layers to prevent noise accumulation.

## De Bruijn Indices

Named variables create scoping headaches in VSA (alpha-equivalence requires renaming, which requires finding and replacing — back to the substitution problem). **De Bruijn indices** replace variable names with positional numbers:

```
λx. λy. x    becomes    λ. λ. 2
λx. λy. y    becomes    λ. λ. 1
```

This maps naturally to VSA: instead of binding a variable name to a role, you bind a **depth counter**. The index is a permutation or shift operation on a fixed "pointer" vector. Substitution becomes: shift all indices, replace index 1 with the argument.

This eliminates the naming/scoping problem entirely but substitution still requires the shift+replace operations, which accumulate noise.

## Smolensky's Tensor Product Representations

Smolensky (1990) provides the theoretical foundation. A variable binding `role:filler` is a **tensor product** `role ⊗ filler`. A structure with multiple bindings is a sum of tensor products:

```
structure = (role_1 ⊗ filler_1) + (role_2 ⊗ filler_2) + ...
```

Unbinding is contraction with the role vector. In the exact (infinite-dimensional) case, this recovers the filler perfectly. In the approximate (finite-dimensional) case — which is what VSA and Sutra actually use — it recovers the filler plus noise proportional to the other terms.

The key insight: **the unbinding problem is formally equivalent to the substitution step in beta reduction.** If you can cleanly unbind, you can cleanly substitute. Both are limited by the same noise floor. This connects the practical engineering question (how noisy is unbinding?) to the theoretical question (can VSA compute arbitrary functions?).

## Tomkins-Flanagan & Kelly: Running Lisp in Vectors

The existence proof. Tomkins-Flanagan and Kelly built a **working Lisp 1.5 interpreter** using Holographic Reduced Representations (an HRR-based VSA). It implements:

- Variable binding via role-filler pairs
- Substitution (beta reduction) via unbind-rebind cycles
- Alpha renaming to avoid variable capture
- Recursive evaluation of nested expressions

This is not a theoretical argument — it actually runs. Lambda terms go in, reduced results come out. The catch: it relies heavily on **cleanup memory** (snap-to-nearest) after every reduction step to prevent noise accumulation from destroying the computation. Without cleanup, the interpreter degrades after a few reduction steps.

**What this means for Sutra:** Lambda calculus semantics are implementable in vector space. The price is mandatory periodic cleanup (snap-to-nearest). Pure algebraic computation without cleanup is limited to short chains. This is why snap-to-nearest is a core non-algebraic operation in Sutra, not an optimization — it's load-bearing for any computation deeper than a few steps.

## Implications for Sutra

VSA gives you a **memory format** for lambda terms. Lambda calculus gives you the **rewrite rules**. The challenge is making the rewrite rules work inside the memory without unpacking back to symbolic form.

Sutra's position: accept that deep computation requires periodic cleanup (snap-to-nearest), design the language so that cleanup points are explicit and predictable (like memory barriers in concurrent programming), and optimize the algebraic chains between cleanup points for maximum depth before noise becomes problematic.
