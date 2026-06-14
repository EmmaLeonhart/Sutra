"""Sutra → thrml (Extropic) compile target — ADDITIVE, experimental.

A SECOND, opt-in backend selected by `--emit-thrml` (queue.md approach G). It
lowers a validated Sutra subset to a thrml/JAX **energy-based-sampling** program:
values → spin/categorical registers, operations → factors, results recovered by
sampling (+ verify / ground-state decode). The canonical PyTorch backend
(`codegen_pytorch.py`) and the `--emit`/`--run` path are UNTOUCHED by this file —
this is purely additive (non-destructive constraint, queue.md §thrml).

The validated op→factor mappings this backend draws on are measured in
`planning/open-questions/2026-06-13-sutra-to-thrml-mapping.md` and the runnable
demos under `experiments/thrml/` (bind = 3-body factor, AND = derived gadget,
adder = sample-and-verify, etc.).

Status: **G.0 — the additive entry point is wired** (`--emit-thrml` dispatches
here, the PyTorch path is unaffected). **G.1 — the op→factor lowering — is the
next step.** Until a construct is supported, `translate_thrml` raises
`ThrmlCodegenNotSupported` with a precise message so nothing mislowers silently
(the integrity rule: surface the gap, never fake a result).
"""
from __future__ import annotations


class ThrmlCodegenNotSupported(Exception):
    """Raised for any Sutra construct the thrml backend cannot yet lower. Carries
    a precise, user-facing reason; `__main__._emit_thrml` prints it as a
    `thrml-codegen:` diagnostic and exits non-zero (no silent mislowering)."""


def translate_thrml(module) -> str:
    """Lower a parsed Sutra `module` to a thrml/JAX program string.

    G.0: the entry point exists and is wired additively; the lowering itself is
    G.1 (see queue.md). Raising here — rather than emitting a half-correct
    program — keeps the substrate-honesty rule: surface the gap explicitly.
    """
    raise ThrmlCodegenNotSupported(
        "lowering not yet implemented (approach G.1). The additive --emit-thrml "
        "entry point is wired and the PyTorch backend is untouched; the next step "
        "is the op->factor lowering for the validated subset (bind / AND / "
        "sample-and-verify). See planning/open-questions/"
        "2026-06-13-sutra-to-thrml-mapping.md and experiments/thrml/."
    )
