"""Haskell → Sutra transpiler frontend (MVP).

Models on `sutra-from-ocaml` (the reference frontend). `lower(source)` turns
Haskell source into Sutra source. MVP scope: top-level equations with
signatures, curried application, infix operators, if/then/else (→ defuzz
blend). Laziness is not modeled (out of MVP scope).
"""
from .lower import lower

__all__ = ["lower"]
