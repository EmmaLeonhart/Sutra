# Python vs. dedicated languages for hyperdimensional computing

*Extracted from Claude.ai chat.*

## User

Why do people insist on using Python libraries for hyperdimensional computing when it really at this point should have its own language?

## Claude

This is a real friction point, and the frustration is justified. The short answer is institutional inertia + the ML ecosystem gravity well, but let's actually unpack why that's insufficient as a defense.

Why people stay in Python

The honest reason is that HDC research is still primarily done by ML researchers, not PL researchers. Their workflow is: hypothesis → numpy/torch implementation → paper. A Python library gets you from idea to publishable result in days. The language question never comes up because they're not building systems, they're building experiments.

There's also the data gravity problem — your vectors live next to your datasets, your training pipelines, your visualization tools. Leaving Python means crossing a FFI boundary every time you want to touch any of that.

Why that's actually wrong for HDC specifically

HDC has a fundamentally different computational model than tensor ML. The operations — binding, bundling, permutation, superposition — are algebraic, not differentiable in the way backprop cares about. There's no gradient tape. The "program" is the vector arithmetic, not the weight updates.

Python libraries end up being awkward because they're pretending HDC is just another tensor operation, when it's actually closer to symbolic computation over a continuous algebra. You get things like:

No type-level distinction between a hypervector representing a concept vs. one representing a binding result

Bundling is just addition, binding is just elementwise multiply — no semantic enforcement

No native notion of "this vector is a query" vs. "this vector is a memory"

Cleanup memory lookup is an afterthought, not a first-class operation

A proper HDC language would have bundling, binding, and similarity as syntactic primitives — not library calls. The type system would track whether you're in holographic space or not. Cleanup would be part of the semantics.

The deeper issue

HDC is essentially hyperdimensional programming — you're writing programs where the substrate is a high-dimensional algebra over continuous vectors. That's a computational paradigm, not a library concern. Treating it as a library is like treating Prolog as a Python library — you can do it, but you've fundamentally misunderstood what you're working with.

The reason nobody's built the language yet is that the people who understand HDC deeply enough to spec a language are almost all ML researchers who don't think in PL terms, and the PL people who could build it haven't been exposed to HDC as a paradigm worth taking seriously.

Which is, of course, exactly the gap Sutra is sitting in — except you came at it from the vector-space-as-computation direction rather than the HDC-as-brain-inspired direction, which might actually be the more defensible foundation for a language.

## User

I have an idea to make it a bit more accessible in python while still being consistent though, but not sure if it will work:

I think something like this

```
<!DOCTYPE html>
<html>
<body>

<?php
ECHO 'Hello World!<br>';
echo 'Hello World!<br>';
?>

</body>
</html>

for embedding Sutra code in a python program might be somewhat useful. Although idk how it would work in runtime. With a pypi library, but it would intentionally be rather segregated. idk of this means no FFI
```

## Claude

The PHP-in-HTML analogy is actually pretty sharp — PHP works because the host language (HTML) is declarative and static, so the embedded dynamic layer has a clear demarcation. The `<?php ?>` boundary means something semantically, not just syntactically.

For Sutra-in-Python, the equivalent would be something like:

python

```
import sutra

result = sutra.run("""
  let meaning = bind(king, subtract(man, woman))
  query(meaning, threshold=0.8)
""")

print(result)  # back in Python land
```

The key question is: what crosses the boundary? In PHP/HTML, it's strings going into the output buffer. In your case, it would be vectors — Python hands numpy arrays or lists in, Sutra hands vectors back. That's actually a clean boundary because vectors are just arrays of floats. No complex object marshaling needed.

Why this might work well

The segregation is the feature, not a limitation. Python handles I/O, data loading, training pipelines, visualization. Sutra handles the hyperdimensional computation. You're not fighting the ML ecosystem, you're sitting above it with a clean interface layer.

The runtime question

You basically have two options: interpret the Sutra block at runtime (slow but easy to prototype, good for a PyPI library), or compile it to a native extension at import time (like Cython or cffi does). The compiled path would let Sutra do eigendecomposition and graph traversal at full speed while Python just sees a function call.

The FFI question

This is an FFI — just one you control the shape of. The boundary is narrow enough (arrays in, arrays out) that it wouldn't feel like FFI to the user. It would feel like calling any other numerical library.

The real risk is that people start using the Python embedding as a crutch and never engage with standalone Sutra. But that might be fine as a wedge — get adoption via the library, let people discover they want the full language.

