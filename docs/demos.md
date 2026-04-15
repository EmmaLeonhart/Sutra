# Demos

Ten `.su` programs that compile and run end-to-end through the numpy backend. All ten live in [`examples/`](https://github.com/EmmaLeonhart/Sutra/tree/master/examples) and are verified by a single harness:

```bash
git clone https://github.com/EmmaLeonhart/Sutra
cd Sutra
python examples/_smoke_test.py
```

Expected output: `PASS` and 85 `OK` lines (one per verified decision). Seed is fixed (`seed=42`, `dim=256`); results are deterministic.

## The ten programs

| # | File | What it demonstrates | Decisions |
|---|---|---|---|
| 1 | [`hello_world.su`](https://github.com/EmmaLeonhart/Sutra/blob/master/examples/hello_world.su) | Embed + retrieve. The minimal program — three candidate phrases, argmax-cosine, map lookup at the edge. | 1 |
| 2 | [`fuzzy_branching.su`](https://github.com/EmmaLeonhart/Sutra/blob/master/examples/fuzzy_branching.su) | Weighted-superposition conditional. 4 program variants × 4 inputs = 16 decisions, all branches fire, argmax commits. | 16 |
| 3 | [`role_filler_record.su`](https://github.com/EmmaLeonhart/Sutra/blob/master/examples/role_filler_record.su) | Structured records as flat vectors. `bundle(bind(role, filler))`; decode a field by unbinding its role. | 6 |
| 4 | [`classifier.su`](https://github.com/EmmaLeonhart/Sutra/blob/master/examples/classifier.su) | Bundled-prototype classifier. Three classes, three examples each, bundle averages them into a prototype. | 9 |
| 5 | [`analogy.su`](https://github.com/EmmaLeonhart/Sutra/blob/master/examples/analogy.su) | Associative pair memory. Five (capital, country) pairs bundled into one vector; query a capital, recover the country. | 5 |
| 6 | [`knowledge_graph.su`](https://github.com/EmmaLeonhart/Sutra/blob/master/examples/knowledge_graph.su) | Flat knowledge graph. Triples as `bind(object, bind(subject, predicate))`; query `unbind(p, unbind(s, graph))`. | 5 |
| 7 | [`predicate_lookup.su`](https://github.com/EmmaLeonhart/Sutra/blob/master/examples/predicate_lookup.su) | Multi-object superposition. When a (subject, predicate) key has multiple objects, all members score high while non-members stay near zero. | 3 |
| 8 | [`fuzzy_dispatch.su`](https://github.com/EmmaLeonhart/Sutra/blob/master/examples/fuzzy_dispatch.su) | N-way dispatch with structured results. Each branch returns a (action, target) record; the winner is decoded with two unbinds. | 4 |
| 9 | [`nearest_phrase.su`](https://github.com/EmmaLeonhart/Sutra/blob/master/examples/nearest_phrase.su) | 20-phrase codebook, clean + noisy retrieval. Target + 0.2·distractor still returns target — dim=256 gives the margin. | 25 |
| 10 | [`sequence.su`](https://github.com/EmmaLeonhart/Sutra/blob/master/examples/sequence.su) | Position-bound sequence encoder. A 5-token sequence is one 256-dim vector; decode any position with `unbind(pos_i, record)`. Two sequences compared by cosine. | 11 |

## The primitive surface, demonstrated

Across the ten programs, the operations exercised are:

- `basis_vector(name)` — fresh random basis vector
- `bundle(a, b, ...)` — superposition (sum + L2 normalize)
- `bind(a, b)` — sign-flip binding (`a * sign(b)`)
- `unbind(role, bound)` — inverse of `bind` (same operation — sign-flip is self-inverse)
- `similarity(a, b)` — cosine similarity
- `argmax_cosine(query, [candidates])` — cleanup to nearest codebook entry
- Scalar-vector multiplication and vector addition (for weighted superposition)
- `map<vector, string>` edge lookup (the single escape from the pure region)

No control flow. No `if`, no `while`, no `for`, no `switch`. Every branch in every program is a weighted sum across all options; the commitment to a discrete answer happens at the final `argmax_cosine` or map lookup.

## What's not demonstrated

- **`loop(condition)`** — implemented in the compiler, not yet exercised in the demo corpus. A data-dependent eigenrotation demo is future work.
- **Real LLM embeddings** — the compiler uses fresh random basis vectors. Wiring `embed("string")` to an actual embedding model is a separate project; the companion paper *Sign-Flip Binding and Vector Symbolic Operations on Frozen LLM Embedding Spaces* characterizes which operations survive that transition.
- **Gradient training** — needs the PyTorch backend. The emitted code is already matrix-only, so the port is mechanical.
- **Connectome execution** — the fly-brain substrate is a separate open research question; see the *Running Sutra on the Drosophila Hemibrain Connectome* companion paper for what does and does not transfer.

## Reading the source

All ten `.su` files are deliberately short (30–100 lines each including comments) and are meant to be read front-to-back. Start with `hello_world.su` for the minimal shape; `role_filler_record.su` and `knowledge_graph.su` are the richest for understanding bind/unbind composition; `fuzzy_dispatch.su` shows the two patterns (fuzzy select + role-filler decode) in one program.

To inspect the generated Python for any demo:

```bash
PYTHONIOENCODING=utf-8 python -m sutra_compiler --emit-numpy examples/knowledge_graph.su
```

The emitted module is self-contained — it instantiates a small `_NumpyVSA` class with `embed`, `bind`, `unbind`, `bundle`, `similarity` methods, then emits the user's declarations and functions as direct Python.
