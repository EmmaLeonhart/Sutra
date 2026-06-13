"""F# → Sutra transpiler frontend (MVP).

Models on `sutra-from-ocaml` (the reference frontend; F# is its close cousin).
`lower(source)` turns F# source into Sutra source. MVP scope: top-level `let`
functions, application spines, infix operators, if/then/else (→ defuzz blend).
The grammar DLL is built locally by `build_grammar.py` (no PyPI wheel exists).
"""
from .lower import grammar_available, lower

__all__ = ["lower", "grammar_available"]
