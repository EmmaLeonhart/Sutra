# 02 — Bind and unbind

Binding is the operation that makes Sutra a programming language instead of a fancy similarity-search interface. It is how you say *"the agent of this sentence is the cat,"* using nothing but vector arithmetic. Without it, you can only do retrieval. With it, you can do *structured representation*.

## What you'll learn

- What `bind` and `unbind` mean geometrically
- Why the textbook VSA binding operation (Hadamard product) fails on natural embedding spaces
- How rotation binding — Sutra's runtime mechanism — recovers correct fillers from bundled structures
- How chained bind-unbind cycles stay in a recoverable basin

## Try it live

The interactive widget below was built around an earlier Sutra binding mechanism (sign-flip) and currently illustrates the bundle / crosstalk / cleanup story rather than the rotation mechanics described in the rest of this page. The shape it shows — bind producing something dissimilar to both inputs, unbind recovering the original modulo crosstalk, snap rescuing the result — is the same shape rotation binding has, even though the per-step arithmetic is different. Treat it as intuition, not as the literal current implementation.

<div id="bind-unbind-widget"><noscript>(This page hosts an interactive bind/unbind widget that requires JavaScript. The prose below covers the same material; the widget is a live playground, not load-bearing content.)</noscript></div>

The [next tutorial](03-snap-to-nearest.md) covers the snap step in depth.

## The motivating example

Imagine you want to encode the sentence *"the cat is sitting"* as a single vector. You have the words `cat`, `sit`, `agent`, `action`. The naive thing is to bundle them with `bundle(cat, sit, agent, action)` — but bundling is *commutative* and *associative*. The bundled vector for `(agent=cat, action=sit)` is identical to the bundled vector for `(agent=sit, action=cat)`. You've lost the structure.

The fix is to *bind* each filler to its *role* before bundling:

```c
vector cat = "cat";
vector sit = "sit";
vector agent  = basis_vector("agent");
vector action = basis_vector("action");

// Bind each filler to its role, then bundle the bound pairs.
vector sentence = bundle(
    bind(agent,  cat),
    bind(action, sit)
);
```

Now the bundled vector encodes *the agent is the cat* and *the action is sit*. Both facts are recoverable by *unbinding* the role you want:

```c
vector recovered_cat = unbind(agent,  sentence);
vector recovered_sit = unbind(action, sentence);
```

`recovered_cat` is approximately `cat` and `recovered_sit` is approximately `sit`. Approximately, not exactly — there is crosstalk from the other bundled pair, but the result is *similar enough* to the original that an `argmax_cosine` against a codebook (or the snap step in tutorial 03) recovers the correct answer.

The argument convention is **role-first**: `bind(role, filler)`, `unbind(role, record)`. Sutra is consistent on this.

## What "binding" actually does, geometrically

Binding two vectors produces a **third vector dissimilar to both inputs**. That dissimilarity is what makes the operation useful: the bound vector `bind(role, filler)` lives in a region of the embedding space that doesn't *look like* either the role or the filler, so a bundle of many bound pairs doesn't collapse all its components into one mushy attractor.

The classical Vector Symbolic Architecture literature uses **the Hadamard product** (elementwise multiplication) for binding. It works on *random* hypervectors — the kind you generate by sampling from a uniform distribution. For two decades nobody questioned it, because everyone in the VSA literature was using random hypervectors.

Then we tried it on **frozen general-purpose text embeddings** (`nomic-embed-text`, `mxbai-embed-large`, `all-minilm`). The Hadamard product failed. Bundled structures lost signal at 2+ role-filler pairs because the recovered filler had cosine similarity barely above noise with the actual filler.

The reason: natural embeddings are **correlated and anisotropic**. The dimensions are not independent. The Hadamard product, applied to two correlated vectors, produces a *very biased* third vector — one that lives in a small subspace and looks too much like everything else.

## Rotation binding: the runtime mechanism

Sutra's runtime `bind` is **rotation binding**. The role argument seeds a deterministic Haar-random orthogonal matrix `Q_role`, and binding is matrix-vector multiplication:

```
bind(role, filler)  =  Q_role  @  filler
unbind(role, rec)   =  Q_role^T @ rec
```

