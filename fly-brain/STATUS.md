# Fly-Brain Akasha: Status and Roadmap

*Companion to `DEMO.md` (audience summary) and `METHODOLOGY.md` (circuit
details). This doc is the honest state of the fly-brain branch of
Akasha: what's been accomplished, what the technical insights are, and
what has to happen next.*

## TL;DR

We built the first end-to-end pipeline where an Akasha programming
language source file compiles down to operations on a simulated
biological connectome — the *Drosophila melanogaster* mushroom body
circuit (50 PNs → 2000 KCs → APL → 20 MBONs, Brian2 spiking model).
Two working demos prove two distinct claims:

1. **Programmer agency.** `programmer_control_demo.py`: same substrate,
   different code, different output. One-character source diffs flip
   the entire behavior mapping. This rules out "Akasha is a pattern
   somebody found" and establishes it as a language.
2. **Compile-to-brain.** `permutation_conditional.py`: the `if/else`
   tree compiles *into* the mushroom body as a prototype table plus
   permutation-keyed query rewrites. Zero Python `if` in the decision
   path. Program variants literally share one compiled artifact and
   differ only in which permutation keys enter the query.

Both demos run on the same `FlyBrainVSA` runtime (Brian2 LIF neurons,
biologically plausible parameters, 7-PN-fan-in sparse projection,
APL-enforced 5% KC sparsity). Nothing in the q-bio literature (as of
my arxiv survey in this session) combines all three of: real
connectome as substrate + VSA arithmetic + a first-class programming
language over it. BPU ([2507.10951](https://arxiv.org/abs/2507.10951)),
the ESA FlyWire reservoir paper (Costi et al. 2025), and Fly-CL
([2510.16877](https://arxiv.org/abs/2510.16877)) each capture one
piece. We captured all three.

## What exists

### Runtime (`vsa_operations.py`, `spike_vsa_bridge.py`, `mushroom_body_model.py`)

The Akasha → fly brain execution layer. A `FlyBrainVSA` instance
exposes the VSA primitives the language needs:

| Operation | Implementation |
|-----------|----------------|
| `bind(a, b)` | Sign-flip binding in numpy (algebraic, no biological analogue in MB) |
| `unbind(a, b)` | Sign-flip binding in reverse |
| `bundle(a, b)` | Addition in numpy (superposition) |
| `snap(v)` | **Routed to the Brian2 circuit.** Encodes `v` as PN input currents, runs the spiking simulation, decodes KC population activity back to a hypervector. |

The hybrid design is deliberate: bind/unbind/bundle are pure algebra
with no mushroom-body counterpart, so they run in numpy for speed.
`snap` is where the biology actually matters — APL-mediated
winner-take-all inhibition on the KC layer is structurally identical
to VSA cleanup, so `snap` routes through the circuit.

### Demo 1 — Programmer agency (`programmer_control_demo.py`)

**4 programs × 4 inputs = 16 runs on one fly brain.** The 4 programs
are `four_state_conditional.py` with 0, 1, 1, or 2 `!` negations on
the `defuzzy()` calls — literally one or two characters of source
diff per program. The circuit is unchanged between runs.

Fuzzy scores the MB produces for the 4 inputs (shared by all programs):

| Input | Smell Score | Hunger Score | `has_smell` | `is_hungry` |
|-------|------------|-------------|-----------|-----------|
| vinegar + hungry | ~+0.60 | ~+0.47 | True | True |
| vinegar + fed | ~+0.47 | ~+0.03 | True | False |
| clean_air + hungry | ~-0.09 | ~+0.54 | False | True |
| clean_air + fed | ~-0.07 | ~+0.09 | False | False |

Branching outputs per program:

| Input | Prog A | Prog B | Prog C | Prog D |
|-------|--------|--------|--------|--------|
| vinegar + hungry | approach | search | ignore | idle |
| vinegar + fed | ignore | idle | approach | search |
| clean_air + hungry | search | approach | idle | ignore |
| clean_air + fed | idle | ignore | search | approach |

Every row is a permutation of the four behaviors. Every column is a
distinct mapping. Every cell differs across programs. The fly brain
is the CPU; the code is the program; different programs on the same
hardware produce different results. That's the definition of a
programming language.

**What this demo leaves unfinished:** the `if/else` tree itself still
runs in Python. The MB produces the fuzzy scores; `defuzzy()` collapses
them; the `if` chain then branches in the host language. Honest, but
not yet "the whole program on the brain."

### Demo 2 — Compile to brain (`permutation_conditional.py` + `.ak`)

This is where the really novel work is. The `if/else` tree is
*compiled away* — the entire conditional is lowered to vector-space
operations that execute through the mushroom body, with no Python
`if` in the decision path at all.

**Compilation strategy:**

| Source construct | Compiled form |
|------------------|----------------|
| `if/elif/else` tree over state conjunctions | **Prototype table**: 4 brain-view vectors, one per case. Each is produced by binding the case's state vectors and running `snap` on the result at compile time. |
| "Which case matches?" lookup | `snap(query)` + cosine argmax against the 4 prototypes. Biological analogue: 4 MBONs competing for a winner. |
| "What behavior for this case?" | Dictionary lookup from winning prototype → behavior name. This is "which MBON → which motor program" — wiring, not control flow. |
| `!X` source negation | `permute(NOT_KEY, X)` — pointwise multiply by a fixed random ±1 vector (a permutation key). |
| Program variants (A/B/C/D) | **Same prototype table.** Variants differ only in which permutation keys multiply into the query before `snap`. The compiled artifact is literally identical across programs. |

That last row is the payoff. The 4 programs don't each have their own
compiled if-tree — they share one table of 4 KC-space prototypes plus
one prototype→behavior map. What varies is the query rewrite: Program
A sends `bind(smell, hunger)` through `snap`; Program B sends
`permute(NOT_SMELL, bind(smell, hunger))`; Program C applies
`NOT_HUNGER`; Program D applies both. The decision fires inside the
mushroom body, not in the host runtime.

## Technical insights (these are the important ones)

### 1. Negation-as-permutation compiles `!` away

In sign-flip VSA, a permutation key is just a fixed random ±1 vector.
Two facts about them matter here:

- **Involutive.** `permute(k, permute(k, x)) == x`. Applying a key twice
  is the identity.
- **Distributive over bind.** `permute(k, bind(a, b)) == bind(permute(k, a), b)`.
  Permutation factors through binding.

The second one is what makes compile-to-brain work. If `smell_absent`
is constructed as `permute(NOT_SMELL, smell_present)` at compile time,
then applying `NOT_SMELL` to the *query* literally rewrites
`bind(smell_present, hunger_hungry)` into
`bind(smell_absent, hunger_hungry)` — and the MB retrieves `search`
instead of `approach` exactly as Program B demands.

So source-level `!smell` compiles to `permute(NOT_SMELL, .)` on the
query. No Python `not`. No host-side negation. The MB's own retrieval
path runs the logic. This is the first place in the language where a
control-flow operator actually has a substrate-level compilation
target — not "approximates using", not "inspired by", but
*algebraically equivalent to*.

### 2. The fixed-frame invariant (a runtime contract the language needs to know about)

The default `FlyBrainVSA.snap` increments the connectivity seed
between calls, producing a fresh PN→KC projection every time. That's
fine for isolated similarity checks against clean reference vectors —
the noise averages out. But it's catastrophic for comparing two
`snap` outputs to each other.

**Measured numbers.** Two independent snaps of the same vector under
different PN→KC projections cosine-match at ~0.28 (the square of the
~0.53 per-snap fidelity). The noise floor is ~0.1. A 4-way cosine
argmax cannot reliably discriminate when the signal is 0.28 and the
floor is 0.1.

**Fix.** `FixedFrameFlyBrainVSA` is a subclass that pins the seed
across all `snap` calls in one execution. With the projection frozen:
matching patterns cosine at 1.0, non-matching at 0.3–0.7. Clean 4-way
separation.

**Why this matters for the language, not just the demo.** Every snap
in a compiled Akasha program has to share mushroom body connectivity
or the prototype-matching step is meaningless. That's a runtime
contract: "during one program execution, there is exactly one MB
connectivity matrix and every `snap` goes through it." The language
needs a way to express and enforce this — right now it's just a
subclass convention inside `permutation_conditional.py`, and any
future compile-to-brain target will rediscover the same pitfall.

The biological analogue is obvious: in a real fly, the mushroom body
is wired once during development and every query goes through the
same circuit. Our runtime has to model the same constraint.

### 3. The MB is a natural VSA substrate — with caveats

From `METHODOLOGY.md`:

| VSA operation | Mushroom body equivalent |
|---------------|------------------------|
| Random projection (encoding) | PN → KC sparse connectivity (7 random inputs per KC) |
| Winner-take-all (snap/cleanup) | APL feedback inhibition (~5% KC activation) |
| Superposition (bundling) | Convergent input from multiple PNs onto a KC |
| Readout (decoding) | MBON population activity |

The structural mapping is tight enough that the `snap` operation
really *is* what the MB does — it's not an approximation. But the
biology is missing primitives the language also needs: there's no
natural mushroom-body implementation of `bind` (the MB does random
projection, not sign-flip multiplication), and there's no
straightforward way to do unbind. The hybrid design (algebra in
numpy, cleanup in the MB) reflects that honestly. A fully-biological
Akasha runtime would need a different substrate — or a proposed
extension to the MB model that implements binding biologically.
Neither exists yet.

## The language-spec gap (this is what has to happen next)

This is the surprise that fell out of wiring up the SDK validator in
this same session: **`permutation_conditional.ak` uses several
constructs that aren't in the Akasha spec.** The validator fires 16
diagnostics on that one file. Every diagnostic is a real language gap,
not a bug in the source — the fly-brain work is running ahead of what
the language formally supports.

Specifically:

| Feature used in `.ak` | Status in spec |
|-----------------------|----------------|
| `permutation` as a type name | Not in the primitive set (`scalar`, `vector`, `matrix`, `tuple`, `string`, `bool`, `fuzzy`, `void`) |
| `map<vector, string>` type expression | Map types aren't in the spec at all |
| `map<K, V> name = { k: v, ... };` map literal | No map literal syntax |
| `name[key]` subscript access | No subscript syntax in the spec |
| `[a, b, c, d]` array literal | No array/list literal syntax |
| `basis_vector("...")`, `permutation_key("...")`, `permute(...)`, `identity_permutation()`, `argmax_cosine(...)` | None declared as builtins; `snap` and `similarity` are mentioned informally but not formally declared either |

Two conclusions fall out of this:

1. **The SDK was worth building.** Without the validator we wouldn't
   know this — we'd keep writing Akasha-shaped code that doesn't
   actually type-check against any formal grammar. Now we have a
   ground truth and a mechanical way to measure drift.
2. **The spec needs to catch up before this code is "real" Akasha.**
   Every entry in the table above is a real design decision we've
   been making implicitly. The fly-brain work is the forcing function
   that turns those into explicit questions.

## What needs to happen next

### Short term — spec and validator

**Goal achieved.** `permutation_conditional.ak` now parses and
validates cleanly against the formal grammar — the validator reports
0 diagnostics on it (down from 46 when this section was first
written). The three substrate-language gaps documented in the
"language-spec gap" table above are all closed.

1. ~~**Add `permutation` as a primitive type.**~~ **Done.** Added to
   `PRIMITIVE_TYPE_NAMES` in the lexer, the parser's `_PRIMITIVE_TYPES`,
   and the validator's `_record_type_usage` PRIMITIVES set. Spec entry
   in `planning/akasha-spec/05-type-system.md` documents the
   distinction from plain `vector` and why permutations deserve their
   own type even though they're sign-flip masks at the substrate
   level. Test corpus:
   `sdk/akasha-compiler/tests/corpus/valid/21_permutation_type.ak`.
2. ~~**Specify map types and map literals.**~~ **Done.** `map<K, V>`
   is a primitive generic type; the inline literal `{k1: v1, ...}`
   parses as a `MapLiteral` expression in expression position; empty
   `{}` is legal; a bare `{ ... }` at statement position is still
   always a block (disambiguation by syntactic position, matching
   C-family languages). Vector-valued keys work, which is what the
   prototype table needs. The lookup semantics for vector keys
   (exact-match vs. cosine-nearest) are documented in the spec as an
   open question tracked in `17-open-questions.md`. Test corpus:
   `sdk/akasha-compiler/tests/corpus/valid/24_map_literal.ak`.
3. ~~**Specify array/tuple literals.**~~ **Done** for array literals
   and for postfix subscript access. `[a, b, c]` parses as an
   `ArrayLiteral` expression (empty `[]` is legal), and `target[index]`
   parses as a `Subscript` postfix. Test corpus:
   `sdk/akasha-compiler/tests/corpus/valid/22_array_literal.ak` and
   `.../23_subscript_access.ak`; parser unit tests added to
   `sdk/akasha-compiler/tests/test_parser.py`.

Steps 4–6 of the original short-term plan (declare the VSA builtins,
add parser/validator support, regression test) are partially
complete: the parser/validator support landed as part of steps 1–3,
the regression test passes (0 diagnostics), and the only remaining
work is formally declaring the builtin signatures in
`planning/akasha-spec/`. That's now the next thing in `todo.md`.
4. **Declare the VSA builtins in the spec.** `snap`, `similarity`,
   `bind`, `unbind`, `bundle`, `permute`, `basis_vector`,
   `permutation_key`, `identity_permutation`, `argmax_cosine`. Give
   each a signature in terms of existing primitives.
5. **Add parser + validator support for each of those.** Roughly:
   - New `TokenKind.LBRACKET/RBRACKET` handling in the expression
     grammar for array literals (already tokenized, just not parsed).
   - New `MapLiteral` AST node and a parser path from `{` in
     expression position (distinguished from block statements by
     context).
   - New `Subscript` AST node for `expr[expr]`.
   - Add `permutation` to `_PRIMITIVE_TYPES`.
6. **Regression test: re-run `akashac --summary` over the repo and
   confirm `permutation_conditional.ak` now reports zero errors.**

Everything in step 5 is a local addition to `sdk/akasha-compiler/`.
None of it touches runtime behavior — the Python demos keep working
unchanged.

### Medium term — compilation path (1-2 sessions)

Goal: wire the parser output to the actual fly-brain runtime so an
`.ak` file can be executed, not just validated.

1. **Translator from AST to `FlyBrainVSA` calls.** Walk the AST of an
   `.ak` file and emit Python that constructs vectors, builds the
   prototype table, and runs the decide function. This replaces the
   hand-written `permutation_conditional.py` with compiler output.
2. **Compile-time vs runtime separation.** The current
   `permutation_conditional.py` does its prototype-table construction
   at module import. A real compiler needs a proper staging split:
   the `vector proto_PH = snap(bind(smell_present, hunger_hungry));`
   lines are compile-time; the `decide()` function body is runtime.
   Encode that in the AST or in an annotation pass.
3. **Fixed-frame requirement enforced at the language level.** A
   program that uses `snap` should automatically get the
   `FixedFrameFlyBrainVSA` runtime contract. This is the point where
   the runtime invariant from Technical Insight #2 becomes a
   compile-time guarantee.
4. **End-to-end: write a new `.ak` file, compile it, run it on the
   circuit, compare output to `permutation_conditional.py`'s
   hardcoded expected behavior table.** When that round-trips, we
   have a real compile-to-brain pipeline.

### Long term — research questions

These are the questions I think matter but don't have answers for yet.
Rough priority order:

1. **Can we compile non-permutation conditionals?** Permutation-keyed
   negation works because `!` is an involution that distributes over
   bind. General boolean expressions (`a && b`, `a || !b`) don't have
   the same structure. Either there's a more general VSA compilation
   scheme, or conditionals on the brain are fundamentally limited to
   what permutation keys can express. Finding out which would be a
   real result.
2. **How far can the prototype-table trick scale?** 4 prototypes × 20
   MBONs is fine; what about 400 prototypes? Does the cosine-argmax
   discrimination survive? When does KC sparsity stop being enough
   separation? The `FixedFrameFlyBrainVSA` numbers give us an
   empirical starting point but the scaling law isn't characterized.
3. **Loops.** Both demos are conditional-only. What does a `while`
   or `foreach` on the brain look like? The obvious answer is
   "iterate in the host runtime, call `snap` on each step" — which is
   honest but basically cheating. A real loop compilation would
   probably need something like recurrent KC→KC connections, which
   the current MB model doesn't have.
4. **Can we run a *real* connectome instead of a 50×2000 model?**
   FlyWire has the full adult *D. mel.* brain (~140,000 neurons)
   available as a graph. The ESA reservoir paper plugged it into an
   ESN; nothing has plugged it into a VSA runtime. The bottleneck
   will be Brian2 performance — spiking simulation at that scale is
   not cheap — but we could start with a mushroom body subset and
   scale up.
5. **Paper.** The "first language runtime on a biological connectome"
   story is real and defensible. The q-bio survey in this session
   found no direct precedent. If we want to make that claim
   citeable, `akasha-paper/paper.md` needs an experiments section
   where the compile-to-brain demo gets written up with numbers,
   ablations, and the fixed-frame discovery called out explicitly.

## File map (current state)

| File | Role |
|------|------|
| `four_state_conditional.ak` | Canonical 4-state conditional, Program A, runs in `four_state_conditional.py` |
| `four_state_conditional.py` | Simplest demo: one program, 4 inputs |
| `permutation_conditional.ak` | The compile-to-brain source (uses un-spec'd syntax; see "language-spec gap" above) |
| `permutation_conditional.py` | Working compiled form, with `FixedFrameFlyBrainVSA` runtime |
| `programmer_control_demo.py` | 4 programs × 4 inputs, branching in Python, proves programmer agency |
| `mushroom_body_model.py` | Brian2 LIF circuit, 50/2000/1/20 neurons, 7-PN fan-in |
| `spike_vsa_bridge.py` | Hypervector ↔ spike pattern encode/decode |
| `vsa_operations.py` | `FlyBrainVSA` runtime; Akasha primitives exposed to Python |
| `minimal_lif_network.py` | Debug substrate |
| `test_bridge.py`, `test_vsa_operations.py` | Unit tests for the runtime |
| `METHODOLOGY.md` | Circuit parameters, neuron models, connectivity |
| `DEMO.md` | Audience-facing results summary |
| `STATUS.md` | This document |

## Running everything

```bash
# Simplest demo (1 program, 4 inputs)
python four_state_conditional.py

# Programmer agency proof (4 programs × 4 inputs, Python branching)
python programmer_control_demo.py

# Compile-to-brain (4 programs × 4 inputs, brain branching)
python permutation_conditional.py

# Validate the .ak source files against the language grammar
cd ../sdk/akasha-compiler
python -m akasha_compiler ../../fly-brain/four_state_conditional.ak
python -m akasha_compiler ../../fly-brain/permutation_conditional.ak  # <- currently fails, see language-spec gap
```

Requires Python 3, Brian2, numpy, scipy. No GPU. Full run under 5
minutes on commodity hardware.

## One-line summary

The fly-brain branch of Akasha is the most ambitious part of the
project right now, it has the clearest "nothing like this exists"
novelty story in the q-bio literature, and the thing blocking it from
becoming a real compile-to-brain pipeline is that the language spec
hasn't yet caught up to what the code is already doing — and now that
the SDK validator exists, we can finally measure that gap
mechanically instead of guessing.
