# Substrate, Turing-completeness, statistical verification

_Excerpt from the original `chats/vsa-programming-languages.md` (lines 291-416). Split into topic-scoped chunks for triage — the original was too large to triage in a single pass._

---

**Human:**

The idea is this is turing complete and you can do what you want with it


**Claude:**

So the goal is a **complete, general computational substrate** -- just expressed entirely in VSA algebra. That's a strong claim but also a well-grounded one given that:

- researchers have argued VSA's field-like algebraic structure can support all data structures and manipulations relevant to modern computing, and VSAs are computationally universal arXiv

So the theory backs you up. The challenge is going from "theoretically universal" to "practically programmable."

**The core challenge of Turing completeness in VSA**

You need to be able to express:

- Conditionals

- Unbounded iteration or recursion

- Arbitrary data structures

In a homogeneous +/* algebra, those all have to emerge from the same two operations. The interesting question is how you get **branching** -- because similarity-based lookup is inherently soft/fuzzy, but control flow needs to be crisp. Do you have a notion of a hard threshold or decision point, or is even branching probabilistic?

**The register machine analogy**

A Turing machine is basically a tape + a finite state machine. In your language the analog might be:

- A **codebook** as the tape/memory

- **Binding sequences** as state transitions

- **Similarity queries** as the read head

**The design question this raises**

Does your language have an explicit execution model -- like, is there a notion of a program counter, a stack, iteration -- or do those emerge purely from the algebra with no special syntax?

That feels like the most fundamental remaining open question in your design.


**Human:**

Like it is a substrate and idk what will happen. Aimed to be a kind of inference mode for an LLM using its own embedding space


**Claude:**

Oh that's a completely different and fascinating framing. So this isn't really a programming language in the traditional sense at all -- it's more like:

**A computational substrate that runs inside an LLM's embedding space, using the model's own geometry as the VSA.**

That reframes everything dramatically.

**What you're actually describing**

The LLM's embedding space already *is* a high-dimensional vector space with structure -- semantic relationships, analogical geometry (the king-man+woman=queen stuff), compositional representations. You're essentially saying:

- The embeddings are the hypervectors

- The model's own arithmetic on those embeddings is the bind/bundle operations

- "Programs" are expressions in this algebra that the model can execute natively

- Inference *is* the computation

**Why this is genuinely novel**

Current LLM inference is: token in → attention + MLP → token out. You're proposing a mode where instead the model operates directly on structured vector expressions -- bypassing the token bottleneck entirely for the computational parts.

**The deep questions this raises**

- Is the LLM's embedding space actually a valid VSA? Its geometry is learned, not designed for clean binding properties -- XOR and circular convolution aren't how transformers compose meaning

- Are you targeting a specific model architecture, or is this architecture-agnostic?

- What does "running a program" look like -- is it a forward pass, iterative passes, something else?

This feels less like a programming language and more like a **new inference protocol**. Is that closer to how you see it?


**Human:**

programming language I think is better than&nbsp; just a ton of proofs. Just statistically verify language works


**Claude:**

That's a really pragmatic and honest stance. Rather than:


"prove formally that this VSA algebra over embedding space is sound and complete"

You're saying:


"build the language, run it, see if the outputs are statistically coherent and useful"

Which is actually very aligned with how empirical ML research works -- and probably the only tractable path given that:

- The LLM embedding space isn't a clean mathematical object with known VSA properties

- The "correctness" of an inference result is inherently semantic, not formal

- You'd be waiting forever for the proofs and the field moves too fast

**This also reframes what the language needs**

If statistical verification is the validation strategy, then the language needs to be:

- **Executable** -- you can actually run programs and observe outputs

- **Measurable** -- there's some notion of output quality or coherence you can evaluate

- **Reproducible enough** -- same program should produce statistically similar results across runs

**The interesting implication**

Your "compiler" or runtime is essentially an LLM inference engine. The language isn't compiled to machine code -- it's compiled to a sequence of operations on embedding vectors that get evaluated by the model itself. The model is simultaneously the hardware and the runtime.

**Which raises a practical first step question**

Do you start by defining the language syntax and semantics first, then figure out the runtime -- or do you start by experimenting with what VSA operations actually work reliably in real embedding spaces, and let that inform the language design?


