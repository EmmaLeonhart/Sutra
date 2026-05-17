# Demos

Ten `.su` programs live in [`examples/`](https://github.com/EmmaLeonhart/Sutra/tree/master/examples) and are exercised end-to-end by the smoke test:

```bash
git clone https://github.com/EmmaLeonhart/Sutra
cd Sutra
python examples/_smoke_test.py
```

The smoke test compiles each `.su` source through the reference codegen path, executes the emitted Python, and compares the output to a hardcoded expected table. Seed and dimensions are fixed, so results are deterministic.

## The smoke-tested programs

| # | File | What it demonstrates |
|---|---|---|
| 0 | [`hello_world.su`](https://github.com/EmmaLeonhart/Sutra/blob/master/examples/hello_world.su) | Embed plus retrieve. Three candidate phrases, `argmax_cosine`, name lookup at the edge. |
| 1 | [`fuzzy_branching.su`](https://github.com/EmmaLeonhart/Sutra/blob/master/examples/fuzzy_branching.su) | Weighted-superposition conditional. Four program variants × four inputs. All branches contribute to a weighted sum; `argmax_cosine` commits at the end. |
| 2 | [`role_filler_record.su`](https://github.com/EmmaLeonhart/Sutra/blob/master/examples/role_filler_record.su) | Structured record as a flat vector. `bundle(bind(role, filler), …)`; decode a field by `unbind(role, record)` followed by `argmax_cosine`. |
| 3 | [`classifier.su`](https://github.com/EmmaLeonhart/Sutra/blob/master/examples/classifier.su) | Bundled-prototype classifier. Three classes, three examples each, bundle averages them into a per-class prototype. |
| 4 | [`analogy.su`](https://github.com/EmmaLeonhart/Sutra/blob/master/examples/analogy.su) | Associative pair memory. Five (capital, country) pairs bundled into one vector; query a capital, recover the country. |
| 5 | [`knowledge_graph.su`](https://github.com/EmmaLeonhart/Sutra/blob/master/examples/knowledge_graph.su) | Bundled triples with compositional query. `bind(object, bind(subject, predicate))`; lookup is `unbind(predicate, unbind(subject, graph))`. |
| 6 | [`predicate_lookup.su`](https://github.com/EmmaLeonhart/Sutra/blob/master/examples/predicate_lookup.su) | Multi-object superposition. When a (subject, predicate) key has multiple objects, all members score above all non-members. |
| 7 | [`fuzzy_dispatch.su`](https://github.com/EmmaLeonhart/Sutra/blob/master/examples/fuzzy_dispatch.su) | N-way dispatch returning structured records. Each branch returns an (action, target) record; the winner is decoded with two `unbind` calls. |
| 8 | [`nearest_phrase.su`](https://github.com/EmmaLeonhart/Sutra/blob/master/examples/nearest_phrase.su) | 20-phrase codebook, clean and noisy retrieval. Target plus 0.2·distractor still returns target. |
| 9 | [`sequence.su`](https://github.com/EmmaLeonhart/Sutra/blob/master/examples/sequence.su) | Position-bound sequence encoder. A 5-token sequence is one vector; decode any position with `unbind(pos_i, record)`. Two sequences compared by cosine. |

The earlier loop demos (`loop_rotation.su`, `counter_loop.su`, `concept_search.su`) used the retired C-style `loop (cond) { ... }` eigenrotation surface; the 2026-04-30 redesign moved loops to first-class declared functions, and those three demos were removed when their syntax stopped parsing. Loop coverage now lives in [`do_while_adder.su`](https://github.com/EmmaLeonhart/Sutra/blob/master/examples/do_while_adder.su) (the canonical `do_while` declared-function example) plus the `test_loop_function_decl.py` test suite (23 tests). See the [Loops page](loops.md) for the current surface.

## Other examples in the directory

`examples/` contains additional programs that aren't part of the smoke-test asserted-output table but exist as reference material:

- `do_while_adder.su` — minimal `do_while` declared-function loop.
- `imperative_reversible.su` — slot-based reversible state demo.
- `classes_demo.su` — empty-body class declarations (the MVP form, see [Ontology](ontology.md)).
- `analogy_minilm.su`, `analogy_mxbai.su` — substrate-sweep variants of `analogy.su`.
- `protein_record.su` — the same role-filler shape applied to ESM-2 protein-language-model embeddings.
- `rotation_hashmap.su`, `rotation_book_catalog.su`, `rotation_record.su` — rotation-binding library patterns.
- `tutorial.su` — companion source for the tutorials.
- `wait_keyword_demo.su` — the `wait` reserved-keyword shape.

These don't have asserted outputs in the smoke test but parse and (where the codegen supports them) execute under the standard pipeline.

## The primitives the smoke-tested demos exercise

| Operation | What it computes | Demo files |
|---|---|---|
| `basis_vector(name)` | embed a string through the substrate | all |
| `bundle(a, b, …)` | sum and L2-normalize | 1, 2, 3, 4, 5, 6, 7, 9 |
| `bind(role, filler)` | rotation binding: `Q_role @ filler` | 1, 2, 5, 7, 9 |
| `unbind(role, record)` | inverse rotation: `Q_role^T @ record` | 2, 5, 6, 7, 9 |
| `similarity(a, b)` | cosine similarity | 1, 6, 9 |
| `argmax_cosine(query, [candidates])` | nearest codebook entry | 0, 1, 3, 4, 5, 7, 8 |
| `select([scores], [options])` | softmax-weighted superposition | 1, 7 |
| Scalar-vector multiply, vector add | weighted superposition | 1, 7 |
| `map<vector, string>` lookup | the single edge bridge from vector to host string | all |

There is no `if`, `while`, `for`, or `switch` in any of these programs. Every conditional is a weighted sum across all options; the commitment to a discrete answer happens at the final `argmax_cosine` or map lookup. Loop primitives show up in `do_while_adder.su` and the dedicated test suite, not in the smoke-tested ten.

## Reading the source

The `.su` files are deliberately short (30–100 lines each including comments) and meant to be read front-to-back. Start with `hello_world.su` for the minimal shape; `role_filler_record.su` and `knowledge_graph.su` are the richest for understanding bind/unbind composition; `do_while_adder.su` is the smallest example of the new loop surface.

To inspect the generated Python for any demo:

```bash
sutrac --emit examples/knowledge_graph.su
```

The emitted module is self-contained — it instantiates a small `_VSA` runtime class and calls into it for every Sutra primitive.