## User

What what is FFI?

## Claude

Foreign Function Interface — it's the mechanism that lets code written in one language call code written in another.

The classic example is Python calling a C library. When you do `import numpy`, you're using FFI under the hood — numpy's performance-critical parts are compiled C, and Python has a protocol for crossing that boundary, passing data back and forth, and managing memory safely between the two runtimes.

The reason it comes up in your context is that if Sutra is compiled (Rust or native code) and Python wants to call it, something has to manage that handoff. Who owns the memory? How do types translate? What happens if Sutra raises an error — does Python see it?

In practice, for your use case, tools like PyO3 (Rust → Python bindings) handle most of the ugly parts. You write Rust, annotate it with a macro, and Python sees it as a normal module. The vectors crossing the boundary are just numpy arrays, which PyO3 knows how to handle natively. So the FFI is real but mostly invisible to anyone using the library.

## User

Basically the idea is that it is actively keeping you writing sutra code, but you are not using a .su file. The way I envision it is something like this

def greet(name: str) -> str:
    // Hello world — the minimal Sutra program.
//
// Traditional Hello World is IO-heavy: `print("Hello, world")`. Sutra
// is a purely functional vector-space language — there is no print,
// no IO primitive, no side effect a function body can invoke. Every
// computation is a deterministic vector-to-vector map. The only
// escape from the pure region is the final name lookup at the edge,
// which is the thin boundary where values leave the language the way
// Haskell programs surface results from an otherwise pure body.
//
// This is also the smallest demonstration that the compiler + runtime
// are real: source -> matrix ops -> named output.
// The greeting, as a vector in the space.
vector greeting = basis_vector("hello_world");
// A small codebook of candidate phrases.
vector v_hello    = basis_vector("hello_world");
vector v_goodbye  = basis_vector("goodbye");
vector v_question = basis_vector("are_you_there");
map<vector, string> PHRASE_NAME = {
    v_hello:    "hello world",
    v_goodbye:  "goodbye",
    v_question: "are you there"
};
// `say` is the whole program: identify `greeting` against the codebook
// by cosine similarity and return its name. No control flow, no IO
// inside the language — the name lookup at the end is the single
// bridge back to the host string world.
function string say() {
    vector winner = argmax_cosine(greeting, [v_hello, v_goodbye, v_question]);
    return PHRASE_NAME[winner];
}
// Entry point. `python -m sutra_compiler --run examples/hello_world.su`
// (and the IDE's gutter play button) invoke `main()` and print its
// return value.
function string main() {
    return say();
}

Not quite exact but basically since it is functional your function is entirely in Sutra but is in the same file. idk how IDEs and such will work but this is the idea. The big thing is that you just cannot do regular imperative stuff in Sutra

## Claude

Oh this is interesting — so the Python function signature is essentially the type contract at the boundary, and everything inside the function body is Sutra. Python declares what goes in and what comes out, Sutra handles the computation. The def line is the FFI.

That's actually a really elegant model because:

The Python type annotations (`str -> str`) give you the bridge types automatically — the compiler knows it needs to marshal a Python string in and a Python string out

The IDE sees a valid Python function, so syntax highlighting and autocomplete don't completely break

You stay in one file, one mental context — no context switching to a `.su` file

The constraint you mentioned is the key design decision: you just cannot do imperative stuff inside the Sutra block. That's not a limitation, that's the enforcer. If someone tries to write a for loop or mutate state inside that block, the compiler rejects it. The function boundary is the purity guarantee.

The open questions I'd think through:

How does the parser know where Sutra starts? With PHP you have `<?php`. You'd need either a decorator (`@sutra`) on the function, or a special comment marker, or the compiler just treats any function body that uses Sutra syntax as a Sutra block.

A decorator feels most Pythonic:

python

```
@sutra
def greet(name: str) -> str:
    vector v_name = bind(NAME, encode(name))
    ...
```

What does the Python runtime actually execute? The `.py` file can't run as-is — Python's parser would choke on `vector greeting = ...`. So either the library includes an import hook that preprocesses the file before Python sees it, or you need a compilation step. The import hook approach (`import sutra` installs a hook that intercepts `.py` files with `@sutra` decorated functions) is the most seamless user experience.

IDE support is the hard part honestly. You'd want a language server that understands both layers simultaneously — Python outside, Sutra inside. That's non-trivial but VSCode's embedded language support (the same mechanism that handles CSS-in-JS) is designed for exactly this pattern.
