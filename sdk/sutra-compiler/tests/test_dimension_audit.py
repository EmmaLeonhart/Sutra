"""Regression guard for the dimension-audit sweep's detection logic.

`experiments/dimension_audit_sweep.py` flags `.su` programs that use NO codebook
(no basis_vector/embed, no axon string-keys) — they pay an LLM-sized dim² for
nothing. This pins that `_uses_codebook` matches the SAME signal the compile-time
dimension warning uses (`codegen_pytorch`: all of collect_basis_vector_strings +
the two collect_axon_keys sets empty ⇒ codebook unused), so the audit can't
silently drift from the warning it promotes.
"""
from __future__ import annotations

import pathlib
import sys

from sutra_compiler.lexer import Lexer
from sutra_compiler.parser import Parser

_ROOT = pathlib.Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from experiments.dimension_audit_sweep import _uses_codebook  # noqa: E402


def _mod(src: str):
    lx = Lexer(src, file="<dim>")
    return Parser(lx.tokenize(), file="<dim>", diagnostics=lx.diagnostics).parse_module()


def test_basis_vector_program_uses_codebook():
    src = 'function vector f() { return embed("dog"); }'
    assert _uses_codebook(_mod(src)) is True


def test_embed_program_uses_codebook():
    src = 'function vector f() { return embed("dog"); }'
    assert _uses_codebook(_mod(src)) is True


def test_axon_string_key_program_uses_codebook():
    # An axon string-key binds into the LLM-rotated space → codebook used.
    src = ('function vector f() {\n'
           '    Axon a;\n'
           '    a.add("k", make_real(1.0));\n'
           '    return a;\n'
           '}\n')
    assert _uses_codebook(_mod(src)) is True


def test_make_real_only_program_is_codebook_free():
    # Pure synthetic-axis arithmetic, no codebook → dimension-reducible.
    src = 'function vector f() { return make_real(5.0); }'
    assert _uses_codebook(_mod(src)) is False
