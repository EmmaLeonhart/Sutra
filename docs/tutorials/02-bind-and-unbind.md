# 02 — Bind and unbind

Binding is the operation that makes Sutra a programming language instead of a fancy similarity-search interface. It is how you say *"the agent of this sentence is the cat,"* using nothing but vector arithmetic. Without it, you can only do retrieval. With it, you can do *structured representation*.

## What you'll learn

- What `bind` and `unbind` mean geometrically
- Why the textbook VSA binding operation (Hadamard product) **fails** on natural embedding spaces
- How sign-flip binding fixes that with a single sign mask
- The empirical numbers from the paper: 14/14 correct recoveries on three different embedding models, sustained 10/10 chained computation

## The motivating example

Imagine you want to encode the sentence *"the cat is sitting"* as a single vector. You have the words `cat`, `sit`, `agent`, `action`. The naive thing to do is just bundle them together with `bundle(cat, sit, agent, action)` — but bundling is *commutative* and *associative*. The bundled vector for `(agent=cat, action=sit)` is identical to the bundled vector for `(agent=sit, action=cat)`. You've lost the structure.

The fix is to *bind* each value to its *role* before bundling:

```c
vector cat = embed("cat");
vector sit = embed("sit");
vector agent = basis_vector("agent");
vector action = basis_vector("action");

// Bind each filler to its role, then bundle the bound pairs.
vector sentence = bundle(
    bind(agent, cat),
    bind(action, sit)
);
```

Now the bundled vector encodes *the agent is the cat* and *the action is sit*, and the two facts are recoverable from the bundle by *unbinding* the role you want:

```c
vector recovered_cat = unbind(agent, sentence);
vector recovered_sit = unbind(action, sentence);
```

`recovered_cat` is approximately `cat`, and `recovered_sit` is approximately `sit`. Approximately, not exactly — there is crosstalk from the other bundled pair, but the result is *similar enough* to the original that a `snap-to-nearest` (next tutorial) recovers the correct answer.

## What "binding" actually does, geometrically

Binding two vectors produces a **third vector that is dissimilar to both inputs**. That dissimilarity is exactly what makes the operation useful: the bound vector `bind(role, filler)` is "stored" in a region of the embedding space that doesn't *look like* either the role or the filler, so the bundle of many bound pairs doesn't collapse all of its components into one mushy attractor.

The classical Vector Symbolic Architecture literature uses **the Hadamard product** (elementwise multiplication) for binding. It works perfectly on *random* hypervectors — the kind you generate by sampling from a uniform distribution. And for two decades nobody questioned it, because everyone in the VSA literature was using random hypervectors.

Then we tried it on **frozen general-purpose text embeddings** (mxbai-embed-large, BGE-large, GTE-large, Jina-v2). The Hadamard product **failed**. At 2 bundled role-filler pairs, the recovered filler had cosine similarity ~0.11 with the actual filler — barely above noise. At 7 bundled pairs, signal was completely gone. Snap-to-nearest got the right answer 2 out of 7 times, no better than chance.

The reason is that natural embeddings are **correlated and anisotropic**. The dimensions are not independent. The vectors are not random. The Hadamard product, applied to two correlated vectors, produces a *very biased* third vector — one that lives in a small subspace and looks too much like everything else.

## Sign-flip binding: the fix

Sutra's default binding operation is **sign-flip**. It is one line:

```python
result = a * np.sign(b)
```

That's it. Take the *sign* of every dimension of `b` (so a vector of `+1`s and `-1`s), then multiply it elementwise into `a`. The sign-pattern of `b` is a deterministic but pseudo-random binary mask. It strips the magnitude-correlation that wrecks the Hadamard product, and what's left is a clean *encrypted* version of `a`.

Critical properties:

