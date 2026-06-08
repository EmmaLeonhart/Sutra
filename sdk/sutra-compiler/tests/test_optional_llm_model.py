"""Optional llm_model — no embedding model required by default.

Emma 2026-05-29 (AskUserQuestion: "Optional llm_model only"): a program
should need NO embedding model unless it actually embeds semantic content.
compile_su's llm_model defaults to "none"; the runtime raises a clear,
actionable error ONLY when `embed`/`embed_batch` is actually reached with
no model — never a bare ollama 404. Programs using only make_real /
matrices / arithmetic (the whole trainable-matrix corpus) run model-free.
"""
from __future__ import annotations

import unittest

from sutra_compiler.codegen_pytorch import translate_module as torch_translate
from sutra_compiler.lexer import Lexer
from sutra_compiler.parser import Parser

def _rv(_vsa, _vec):
    # Host-side terminal-boundary read of a number-vector's real axis
    # (the `real()` runtime method was removed — no scalar accessor). This
    # is the sanctioned external verification read, done by direct indexing.
    return float(_vec[_vsa.semantic_dim + _vsa.AXIS_REAL])


def _compile(src: str, **kw):
    lx = Lexer(src, file="<t>")
    ast = Parser(lx.tokenize(), file="<t>", diagnostics=lx.diagnostics).parse_module()
    assert not lx.diagnostics.has_errors(), list(lx.diagnostics)
    ns: dict = {}
    exec(torch_translate(ast, **kw), ns)
    return ns


class TestOptionalLLMModel(unittest.TestCase):
    def test_model_free_program_runs_with_llm_model_none(self):
        # make_real / arithmetic: no embed -> no model needed.
        ns = _compile(
            "function number f() { return make_real(2.0) + make_real(3.0); }\n"
            'function string main() { return "ok"; }\n',
            llm_model="none", runtime_dim=8,
        )
        self.assertEqual(round(float(_rv(ns["_VSA"], ns["f"]()))), 5)
        self.assertEqual(ns["_VSA"].llm_model, "none")

    def test_embed_program_raises_clear_error_without_model(self):
        # basis_vector needs an embedding; with llm_model='none' the
        # codebook prefetch raises a clear RuntimeError naming llm_model —
        # NOT an opaque ollama 404. (Prefetch fires at module exec.)
        with self.assertRaises(RuntimeError) as cm:
            _compile(
                'function vector g() { return basis_vector("cat"); }\n'
                'function string main() { return "ok"; }\n',
                llm_model="none", runtime_dim=8,
            )
        msg = str(cm.exception).lower()
        self.assertIn("llm_model", msg)
        self.assertIn("embed", msg)

    def test_compile_su_defaults_to_no_model(self):
        # The public compile_su API: llm_model is optional, defaults to
        # "none"; a model-free .su file compiles + runs without it.
        import os

        from sutra_compiler import compile_su

        repo = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..", "..")
        )
        digits = os.path.join(repo, "demos", "calc", "digits.su")
        if not os.path.isfile(digits):
            self.skipTest("demos/calc/digits.su not present")
        mod = compile_su(digits, runtime_dim=8, runtime_dtype="float64",
                         verbose=False)  # no llm_model arg
        self.assertEqual(mod._VSA.llm_model, "none")
        self.assertEqual(round(float(_rv(mod._VSA, mod.digit(1234.0, 100.0)))), 2)


if __name__ == "__main__":
    unittest.main()
