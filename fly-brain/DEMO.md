# Fly Brain Demo: Proof of Programmer Control

## What This Proves

Sutra is a programming language, not a found pattern. The proof is simple: **same substrate, different code, different outputs.**

The fly brain (mushroom body circuit) computes identical fuzzy scores regardless of which program runs. The programmer controls the branching logic. Changing the code changes the behavior. The substrate is general-purpose — it discriminates inputs without imposing policy.

## The Programs

All four programs share the same structure: two nested if-statements over two fuzzy axes (smell and hunger). The only difference is whether each condition is negated.

### Program A — Natural (biologically sensible)

```sutra
if (defuzzy(has_smell)) {
    if (defuzzy(is_hungry)) { return "approach"; }
    else { return "ignore"; }
} else {
    if (defuzzy(is_hungry)) { return "search"; }
    else { return "idle"; }
}
```

Smell + hungry → approach food. This is what a real fly does.

### Program B — Inverted smell axis

```sutra
if (!defuzzy(has_smell)) {          // ← one character changed
    if (defuzzy(is_hungry)) { return "approach"; }
    ...
```

Absence of smell triggers approach. Biologically absurd — but the code compiles and runs.

### Program C — Inverted hunger axis

```sutra
if (defuzzy(has_smell)) {
    if (!defuzzy(is_hungry)) { return "approach"; }  // ← one character changed
    ...
```

Approaches when fed, ignores when hungry. The fly brain doesn't object.

### Program D — Both axes inverted

```sutra
if (!defuzzy(has_smell)) {          // ← changed
    if (!defuzzy(is_hungry)) { return "approach"; }  // ← changed
    ...
```

Everything backwards. No smell + fed → approach. Two characters changed from Program A.

## Results: 4 Programs × 4 Inputs = 16 Executions

The fly brain substrate produces these fuzzy scores (computed once, shared by all programs):

| Input | Smell Score | Hunger Score | has_smell | is_hungry |
|-------|------------|-------------|-----------|-----------|
| vinegar + hungry | ~+0.60 | ~+0.47 | True | True |
| vinegar + fed | ~+0.47 | ~+0.03 | True | False |
| clean_air + hungry | ~-0.09 | ~+0.54 | False | True |
| clean_air + fed | ~-0.07 | ~+0.09 | False | False |

Each program applies different branching logic to those same scores:

| Input | Prog A | Prog B | Prog C | Prog D |
|-------|--------|--------|--------|--------|
| vinegar + hungry | approach | search | ignore | idle |
| vinegar + fed | ignore | idle | approach | search |
| clean_air + hungry | search | approach | idle | ignore |
| clean_air + fed | idle | ignore | search | approach |

Every row is a permutation of the four behaviors. Every column is a distinct mapping. The fly brain doesn't change — only the code does.

Every cell is different across programs. Same substrate, different code, different output.

## Why This Matters

Most "AI language" claims amount to: "we found a pattern in a neural network." That's discovery, not programming. A programming language requires **programmer agency** — the developer writes code, and the code determines the output.

This demo proves programmer agency:
1. **The substrate is fixed.** The mushroom body computes the same sparse random projection + winner-take-all cleanup regardless of the program.
2. **The code varies.** Each program is a one-or-two-character change (`!` negation on `defuzzy()` calls).
3. **The output changes.** Each program produces a completely different behavior mapping.
4. **The code is the cause.** The only variable between runs is the Sutra source code.

The fly brain is the CPU. The Sutra code is the program. Different programs produce different results on the same hardware. That's what a programming language is.

## Permutation Conditionals: Compiling The If-Tree Into The Brain

`programmer_control_demo.py` above is honest about its architecture: the fly brain computes fuzzy scores, the if/else tree runs in Python. That was enough to prove programmer agency, but it left the conditional itself outside the substrate.

`permutation_conditional.py` closes that gap. It compiles the entire if-tree to vector-space operations that run through the mushroom body, with no Python `if` in the decision path.

### The compilation strategy

| Source construct | Compiles to |
|------------------|-------------|
| `if/elif/else` tree | **Prototype table**: 4 brain-view vectors, one per case, each produced by running `snap` on the conjunction of smell/hunger state vectors at compile time |
| Looking up a case | `snap(query)` on the fly brain + cosine argmax against the 4 prototypes |
| Picking a behavior | Dictionary lookup from the winning prototype to its behavior name — the "MBON-to-motor-neuron" wiring |
| `!X` negation | `permute(NOT_KEY, X)` — pointwise multiply by a fixed ±1 permutation key |
| Program variants | Different permutation keys composed into the query, **same prototype table** |