`Q_role` is orthogonal, so `Q_role^T = Q_role^{-1}` and unbinding exactly inverts binding when applied to a bound vector alone. When applied to a bundled vector containing the bound pair plus other bound pairs, unbinding recovers the target filler plus crosstalk from the other terms — the standard VSA story, but with rotation as the algebra.

Why rotation works on natural embeddings where Hadamard doesn't:

- **Orthogonality is exact, not statistical.** `Q_role^T Q_role = I` by construction. The unbinding does not depend on the filler being uncorrelated with anything.
- **Cross-role isolation is exact in expectation.** Two Haar-random matrices from different role seeds are orthogonal in expectation, so binding the same filler under two different roles produces vectors that are uncorrelated.
- **The filler's geometry is preserved up to rotation.** A rotation is an isometry — it preserves norms, angles, and the substrate's metric structure. Bundle of rotated fillers is just bundle in a rotated frame.

The runtime cost is one matrix-vector multiply per bind, one per unbind. On GPU this is one kernel launch; on CPU at 768 dimensions it is ~590k float multiply-adds per bind (768²) and is the dominant per-op cost. The compiler's matrix-chain fusion pass (egglog post-pass, landed 2026-04-25) folds chains of binds into one cached matrix where it can.

## Sustained computation across chained operations

A single bind-unbind pair is not the interesting case. The interesting case is *can you do this over and over and have the result still mean something?* The chained pattern is:

1. Take the previous result, bind it with a fresh role.
2. Bundle the bound pair into a structure with two other bound pairs.
3. Unbind the target role.
4. Clean up against a codebook (`argmax_cosine` or `snap`).
5. Use the result as the input to step 1 of the next iteration.

The Sutra paper characterizes how long this loop stays in a recoverable basin — the cosine trajectory across cycles, the conditions under which cleanup recovers the right entry, and the substrates on which the loop is stable. The numbers in the paper were measured against an earlier sign-flip binding mechanism; the rotation-binding version preserves the cleanup property by construction (the inverse is exact when the bundle has only one term, and crosstalk is bounded by the substrate's cleanup margin) and is the binding `bind` actually compiles to today.

## Multi-hop composition

The other test that matters: can you take a value out of one structure and put it into a *different* structure?

```c
vector A = bundle(
    bind(agent_role,  cat),
    bind(action_role, sit)
);

vector B = bundle(
    bind(agent_role,   dog),
    bind(patient_role, unbind(agent_role, A))
);
```

The inner `unbind(agent_role, A)` extracts the cat from structure `A`. That extracted (and noisy) `cat` then gets bound to `patient_role` in structure `B`. Now `B` represents *"dog (agent) [is doing something to] cat (patient)."* Final test: extract the patient from `B` and check that it is still recognizably `cat`.

When binding and cleanup are operating in their valid range (per-substrate margins), all three extractions — `agent` from `A`, `patient` from `B`, `agent` from `B` — return the correct filler. This is the operation you need for *any* multi-step inference: pull a fact out of one place, plug it into another, keep going.

The `examples/knowledge_graph.su` and `examples/role_filler_record.su` demos exercise this pattern end-to-end.

## What you should remember

- Binding is the geometric way to *associate* one vector with another, producing a third vector dissimilar to both.
- Unbinding inverts binding by applying the transpose of the role's rotation matrix.
- Bundling combines multiple bound pairs into one structure-vector.
- Hadamard binding fails on natural embeddings. Rotation binding is what Sutra's runtime uses.
- The whole binding-bundling-unbinding-cleanup loop works on real LLM embeddings, sustained over many steps, across multiple substrates.

## What to read next

- **[03 — Snap-to-nearest](03-snap-to-nearest.md)** — the cleanup operation that keeps chained computation in a recoverable basin.
- The [binding spec](https://github.com/EmmaLeonhart/Sutra/blob/master/planning/sutra-spec/binding.md) — full design of semantic (learned-matrix) and rotation (synthetic-subspace) binding kinds.
- The [Sutra paper](../theory-and-paper.md) — empirical characterization of which bindings recover correctly across substrates and the per-operation costs.
