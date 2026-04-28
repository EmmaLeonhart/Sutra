# Decision to build one — audience, level, VSA-as-assembly framing

_Excerpt from the original `chats/vsa-programming-languages.md` (lines 83-290). Split into topic-scoped chunks for triage — the original was too large to triage in a single pass._

---

**Human:**

Yes imma make one


**Claude:**

That's a genuinely exciting project -- you'd be in pretty novel territory. A few things worth thinking through as you start:

**Core design questions**

- What's the primary VSA model you'll target? BSC (binary, XOR-based), HRR (real-valued, circular convolution), MAP, or FHRR? Each has different properties for binding/unbinding that would shape the language semantics significantly.

- Is the language general-purpose, or domain-scoped (e.g., AI/reasoning tasks, robotics, cognitive architectures)?

- What does the programming model look like to the user? Do they think in terms of hypervectors explicitly, or does the language abstract that away entirely (like how C programmers don't think about transistors)?

**The hardest design problems**

- **Type system** -- In conventional languages, types tell you what operations are valid. In VSA, everything is a hypervector, but the *semantic* meaning of a vector (is it a bound pair? a bundle? an atomic symbol?) isn't encoded in its representation. How do you surface that in the type system?

- **Determinism** -- VSA operations are inherently approximate and probabilistic. How does your language handle that? Do you expose it, or hide it behind thresholds?

- **Memory/codebook management** -- The item memory (the set of base atomic vectors) needs to be managed somewhere. Is that a language-level construct, or runtime?

- **Unbinding as a language primitive** -- Query/unbinding is essentially pattern matching under similarity. That maps interestingly onto logic programming or functional pattern matching.

**Possible inspirations to look at**

- **Prolog** -- its unification model has structural parallels to VSA binding/unbinding

- **APL/J** -- terse array-oriented languages; VSA is fundamentally array math

- **Probabilistic programming languages** (Church, Gen, Pyro) -- deal with approximate/stochastic computation explicitly

- **NengoSPA** -- the Semantic Pointer Architecture gives a neural/VSA programming model worth studying as prior art

What's your current thinking on the programming model -- do you want it to feel more like a logic language, a functional language, or something else entirely?


**Human:**

Abstracts mostly away.&nbsp;But this is intended still not for a general audience


**Claude:**

So a kind of "expert DSL" -- the user understands VSA conceptually but doesn't want to manually manage hypervectors, codebooks, binding sequences, etc. That's a sweet spot that makes a lot of sense.

A few follow-up thoughts on that framing:

**What "abstracted away" probably still needs to be visible**
Even for VSA-literate users, they'd likely still want to reason about:

- Capacity limits (how many items bundled before similarity degrades)

- Which VSA model is being used under the hood (affects what operations are lossless vs approximate)

- Whether two things are the same *symbol* vs the same *structure*

Hiding these completely could make programs hard to debug or reason about.

**What the abstraction buys you**
The tedious parts that should definitely be hidden:

- Codebook initialization and dimensionality

- Manual bind/bundle/permute sequences for common structures (lists, trees, key-value pairs)

- Similarity threshold tuning for queries

**A key question: what's the primary computational metaphor?**

This shapes everything about syntax and semantics. Some options:

- **Relational** -- you declare facts and query them, VSA handles the encoding. Feels like Datalog.

- **Functional** -- you transform hypervector structures through pipelines

- **Imperative with VSA primitives** -- feels like a normal language but `bind`, `bundle`, `query` are first-class

- **Pattern-matching driven** -- programs are mostly queries against a VSA memory

What's the kind of program you imagine someone writing in it? Even a rough pseudocode sketch of what it should *look* like would help crystallize the design enormously.


**Human:**

biggest and maybe most confusing thing: no regular datatypes and everything can be added or multiplied


**Claude:**

Ah, so you're going for a **fully homogeneous value model** -- one kind of thing (the hypervector), and the language's entire algebra is just addition and multiplication on those. That's a radical and coherent choice.

This actually maps cleanly onto how VSA math actually works:

- **Addition = bundling** (superposition, similarity-preserving)

- **Multiplication = binding** (circular convolution, XOR, etc. -- structure-preserving)

And from those two operations you get everything -- lists, records, sequences, analogies, all of it emergent from algebra rather than built-in types.

**The interesting consequences of this**

- There are no "wrong type" errors -- only meaningless or noisy results. Your error model is fundamentally different from conventional languages.

- Literals are just named atomic hypervectors. `cat` and `dog` aren't strings -- they're basis vectors.

- Equality doesn't exist in the conventional sense. You only have **similarity** (`~=` rather than `==`).

- Commutativity of addition means order of bundling doesn't matter -- which has weird implications for sequences (you'd need permutation/rotation to encode order).