The prototype table is built once at compile time. The four programs (A/B/C/D) share it — they differ only in which permutation keys multiply into the query vector before `snap`. That is "same substrate, different code" at a stricter level than the earlier demo: now the compiled artifact (the 4 brain-view prototypes plus the prototype→behavior map) is literally identical across programs.

### What the fly brain actually does in this demo

1. At compile time, each of the 4 input conjunctions (`bind(smell_X, hunger_Y)`) is run through the mushroom body once, producing a **brain-view prototype** — the specific PN-space pattern the MB reconstructs for that input.
2. At decision time, the query `bind(smell, hunger)` (with any program-specific permutations composed in) goes through `snap`: the same sparse random projection → APL winner-take-all → pseudoinverse reconstruction. The decoded query lands in the same reconstruction frame as the prototypes because all snaps share the same MB connectivity.
3. The decoded query is matched by cosine argmax against the four prototypes. This is the vector analogue of four MBONs voting — each prototype is a KC population pattern the MB has "learned" to recognize, and the winning pattern selects the behavior.

There is no point in this pipeline where a Python `if` decides between behaviors. The decision is executed *by* the substrate: the MB's encoding determines which prototype the query matches, and the prototype→behavior map is just wiring.

### Runtime contract: one MB, one frame

A subtle but important detail: for the prototype-matching step to work, **every snap in the pipeline must use the same MB connectivity**. The default `FlyBrainVSA.snap` increments a seed counter between calls, producing a fresh PN→KC projection each time — which is fine for isolated similarity checks against clean reference vectors but catastrophic for comparing two snap outputs to each other. Two independent snaps of the same vector under different projection matrices cosine-match at ~0.28 (square of the 0.53 fidelity), which is too close to the ~0.1 noise floor for confident 4-way discrimination.

`permutation_conditional.py` uses a `FixedFrameFlyBrainVSA` subclass that pins the seed across all snaps. With a fixed projection, the decision-time query snap and the compile-time prototype snaps land in the same reconstruction frame, producing cosine 1.0 for matching patterns and ~0.3–0.7 for non-matching ones — a clean 4-way separation.

### Negation as a permutation

In sign-flip VSA, a permutation key is just a fixed random ±1 vector. Multiplying by it is an involution (applying it twice is the identity), and it distributes over binding: `permute(k, bind(a, b)) == bind(permute(k, a), b)`.

That distributivity is what makes the whole scheme work. Program B wants `!smell`, which should swap the smell axis of the query. With `smell_absent` constructed as `NOT_SMELL * smell_present`, applying `NOT_SMELL` to the query literally transforms `k_PH = bind(smell_present, hunger_hungry)` into `k_AH = bind(smell_absent, hunger_hungry)` — and the memory retrieves `search` instead of `approach`, exactly as Program B demands.

So the source-level `!` compiles to `permute(NOT_KEY, .)`, and "run Program B" compiles to "multiply the query by `NOT_SMELL` before lookup". No Python `not`, no Python `if`.

## Files

| File | Purpose |
|------|---------|
| `four_state_conditional.su` | Sutra source code (Program A, the natural/sensible mapping) |
| `four_state_conditional.py` | Simple demo: runs Program A on the fly brain (4 executions) |
| `programmer_control_demo.py` | Programmer-agency proof: 4 programs × 4 inputs = 16 executions (branching in Python) |
| `permutation_conditional.su` | Sutra source showing if/else → associative memory, `!` → permutation key |
| `permutation_conditional.py` | Full compile-to-brain demo: 4 programs share one memory, decision runs in the mushroom body |
| `mushroom_body_model.py` | Brian2 spiking circuit model (the substrate) |
| `spike_vsa_bridge.py` | Encode/decode between hypervectors and spike patterns |
| `vsa_operations.py` | FlyBrainVSA class (Sutra operations API) |
| `../fly-brain-paper/paper.md` | Technical details: challenges, solutions, results (the paper-shaped writeup, formerly `fly-brain/METHODOLOGY.md`) |
| `DEMO.md` | This file |

## Running It

```bash
# Simple demo (Program A only, 4 executions)
python four_state_conditional.py

# Programmer control proof with Python-side branching (4 × 4 = 16 runs)
python programmer_control_demo.py

# Permutation conditionals — if-tree compiled into the brain (4 × 4 = 16 runs)
python permutation_conditional.py
```

Requires: Python 3.x, Brian2, numpy, scipy. No GPU needed. Runs in under 5 minutes.
