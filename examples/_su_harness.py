"""Shared test-harness utilities for compiling .su programs.

Used by `_smoke_test.py`, `_king_queen_multi_substrate.py`,
`_king_queen_mlp_attractor.py`, and `_rotation_hashmap_test.py`.
The one-line purpose of this module: compile a .su file into a
runnable Python module, honoring an optional `// @embedding`
directive at the top of the file that overrides the default
frozen-LLM substrate.

The directive syntax (per STATUS #1, user direction 2026-04-22):

    // @embedding: <model-name>
    // @embedding: <model-name> dim=<N>

Placed on any of the first ten lines of the .su file (so a program
with a license header or long doc comment can still declare). If
present, the test harness passes `llm_model=<model-name>` and,
optionally, `runtime_dim=<N>` to `NumpyCodegen`. If absent, the
codegen defaults apply (nomic-embed-text, 768-dim).

Known-model dim lookup lives in KNOWN_MODEL_DIMS; add new models
here as they become relevant. The `dim=<N>` override is for
unknown models or for testing a truncated-dim substrate.
"""
from __future__ import annotations

import os
import re
import sys
import types

# Make the compiler importable even when this harness is invoked
# from arbitrary cwd. `_su_harness.py` lives in `examples/`.
HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, ".."))
SDK_PATH = os.path.join(REPO_ROOT, "sdk", "sutra-compiler")
if SDK_PATH not in sys.path:
    sys.path.insert(0, SDK_PATH)

from sutra_compiler.codegen_numpy import translate_module  # noqa: E402
from sutra_compiler.lexer import Lexer  # noqa: E402
from sutra_compiler.parser import Parser  # noqa: E402


# Native dimension per embedding model, checked locally against
# Ollama on 2026-04-22. Add models here as they become relevant.
KNOWN_MODEL_DIMS = {
    "nomic-embed-text":  768,
    "mxbai-embed-large": 1024,
    "all-minilm":        384,
}


# Directive pattern matched against the first ten lines of the file:
#   // @embedding: <model>
# or
#   // @embedding: <model> dim=<N>
# Anchored to `//` + optional whitespace; tolerates extra whitespace.
_DIRECTIVE_RE = re.compile(
    r"^\s*//\s*@embedding\s*:\s*(?P<model>[\w\-\.]+)"
    r"(?:\s+dim\s*=\s*(?P<dim>\d+))?"
    r"\s*$"
)


def parse_embedding_directive(src: str) -> tuple[str | None, int | None]:
    """Return (model, dim) from the source's @embedding directive,
    or (None, None) if the directive is absent.

    Only scans the first 10 lines — the directive is meant to be near
    the top of the file. Silently ignores malformed directives so a
    typo doesn't break compilation.
    """
    for line in src.splitlines()[:10]:
        m = _DIRECTIVE_RE.match(line)
        if m is None:
            continue
        model = m.group("model")
        dim_str = m.group("dim")
        if dim_str is not None:
            return model, int(dim_str)
        # No explicit dim. Use the known-model dim, or None (codegen default).
        return model, KNOWN_MODEL_DIMS.get(model)
    return None, None


def compile_to_module(
    src_path: str,
    llm_model: str | None = None,
    runtime_dim: int | None = None,
) -> types.ModuleType:
    """Compile a .su file to a runnable Python module.

    If `llm_model` is explicitly passed, it overrides any directive in
    the source (useful for cross-substrate sweeps). Otherwise the
    directive in the source (if any) chooses the substrate. If neither
    is provided, NumpyCodegen defaults apply.

    `runtime_dim` follows the same precedence. If left None after
    merging, NumpyCodegen uses `DEFAULT_LLM_DIM = 768`.
    """
    with open(src_path, encoding="utf-8") as f:
        src = f.read()

    # Merge directive-derived config with caller-supplied overrides.
    # Caller args win; directive fills in whatever caller didn't pass.
    directive_model, directive_dim = parse_embedding_directive(src)
    if llm_model is None:
        llm_model = directive_model
    if runtime_dim is None:
        runtime_dim = directive_dim

    lexer = Lexer(src, file=src_path)
    tokens = lexer.tokenize()
    parser = Parser(tokens, file=src_path, diagnostics=lexer.diagnostics)
    module = parser.parse_module()

    kwargs = {}
    if llm_model is not None:
        kwargs["llm_model"] = llm_model
    if runtime_dim is not None:
        kwargs["runtime_dim"] = runtime_dim
    py_src = translate_module(module, **kwargs)

    mod = types.ModuleType(os.path.basename(src_path))
    mod.__file__ = f"<generated from {src_path}>"
    exec(compile(py_src, mod.__file__, "exec"), mod.__dict__)
    return mod
