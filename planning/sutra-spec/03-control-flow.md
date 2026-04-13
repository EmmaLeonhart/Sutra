# Control Flow

## Fuzzy-superposition conditionals
```
result = (condition * branch_true) + (NOT_condition * branch_false)
```
Both branches execute simultaneously via superposition. The condition vector weights which branch dominates the result. Confidence propagates through computation as geometry.

This is the default and preferred way to branch. It is inherently fuzzy — both branches contribute to the result proportional to the condition's truth value. There is no "wrong branch"; there is a weighted mixture. The scalar multiplications and the bundle both execute on the substrate.

## Cone-traversal branching
When you need discrete navigation — "go here OR there, not a mixture" — cone traversal provides it. The current vector state determines a direction, and the cone finds the appropriate next state in the semantic graph. This is more like a jump table or pattern match than an if/else.

**When to use which:**
- Fuzzy conditional: when both branches are meaningful and you want a weighted blend
- Cone traversal: when you need to navigate to a discrete next state in a graph, resolve a many-to-many relationship, or branch based on relational topology rather than vector similarity

## Iteration via Geometric Rotation

Iteration in Sutra is not host-runtime looping. A `while` loop compiles to a **geometric rotation on the substrate** — the loop body is a rotation matrix R, and each iteration applies R to the state vector, snaps through the substrate's cleanup operation, and checks whether the resulting pattern matches a target prototype. The substrate does the iteration; the host runtime just initiates it.

### Mathematical Definition

Let V be the hypervector space of dimension d. Let S: V → V be the substrate's snap operation (in the fly-brain substrate, this is PN encoding → KC sparse projection → APL feedback → learned MBON readout). Let P: V → {0,1}^n_kc be the substrate's pattern projection (the raw KC activation pattern before decoding).

A **geometric loop** is a tuple (v₀, R, T, θ) where:
- v₀ ∈ V is the **initial state** (starting hypervector)
- R ∈ O(d) is the **rotation matrix** (an orthogonal matrix, R^T R = I)
- T ⊂ V × {names} is the **prototype table** (target vectors compiled to KC patterns)
- θ ∈ [0,1] is the **convergence threshold** (Jaccard overlap in KC space)

Execution proceeds as:

```
state ← v₀                     (loaded into the substrate)
for i = 1, 2, 3, ..., max_iters:
    state ← R · state          (one rotation step on the substrate)
    kc ← P(state)              (KC pattern via the substrate projection)
    for (name, kc_proto) in T:
        J ← |kc ∩ kc_proto| / |kc ∪ kc_proto|
        if J ≥ θ:
            return (name, S(state), i)
return (⊥, state, max_iters)
```

The trajectory v₀, Rv₀, R²v₀, R³v₀, ... traces a path through V. Each rotation step is a full circuit pass through the substrate: on the fly-brain backend, Q enters as synaptic weights and the next state is read from spike rate or membrane voltage. Each point is then projected through the substrate's cleanup to produce a KC pattern. When that pattern overlaps sufficiently with a target prototype, the loop terminates. The substrate does the iteration. Implementations that accumulate `R^i v₀` on the host — whether framed as "no decode noise" or "pure math" — are not running the loop on the substrate; that is a limitation of the implementation to close, and results produced that way must be reported as host-iterated.

### Key Invariant: Fixed Frame

All prototype compilations and loop iterations MUST share the same substrate projection (the **fixed-frame invariant**). In the fly-brain substrate, this means using the same `frame_seed` for `compile_prototypes()` and `loop()`. Without this, KC patterns from different circuit instantiations are not comparable — the same input vector produces different KC patterns through different random projections.

This is not a limitation; it is a feature. The fixed frame is the biological analogue of a consistent sensory reference frame — the fly's mushroom body has one set of PN→KC connections, not a new random wiring for every decision.

### Rotation Construction

A rotation matrix R is constructed as a composition of Givens rotations in 2D subplanes of V:

```
R = G(i₁,j₁,α) · G(i₂,j₂,α) · ... · G(iₖ,jₖ,α)
```

