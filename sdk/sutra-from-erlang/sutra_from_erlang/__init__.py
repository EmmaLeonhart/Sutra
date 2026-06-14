"""Erlang → Sutra transpiler frontend (MVP).

Models on `sutra-from-ocaml` / `sutra-from-elixir` (Elixir is on the BEAM but
Erlang's own syntax/grammar is separate). `lower(source)` turns Erlang source
into Sutra source. MVP scope: `fun_decl` function clauses (multi-clause heads
with literal/var patterns + `when` guards → dispatch blend), binary ops, calls,
`if`/`case` → defuzz blend, single-clause `if`-based tail recursion → `while_loop`
and foldable non-tail recursion → CPS accumulator. The grammar DLL is built
locally by `build_grammar.py` (no PyPI wheel exists).
"""
from .lower import grammar_available, lower

__all__ = ["lower", "grammar_available"]
