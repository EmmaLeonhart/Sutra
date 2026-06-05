"""sutra-from-ocaml — transpile a functional core of OCaml into Sutra (.su).

Public surface mirrors `sutra-from-ts`: import `lower` and call it on a
source string.
"""

from .lower import lower

__all__ = ["lower"]
__version__ = "0.1.0"
