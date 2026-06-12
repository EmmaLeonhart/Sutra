"""Rust → Sutra transpiler frontend (MVP).

Models on `sutra-from-ocaml` (the reference frontend). `lower(source)` turns
Rust source into Sutra source. MVP scope: `fn` items with typed params, `let`
bindings + tail expression, binary operators, if/else (→ defuzz blend), calls.
"""
from .lower import lower

__all__ = ["lower"]
