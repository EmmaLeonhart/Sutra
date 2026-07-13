# Demos

Twelve of the `.su` programs in [`examples/`](https://github.com/EmmaLeonhart/Sutra/tree/main/examples) are exercised end-to-end by the smoke test (the directory holds more — see [Other examples](#other-examples-in-the-directory) below):

```bash
git clone https://github.com/EmmaLeonhart/Sutra
cd Sutra
python examples/_smoke_test.py
```

The smoke test compiles each `.su` source through the reference codegen path, executes the emitted Python, and compares the output to a hardcoded expected table. Seed and dimensions are fixed, so results are deterministic.

## The smoke-tested programs

| # | File | What it demonstrates |
|---|---|---|
| 0 | [`hello_world.su`](https://github.com/EmmaLeonhart/Sutra/blob/main/examples/hello_world.su) | Embed plus retrieve. Three candidate phrases, `argmax_cosine`, name lookup at the edge. |
| 1 | [`fuzzy_branching.su`](https://github.com/EmmaLeonhart/Sutra/blob/main/examples/fuzzy_branching.su) | Weighted-superposition conditional. Four program variants × four inputs. All branches contribute to a weighted sum; `argmax_cosine` commits at the end. |
| 2 | [`role_filler_record.su`](https://github.com/EmmaLeonhart/Sutra/blob/main/examples/role_filler_record.su) | Structured record as a flat vector. `bundle(bind(role, filler), …)`; decode a field by `unbind(role, record)` followed by `argmax_cosine`. |
| 3 | [`classifier.su`](https://github.com/EmmaLeonhart/Sutra/blob/main/examples/classifier.su) | Bundled-prototype classifier. Three classes, three examples each, bundle averages them into a per-class prototype. |
| 4 | [`analogy.su`](https://github.com/EmmaLeonhart/Sutra/blob/main/examples/analogy.su) | Associative pair memory. Five (capital, country) pairs bundled into one vector; query a capital, recover the country. |
| 5 | [`knowledge_graph.su`](https://github.com/EmmaLeonhart/Sutra/blob/main/examples/knowledge_graph.su) | Bundled triples with compositional query. `bind(object, bind(subject, predicate))`; lookup is `unbind(predicate, unbind(subject, graph))`. |
| 6 | [`predicate_lookup.su`](https://github.com/EmmaLeonhart/Sutra/blob/main/examples/predicate_lookup.su) | Multi-object superposition. When a (subject, predicate) key has multiple objects, all members score above all non-members. |
| 7 | [`fuzzy_dispatch.su`](https://github.com/EmmaLeonhart/Sutra/blob/main/examples/fuzzy_dispatch.su) | N-way dispatch returning structured records. Each branch returns an (action, target) record; the winner is decoded with two `unbind` calls. |
| 7b | [`content_addressed_read.su`](https://github.com/EmmaLeonhart/Sutra/blob/main/examples/content_addressed_read.su) | NTM-style content-addressed read head. A colour key recalls the bound value by associative lookup. |
| 8 | [`nearest_phrase.su`](https://github.com/EmmaLeonhart/Sutra/blob/main/examples/nearest_phrase.su) | 20-phrase codebook, clean and noisy retrieval. Target plus 0.2·distractor still returns target. |
| 9 | [`sequence.su`](https://github.com/EmmaLeonhart/Sutra/blob/main/examples/sequence.su) | Position-bound sequence encoder. A 5-token sequence is one vector; decode any position with `unbind(pos_i, record)`. Two sequences compared by cosine. |
| 10 | [`semantic_faq.su`](https://github.com/EmmaLeonhart/Sutra/blob/main/examples/semantic_faq.su) | Semantic FAQ matcher. A paraphrased question matches the right canned answer by meaning — `embed` + `argmax_cosine` over a question codebook. |
| 11 | [`strings_and_formatting.su`](https://github.com/EmmaLeonhart/Sutra/blob/main/examples/strings_and_formatting.su) | String concat, interpolation, and `int_to_string` — text assembled entirely on the substrate. |
| 12 | [`fizzbuzz.su`](https://github.com/EmmaLeonhart/Sutra/blob/main/examples/fizzbuzz.su) | The real FizzBuzz, 1..15. No `if` — a softmax-weighted `select` superposition picks each word; a loop threads the growing `String` accumulator and returns it as a value. |
| 13 | [`loop_forms.su`](https://github.com/EmmaLeonhart/Sutra/blob/main/examples/loop_forms.su) | Every loop call form on small checkable loops: by-reference `slot` mutation, the expression form (`int x = loop f(...)`), multi-state tuple-destructure (`(a, b) = loop g(...)`), and a `String` accumulator by reference. |

Loops use first-class declared functions. Start with [`do_while_adder.su`](https://github.com/EmmaLeonhart/Sutra/blob/main/examples/do_while_adder.su) for the minimal shape, then [`loop_forms.su`](https://github.com/EmmaLeonhart/Sutra/blob/main/examples/loop_forms.su) for all three call forms and [`fizzbuzz.su`](https://github.com/EmmaLeonhart/Sutra/blob/main/examples/fizzbuzz.su) for a loop doing real work. See the [Loops page](loops.md) for the surface.

## The big Unix tools, on a completely neural computer

The substrate can run the classic Unix utilities — not as a metaphor, but with the actual byte-processing
done on the substrate and checked **char-for-char against the real coreutils binaries**. The machine is
NTM-style (external addressable RAM and a persistent disk, not a plain RNN); the host does only I/O, the
substrate does the transform. Fifteen tools are implemented and verified:

> `echo` · `cat` · `wc` · `head`/`tail` · `tr` · `rev`/`tac` · `cut` · `uniq` · `sort` · `grep` (fixed
> string **and** regex) · `sed` · `awk` (field/pattern subset) · `cat FILE`/`ls`/`cp`/`mv`/`rm` · `find`

One primitive does most of the work: an **exact codepoint indicator** — `1` at the target character, a
hard `0` at every other — which composes into counters (`wc`), gates (`head`/`cut`), codebook maps (`tr`),
and comparators (`uniq`/`sort`). Regex (`grep -E`/`sed`/`awk`) runs a Thompson NFA as a genuine
vector-valued substrate state, stepped by matrix multiplications. Source + per-tool self-tests:
[`experiments/ntm_ram/`](https://github.com/EmmaLeonhart/Sutra/tree/main/experiments/ntm_ram) (see its
README).

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
| `embed(name)` | embed a string through the substrate | all |
| `bundle(a, b, …)` | sum and L2-normalize | 1, 2, 3, 4, 5, 6, 7, 9 |
| `bind(role, filler)` | rotation binding: `Q_role @ filler` | 1, 2, 5, 7, 9 |
| `unbind(role, record)` | inverse rotation: `Q_role^T @ record` | 2, 5, 6, 7, 9 |
| `similarity(a, b)` | cosine similarity | 1, 6, 9 |
| `select([scores], [options])` | softmax-weighted superposition | 1, 7 |
| Scalar-vector multiply, vector add | weighted superposition | 1, 7 |
| `map<vector, string>` lookup | the single edge bridge from vector to host string | all |

There is no `if`, `while`, `for`, or `switch` in any of these programs. Every conditional is a weighted sum across all options; the commitment to a discrete answer happens at the final cleanup step or map lookup. Loop primitives show up in `do_while_adder.su` and the dedicated test suite, not in the smoke-tested set.

## Reading the source

The `.su` files are deliberately short (30–100 lines each including comments) and meant to be read front-to-back. Start with `hello_world.su` for the minimal shape; `role_filler_record.su` and `knowledge_graph.su` are the richest for understanding bind/unbind composition; `do_while_adder.su` is the smallest example of the loop surface and `loop_forms.su` walks every loop call form.

To inspect the generated Python for any demo:

```bash
sutrac --emit examples/knowledge_graph.su
```

The emitted module is self-contained — it instantiates a small `_VSA` runtime class and calls into it for every Sutra primitive.
