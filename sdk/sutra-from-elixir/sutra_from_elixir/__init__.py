"""Elixir → Sutra transpiler frontend (MVP).

Models on `sutra-from-ocaml` (the reference frontend). `lower(source)` turns
Elixir source into Sutra source. MVP scope: `defmodule` functions (inline and
block bodies), numeric literals, binary operators, `if/else` (→ defuzz blend),
calls.
"""
from .lower import lower

__all__ = ["lower"]
