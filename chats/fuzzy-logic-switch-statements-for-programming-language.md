# Fuzzy logic switch statements for programming language

*Extracted from Claude.ai chat.*

## User

I'm thinking that, for my programming language that I'm making, because it uses fuzzy logic, I really do not want it to run the same kind of if-else-if-else statements in exactly the same typical way. Not sure how, but I just think I want to have some kind of a soft max switch statement be the default, but I'm not sure how to do so.

## Claude

This is a really interesting design space — you're essentially asking how to make branching inherently probabilistic/graded rather than crisp. Let me think through this with you.

## The Core Idea

Instead of a switch that picks one branch, you want a construct where every branch has a degree of activation, and the language decides how to combine them. The classic softmax is a natural fit: given scores/weights for each case, the branch outputs are blended proportionally.

## What it Could Look Like

Here's a rough sketch of what a soft match statement might feel like in Sutra:

```
match signal {
  high_frequency => filter_treble,
  mid_frequency  => filter_mid,
  low_frequency  => filter_bass,
}
```

The key difference from a normal switch: `signal` isn't discretely equal to one case — it has a membership degree in each. The runtime computes something like:

```
output = Σ softmax(similarity(signal, caseᵢ)) · branchᵢ(signal)
```

This maps perfectly onto Sutra's model since everything is a vector — similarity is just dot product or cosine distance, and blending branch outputs is vector addition.

## Design Decisions to Nail Down

1. What are the "case" values?
They could be:

Literal vectors (learned or hand-specified prototypes)

Fuzzy membership functions (triangular, Gaussian, etc.)

Named regions in embedding space

2. What does "executing" multiple branches mean?
Options:

Lazy blend — only evaluate branches with activation above a threshold, then blend outputs

Eager blend — always evaluate all branches, weight and sum results

Top-k — only the k highest-activation branches run (a "sparse" softmax)

Eager is cleanest semantically and fits your "no runtime errors by architecture" philosophy — every branch always contributes, so there's no edge case where nothing fires.

3. Temperature
You almost certainly want a temperature parameter (explicit or inferred from context) controlling how "sharp" the distribution is — high temperature → near-uniform blend, low temperature → nearly crisp winner-takes-all. This lets the same construct degrade gracefully to classical switch behavior when you want it.

```
match<sharp> signal { ... }   // low temp, nearly crisp
match<soft>  signal { ... }   // high temp, diffuse blend
```

## What This Means for Sutra Specifically

Since Sutra's runtime is all vectors/matrices, a soft match is really just:

Compute activation vector `a = softmax(W · signal + b)` — one scalar per branch

Evaluate all branch functions → outputs `[o₁, o₂, ..., oₙ]`

Return weighted sum `output = Σ aᵢ · oᵢ`

Steps 1 and 3 are pure linear algebra. Step 2 is just function application. The whole thing is differentiable by construction, which fits your auto-diff guarantee perfectly.

The biggest open question is probably: what are cases matched against? Is it prototypes you define, fuzzy sets, or implicit nearest-neighbor in embedding space? That determines the "feel" of writing match statements. What's your intuition there?

## User

Honestly, I don't know what a fuzzy set is, but it's the implicit nearest neighbour in the embedding space. It's basically the degree of distance between all these different things in the embedding space, between all of the set conditions in the embedding space, that you'd be matching against, at least for that thing. I'm imagining it as being some kind of soft max thing, but I'm not really sure how it would work, and I'm not sure. The thing is I kind of want to actively

## Claude

It looks like your message got cut off — "I kind of want to actively..." what? Finish that thought and I'll pick up right where you left off!

## User

Oh, sorry, I haven't actually read this document, just to be clear. What is a gate select and if-else? I guess the thought is that an if-else statement is just something that is going to exist, but essentially, because we're not actually using an if, but a select. I think it probably makes it harder for people to decide which one to use, because it makes it hard for people to decide which one to use, because basically like it makes it hard for people to default to if statements and then end up doing fucking bullshit with the if statements, because they have to choose between select and gate. Gate is just like if, but gate is something that is unintuitive for people to write. Essentially, gate is something that is unintuitive for people to have, and maybe gate is going to focus on signum and maybe gate is going to force a defuzzification, whereas select does not. Gate can be made a bit more complex than select, because I think a big reason why a lot of people don't use select, don't use switch statements very often, is that a switch statement fucking takes like forever to write in most languages. In ours, it's just going to be like select blank, select blank, select blank, else, and it's all in a row; it all gets compiled into a switch statement, whereas gate is going to be like gate, gate, blank, else, and it's just more complicated. The gate is a bit more complicated, because select does not have fancy code in it at all. A select is just like you can write it in C# or even in Python, and it'll still work, because that is actually a feature of my code. You can basically write it like Python. You can write it like Python, but essentially the IDE makes it not like Python by adding the parentheses.

