# Control Flow

## Algebraic Conditionals (Fuzzy Branching)
```
result = (condition * branch_true) + (NOT_condition * branch_false)
```
Both branches execute simultaneously via superposition. The condition vector weights which branch dominates the result. Confidence propagates through computation as geometry. This is **O(1)** and purely algebraic.

This is the default and preferred way to branch. It is inherently fuzzy — both branches contribute to the result proportional to the condition's truth value. There is no "wrong branch" — there is a weighted mixture.

## Cone Traversal (Non-Algebraic Branching)
When you need discrete navigation — "go here OR there, not a mixture" — cone traversal provides it. The current vector state determines a direction, and the cone finds the appropriate next state in the semantic graph. This is more like a jump table or pattern match than an if/else.

**When to use which:**
- Fuzzy conditional: when both branches are meaningful and you want a weighted blend
- Cone traversal: when you need to navigate to a discrete next state in a graph, resolve a many-to-many relationship, or branch based on relational topology rather than vector similarity

## Iteration
The hardest unsolved primitive. Current candidates:
- **Fixed unrolling:** Compile-time expansion of loops to a fixed depth
- **Convergence:** Recurrent application of an operation until similarity between successive states drops below a threshold (the result "stabilizes")
- **State encoding:** Encode loop state as a hypervector, bind the iteration counter, update per step

Iteration interacts with the noise problem — each iteration potentially accumulates error, so snap-to-nearest may be needed between iterations.

Note: bounded integer iteration (`repeat N:`) is available as a primitive operation (see [Operations](02-operations.md)), which covers the most common case pragmatically.
