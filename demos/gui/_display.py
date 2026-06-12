"""Terminal/display boundary helper for the GUI demos.

The Sutra language has no scalar-readout accessor — `real()` was removed for
substrate purity (2026-06-07). A substrate function returns a number-VECTOR; the
host reading that final vector's real-axis value FOR DISPLAY is the one external
terminal boundary (the same as printing a returned value in any runtime), not
in-language introspection. This mirrors the compiler CLI's own
`_decode_terminal_result` (sdk/sutra-compiler/sutra_compiler/__main__.py).

Substrate code never calls this — it is host-side display assembly only.
"""
from __future__ import annotations


def read_real(vsa, v) -> float:
    """Read a number-vector's real-axis component to a host float, for display.

    `v` is a 1-D substrate tensor of length `vsa.dim`; the real axis lives at
    `vsa.semantic_dim + vsa.AXIS_REAL`. This is the output boundary, NOT a
    language feature.
    """
    return float(v[vsa.semantic_dim + vsa.AXIS_REAL])
