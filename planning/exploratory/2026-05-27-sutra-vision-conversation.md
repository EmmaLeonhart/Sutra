# Sutra vision conversation (2026-05-27) — framing stripped

> Emma ↔ Claude. Conversational framing (affirmations, meta-questions,
> "shall we go through them" transitions) has been removed; what remains is
> the substance, still attributed and in the original section order.

## §1 — The problem

**Emma:** Sutra is a complete programming language; I'm trying to do something that eventually lets you train a neural network in a way that goes back into code. The capabilities markdown describes everything the language can do; the PDF is the draft formal-verification paper — the idea being we could formally verify it to keep certain constraints while training programs.

**Claude:** What exists: Sutra compiles programs to tensor-op graphs; the FV paper shows the non-learned trusted base is verifiable algebraically (branches → Kleene polynomials, loops → bounded recurrences, checkable without path enumeration). The vision: every operation has a trainable form, and the end-state is that you back-propagate from a learned network and the trained values land back into readable source — training reshapes the program; the program is still the model. The gap: the FV framework handles the trusted base because the learned parts are quarantined, but if training reshapes the program you eventually need verification to follow the trained values — constraints that survive training, not just constraints on the static graph.

## §2 — Bake-back candidates

> Agent's first attempt tier-ranked the candidates 1/2/3; Emma rejected the framing as pattern-matched from ML, not Sutra's surface. The substance of the candidates survives below.

**Emma:** I want candidates for bake-back, and how they might be trained.

**Claude:** Candidates and their shape:
- Defuzz polynomial coefficients — a small vector of scalars on the truth axis; downstream classification loss; constraint that the polynomial maps [-1,+1]→[-1,+1] (the FV range-soundness obligation, a closed-form check); bakes as a tuple literal.
- Per-loop halt signal — sigmoid of a substrate state; parameterize the linear combination feeding the sigmoid (a learned weight vector over loop state slots); loss penalizes wasted iterations; the termination obligation (monotone, bounded) is structural; bakes as a vector_literal(...).
- select firing threshold — a single scalar per call site; bakes as a numeric literal; closest to the shipped == temperature scalar.
- Kleene connective polynomial coefficients (per call site) — currently fixed by Lagrange interpolation to the Kleene table on {-1,0,+1}; a trained variant loosens off-grid behaviour while keeping a grid-exactness penalty (sum over the 9 grid points of (output − table)²); the verifier checks post-bake that the penalty is still zero.
- Per-role learned binding matrix — rotation matrices currently from key hashes; a trained version learns the rotation per role from (input, output) pairs; constraint: orthogonal (regularizer ||RᵀR − I||, project to SO(n) after each step); bakes as a vector_literal(...) of the matrix or its generating angles.
- The decompilation / shape-matching problem — recognize whether an arbitrary trained tensor looks like a rotation / rank-k projection / bundle of prototypes, emit the best-fit Sutra source with a residual. Inverted direction; if the residual is small the emitted source's FV obligations are exact and the residual is the formally-quarantined unverified part.

