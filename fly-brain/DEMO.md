# Fly Brain Demo: Proof of Programmer Control

## What This Proves

S2 is a programming language, not a found pattern. The proof is simple: **same substrate, different code, different outputs.**

The fly brain (mushroom body circuit) computes identical fuzzy scores regardless of which program runs. The programmer controls the branching logic. Changing the code changes the behavior. The substrate is general-purpose — it discriminates inputs without imposing policy.

## The Programs

All four programs share the same structure: two nested if-statements over two fuzzy axes (smell and hunger). The only difference is whether each condition is negated.

### Program A — Natural (biologically sensible)

```s2
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

```s2
if (!defuzzy(has_smell)) {          // ← one character changed
    if (defuzzy(is_hungry)) { return "approach"; }
    ...
```

Absence of smell triggers approach. Biologically absurd — but the code compiles and runs.

### Program C — Inverted hunger axis

```s2
if (defuzzy(has_smell)) {
    if (!defuzzy(is_hungry)) { return "approach"; }  // ← one character changed
    ...
```

Approaches when fed, ignores when hungry. The fly brain doesn't object.

### Program D — Both axes inverted

```s2
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
4. **The code is the cause.** The only variable between runs is the S2 source code.

The fly brain is the CPU. The S2 code is the program. Different programs produce different results on the same hardware. That's what a programming language is.

## Files

| File | Purpose |
|------|---------|
| `four_state_conditional.s2` | S2 source code (Program A, the natural/sensible mapping) |
| `four_state_conditional.py` | Simple demo: runs Program A on the fly brain (4 executions) |
| `programmer_control_demo.py` | Full proof: runs all 4 programs × 4 inputs = 16 executions |
| `mushroom_body_model.py` | Brian2 spiking circuit model (the substrate) |
| `spike_vsa_bridge.py` | Encode/decode between hypervectors and spike patterns |
| `vsa_operations.py` | FlyBrainVSA class (S2 operations API) |
| `METHODOLOGY.md` | Technical details: challenges, solutions, results |
| `DEMO.md` | This file |

## Running It

```bash
# Simple demo (Program A only, 4 executions)
python four_state_conditional.py

# Full programmer control proof (4 programs × 4 inputs = 16 executions)
python programmer_control_demo.py
```

Requires: Python 3.x, Brian2, numpy, scipy. No GPU needed. Runs in under 5 minutes.
