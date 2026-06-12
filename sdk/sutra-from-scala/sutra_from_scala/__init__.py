"""Scala → Sutra transpiler frontend (MVP).

Models on `sutra-from-ocaml` (the reference frontend). `lower(source)` turns Scala
source into Sutra source. MVP scope: top-level `def` functions, Int/Double/Boolean
params + return types, integer/float literals, infix arithmetic/comparison, and calls.
"""
from .lower import lower

__all__ = ["lower"]