**The confusing part you mentioned**

I think the confusion for users comes from the fact that `a + b` doesn't produce something *bigger* than `a` or `b` -- it produces something *similar* to both, at the same dimensionality. That's deeply counterintuitive coming from any conventional language.

How are you thinking about syntax -- do `+` and `*` literally mean those operators, or different symbols?


**Human:**

It is not exactly a general purpose programming language. It is specialized in a way I see as analogous to assembly


**Claude:**

Oh that reframes everything. So this is essentially **VSA assembly** -- not meant to be written by end users of some higher system, but the low-level substrate that higher-level VSA languages or compilers would target.

That makes the design philosophy completely different:

**What that implies**

- Explicitness over convenience -- the programmer should be able to see exactly what VSA operations are happening

- No magic, no inference -- if something gets bound or bundled, you said so explicitly

- It's probably the thing a VSA compiler *emits*, not what a human reaches for first

- Minimal abstraction, maximal control -- like how assembly exposes registers and memory directly

**The analogy to assembly is tight**
In x86 assembly:

- Everything is bits in registers

- You have a small set of primitive operations (MOV, ADD, MUL, XOR...)

- Structure (arrays, structs, functions) is a convention, not a built-in

In your language:

- Everything is a hypervector

- You have a small set of primitive operations (bind, bundle, permute, query...)

- Structure (records, sequences, sets) is a convention built on top

**The interesting design tension**
Assembly still has *some* abstraction over raw hardware -- named registers, labels, mnemonics. Your language presumably needs analogous affordances:

- Named symbols instead of raw random vectors

- Labels or variables for intermediate hypervectors

- Maybe directives for dimensionality or VSA model selection

Does it have a notion of a "program" in the traditional sense -- sequential execution, control flow -- or is it more declarative? That feels like a critical fork in the design.


**Human:**

Mine is higher than assembly, lower than C#


**Claude:**

So somewhere in the **C / systems language tier** of abstraction -- you have named things, some structure, real syntax, but you're still close enough to the VSA operations that nothing is hidden from you. The programmer is always aware they're working in hypervector space.

That's actually a really well-defined niche. Like C is to x86, your language is to VSA hardware/runtime.

**What that tier typically gives you**

- Named variables and symbols

- Some control flow (but probably minimal -- do you even need loops in the traditional sense?)

- Functions or procedures

- Manual memory/codebook management is visible but not painful

- No garbage collection of semantics -- if your bundle gets noisy, that's on you

**The interesting question at this tier**

C at its level still has `int`, `float`, `char`, `pointer` -- a small but real type system that maps directly to hardware primitives. Your language has one "type" -- the hypervector -- but you probably still need some notion of:

- **Dimensionality** -- is that a compile-time constant, a runtime parameter, or a per-symbol property?

- **VSA model** -- is it fixed for the whole program like an architecture target, or switchable?

- **Atomic vs composite** -- does the language distinguish a freshly drawn random vector from a bound/bundled one, even if they're the same underlying representation?

That last one feels like the analog of C's pointer vs int distinction -- technically both are just bits, but conflating them is a bug.

What's your instinct on those three -- fixed at compile time, runtime configurable, or not surfaced at all?


