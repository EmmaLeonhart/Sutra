"""Test cycle_step -- Emma's glyph-cursor step, a real substrate-state RNN
(rewritten 2026-05-28, Option B).

New shape: `cycle_step(vector typed_onehot, scalar has_typed) -> vector`. The
glyph cursor is a 36-dim ONE-HOT held in a `recurring vector` slot that lives
ON THE SUBSTRATE across ticks (non-halting-loop.md). Each tick advances it by
one via a single matmul `next = P @ glyph` against the frozen 36x36
cyclic-permutation matrix P (built with `matrix_literal`). With has_typed=1.0,
a host-provided typed one-hot replaces the advance via the substrate weighted
sum.

This is the substrate-RNN the prior host-state-shuttle shape was blocked from
being (see planning/findings/2026-05-28-cycle-step-rewrite-blocked.md): the
recurring slot is a vector surviving across calls without any host `real()`
extraction feeding back between ticks.

These tests compile `cycle_step` IN ISOLATION (extracted from the generated
font.su) rather than the full font.su. The full file's glyph_pixel / bit_<C>
selects carry a large, PRE-EXISTING egglog-simplify cost (>300s) unrelated to
the cycle path, which renders via the separate font_bound_antipodal.su compile.
Isolating cycle_step keeps this test fast and focused on the RNN behavior.
"""
from __future__ import annotations

import pathlib
import re
import types

import pytest

torch = pytest.importorskip("torch", reason="cycle_step runs through real Sutra")

import sys

DEMO_FONT = pathlib.Path(__file__).resolve().parent
SDK = DEMO_FONT.parents[1] / "sdk" / "sutra-compiler"
if str(SDK) not in sys.path:
    sys.path.insert(0, str(SDK))

from sutra_compiler.codegen_pytorch import translate_module as torch_translate  # noqa: E402
from sutra_compiler.lexer import Lexer  # noqa: E402
from sutra_compiler.parser import Parser  # noqa: E402

CYCLE = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
N = len(CYCLE)


def _cycle_step_source() -> str:
    """Extract just the generated `cycle_step` function from font.su and wrap
    it in a minimal compilable module. Tests the REAL generated code (the
    36x36 matrix_literal permutation) without paying the full-font compile."""
    src = (DEMO_FONT / "font.su").read_text(encoding="utf-8")
    m = re.search(r"function vector cycle_step.*?\n\}", src, re.S)
    assert m, "cycle_step not found in font.su"
    return m.group(0) + '\nfunction string main() { return "ok"; }\n'


def _fresh_cycle():
    """Compile cycle_step into a fresh module (recurring slot reset to 'A')."""
    src = _cycle_step_source()
    lexer = Lexer(src, file="<cycle>")
    tokens = lexer.tokenize()
    module = Parser(tokens, file="<cycle>", diagnostics=lexer.diagnostics).parse_module()
    assert not lexer.diagnostics.has_errors(), list(lexer.diagnostics)
    py = torch_translate(module, runtime_dim=8, runtime_seed=42)
    ns: dict = {}
    exec(compile(py, "<cycle>", "exec"), ns)
    return ns


def _onehot(ch: str, vsa) -> torch.Tensor:
    v = torch.zeros(N, dtype=vsa.dtype, device=vsa.device)
    v[CYCLE.index(ch)] = 1.0
    return v


def _zeros(vsa) -> torch.Tensor:
    return torch.zeros(N, dtype=vsa.dtype, device=vsa.device)


def _decode(oh: torch.Tensor) -> str:
    return CYCLE[int(torch.argmax(oh))]


def test_advance_walks_full_cycle_with_both_wraps():
    """38 pure-advance ticks from the initial 'A' produce
    B C ... Z 0 ... 9 A B C — exercising every single-step advance, the
    Z->0 and 9->A wraps, and the full-loop return, all on the substrate."""
    ns = _fresh_cycle()
    vsa = ns["_VSA"]
    z = _zeros(vsa)
    seq = "".join(_decode(ns["cycle_step"](z, 0.0)) for _ in range(38))
    # First call advances the initial 'A' to 'B'.
    expected = "".join(CYCLE[(i + 1) % N] for i in range(38))
    assert seq == expected, f"advance seq: got {seq!r}, want {expected!r}"


def test_state_is_exact_one_hot_each_tick():
    """The recurring state stays a bit-exact one-hot across ticks — the
    signal-separation gap (CLAUDE.md 'Subtler substrate breaches' #3) is
    1.0 - 0.0 = 1.0: the active glyph is exactly 1.0, every other exactly 0.0,
    so the argmax decode never ambiguous and no drift accumulates."""
    ns = _fresh_cycle()
    vsa = ns["_VSA"]
    z = _zeros(vsa)
    for _ in range(40):
        oh = ns["cycle_step"](z, 0.0)
        active = float(oh.max())
        others = float((oh - oh.max()).abs().sum())  # sum of |non-max|
        assert abs(active - 1.0) < 1e-6, f"active weight {active}, want 1.0"
        assert abs(float(oh.sum()) - 1.0) < 1e-6, f"one-hot sum {float(oh.sum())}"
        # gap = active(1.0) - max(others)(0.0); all non-active are 0.
        nonactive_max = float(oh.masked_fill(oh == oh.max(), -1.0).max())
        assert nonactive_max < 1e-6, f"non-active max {nonactive_max}, want ~0"


def test_typed_override_replaces_advance():
    """has_typed=1.0 -> the host-provided typed one-hot wins over the advance,
    and becomes the new state (so the next advance continues from it)."""
    ns = _fresh_cycle()
    vsa = ns["_VSA"]
    q = _onehot("Q", vsa)
    got = ns["cycle_step"](q, 1.0)
    assert _decode(got) == "Q", f"typed override: got {_decode(got)}, want Q"
    # State is now Q; a pure advance goes Q -> R.
    nxt = ns["cycle_step"](_zeros(vsa), 0.0)
    assert _decode(nxt) == "R", f"advance after typed Q: got {_decode(nxt)}, want R"


def test_has_typed_zero_ignores_typed_onehot():
    """has_typed=0.0 -> the typed one-hot is ignored (gated out by the
    substrate weighted sum); the advance passes through. From initial 'A'
    that means 'B' regardless of the typed input."""
    ns = _fresh_cycle()
    vsa = ns["_VSA"]
    q = _onehot("Q", vsa)
    got = ns["cycle_step"](q, 0.0)
    assert _decode(got) == "B", f"has_typed=0 with typed=Q: got {_decode(got)}, want B"


if __name__ == "__main__":
    import unittest

    # Allow `python test_font_cycle.py` to run the plain-function tests.
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            print(f"{name} ...", end=" ")
            fn()
            print("ok")
