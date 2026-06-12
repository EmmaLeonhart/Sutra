"""Terminal/display boundary helper for the font demos.

The Sutra language has no scalar-readout accessor — `real()` was removed for
substrate purity (2026-06-07). A substrate function returns a number-VECTOR; the
host reading that final vector's real-axis value FOR DISPLAY (here: a glyph
pixel's brightness / a bound-similarity score) is the one external terminal
boundary, not in-language introspection. Mirrors the compiler CLI's own
`_decode_terminal_result` and demos/gui/_display.py.

Substrate code never calls this — it is host-side display assembly only.
"""
from __future__ import annotations


def read_real(vsa, v) -> float:
    """Read a number-vector's real-axis component to a host float, for display.

    `v` is a 1-D substrate tensor of length `vsa.dim`; the real axis lives at
    `vsa.semantic_dim + vsa.AXIS_REAL`. Output boundary, NOT a language feature.
    """
    return float(v[vsa.semantic_dim + vsa.AXIS_REAL])
