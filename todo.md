# S2 TODO

## Pending Decisions

- Decide on anonymous functions. Leaning toward `lambda` keyword. Need to pick exact form.
- Rework function declaration details — modifiers, full signature shape, how hidden/internal forms relate to surface syntax.
- Expression-versus-statement bias.
- Whether S2 has explicit namespaces or just files plus symbols.
- How primitive substrate operations read in source.
- Declaration syntax for implicit conversions.
- Whether there is a lightweight role-annotation system for semantic roles.
- Return annotation syntax (currently return type goes before name, C#-style).

## Recently Decided (2026-04-08)

- Function declarations use C# signature shape: `function vector Add(vector a, vector b) { ... }`
- `function.` prefix is for calling (disambiguation), not declaration
- Full internal form: `function public static scalar operator +(scalar a, scalar b) { ... }`
- `if (cat)` is a compilation error — classes don't exist at runtime
- Truthiness is geometric — euclidean distance from true/false, accessed via unsafe cast only
- Operators support overloading
- Implicit casts allowed but must be explicitly defined
- `fuzzy` to `bool` cast performs `defuzzy`
- Class system is user-defined, not runtime-special
