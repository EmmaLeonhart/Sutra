# Formal Sutra grammar — moved

The canonical grammar has moved. Use:

- [`24-grammar.ebnf`](24-grammar.ebnf) — the formal ISO 14977 EBNF, canonical.
- [`24-grammar.md`](24-grammar.md) — prose wrapper, version policy, diagnostic-code index.

When this file's ancestors disagreed with the reference parser, the parser won. That disagreement is resolved by deferring to `24-grammar.ebnf`, which is regenerated from the parser's current state.

This stub exists so that links to `planning/sutra-spec/grammar.md` (notably from `queue.md` and `language-paper/paper.md`) keep working. Update those pointers opportunistically.
