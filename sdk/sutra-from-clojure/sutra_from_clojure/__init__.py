"""Clojure → Sutra transpiler frontend (MVP).

Models on `sutra-from-ocaml` (the reference frontend). `lower(source)` turns
Clojure source into Sutra source. MVP scope: `defn` functions, n-ary operator
forms, `if` (→ defuzz blend), calls. The grammar DLL is built locally by
`build_grammar.py` (no PyPI wheel exists).
"""
from .lower import grammar_available, lower

__all__ = ["lower", "grammar_available"]
