# sutra-from-ocaml

Transpile a functional core of [OCaml](https://ocaml.org) into
[Sutra](https://sutra.noldor.tech) (`.su`) source.

## Why OCaml first

Sutra is a *purely functional* language. The roadmap for source-language
frontends (see the repo roadmap) does the **functional languages first**,
because their expression-orientation, immutability, and algebraic data
types line up with Sutra's core instead of fighting it — unlike the
dynamic, mutation-heavy JavaScript surface that the TypeScript frontend
(`sutra-from-ts`) has to wrestle with. OCaml is first in that order:
ML-family syntax + algebraic data types + pattern matching are the
closest structural match to Sutra's axon/record model.

## Status: alpha (first frontend tick)

The lowering pass currently handles:

- Top-level `let name p1 p2 … = body` definitions with ≥ 1 parameter →
  Sutra `function` declarations. `let main () = …` (a `unit` parameter)
  → a zero-argument `function … main()`.
- Parameters: plain `a` (untyped → `int`) or typed `(x : int)`. Trailing
  return-type annotation (`… : int = body`) is read when present.
- Expression bodies: infix arithmetic (`+ - * /` and float `+. -. *. /.`),
  comparisons (`= <> < > <= >=` → `== != < > <= >=`), variable
  references, integer/float literals, function application (`f a b` →
  `f(a, b)`), and parenthesised expressions.

Everything else lowers to a `// UNSUPPORTED-*` comment so blocked
constructs are visible in the output. Type inference is not attempted
yet (OCaml is globally Hindley–Milner inferred); the MVP defaults
unannotated types to `int` and relies on annotations otherwise. The
agenda — `if/then/else`, `let … in`, `let rec`, tuples/records/variants,
`match … with` — is tracked in the repo work queue. (Flat tuple-`let`
destructure `let (a, b) = t in …` → `realvec(t.item("_0"))` substitution
and record-`let` destructure `let { x; y } = p in …` [punned + renamed `{ x = a }`]
→ `realvec(p.item("x"))` shipped 2026-06-18.)

## Use

```bash
# Write next to input with .su extension
ocaml2su path/to/file.ml            # -> path/to/file.su

# Override output path
ocaml2su input.ml -o out/custom.su

# Pipe into the Sutra compiler
ocaml2su input.ml -o /tmp/x.su && sutrac --emit /tmp/x.su
```

## License

Apache-2.0. See `LICENSE`.
