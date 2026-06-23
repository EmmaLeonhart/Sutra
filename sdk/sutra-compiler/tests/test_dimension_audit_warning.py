"""Dimension-audit warning (CLAUDE.md "Subtler substrate breaches" #1).

A program that uses no codebook (no `basis_vector` / `embed`, no axon string-keys)
does not touch the LLM semantic subspace, so running it at an LLM-sized
`semantic_dim` pays for the dimension for nothing (matrices scale with dim^2). The
compiler warns loudly but still compiles. The warning fires ONLY when the codebook
is genuinely unused AND the dim is LLM-sized, so it never false-flags a program that
embeds strings or binds axon keys.
"""
from __future__ import annotations

import warnings

from sutra_compiler.codegen_pytorch import translate_module
from sutra_compiler.lexer import Lexer
from sutra_compiler.parser import Parser


def _warnings_for(src: str, dim: int) -> list[str]:
    lx = Lexer(src, file="t.su")
    ps = Parser(lx.tokenize(), file="t.su", diagnostics=lx.diagnostics)
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        translate_module(ps.parse_module(), llm_model="none", runtime_dim=dim)
        return [str(x.message) for x in w]


def test_codebook_free_large_dim_warns():
    msgs = _warnings_for("function int main() { return 3 + 4; }", 768)
    assert any("uses no codebook" in m for m in msgs), msgs


def test_codebook_free_small_dim_does_not_warn():
    # Below the LLM-sized threshold: an intentionally small dim is not flagged.
    assert _warnings_for("function int main() { return 3 + 4; }", 8) == []


def test_axon_key_program_does_not_warn():
    # Axon string-keys ARE embedded via the codebook, so the dim is justified.
    src = (
        'function int f() { Axon a; a.add("x", 5); return realvec(a.item("x")); }\n'
        'function int main() { return f(); }\n'
    )
    assert _warnings_for(src, 768) == []


def test_basis_vector_program_does_not_warn():
    src = 'function int main() { vector v = embed("cat"); return 0; }'
    assert _warnings_for(src, 768) == []