- **Self-inverse.** `bind(a, b) = a * sign(b)`, and applying sign(b) again recovers `a` because `sign(b) * sign(b) = +1` everywhere. Unbinding *is* binding.
- **Nearly orthogonal across roles.** Two different role vectors produce two different sign masks, and the masks have ~50% overlap by chance, so binding the same filler under two different roles produces two vectors that are ~0 correlated.
- **Cheap.** 6.6 microseconds per operation on a CPU. About 4× the cost of Hadamard, but vastly cheaper than rotation binding (321 µs).

The empirical numbers from the [Sutra paper](../papers.md):

| Method            | Cos at 2 roles | Cos at 7 roles | Snap correct (7) | Cost (µs) |
|-------------------|---------------:|---------------:|-----------------:|----------:|
| Hadamard          |           0.11 |           0.09 |              2/7 |       1.5 |
| **Sign-flip**     |       **0.74** |       **0.40** |          **7/7** |   **6.6** |
| Permutation       |           0.71 |           0.37 |              7/7 |      30.9 |
| Circular conv     |           0.29 |           0.13 |              7/7 |      79.3 |
| FFT correlation   |           0.62 |           0.34 |              7/7 |      67.3 |
| **Rotation**      |       **0.89** |       **0.80** |          **7/7** |   **321** |

Sign-flip is the best cost/quality tradeoff on natural embeddings. It is Sutra's default for that reason, and rotation binding (`bind_precise`) is available as the high-accuracy alternative when you need it.

## Sustained computation: 10/10 chained operations

A single bind-unbind pair is not the interesting case. The interesting case is *can you do this over and over and have the result still mean something?* In the paper we built a chained loop:

1. Take the previous result, bind it with a fresh role
2. Bundle the bound pair into a structure with two other bound pairs
3. Unbind the target role
4. Snap-to-nearest to clean up
5. Use the result as the input to step 1 of the next iteration

Sign-flip binding survives **10/10 cycles** of this on GTE-large with raw cosine staying in the 0.58-0.65 range and snap recovering the exact target every time. This is what makes long-form Sutra programs feasible — you can do real multi-step computation without the signal degrading into noise.

The same result holds across substrates: BGE-large-en-v1.5 (1024-dim) and Jina-v2-base-en (768-dim) both achieve identical 10/10 sustained chains. The choice of binding operation matters; the choice of substrate (within reason) does not.

## Multi-hop composition

The other test that matters: can you take a value out of one structure and put it into a *different* structure? We constructed two bound bundles:

```c
vector A = bundle(
    bind(agent_role, cat),
    bind(action_role, sit)
);

vector B = bundle(
    bind(agent_role, dog),
    bind(patient_role, unbind(agent_role, A))
);
```

The inner `unbind(agent_role, A)` extracts the cat from structure `A`. That extracted-and-noisy `cat` then gets bound to `patient_role` in structure `B`. Now `B` represents *"dog (agent) [is doing something to] cat (patient)"*. Final test: extract the patient from `B` and check that it is still recognizably `cat`.

All three extractions — `agent` from `A`, `patient` from `B`, `agent` from `B` — return the correct filler. **Multi-hop composition works.** This is the operation you need for *any* multi-step inference: pull a fact out of one place, plug it into another, keep going.

## What you should remember

- Binding is the geometric way to *associate* one vector with another, producing a third vector dissimilar to both.
- Unbinding is the inverse, and for sign-flip binding it is *the same operation*.
- Bundling is how you *combine* multiple bound pairs into one structure-vector.
- Hadamard binding doesn't work on natural embeddings. Sign-flip does.
- The whole binding-bundling-unbinding-snap loop works on real data, sustained over many steps, across multiple substrates.

## What to read next

- **[03 — Snap-to-nearest](03-snap-to-nearest.md)** — the cleanup operation that makes the chained computation in this tutorial possible. Without snap, the noise from each unbind step accumulates and the signal eventually dies. With snap, you stay locked to the codebook and the loop runs forever.
- The [Sutra paper](../papers.md) — §6.2 has the full binding alternatives table, the chained-computation result, and the multi-hop composition result.