where each Givens rotation G(i,j,α) acts on the 2D subplane spanned by dimensions i and j:

```
G(i,j,α) = I + (cos α - 1)(eᵢeᵢᵀ + eⱼeⱼᵀ) + sin α (eⱼeᵢᵀ - eᵢeⱼᵀ)
```

The **angle** α determines how far the state moves per iteration — larger angles give faster traversal but coarser resolution. The **number of planes** k determines the richness of the trajectory:
- k=1: the trajectory is a circle in one 2D plane (all other dimensions fixed)
- k>1: the trajectory is a higher-dimensional spiral
- k=d/2: maximum coverage of the vector space

### Properties

**R is orthogonal** (R^T R = I), so:
- ‖R^i v₀‖ = ‖v₀‖ for all i (norm is preserved — no explosion or collapse)
- R^i is also orthogonal for all i (composition of rotations is a rotation)
- The trajectory is periodic with period p = 2π/α for a single-plane rotation

**Counting** works because N applications of rotation by angle α accumulate Nα total rotation. Place a target prototype at the vector reached after N substrate-side rotation steps, and the loop terminates after N iterations. The brain counts by geometric displacement.

Each step feeds the current substrate state back through R on the substrate. Decode noise does accumulate across iterations when the step reads state out of the substrate and back in, and that is a real limit on how many iterations can run before snap-based cleanup (or a lower-noise in-circuit path) is needed. Pre-computing `R^i v₀` on the host to dodge this noise is not an option — it moves the iteration off the substrate, which is what the loop exists to do on the substrate in the first place.

### Nested Loops

Nested loops are rotations in **orthogonal subspaces**. An outer loop rotates in the 2D subplane (i, j) while an inner loop rotates in the subplane (k, l). Because the subspaces are orthogonal, the rotations do not interfere:

```
R_outer = G(i, j, α_outer)
R_inner = G(k, l, α_inner)

# Inner loop result does not disturb outer loop's accumulated rotation
R_inner · R_outer · v = R_outer · R_inner · v   (commute when subspaces are orthogonal)
```

With d input dimensions, there are d/2 independent 2D rotation planes — enough for d/2 levels of nesting. On the hemibrain substrate (d=140), this gives up to 70 independent loop levels.

**Cross-loop communication** uses the existing binding operation. The inner loop's result is bound with a role vector that lives in the outer loop's subspace:

```
outer_update = bind(inner_result, role_vector)
```

This carries information from the inner loop into the outer loop without interfering with the rotation geometry.

### Termination

Termination is by **prototype matching in KC space** (Jaccard overlap of binary activation patterns). This is biologically grounded — it is the same pattern-completion mechanism the fly's mushroom body output neurons (MBONs) use for olfactory decision-making.

Three termination modes:
1. **Target match**: terminate when a specific named prototype is matched (counting to N)
2. **Any match**: terminate when any prototype in the table is matched (convergence)
3. **Max iterations**: safety limit, returns ⊥ if no prototype is matched

I/O-driven termination is also possible: an external input modifies the target prototypes or the convergence threshold between iterations, allowing the loop to respond to changing conditions. This is the analogue of a `break` in imperative code — the external signal deforms the termination landscape.

### Biological Interpretation

The geometric loop has direct biological analogues in insect neuroscience:

- **The rotation** is a sensory transformation applied to the input before each mushroom-body pass — analogous to lateral antennal-lobe processing that transforms the odor representation before it reaches the Kenyon cells.
- **The prototype matching** is what MBONs do: compare the current KC pattern against stored patterns from prior associative learning.
- **The ring attractor** in the insect central complex (Seelig & Jayaraman 2015) implements a continuous rotation for heading-direction computation. A bump of neural activity rotates around a ring of neurons, and goals modulate the drift rate. Geometric loops in Sutra are structurally analogous.

### Syntax: The `loop` Keyword

Sutra uses a single `loop` keyword for all iteration. The argument inside the parentheses determines which kind of loop it is:

