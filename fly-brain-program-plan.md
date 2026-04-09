# Fly Brain Program Plan

## The Idea

Run an S2 program on a fly brain. The program is an if-statement about smell.

This is a natural fit because:
- A fly's olfactory system is already a vector computer. Olfactory Receptor Neurons (ORNs) fire in patterns that are literally vectors of activation. The Mushroom Body performs sparse random projection on those vectors — the same operation S2 treats as primitive.
- S2's fuzzy-by-default semantics match how a fly actually decides things. A fly doesn't compute `smell == food` as a boolean. It computes something like "how food-like is this smell" — a fuzzy truth value that gets sharpened into a behavioral decision (approach vs. avoid). That's `defuzzy()`.
- The if-statement is the simplest interesting program: sense a smell, evaluate a fuzzy condition, branch to a behavior.

## The Fly Olfactory Pipeline

```
Antenna (ORNs)  →  Antennal Lobe (glomeruli)  →  Projection Neurons  →  Mushroom Body (Kenyon Cells)  →  Output Neurons  →  Behavior
   [raw signal]      [normalization/contrast]       [dense vector]         [sparse vector]               [decision]         [action]
```

Each stage maps to an S2 concept:
- **ORN activation** = raw vector from `embed()`
- **Antennal Lobe** = vector normalization (the AL does lateral inhibition, which is a kind of contrast enhancement — analogous to normalizing a vector)
- **Mushroom Body** = bind/bundle operations producing a sparse high-dimensional representation
- **Output Neurons** = `defuzzy()` — collapsing a fuzzy smell-match into a go/no-go decision

## Candidate Program: Smell → Approach/Avoid

The simplest meaningful program:

```s2
// A fly smells something. Is it food? Approach or avoid.

function fuzzy SmellLikeFood(vector smell) {
    vector food = embed("ripe fruit sugar fermenting");
    vector danger = embed("toxic bitter predator");

    // Bundle the food markers, bind with the smell
    vector foodSignal = smell * food;
    vector dangerSignal = smell * danger;

    // The fuzzy truth: how food-like is this relative to danger?
    fuzzy foodiness = unsafeCast<fuzzy>(foodSignal + dangerSignal);
    return foodiness;
}

function string Behave(vector smell) {
    fuzzy isFood = SmellLikeFood(smell);

    if (defuzzy(isFood)) {
        return "approach";
    } else {
        return "avoid";
    }
}

// Run it
vector vinegar = embed("acetic acid vinegar sharp sour");
Behave(vinegar);
```

This is ~15 lines. It's a real if-statement. It does something a fly actually does. And it uses S2's core primitives: `embed()`, `*` (bind), `+` (bundle), `unsafeCast<fuzzy>()`, `defuzzy()`.

## Open Questions

### 1. What substrate are we targeting?
- **Literal fly brain** (connectome data, e.g. FlyWire/FAFB)? This means mapping S2 vectors onto actual neuron activation patterns.
- **Simulated fly brain** (a model of the olfactory circuit)? More tractable, still meaningful.
- **LLM embedding space as a model of what the fly is doing**? The metaphorical version — we're not literally running on neurons, but we're using the same computational structure.

### 2. What does "run on a fly brain" mean concretely?
- Compile S2 to neuron activation patterns?
- Show that the S2 program's computation is isomorphic to the fly's olfactory processing?
- Use fly connectome data as the embedding space instead of an LLM?

### 3. How complex should the if-statement be?
Candidates in increasing complexity:
- **Binary**: food vs. not-food (the example above)
- **Multi-branch**: food vs. mate vs. danger vs. ignore
- **Contextual**: same smell, different behavior depending on internal state (hungry vs. satiated) — this would need some notion of state or environment
- **Learned**: a program that changes its if-threshold based on experience (associative learning — this is literally what the Mushroom Body does)

### 4. What's the real smell vocabulary?
Drosophila has ~50 ORN types. Real odorants to consider:
- **Attractive**: ethyl acetate (fruity), acetic acid (vinegar), 2,3-butanedione (yeasty)
- **Aversive**: benzaldehyde (bitter almond), CO2 (stress signal), geosmin (toxic mold)
- **Pheromones**: cis-vaccenyl acetate (cVA, male pheromone — triggers different responses in males vs. females)

### 5. What makes this more than a demo?
The demo above is cute but trivial. To be genuinely interesting, the program should demonstrate something that:
- Can't be easily done in a conventional language (the fuzziness is load-bearing, not decorative)
- Maps onto real neuroscience (the computation structure matches the fly's actual circuit)
- Shows S2's value proposition (programming in embedding space gives you something you didn't have before)

## Next Steps

1. Decide which "substrate" interpretation we're going for
2. Pick the specific smell scenario
3. Write the actual `.s2` file
4. Figure out what "running it" means in practice
