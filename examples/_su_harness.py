"""Shared test-harness utilities for compiling .su programs.

Used by `_smoke_test.py`, `_king_queen_multi_substrate.py`,
`_king_queen_mlp_attractor.py`, and `_rotation_hashmap_test.py`.
The one-line purpose of this module: compile a .su file into a
runnable Python module, honoring source-level and project-level
substrate declarations.

Substrate precedence (highest wins), per user direction 2026-04-22:

1. **Explicit kwarg** to compile_to_module (Python-level override).
   Used by cross-substrate sweeps like _king_queen_multi_substrate.
2. **File-level `// @embedding: <model>` directive** in the .su
   source. Overrides atman.toml for one program.
3. **Project-level `[project.embedding]` in atman.toml** walked up
   from the .su file's directory. Project default.
4. **Hardcoded NumpyCodegen defaults** (nomic-embed-text, 768-dim)
   if none of the above declares anything.

Directive syntax (file-level, placed anywhere in the first 10 lines):

    // @embedding: <model-name>
    // @embedding: <model-name> dim=<N>

atman.toml schema (project-level; example in examples/atman.toml):

    [project.embedding]
    provider = "ollama"
    model    = "nomic-embed-text"
    dim      = 768
    mean_center = true

`main(embedding_space: string)` as a runtime-override at the .su
language level is deferred. This file implements the file-level
and project-level halves only.
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

from sutra_compiler.codegen import translate_module  # noqa: E402
from sutra_compiler.lexer import Lexer  # noqa: E402
from sutra_compiler.parser import Parser  # noqa: E402


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


def find_atman_toml(start_path: str) -> str | None:
    """Walk up from `start_path` looking for an `atman.toml` manifest.

    Walks up to a reasonable maximum depth (8 levels) to avoid
    accidentally reading a stray atman.toml from a parent directory
    unrelated to the target program.

    Returns the absolute path to atman.toml, or None if not found.
    """
    current = os.path.abspath(start_path)
    if os.path.isfile(current):
        current = os.path.dirname(current)
    for _ in range(8):
        candidate = os.path.join(current, "atman.toml")
        if os.path.isfile(candidate):
            return candidate
        parent = os.path.dirname(current)
        if parent == current:
            return None
        current = parent
    return None


def read_atman_embedding(path: str) -> tuple[str | None, int | None]:
    """Read (model, dim) from atman.toml's [project.embedding] section.

    Returns (None, None) if the section is missing, malformed, or the
    toml file can't be parsed. This is deliberately lenient: harness
    uses should fall back to other sources rather than fail outright
    if the manifest has an unrelated issue.
    """
    try:
        import tomllib  # Python 3.11+
    except ImportError:
        try:
            import tomli as tomllib  # type: ignore
        except ImportError:
            return None, None
    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)
    except Exception:
        return None, None
    emb = data.get("project", {}).get("embedding", {})
    if not isinstance(emb, dict):
        return None, None
    model = emb.get("model")
    dim = emb.get("dim")
    if not isinstance(model, str):
        model = None
    if not isinstance(dim, int):
        dim = None
    return model, dim


def compile_to_module(
    src_path: str,
    llm_model: str | None = None,
    runtime_dim: int | None = None,
) -> types.ModuleType:
    """Compile a .su file to a runnable Python module.

    Substrate precedence (highest wins):
      1. Explicit kwarg (`llm_model`, `runtime_dim`).
      2. `// @embedding: <model>` directive at the top of the source.
      3. `[project.embedding]` in the nearest `atman.toml` (walked up
         from the .su file's directory).
      4. NumpyCodegen defaults (nomic-embed-text, 768-dim).

    The precedence is implemented by resolving each layer in order and
    stopping as soon as a concrete value is found for each field.
    Different fields can come from different layers (e.g. model from
    the directive, dim from atman.toml).
    """
    with open(src_path, encoding="utf-8") as f:
        src = f.read()

    # Layer 2: file-level directive.
    directive_model, directive_dim = parse_embedding_directive(src)

    # Layer 3: project-level atman.toml.
    toml_model: str | None = None
    toml_dim: int | None = None
    toml_path = find_atman_toml(src_path)
    if toml_path is not None:
        toml_model, toml_dim = read_atman_embedding(toml_path)

    # Resolve each field in precedence order.
    if llm_model is None:
        llm_model = directive_model if directive_model is not None else toml_model
    if runtime_dim is None:
        # Dim resolution is slightly subtle: if the directive picks a
        # model but doesn't specify a dim, we should look up the dim
        # for THAT model (or use atman.toml's dim if atman.toml's
        # model is the one being used). This is already handled for
        # the directive case by parse_embedding_directive (which looks
        # up KNOWN_MODEL_DIMS). For atman.toml, the toml's dim is
        # authoritative when the toml's model is the one selected.
        if directive_dim is not None:
            runtime_dim = directive_dim
        elif directive_model is None and toml_dim is not None:
            # Using atman.toml's model; use atman.toml's dim too.
            runtime_dim = toml_dim
        # Else fall through — codegen default.

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
