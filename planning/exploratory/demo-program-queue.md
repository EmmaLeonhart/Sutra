# Demo program queue (2026-04-14)

Seven programs that are reachable with Sutra's current primitive set
(`bundle`, `bind`, `unbind`, `similarity`, `argmax_cosine`, plus the
`map<vector, string>` edge). None require `loop(cond)`, PyTorch, real
LLM embeddings, or the connectome substrate. Each is a natural next
demonstration past the three that already run (hello world, fuzzy
branching, role-filler record).

Built in this order because each builds on what the previous ones
exercise:

## 1. Classifier

Bundle prototype vectors per class, `argmax_cosine` to classify novel
inputs.

```
proto_A = bundle(example_A_1, example_A_2, example_A_3);
proto_B = bundle(example_B_1, example_B_2, example_B_3);
classify(input) = argmax_cosine(input, [proto_A, proto_B, proto_C, ...]);
```

Generalizes `fuzzy_branching.su` from 4 hand-coded behaviors to
averaged prototypes. Distinct because the prototype comes from
bundling multiple examples rather than a single basis vector, which is
the first demonstration of bundle's averaging / noise-averaging
property.

## 2. Analogy solver

`A : B :: C : ?` via VSA:

```
transform = unbind(A, B);      // "what operation takes A to B"
answer    = bind(C, transform); // apply the same op to C
result    = argmax_cosine(answer, codebook);
```

Textbook VSA demonstration. First demo where `bind` and `unbind` are
used compositionally rather than as straight encode/decode.

## 3. Flat knowledge graph

Triples as bound-pair records, bundled into a flat vector:

```
triple(s, p, o) = bind(s, bind(p, o));
graph = bundle(triple_1, triple_2, ..., triple_N);
```

Query: given subject + predicate, recover object:

```
object ~= unbind(p, unbind(s, graph));
```

Generalization of `role_filler_record.su` where roles are now
*predicates* and the record holds N triples rather than one
three-field record. Exercises nested bind/unbind and larger bundles.

## 4. Predicate/relation lookup

A specific shape of (3): given a predicate and a subject, the decode
path should give every object that participated. The demo exercises
bundle's superposition property — if `alice likes cats` and `alice
likes dogs`, the unbind path yields a superposition of cat+dog which
decodes in either direction but with a distinctive split-similarity
signature.

## 5. Fuzzy dispatch (N-way)

`select` over N branches where each branch result is a bound record,
not a scalar behavior. Inputs dispatch fuzzily, and the result carries
structured information (e.g. "which action, toward which target, with
what intensity") that can be decoded by further unbinds.

Generalization of `fuzzy_branching.su` from 4 → N branches and from
scalar → structured result.

## 6. Nearest-phrase / spell-correct

Codebook of phrases, embed input, argmax_cosine. Scales
`hello_world.su` from 3 candidates to something realistic (20–50
phrases). The point is to exercise codebook lookup at non-trivial
scale and to verify that cosine-argmax remains well-behaved.

## 7. Sequence encoder

Position-bound bundle:

```
encode(seq) = bundle(
    bind(pos_0, seq[0]),
    bind(pos_1, seq[1]),
    ...
);
decode_at(record, i) = argmax_cosine(unbind(pos_i, record), token_codebook);
```

First demo where a vector represents a *sequence*. Also supports
sequence similarity (bundled encodings compared by cosine) and sliding-
window extraction. Foundational for any future parsing / language-model
demos.

## Out of scope for this queue

- `loop(cond)` demos — the primitive is implemented but untested.
  Building a data-dependent iteration demo is worthwhile, but comes
  after these seven bind/bundle/unbind/select demos land.
- Real LLM embeddings — the compiler uses fresh random basis vectors.
  Wiring `embed("string")` to an actual model is a separate project.
- Training / gradient descent — needs the PyTorch backend.

## Harness

All seven go through `examples/_smoke_test.py` the same way the
existing three do: compile via `sutra_compiler`, exec, verify outputs
against a committed expected table. A clean run should report `PASS`
and however many `OK` lines the seven new demos add.