#### Bounded loop: `loop (N)` — unrolls at compile time

```sutra
loop (3) {
    state = snap(bind(transform, state));
}
```

The compiler unrolls this to 3 copies of the body. No rotation matrix, no circuit iteration, no eigenrotation. The body is emitted as straight-line code. This is the default, easy, preferred loop — use it whenever you know the count.

#### Bounded loop with index: `loop (N as i)`

```sutra
loop (10 as i) {
    state = snap(bind(steps[i], state));
}
```

Same as `loop (N)` but provides an index variable `i` counting from 0 to N-1. When N is a literal integer, the compiler unrolls. When N is an expression, it emits a bounded iteration.

#### Eigenrotation loop: `loop (condition)` — the brain iterates

```sutra
loop (similarity(current, target) < 0.9) {
    current = snap(bind(current, step));
}
```

When the argument is a boolean expression (not an integer literal), the compiler emits an eigenrotation loop. This compiles to:

```
R = make_random_rotation(angle=π/4, n_planes=20)
prototypes = compile_prototypes({"target": target})
(matched, current, iters) = loop(current, R, prototypes, target="target")
```

The condition `similarity(current, target) < 0.9` is compiled as: "loop until the KC pattern matches the prototype compiled from `target`." The loop body is replaced by the rotation matrix R. The brain iterates via geometric rotation; the host runtime just initiates the `loop()` call.

**Writing an eigenrotation loop is intentionally harder than a bounded loop.** `loop (10)` is trivial. `loop (condition)` forces you to think about what the convergence target is, because eigenrotation is genuinely more complex — it requires building a rotation matrix, compiling prototypes, and matching in KC space.

### Why One Keyword

The `loop` keyword unifies bounded and unbounded iteration under a single construct. The complexity gap is in the argument, not the syntax:

| Form | Argument | Compilation | Complexity |
|------|----------|-------------|------------|
| `loop (10)` | integer literal | unrolls at compile time | trivial |
| `loop (10 as i)` | integer + binding | unrolls with index | trivial |
| `loop (expr)` | boolean expression | eigenrotation on brain | requires geometric thinking |

This design makes bounded loops the path of least resistance. You reach for eigenrotation only when you need convergence-based termination — and the syntax makes you state what you're converging *toward*.

### Explicit Geometric Loop Builtins

For programs that need direct control over the rotation geometry, Sutra provides three builtins:

```sutra
// Build a rotation matrix
vector R = make_rotation(0.785, 20);    // angle in radians, number of planes

// Compile target vectors to KC-space prototypes
map<string, vector> protos = compile_prototypes(targets);

// Execute the geometric loop on the brain
vector result = geometric_loop(start, R, protos, "target_name");
```

These expose the loop primitive directly, without the compiler needing to infer the rotation from the loop body. Use these when:
- The rotation needs specific angle or plane selection
- The prototype table is constructed dynamically
- The loop geometry matters for the algorithm's correctness

### Legacy `while` and `for`

The C#-style `while (cond) { body }` and `for (init; cond; step) { body }` constructs are still supported by the parser for backward compatibility. Both compile to eigenrotation (geometric loop) on the fly-brain backend. New code should use `loop` instead — it is clearer about the distinction between bounded and convergence-based iteration.

## What Is NOT Supported

- **Host-runtime iteration** (Python `while` with brain ops inside): this is explicitly rejected. The whole point is that the brain does the iteration via geometric rotation. "Iterate in the host, call snap each step" is cheating — it reduces the biological substrate to a co-processor rather than treating it as the computational medium.
- **Arbitrary loop bodies as rotations**: not every computation can be expressed as a single rotation matrix. The codegen handles the common case (convergence loops, bounded iteration). For complex loop bodies, use the explicit `geometric_loop` builtins and construct the rotation manually.
- **Unbounded iteration without prototype matching**: a pure eigenrotation loops forever. Termination requires either a prototype match or a fixed bound. There is no `loop (true)` on the brain — every loop must have a geometric termination condition.