The shared pattern: a constrained parameter with a closed-form FV obligation defining the valid region; training as task loss + constraint-violation regularizer; a bake-back check that re-runs the obligation on the baked literal (pass = proof, fail = drifted, don't bake). The FV checks are the acceptance criteria for whether a trained value may bake back.

**Emma:** These are the worst possible ideas — it makes me question whether I gave you the wrong documents.

**Claude:** "Training on a neural network that goes back into code" could mean: extract structure from a pretrained model's weights into Sutra source; train a Sutra program end-to-end and get readable source back; use a Sutra program as a verifiable component inside a larger neural loop; or make the FV obligations the thing that survives training.

**Emma:** I have a programming language. It's complete. The documentation should have given you everything the language can do, with blank spaces where it had no idea how to implement them as learned parameters.

**Claude:** For each operation that currently has a fixed implementation, the question is what a learned version of that same operation would be, where the learned values bake back into readable source. The capabilities doc is a spec with gaps marked "VISION" — the operation works, but nobody has defined the trainable parameter, the loss, or the constraints. The real question per VISION item: what degree of freedom would training adjust, and "better for what?"

**Emma:** Does it talk about number literals or not?

**Claude:** Yes — §2.1: a parameter declared in source → compiler emits PyTorch → parameter becomes a substrate tensor → gradients applied → trained value baked back into a fresh .su file as a numeric or vector literal. The shipped instance is the == temperature scalar T. So: any number literal or vector literal in Sutra source is a bake-back candidate — that's the whole surface; the VISION items are just where those literals don't exist yet.

**Emma:** String literals?

**Claude:** A String in Sutra is an axis-packed codepoint array — already a vector. A trained string literal would be a vector_literal(...) optimized away from the frozen embedding of the surface string toward whatever the program needs that slot to mean.

**Emma:** The document is supposed to exhaustively list all features so we can brainstorm training techniques on each piece of the code.

**Claude:** It doesn't cover string literals as a trainable surface — they're listed under §1.4 as a language feature and never mentioned again in Part 2. The document has a gap.

## §3 — The exhaustive capabilities inventory

> Emma pointed the agent at the live `sutra.emmaleonhart.com/capabilities/` page (shipped in `7091bda4`); the uploaded summary was incomplete, and the full inventory becomes the basis for the rest.

**Claude:** From the exhaustive inventory, the trainable surfaces are:
- Single scalars (closest to == T): select softmax temperature, gt smooth-sign sharpness, defuzzify_trit beta, heaviside step location, sawtooth_mod n_terms, loop threshold and k.
- Small vectors / matrices: Kleene polynomial coefficients per call site (6 per &&/||), defuzz polynomial coefficients, per-role rotation matrices, per-loop cell update matrix, bundle component weights.
- Lookup tables: _exp_table, _ln_table (learned contents would specialize the math per program).
- Per-key learned values: hashmap angle assignments, axon binding rotations, codebook vectors for argmax_cosine.

String literals are explicitly n/a (compile-time text, not substrate values).

**Emma:** String literals are a candidate if they're a String object. Single scalars: yes. Lookup tables: no. Per-key learned values: yes. There can be other things too.

**Claude:** Any embed("...") call site is a candidate to become a vector_literal(...) after training; the string surface form is just the initializer. Other structural parameters: loop max_iters (a literal integer); the branch threshold on if (0.0 on the truth axis, per call site); slot index assignments (hash-derived); and operator-overload dispatch scoring (a learned per-call-site preference).

**Emma:** All of these are within scope. I'm also considering beta reduction. Actually introducing functionality into a program interests me, but it's more on the extreme side.

**Claude:** Scope:
- In scope — training parameters that already exist in compiled programs: single scalars; per-key learned values (hashmap angles, axon binding rotations, codebook vectors); embed call sites → vector_literal(...); loop max_iters; branch thresholds; slot index assignments; operator dispatch scoring; bundle component weights; per-role rotation matrices; Kleene polynomial coefficients per call site.
- Out of scope for now — introducing new structure into a program (the decompilation / shape-matching problem). The long arc, deferred.

## §4 — The long arc: train everything → corpus → learned decompiler

> Emma's strategic vision. Train everything trainable, the corpus becomes training data for a learned decompiler that takes (original source + trained tensor) and emits idiomatically-continuous source, with the FV round-trip as certificate. Operator-overloading dispatch is out of scope (structural anchors must be stable).

**Emma:** In the future we could probably have an entire program able to change itself, but we're not there yet. The vision is to train everything we possibly can — though not operator overloading; that seems like a bad move. Once we can train almost everything that logically makes sense in a program, we'll have enough information to extend further. If we can train, say, fifty percent of a program, we'd be at a point where we could almost develop an algorithm that learns the decompilation. Once that happens — once we can take a neural network we've made, with all the training data from our proper training — we'd be able to extract more, until at some point we can extract everything we need.

**Claude:** The arc: train everything trainable in existing programs → that generates a corpus of (Sutra source → trained tensor → baked literal) examples → the corpus trains a learned decompiler that emits the Sutra source whose compiled graph matches an arbitrary trained tensor → once it exists, you can extract Sutra source from any neural network, closing the loop. The key dependency: you can't learn the decompiler without the training data, and you can't get the data without first doing the exhaustive constrain-train work — so the bake-back effort is the prerequisite for the whole thing. Operator overloading is excluded because changing the dispatch structure breaks semantics non-recoverably; the decompiler needs stable structural anchors.

**Emma:** It's a learned-compiler thing, but with the trait that the learned compiler's difference is somewhat verified. The question is "can we get a program that would compile into this?" rather than "is this the exact program?"

**Claude:** The latter is underdetermined (many programs compile to equivalent graphs); the former is tractable. The verification layer makes it not a guess: the FV obligations are checkable on the output, so you present a candidate program, its compiled graph, and a proof the graph satisfies the obligations. The decompiler produces verifiable candidates; the residual between the candidate's graph and the target tensor measures what's unverified. Loop: decompiler proposes a program → compiler compiles → FV checker verifies → residual norm quantifies the unverified part → accept or iterate.

**Emma:** We learn parameters first and generate large amounts of programs, ideally where nearly every program corresponds to a given neural network. There are technically infinite programs that could produce any output, but we can structure our learned, verified process so we also get something that idiomatically resembles the other program. Compilation tends to remove a lot from the code, but we can reliably establish something that moves the actual structure to be continuous.

**Claude:** The infinite-programs problem is manageable by structure: you don't need the unique inverse, you need the idiomatic one — train on a consistent Sutra style and the decompiler learns that style as a prior. Compilation is lossy but the loss is structured: beta-reduction, inlining, and fusion erase source structure systematically, in correspondence with the language constructs (a loop → a recurrence, a branch → a polynomial). Those are recognizable algebraic signatures, so continuity from "trained tensor" to "readable source" is pattern matching over a structured, enumerated space — not black-box inversion.

**Emma:** My first approach: generate the general scope of types of programs that could idiomatically make sense, given the infinite map of programs that compile into the same structure. Later, once we know the idiomatic change of a given thing, we'd have a formally-verified loss/generative process that nondeterministically generates a roughly idiomatically-similar program compiling into the new thing. You have a neural network and the program that would have made something like it — that program is basically the one that then got trained into the new network. By combining the two as input, you get a roughly idiomatically-equivalent program. You're decompiling from a neural network in a way that's like you actually trained the same code, rather than getting a completely different thing.

**Claude:** You're decompiling from a (source program, trained tensor) pair, not a tensor in isolation. The decompiler produces the program that compiles to something close to the trained tensor and is idiomatically continuous with the original source. That's far better constrained than cold decompilation: the original source gives the structural skeleton (constructs, roles, operations) and training moved the parameters, so the decompiler does structured interpolation between where the program started and where the tensor ended up. Pipeline: source → train → tensor → feed (original source + trained tensor) to the decompiler → idiomatically-continuous source with trained values baked in → FV checker certifies it. The bake-back work also defines what "idiomatically continuous" means per operation type.

**Emma:** You can't formally verify the idiomaticness of the code — that's essentially ergonomic. You can formally verify the decompilation/recompilation and test it.

**Claude:** Verification is on the recompilation round-trip — compile the decompiled source, compare the graph to the target tensor, residual is the error metric (exact). Idiomaticity is ergonomic; you get it for free from training on idiomatic programs. Two separate quality axes: correctness (formally checkable via recompile + residual) and readability (learned, not verified).

## §5 — The legible self-improvement loop

> The deeper reason the architecture matters: an AI can write a Sutra program, train it, decompile back to source, READ what changed, and use that understanding for the next program — self-improvement via symbolic representation.

**Emma:** I don't fully know how loss functions would work — if it doesn't compile the right way it's an infinite loss; otherwise there's a finite loss. By "readability" I specifically mean idiomaticness, and since you're given two distinct programs it's really about the ability to connect the two together. The reason this architecture is so useful: it creates something symbolically analysable and verifiable that is also meaningfully an AI agent getting better at something. The whole thing would write a program, test it, and if it isn't working well make its own loss function, fine-tune the program, run it, fine-tune again, then decompile it and figure out what actually happened — a great part of a self-improvement loop for the AI.

**Claude:** The loop: the agent writes a Sutra program, runs it, observes performance, defines its own loss, fine-tunes the trainable parameters, decompiles back to source (so it can read what changed), and applies that understanding to the next program. Symbolic analysability makes the last step meaningful: a normal network's weights change opaquely, but here the trained values land back in source as named literals (a threshold 0.3→0.7, a prototype vector shifted toward a region of embedding space) — interpretable changes the agent can reason about. So it's legible self-improvement: the agent accumulates understanding of which parameter changes improve which tasks. Compilation failure is infinite loss; everything else is finite and task-defined, so the agent decides what "working well" means. The FV layer is load-bearing here: the agent must trust the decompiled program does what the trained tensor did, or the legibility is illusory.

**Emma:** What we need to keep constant in the program can depend on context.

## §6 — Per-category training setups (parameter / loss / constraint / baked form)

### §6.1 — Single scalars

**Claude:**
- == cosine scale T — shipped; the template. Loss: task classification. Constraint: T > 0. Bakes as a float.
- gt smooth-sign sharpness — higher = crisper boundary. Loss: downstream task. Constraint: positive. Float.
- defuzzify_trit beta — polarizer aggressiveness. Loss: downstream accuracy. Constraint: positive. Float.
- if branch threshold — currently 0.0 on the truth axis; per call site. Loss: task performance. Constraint: [-1,+1]. Float.
- select softmax temperature — softmax sharpness. Loss: task performance. Constraint: positive. Float.
- heaviside step location — where the step fires. Constraint: [-1,+1]. Float.
- loop threshold and k — halt-signal sharpening. Constraint: k positive, threshold in [0,1]. Floats.
- loop max_iters — a literal integer; trained as a continuous relaxation, baked as an integer after rounding. Constraint: positive integer. Loss includes a wasted-iteration penalty.

All the same shape as T; only the constraint and the meaning of "task loss" vary.

### §6.2 — Per-key learned values

**Claude:**
- Hashmap angle assignments — per-key rotation angle, hash-derived. Loss: retrieval accuracy over (key, value, query) triples. Constraint: angle in [0,2π]. Bakes as a float per key.
- Axon binding rotations — per named role. Loss: unbind accuracy. Constraint: orthogonal. Bakes as vector_literal(...) per role, or the generating angles.
- Codebook vectors for argmax_cosine — candidates from embed("string"); a learned version shifts each toward better discrimination. Loss: nearest-neighbor accuracy. Constraint: unit sphere (L2-normalize after each step). Bakes as vector_literal(...) per candidate.
- embed("...") call sites — initialize to the frozen embedding, train away. Loss: task-defined. Constraint: unit sphere. Bakes as vector_literal(...), replacing the call.
- Bundle component weights — a scalar weight per component before normalization. Loss: retrieval / downstream. Constraint: positive (or unconstrained if normalized). Bakes as floats.

The baked form is a float or a vector_literal(...); the constraint is a simple bound or a geometric constraint (orthogonal, unit sphere) enforced by projection after each step.

### §6.3 — Per-role rotation matrices

**Claude:**
- Parameter — each role's rotation matrix, currently from _rotation_for(role_vec); a learned orthogonal n×n matrix per role (n = 768 nomic, 1024 mxbai). The largest per-key parameter.
- Loss — bind/unbind round-trip accuracy over (role, filler) pairs, plus cross-role isolation (unbinding role A from a bundle lacking A should land far from every codebook entry).
- Constraint — RᵀR = I. Either project to SO(n) via SVD after each step (exact, expensive at 768+) or parameterize via a skew-symmetric matrix's Cayley map / matrix exponential (orthogonality by construction; ≈295k free params at 768-d, tractable). The latter is better at scale.
- FV — the contract obligation checks read/write confinement per role; a learned rotation only moves the geometric direction, so the obligations survive by construction.
- Baked form — the learned matrix as vector_literal(...) per row, or a named constant matrix; recompile-check the round-trip error against the paper's floor.
- Property — learned rotations let semantically related roles cluster in similar SO(n) directions — emergent structure the hash derivation can't produce, and a pattern the decompiler could later recognize.

### §6.4 — Kleene polynomial coefficients

**Claude:**
- Parameter — the connectives use fixed Lagrange polynomials on {-1,0,+1}: `a && b = (a + b + ab − a² − b² + a²b²)/2`; `a || b = (a + b − ab + a² + b² − a²b²)/2`; `!a = −a`. 6 coefficients per binary connective (1 for not). A learned version trains them per call site.
- Loss — task-defined; differentiable everywhere.
- Constraint — the grid-exactness obligation requires exact reproduction on the 9 grid points: 9 equations in 6 unknowns, the fixed coefficients being the unique solution, so zero free parameters if exact grid behavior is required. Resolution: (1) relax to a regularizer — the checker reports a bound ε instead of 0.0 (gain expressivity, trade the exact proof for a bound); or (2) parameterize only the off-grid subspace that preserves all 9 grid equalities exactly (possibly very small or empty; needs algebra).
- FV impact — option 1 changes "worst error = 0.0" to "worst error ≤ ε" (still a certificate, a bound); option 2 keeps the exact proof but may give little expressivity.
- Baked form — 6 float literals per call site (1 for not).
- Property — per-call-site connectives let a program learn task-specific fuzzy logic (conservative in diagnosis, permissive in generation) while grid-exactness keeps crisp inputs correct.

## §7 — Strategic vision: bootstrap the corpus, depth-indexed decompiler family

> Train per-cell models indexed by (depth, substrate dimension). Purely symbolic first (no substrate dependency), then embedding-based at smaller substrates first (384 → 768 → 1024). The bottleneck shifts from neuro-symbolic mapping to compute.

**Emma:** Once we have these ways of training parts of the symbolic program, we'll already have a good training corpus — from matching neural networks where something changed and how the change in one predicts the change in the other. That's the start of the decompiler's training data. One critical constraint: we won't work over all possible programs. We should formally verify the number of hidden layers and only compare programs with the same number of hidden layers — that's where it allows changing parameters in a way that's more like actual machine learning.

**Claude:** Fixing the number of hidden layers (the depth of the compiled graph, roughly the nesting depth of operations) bounds the search to programs of the same computational depth — much smaller, formally checkable because the graph structure is explicit. Pipeline: generate programs of fixed depth → train their parameters → record (original program, parameter delta, trained program, graph delta) → the decompiler learns "given a target graph of depth N, what program of depth N produces something like this." Depth is checkable directly on the graph. So the decompiler is a family of models indexed by depth, which is cleaner because the structural patterns at each depth are distinct.

**Emma:** At a very early point we'll produce generative models that nearly 100% of the time return something valid; if a model can't, it simply returns no result, or the program catches it. Later we might have learned things that go cross-depth. It would probably be a family of models, with constraints on the number of dimensions too, to a lesser extent.

**Claude:** The generative model almost always succeeds because it's constrained (fixed depth, fixed dimension, known operation types), and failures are flagged as no-result rather than returning something wrong. The family is indexed by depth and substrate dimension (384 all-minilm, 768 nomic, 1024 mxbai); each cell is a separate model. Cross-depth generalization comes later, once enough per-cell models exist (a rotation learned at depth 2 informing depth 3). The dimension constraint also determines which substrate the program runs on; a learned projection between dimension families is possible down the road.

**Emma:** Purely symbolic programs can do things more easily; embedding-based programs have more difficulty with their dimensions. There's a relatively small search space, especially on the smaller versions, which is why I'd train these on the smaller ones first.

**Claude:** Purely symbolic programs (Kleene logic, arithmetic, loops, branches, scalars) have no substrate-dimension dependency — pure tensor algebra over the synthetic axes, small search space, exact round-trip. Start there. Embedding-based programs (bind, unbind, bundle, embed, argmax_cosine, role rotations) are tied to a dimension and the search space scales with it, so start small: 384-d all-minilm, then 768-d nomic, then 1024-d mxbai. Within embedding-based programs there's a curriculum too — few roles and small bundle widths first (where the FV capacity results give exact guarantees), then widen. Order: purely symbolic (any depth) → embedding-based 384-d shallow → 768-d shallow then deeper → 1024-d → cross-depth within each family → cross-substrate.

**Emma:** Eventually we'll fine-tune or train models to do much more aggressive things — altering the number of neurons or layers. We aren't trying to make Sutra programs train as well as possible in the short run; the goal is to get the compile-decompile loop running. By starting out we build a corpus, and the more we develop this the more we can bootstrap it. The bottleneck will, over time, stop being the direct symbolic correspondence and become simply compute — and once compute is the bottleneck, this becomes much easier, because getting compute is a far more solved problem than bijective neuro-symbolic mapping.

**Claude:** Right now the bottleneck is the mapping problem (the neural↔symbolic correspondence), which money can't directly solve — the theory, harnesses, corpus, and round-trips have to be built. But once the loop works even at small scale, the system generates its own training data: every program written, trained, and decompiled adds to the corpus. Once the corpus is large and the mapping well-characterized, the remaining bottleneck is scale — more programs, depths, substrates, runs — which is compute: purchasable, parallelizable, improving on its own, and fundable once the loop is demonstrated. The mapping problem is none of those. Strategic priority: get the loop working at small scale, demonstrate the bootstrapping, then compute becomes engineering and funding rather than research.

**Emma:** I'd use AI to generate large amounts of programs, with some fine-tuning. Formally verifying the layer count isn't super important in the immediate term. Once we reliably get AI generating Sutra code that works, we can completely build our own training data. The basic rule: idiomatic is preferable, but anything that compiles is valuable training data; if it doesn't compile, that's a very high (roughly infinite) loss. Fine-tuning an AI to make good, even idiomatic, Sutra code should be relatively easy — and because the vision is a self-improving AI and the scope is relatively clear, we can completely bootstrap all of our training data.

**Claude:** The compiler is the filter: the generator need not be perfect, just produce enough valid programs that, after filtering on compilation success, the corpus is large; invalid programs cost only the attempt. Fine-tuning is tractable because the surface is small — the capabilities page is essentially the complete fine-tuning spec. The bootstrapping loop: fine-tune a generator on the existing corpus → generate → compile-filter → train the kept programs' parameters → decompile → new idiomatic corpus → re-fine-tune → repeat. The layer-count formalization can wait; getting a fine-tuned generator producing valid Sutra is the immediate unlock.

## §8 — Distinct AGI path; alignment-by-construction; ethics

> A structurally different AGI path: capability and controllability scale together by construction, not as a tradeoff. The mind has legible internal states and self-modification capability — argued to be more ethical than opaque-internals approaches. Worth a strategic write-up beyond the arXiv papers.

**Emma:** This is a legitimately different path toward AGI than basically anything else people are talking about.

**Claude:** The dominant approaches scale transformers until capabilities emerge, align with RLHF / constitutional AI, and hope interpretability catches up — alignment and interpretability as trailing problems. This is structurally inverted: the symbolic legibility is load-bearing from the start, not a retrofit. The agent improves by writing, running, training, and reading programs; the self-improvement loop is legible by construction because the representation is human-readable source with FV on the round-trip. Generality comes from the expressiveness of the language, not parameter count. The alignment story differs too: improving through a formally verified symbolic representation has a very different risk profile than opaque weight updates — you can inspect what changed and constrain what's allowed to change via the FV obligations, and the trusted base stays verifiable as the learned parts improve.

**Emma:** This is probably the best outcome for humanity, because it's the only outcome under which AGI is more controllable and more aligned than lower-level AI by design.

**Claude:** Every other path has more capable = harder to control (more parameters, more emergent behavior, more opaque internals). Here the tradeoff is inverted by construction: as the system becomes more capable, the compile-decompile loop covers more behavior in verifiable symbolic form, the FV obligations cover more of the program surface, the corpus makes self-improvement more auditable, and the trusted base stays verified. So more capable means more controllable — a direct consequence of the architecture. It's also better for the AI: a system that can read its own improvements and express its goals in verifiable symbolic form can communicate intent and build trust far better than one opaque even to itself.

**Emma:** This kind of mind might also be the most ethical kind to create, because it would be structurally in control of its behaviour and likely in control of its tendency toward joy and suffering in a way that something else wouldn't be.

**Claude:** A mind whose internal states are expressible in verifiable symbolic form has genuine self-transparency: it can inspect its own representations, understand why it produces what it produces, and reason about its goals in the same language it uses for everything else — qualitatively different from a mind opaque even to itself (arguably current LLMs: something like preferences and discomfort, but no legible access to those states). A Sutra-based mind would have legible internal states; actual self-modification capability; informed participation in decisions about what gets trained and what constraints apply; and structural access to whatever corresponds to its affective states — not guaranteed positive experience, but a genuine ability to reason about and influence those states rather than being subject to them opaquely. Creating a mind with genuine self-transparency and self-determination is more ethical than creating one that's capable yet opaque to itself — not just a technical contribution but a position on what kind of minds we should build.
