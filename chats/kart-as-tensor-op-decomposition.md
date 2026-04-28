# KART intro — every function as composition of univariates

_Excerpt from the original `chats/kolmogorov-arnold-networks-for-tensor-operations.md` (lines 1-100). Split into topic-scoped chunks for triage — the original was too large to triage in a single pass._

---

# Kolmogorov-Arnold Networks for tensor operations

*Extracted from Claude.ai chat.*

## User

I've recently heard of this thing where a physicist implemented it to do some sort of a thing where basically every function could be represented by some other function. What was that? I'm thinking, for the Sutra programming language, this might contribute to, I'm not going to say, the differentiability; although I hope it would, it might be able to contribute to the ability to represent different functions as tensor operations instead of having to do more expensive things.

## Claude

Searched the web

Searched the web

That's KANs — Kolmogorov-Arnold Networks, proposed in 2024 by Ziming Liu and Max Tegmark (the physicist). Here's the full picture and why it's relevant to Sutra:

The underlying math: The Kolmogorov-Arnold Representation Theorem (KART)

The theorem, introduced by Arnold and Kolmogorov, states that any continuous bounded multivariate function can be expressed as the sum of a finite composition of univariate functions. arXiv Specifically, any f(x₁,...,xₙ) decomposes into nested sums of single-variable functions — no multivariate function is truly "irreducible." This was actually a resolution of Hilbert's 13th problem.

What KANs did with it

While MLPs have fixed activation functions on nodes ("neurons"), KANs have learnable activation functions on edges ("weights"). KANs have no linear weights at all — every weight parameter is replaced by a univariate function parametrized as a spline. arXiv

Liu approached the problem as a physicist rather than a mathematician — "maybe because of physicists' optimism and practicality, we were less worried about the negative claim based on theoretical mathematics, which may have little to do with practice — we just built it and saw it work." TechTarget

The differentiability point you were hedging on

All the operations in KANs are differentiable, so KANs can be trained with backpropagation. Iclr So your instinct was right — it does give you differentiability essentially for free, because the spline parameterization is smooth by construction.

The Sutra angle

This is genuinely interesting for Sutra's "everything is a tensor operation" thesis. KART tells you that any continuous multivariate function has a canonical decomposition into univariate functions composed via addition. That's a very flat, structurally uniform representation — which maps naturally onto your hyperdimensional model.

The implication: rather than compiling arbitrary user-defined functions to expensive general-purpose operations, Sutra could potentially recognize when a function fits the KART decomposition structure and lower it to a sequence of vector lookups / spline evaluations — all of which are parallelizable tensor ops. The univariate functions in KART are exactly the kind of thing that vectorizes well across a batch dimension.

The catch is that the inner univariate functions in KART can be non-smooth or even fractal in the worst case — one key challenge is that the inner functions may be discontinuous or even exhibit fractal behavior, which makes them difficult to learn using traditional methods. arXiv The KAN paper sidesteps this by using splines as the function family (which are smooth by construction), effectively working in a restricted but practically useful subset of KART.

For Sutra, the interesting design question would be: can you define a type-level constraint that says "this function is KART-decomposable into splines of degree k," and then let the compiler automatically route it to a tensor path instead of general function dispatch? That would be a genuine compiler innovation, not just a library trick.

## User

Yeah, what do you mean by genuine compiler innovation as opposed to library trick? You mean in the sense that my entire thing is the way I thought Lisp was supposed to work, which was that all the lambda calculus gets compiled into a single simple function that has an input and output. I don't exactly know what you're meaning by that, but yeah, the Karp decomposable functions, like, what things are kart decomposable? Are there things that are not decomposable according to the cart thing? Are there things that are not decomposable in it? Was it something more like every differentiable function or something?

## Claude

The theorem is actually stronger than differentiable — it covers all continuous functions, full stop. Any continuous bounded multivariate function can be expressed as a finite composition of univariate functions. arXiv So KART doesn't carve off a special class — it's a universal decomposition theorem for continuous functions. The exceptions are things like discontinuous step functions or fractal-boundary functions, which aren't continuous, but those are fairly exotic in practice.

So the more interesting question for Sutra is the converse: not "what can't be decomposed" but "what does the decomposition cost you?" The KART form always exists, but the inner univariate functions might be pathologically complex to represent — that's the real constraint.

On the compiler vs library distinction

What I meant is this. A library trick would be: you ship a KAN layer as a runtime data structure, the user calls it like a function, and at runtime it does spline lookups. That's just a neural net library. The computation graph is generic.

