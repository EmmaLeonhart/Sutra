# Compile-only-with-embedding-access; precision = embedding precision; currency stdlib

_Excerpt from the original `chats/kolmogorov-arnold-networks-for-tensor-operations.md` (lines 340-486). Split into topic-scoped chunks for triage — the original was too large to triage in a single pass._

---

## User

Yeah, the way I was actually doing it is a bit different. The embedding isn't considered to be external data. You can only compile it when you have access to the embedding space, because it's compiled to an embedding space. The variable that I meant here is essentially the actual cat thing, which could be an input for your programme, because your entire programme is just figuring out if a word is cat or at least is close enough to cat that this thing likes it.

## Claude

Oh right, so the flow is actually:

The embedding space is a compile time constant — it's baked in when you compile, like how a target architecture is baked in. You're not embedding at runtime, you're compiling against an embedding space the same way you compile against an instruction set.

So `"cat"` gets embedded at compile time into a fixed vector — that's just part of compilation. And then `is_cat_function` is a precomputed vector in that space, fully known at compile time.The actual variable — the thing that's unknown — is the input to the program. Like:

```
fn is_cat(word: Word) -> Bool {
    word == "cat"
}
```

Where `word` is what flows through at runtime as a vector, and `is_cat_function` is a fixed compiled vector, and the whole program is just:

```
dot(word_vector, is_cat_function) > threshold
```

Which is a single vector operation. The input is the only thing that's runtime. Everything else collapsed at compile time because the embedding space was known.

So the TOML config probably needs an embedding space setting alongside the precision setting:

toml

```
[compilation]
embedding_space = "nomic-embed-text-v1"
approximation_precision = 1e-6
```

And that's what "compiling to an embedding space" means concretely — it determines what all your string literals, type names, and semantic constants resolve to at compile time.

## User

Basically, your precision that you'd be having would be essentially the amount of precision you want for the embedding states that you're using, and practically, stuff like: are you doing it to CUDA, are you doing it to whatever PyTorch settings?

## Claude

Right, so the TOML settings are really about the backend compilation target rather than abstract mathematical precision. More like:

toml

```
[backend]
target = "cuda"  # or "cpu", "metal", "tpu"
dtype = "float16"  # or "float32", "bfloat16"
embedding_space = "nomic-embed-text-v1"

[pytorch]
compile = true  # torch.compile
mixed_precision = true
```

Because in practice "precision" in this context means float16 vs float32 vs bfloat16 — which is exactly the tradeoff ML practitioners already make consciously. bfloat16 is popular for training because it preserves the exponent range even though it has less mantissa precision. float16 is faster on certain hardware. float32 is when you need the extra precision.

And those choices are already deeply hardware-dependent — float16 is dramatically faster on CUDA tensor cores specifically, but the speedup is much smaller on CPU. So the backend target and the dtype are coupled decisions.

The interesting thing is that Sutra makes this a project-level architectural decision rather than something you sprinkle through your code with `torch.float16` casts and `autocast()` context managers everywhere. In PyTorch that precision management leaks all over your codebase. In Sutra it's one setting and the compiler handles the rest.

Which is again a cleaner story than Julia or F# — neither of them have any concept of "compile my math to this dtype on this GPU backend."

## User

Okay, I guess that's cool. I'm guessing that, with F#, it's kind of hard to just make up your own currency to do stuff with. Whereas in Sutra it's extremely easy because of the way the ontology is structured. For the most part, you don't.

This is the best thing. This is the way to say it in F#. In F#, you make your own class, and you have to implement the operators for everything. You have to implement the operators on everything. In Sutra, every single thing has operators implemented by default, and you get to choose.

The way it works is that the top class is tensor, and then you have vector and matrix. That's what's called super matrix, matrix, whatever that thing is. Everything is a tensor. As far as vectors go, you have your immediate ontological, synthetic, and semantic vectors, and then, for practical purposes, you have float. You have number, and anything that inherits from number has all of the operations set up. In practise, I think Lenny will be inheriting from int. I think Currency will be inheriting from int, with, like, a.

I don't know if it's actually possible in C# to disable an operation in an inherited class as opposed to overriding it. Essentially, most classes that you use that would represent something like a person or something have their operators disabled so that you don't accidentally add fox to cat and then result in some weirdness.

## Claude

Right, so the hierarchy is doing a lot of work here:

```
Tensor
├── Matrix
└── Vector
    ├── Semantic (embedding space vectors)
    ├── Synthetic (constructed vectors)
    └── Immediate (literal vectors)
    
Number (extends Vector conceptually)
├── Float
├── Int
│   ├── Currency
│   │   ├── Dollar
│   │   ├── Euro
│   │   └── ...
│   └── ...
└── ...

Entity (operators disabled by default)
├── Person
├── Cat
└── ...
```

The key insight is that operators being on by default for numbers, off by default for entities is the right default because it matches what things mean. You almost never want to add two People. You almost always want to add two Dollars.

On the C# question — you can't truly disable an inherited operator, but you can override it to throw a compile-time or runtime error. The cleaner Sutra-native approach would probably be that `Entity` simply doesn't inherit from anything that has operators defined, so there's nothing to disable. The operators just genuinely don't exist on that branch of the hierarchy.

And the F# contrast is sharp here — in F# you'd define `Dollar` as a record or struct and then manually implement `+`, `-`, comparison, everything. It's maybe 20-30 lines of boilerplate per currency. In Sutra, `Dollar extends Int` and you're done. All arithmetic just works, and the type safety comes free because `Dollar + Euro` is a type error without any extra work.

## User

I feel like probably what I would do is I would implement what I would do to just make it easier. The standard library will have a currency class, which basically gives you a bunch of basic resources for it, and everything that inherits from it has the operators work for it. Currency classes have the characteristic that you cannot add a currency class to another currency class. I think there probably could be some level of mixing; you can't add one currency to another currency. You have to do the matrix model; you'd have to do a conversion or something.

## Claude

Right, so Currency as a base class gives you:

All arithmetic operators work within the same currency — `Dollar + Dollar` is fine

Cross-currency arithmetic is a type error by default — `Dollar + Euro` doesn't compile

To mix currencies you have to go through an explicit conversion or exchange rate operation

Which is actually the correct financial model. In real quant finance you never just add dollars to euros — you always have an exchange rate matrix involved. So the type system is encoding actual financial semantics, not just arbitrary restrictions.

The exchange rate operation would naturally be a matrix in Sutra's model anyway:

```
exchange: ExchangeMatrix<Dollar, Euro> -> Dollar -> Euro
```

Which is literally just a scalar multiply — one entry matrix. But the type signature forces you to be explicit that you're doing a currency conversion, which is exactly what a financial auditor would want to see.

And you could extend this to portfolios naturally:

```
Portfolio<Dollar> + Portfolio<Dollar>  // fine
Portfolio<Dollar> + Portfolio<Euro>    // type error
normalize(Portfolio<Dollar>, Portfolio<Euro>, ExchangeMatrix)  // explicit, fine
```

The nice thing is this isn't special casing — Currency just defines `+` to require matching type parameters, which is a normal generic constraint. Everything else falls out from the tensor hierarchy as normal.

So the standard library story is: Currency gives you the financial semantics, Number gives you the math, Tensor gives you the operations, and you pick where in that hierarchy your domain concept lives.