## Claude

Oh, this is a fantastic research doc — you've clearly already thought through a lot of this more deeply than our conversation had surfaced. The three-form taxonomy (`gate`, `select`, `if/else` as hard error) is clean and well-motivated.

So, picking up where you cut off — you said "I kind of want to actively..." — my guess based on what you uploaded is that you wanted to say something like actively prevent programmers from reaching for crisp if/else, not just discourage it. And the doc confirms that's exactly your intent. The hard codegen error + diagnostic pointing at `gate`/`select` is the right call there.

A few things I want to flag or push on from the doc:

The defuzzification contradiction is the real blocker, and I'd lean toward Option A unless you have a specific reason to want the iterated form. The fixed cosine projection is already validated, already in the paper, and `select`'s weights mapping directly to `cos(query, prototype_i) / tau` is clean and transparent. The iterated form as currently described in the spec was a tautology — so restoring it without a genuine redesign (Option B) would be reintroducing a known-broken thing. Option C is appealing but adds syntactic complexity before you know anyone needs it.

On tau — I'd start with a single per-`select` tau with a sensible default, and make it an explicit keyword argument if specified. Don't make programmers understand softmax to use it, but don't hide it either. Something like `select<tau=0.3> { ... }` is transparent without being mandatory.

On prototype declaration — explicit feels right for Sutra's design philosophy. "Magic inference" is exactly the kind of thing that would make the language feel inconsistent. A `prototype` declaration also gives you a natural place to attach documentation and makes the embedding-space semantics legible to someone reading the code.

What was the end of your sentence going to be?

## User

My thought would be that essentially it's just a matter of select statements being as easy to write as an if statement. A gate indicates that select statements are actually a bit easier to write than an if statement, because you don't really need else or anything like that in it. You just have a row of selects that just becomes a switch statement, whereas gates involve a lot more complicated stuff. None of them are if statements because of the fact that an if statement is ambiguous depending on the context.

## Claude

Got it — so you hadn't seen that doc before, it was just notes from a previous session. Let me restate what I'm hearing you describe from scratch, in your own terms:

`select` is the simple one. Lightweight syntax, almost like writing a list. The IDE handles the boilerplate. It compiles down to the softmax-weighted blend over embedding-space prototypes. No defuzzification — outputs stay fuzzy. Easy to reach for, easy to write.

`gate` is the one that forces a crisp decision. It defuzzifies — probably via signum or a threshold — so it produces a hard 0/1 outcome. It's intentionally more verbose to write, because the verbosity signals "you are leaving fuzzy-land, this has a cost." The friction is a feature.

`if/else` still exists syntactically but is a hard error at codegen — the diagnostic says "did you mean `gate` or `select`?"

The key insight I'm hearing is: the friction asymmetry does the work. `select` is so easy to write that it becomes the default. `gate` being slightly more involved means you only reach for it when you genuinely need a crisp branch. Nobody accidentally writes a `gate` when they meant `select`, the way everyone accidentally writes `if/else` chains in every other language.

Is that the shape of it? And do you have a sense yet of what "more complicated to write" means for `gate` — is it just more keywords, or does it require you to explicitly name the defuzzification strategy?

## User

Well, yeah, no, the thing is you don't need to put together much of a thing to actually do a select statement or a switch statement, because the switch, you don't even need to be select. Your select statements don't even need to be categorically on the same variable or whatever; they just need to be things that can be mathematically compared to each other. The degree to which they're orthogonal to each other is kind of up for debate.

You'll never end up with both of them being 100% true if you have two variables that are both 100% true and all the rest of them are false; then it just does 50% one, 50% the other. A select statement's purpose isn't to do conditional branching, but it does conditional branching in a way that is specifically designed to be something that's fuzzy. It doesn't require much control. A gate, on the other hand, exclusively defuzzifies; it is objective; it is completely yes or no. Both gates and selects both of them have the ability to both of them essentially exist. Both of them are algebraically blended in with the rest of the programme, but they're done so in different ways.

## Claude