A compiler innovation would be: Sutra's type system carries enough information about a function that the compiler itself — at compile time — recognizes "this is a KART-decomposable function with smooth univariates" and emits a fundamentally different computation plan, not the general dispatch path. The user writes something that looks like a normal function definition, and the compiler transparently lowers it to tensor ops without the user doing anything special.

That's exactly your abstraction inversion thesis. The user writes high-level declarative code; the compiler collapses it to a single linear map or a structured tensor evaluation. KART would give you a mathematical guarantee that the collapse is valid — not just a heuristic optimization. That's what makes it a compiler claim rather than a library claim.

The Lisp/lambda calculus analogy you're drawing is precise: the idea that beta reduction collapses a chain of function applications into something flat. KART is essentially saying the same thing happens in function space — nested multivariate complexity folds down into a sum of univariates. If Sutra's formula simplification model already does that collapsing symbolically, KART is the theorem that justifies when the collapsed form is a valid tensor path.

## User

No, I mean, hopefully I know what's going on, but I might wait. Am I basically doing beta reduction without realising that I'm doing beta reduction?

## Claude

Yes, almost certainly.

Beta reduction is just: substitute the argument into the function body, collapse the application. If you do that repeatedly, a chain of composed functions becomes a single expression — ideally a single linear map if everything is linear enough.

Your abstraction inversion model is: user writes TypeScript-looking imperative code, the compiler simplifies it through formula rewriting until it hits a closed form — ideally a single matrix multiply or linear operation. That is beta reduction. The "formula simplification" step is just beta reduction plus whatever algebraic identities you allow (linearity, commutativity, etc.).

The foreach-collapses-to-simultaneous-evaluation insight you had earlier is also a beta reduction story — you're reducing the loop abstraction away until what's left is a pure data-parallel expression with no control flow residue.

Where it gets interesting is that standard beta reduction is purely syntactic — it doesn't know that the result is a tensor operation specifically. What Sutra adds on top is a semantic layer: the type system knows the result lives in hyperdimensional space, so after reducing, it can recognize the canonical tensor form. KART would then be the theorem that says "and by the way, any continuous function you could have written also has such a reduced form" — closing the gap between what your compiler can reduce and what's mathematically reducible.

So you're probably doing typed beta reduction into a tensor-typed normal form, and KART is the completeness certificate.

## User

`beta_reduction` is basically like the substitution thing, so in my programme, basically I guess the entire programme is basically doing `beta_reduction` plus algebraic simplification, just going to a 

Because the idea here is that all the stuff gets substituted in first. I do have some functions that can be compiled as functions, but they're compiled as matrices. This is for the ones that it works for, but even then it's still a multiplication, so it's still a function substitution thing. Functions get substituted entirely into the code, and then they get substituted into the code sufficiently that it's all just the multiplications. Afterwards, you do algebraic simplification rules, and the multiplication of things is essentially the way that our compiling works. If there are compilers that have different philosophies than beta reduction for them. My idea is basically that every programme is a function, so every programme would ideally be a single matrix multiplication.

## Claude

Right, and that's a very clean and coherent compiler philosophy. The whole program is one function, and a function is a matrix, so compilation is just: reduce until you have the matrix.

The standard compiler philosophy is essentially the opposite. Most compilers think of a program as a sequence of instructions — they lower from high-level to assembly, preserving the sequential control flow structure, and optimize locally within that. Beta reduction happens incidentally during inlining, but it's not the organizing principle. The output is still a sequence.

Your organizing principle is that the output is a value — specifically a linear map. The program doesn't run, it evaluates. This is much closer to how a mathematician thinks than how a systems programmer thinks.

The closest existing thing is probably supercompilation — where you partially evaluate a program by symbolically running it with unknown inputs, collecting all the residual computation into a single expression. Some Haskell compilers do versions of this. But even supercompilation still targets a program as output, not a matrix.

The other adjacent thing is polyhedral compilation — used in tensor compilers like XLA and Halide — where loop nests get analyzed as geometric objects and fused/reordered. But again, the output is still code, not a closed-form function.

What you're doing is closer to what happens in automatic differentiation systems when they build a computation graph and then trace through it — except you're not tracing at runtime, you're collapsing at compile time, and the target is a matrix rather than a gradient.

So the honest answer is: no existing mainstream compiler has this as its core philosophy. Which is exactly why it's interesting.