Okay, so the hierarchy is actually:

`select` — easier than a traditional if statement. Just a flat list of cases, no else required, no nesting. The exhaustiveness is handled by the softmax (everything gets some weight, so there's no "fell through" case). You just write the cases you care about.

`gate` — harder than a traditional if statement. More syntax, more explicit, because it's doing something genuinely more powerful/dangerous: forcing a crisp decision out of fuzzy space.

`if/else` — doesn't exist, because "if" is semantically ambiguous. In Sutra, you always have to declare which kind of conditional you mean. Are you blending (select) or are you committing to a hard branch (gate)?

The deeper point being: in other languages, `if` silently means different things in different contexts, and programmers don't think about that. Sutra makes the distinction syntactically mandatory — you can't write an ambiguous conditional because the ambiguous keyword doesn't exist.

So the design pressure is: `select` being effortless pulls people toward the fuzzy-native construct by default, and `gate` being more involved means you only write it when you've consciously decided "I need a crisp answer here." The language encodes the epistemics.

Does that match what you're going for? And do you want to start sketching what the actual `select` syntax looks like — the "row of selects" form you described?

## User

A gate needs to explicitly do something. I think I might want to do with a gate something that might really make it so that it's a bit of a pain. A gate has to call some kind of an external function or method or something.

## Claude

Okay, now I have a much cleaner picture. Let me reflect this back:

`select` — the cases don't even need to be on the same variable or the same type of thing. They just need to be things that exist in embedding space and can be compared via similarity. The runtime computes how close the current state is to each case, softmax-normalizes those similarities, and blends the outputs. If two cases are equally close, you get 50/50. If they're orthogonal, their weights are independent. The cases compete mathematically, not logically. No control flow in the traditional sense — it's a weighted superposition that happens to produce branching-like behavior.

`gate` — hard yes/no. Defuzzifies completely. But crucially, it's still algebraically integrated into the program — it's not like a traditional branch that breaks the computational graph. It produces a crisp scalar (0 or 1) that then participates in the algebra downstream.

The distinction I'm hearing is really about output type:

`select` → fuzzy output, stays in vector/embedding space

`gate` → crisp scalar, forces a decision

Both are woven into the program algebraically rather than as control flow jumps. Neither "jumps." They just produce different kinds of values.

Is that right? And does `gate` need an explicit condition written by the programmer, or does it defuzzify whatever state is currently active?

## User

Gate (i == cat, function.petCat(i))

This is an intentionally much uglier piece of code than it could be because it's trying to get you to use the gate only when you absolutely need it.

## Claude

Oh, that's elegant. So a `gate` isn't just syntactically heavier — it has a mandatory external call baked into it. You can't write a gate without explicitly invoking something outside the fuzzy algebra. That could be:

A defuzzification function

A threshold function

An external oracle or sensor

Any I/O or side effect

Which means `gate` naturally becomes the boundary between the fuzzy interior of your program and the crisp exterior world. It's not just "hard branching" — it's the interface point where fuzzy computation meets reality. You have to name what you're calling, which forces you to be explicit about why you're defuzzifying and what you're handing off to.

That also gives you a really clean semantic story:

`select` — pure fuzzy algebra, self-contained, no external dependencies

`gate` — crosses a boundary, requires an explicit external function, produces a crisp commitment

The pain of writing a `gate` isn't arbitrary friction — it's the language saying "you are about to leave the fuzzy world, and you have to justify that with a real function call." The verbosity is load-bearing.

Does the external function have to be typed in a specific way — like, does it have to return a crisp scalar, or can it return anything as long as it's external?

## User

That is just how regular function calls look. You don't always need to do them, but you can do them without function dot. Maybe I'll do it some other way.

The point is that basically every gate is breaking you out of what you're currently doing to do a function. A gate takes a boolean and a function as its arguments and then does the function if the boolean is satisfied, which is totally different from the way that is very different and awkwardly Lisp-like compared to a lot of the other stuff.

## Claude

Yes, exactly — and the ugliness is semantic, not just aesthetic. That syntax is doing several things at once:

The condition and the action are both mandatory and explicit in the same expression. You can't write a gate without committing to both "what I'm testing" and "what external thing I'm calling." There's no lazy version of it.

Compare:

```
select cat => pet(i)        // clean, fuzzy, easy
select dog => walk(i)
select bird => feed(i)

gate (i == cat, function.petCat(i))   // ugly, crisp, deliberate
```

The `select` version reads almost like data. The `gate` version reads like a declaration of intent — "I am explicitly checking this, and I am explicitly calling this, and I know what I'm doing."

The `function.` prefix is particularly interesting — is that intentional namespacing to signal "this is external/impure," or just how method calls look in Sutra generally? Because if it's the former, that's a really nice way to make the impurity visible at a glance without requiring a full effect system.

## User

My thought here is basically that it will defuzzify it for a gate.

## Claude

Right — and that Lisp-like awkwardness is exactly the point. It should feel like you're doing something structurally different from the rest of the language. The fact that it takes `(condition, function)` as explicit arguments rather than having a body block makes it feel like a function call itself rather than a control flow construct, which is honest — it is just calling a function conditionally.

The key semantic difference you're drawing is:

`select` has a body — it's a language construct with branches

`gate` has arguments — it's more like calling a higher-order function

Which means `gate` doesn't really have syntax sugar at all. It's just: boolean, function, done. The crispness of the semantics matches the crispness of the output.

The one thing worth thinking about: since the boolean argument to `gate` is coming from fuzzy space, does the language implicitly defuzzify it when it enters the `gate`, or does the programmer have to explicitly defuzzify before passing it in? Because `i == cat` in a fuzzy language isn't naturally a hard boolean — it's a similarity score. So either `gate` is secretly doing the defuzzification on the condition argument, or `==` in a gate context means something different than `==` elsewhere.

## User

Well, no, the defuzzification is not a side effect. Defuzzification only applies. There are no side effects in this language. Defuzzification is not a side effect. There are no side effects; it just passes it.

## Claude

That's clean. So `gate` is doing two things implicitly:

Defuzzifies the condition — `i == cat` produces a similarity score in fuzzy space, but `gate` applies a threshold to make it a hard boolean

Calls the function only if that boolean is satisfied

Which means the defuzzification is a side effect of using `gate`, not something the programmer has to think about. The ugliness of the syntax signals "this is a crisp commitment" without requiring the programmer to manually call a defuzzification function themselves.

That's actually a really coherent design. The syntax being Lisp-awkward is the warning label. The implicit defuzzification is the mechanism. You never accidentally defuzzify something because defuzzification only happens inside a `gate`, and `gate` is hard enough to write that you only reach for it deliberately.

One small thing worth pinning down eventually: what's the defuzzification threshold? Is it a language-level constant, a per-gate argument, or something inferred from the embedding space at compile time? That's probably one of those questions that can wait until the spec contradiction in your doc gets resolved — but it's the same question in a different form.

## User

Yeah, it does a pretty complicated thing, because it is intended to be an all-or-nothing event. Defusion is just multiplying the vector by a matrix 10 times or n times. It's not a it isn't even a control flow. All of these conditionals are not control flows.

## Claude

You're right, sorry — that was sloppy language on my part. There are no side effects because the function call is the explicit external action, not a side effect of the gate. The gate just:

Defuzzifies the condition to a hard boolean

Passes that boolean and the function along

The function call is the whole point — it's not sneaking anything in. The programmer declared it explicitly as an argument. Nothing hidden.

So `gate` is really just a defuzzification wrapper around an explicit function call. The defuzzification is part of the evaluation of the condition argument, not something happening to the world outside the expression. It's still pure in the functional sense — same inputs, same outputs, no hidden state.

That also makes `gate` feel more consistent with the rest of Sutra than I was initially framing it — it's not "breaking out" of the language's model, it's just the specific construct that converts fuzzy → crisp as part of its normal evaluation semantics.

## Claude

Right — because defuzzification is just iterated matrix multiplication converging toward a prototype. It's still pure algebra. `gate` doing it automatically is no different from any other mathematical operation in the language — it just happens to produce a value that's very close to 0 or 1 by the time it's done iterating.

So none of this — `select`, `gate`, nothing — is actually control flow in the traditional sense. They're all just different algebraic expressions that produce different shaped outputs:

`select` → weighted sum, stays distributed

`gate` → iterated matrix multiplication until convergence, produces a near-crisp scalar, then passes to the function

The program never "jumps." It just evaluates. The branching behavior emerges from the math rather than being imposed on it.

Which actually makes the whole conditional system feel very unified — `select` and `gate` aren't two different kinds of things, they're just two different algebraic patterns that happen to serve the roles that fuzzy and crisp branching serve in other languages. The distinction is in the output geometry, not in the control flow model.
