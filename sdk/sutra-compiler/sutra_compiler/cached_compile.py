"""Disk-cached convenience wrapper around the lex -> parse -> translate -> exec dance.

`codegen_pytorch.translate_module` is deterministic for a fixed
(.su content, codegen source, lowering kwargs) tuple, but on big .su
files it is slow -- e.g. Yantra's `apps/font/font.su` (36 letter
functions x 25-way `select` each, ~25k AST tokens) takes ~410 s on
a typical CPU machine, of which ~297 s is `translate_module` itself.

`compile_su` memoizes the emitted Python source on disk so subsequent
calls skip the codegen pass entirely (~3 s end-to-end vs ~410 s).

Usage:

    from sutra_compiler import compile_su

    mod = compile_su(
        "apps/font/font.su",
        llm_model="nomic-embed-text",
        runtime_dim=768,
        runtime_dtype="float64",
    )
    glyph = mod.glyph_pixel(1.0, 0.0, 65.0)
    vsa = mod._VSA

Returns a `types.ModuleType` populated with the compiled functions and
the `_VSA` runtime, exactly as the idiomatic `lex -> parse -> translate
-> exec` produces. Each call returns an independent module so two
callers compiling the same .su don't share state.

The cache filename is

    <cache_dir>/.<src_stem>.compiled-sutra<ver>-<hash16>.py

where `<cache_dir>` defaults to the .su's parent directory. The hash
covers EVERYTHING that could change the codegen output:

  - .su file content
  - sutra_compiler/codegen_pytorch.py source
  - sutra_compiler/codegen_base.py source
  - (llm_model, runtime_dim, runtime_dtype) tuple

so a Sutra-side codegen change invalidates every consumer's cache and
the next call regenerates. Atomic write (tmp + rename) so Ctrl-C
mid-codegen never leaves a half-written cache.

Substrate purity is unaffected -- the cached output IS the same Python
the codegen emits today. The cache memoizes a pure function of its
inputs; nothing changes about what runs on the substrate.
"""
from __future__ import annotations

import hashlib
import os
import pathlib
import sys
import tempfile
import types
from typing import Optional, Union

from . import __version__


# Source files whose content participates in the codegen output. If any
# of these change, every cache key changes -> every cache invalidates.
# Keep this list MINIMAL: only the files whose source text directly
# shapes the emitted Python.
_CODEGEN_SOURCE_FILES = ("codegen_pytorch.py", "codegen_base.py")


def _codegen_source_hash() -> str:
    """SHA-256 of the codegen source files, contributing to the cache key.

    Concatenates `<name>\\0<content>\\0` for each file so reordering or
    renaming a file produces a different hash.
    """
    h = hashlib.sha256()
    pkg_dir = pathlib.Path(__file__).resolve().parent
    for name in _CODEGEN_SOURCE_FILES:
        h.update(name.encode("utf-8"))
        h.update(b"\0")
        h.update((pkg_dir / name).read_bytes())
        h.update(b"\0")
    return h.hexdigest()


def _cache_key(
    src: str, *, llm_model: str, runtime_dim: int, runtime_dtype: str,
) -> str:
    """16-char hex digest covering everything that affects codegen output."""
    h = hashlib.sha256()
    h.update(b"SU\0")
    h.update(src.encode("utf-8"))
    h.update(b"\0CODEGEN\0")
    h.update(_codegen_source_hash().encode("utf-8"))
    h.update(b"\0KWARGS\0")
    h.update(f"{llm_model}|{runtime_dim}|{runtime_dtype}".encode("utf-8"))
    return h.hexdigest()[:16]


def compile_su(
    src_path: Union[str, pathlib.Path],
    *,
    llm_model: str = "none",
    runtime_dim: int,
    runtime_dtype: str = "float32",
    cache_dir: Optional[Union[str, pathlib.Path]] = None,
    verbose: bool = True,
) -> types.ModuleType:
    """Compile a .su to a runnable module, caching the codegen output on disk.

    Args:
        src_path: Path to a .su source file.
        llm_model: Frozen-LLM model name for semantic embeddings
            (e.g. "nomic-embed-text"). OPTIONAL — defaults to "none"
            (no model). A program that never calls `embed` (no
            basis_vector, no axon string keys, no semantic embedding —
            e.g. pure make_real / matrix / arithmetic programs, the whole
            trainable-matrix corpus) compiles and runs with NO model. The
            runtime raises a clear error only if `embed` is actually
            reached with llm_model="none". (Emma 2026-05-29: no nomic by
            default; pass a model only when truly embedding content.)
        runtime_dim: Total extended-state dim (semantic + synthetic);
            e.g. 768 for the default `nomic-embed-text` build.
        runtime_dtype: "float32" (default) or "float64".
        cache_dir: Where to write the cached emitted Python. Default is
            next to the .su file.
        verbose: Print one line on cache miss (the codegen pass can take
            minutes for big .su files; the message tells the user what
            is happening).

    Returns:
        A `types.ModuleType` whose namespace contains the compiled
        functions and the `_VSA` runtime instance.

    Raises:
        FileNotFoundError: if `src_path` does not exist.
        RuntimeError: on parse error in the .su.
    """
    src_path = pathlib.Path(src_path).resolve()
    if not src_path.is_file():
        raise FileNotFoundError(f"Sutra source not found: {src_path}")
    src = src_path.read_text(encoding="utf-8")

    cache_hash = _cache_key(
        src, llm_model=llm_model, runtime_dim=runtime_dim, runtime_dtype=runtime_dtype,
    )

    if cache_dir is not None:
        cache_dir = pathlib.Path(cache_dir).resolve()
        cache_dir.mkdir(parents=True, exist_ok=True)
    else:
        cache_dir = src_path.parent

    safe_ver = __version__.replace(".", "_")
    cache_path = cache_dir / f".{src_path.stem}.compiled-sutra{safe_ver}-{cache_hash}.py"

    if cache_path.is_file():
        py_src = cache_path.read_text(encoding="utf-8")
    else:
        # Cache miss -- run codegen.
        if verbose:
            print(
                f"[sutra_compiler] codegen cache miss for {src_path.name}; "
                f"running translate_module (can take minutes for big .su files; "
                f"output cached to {cache_path.name}).",
                file=sys.stderr,
                flush=True,
            )

        from .codegen_pytorch import translate_module as torch_translate
        from .lexer import Lexer
        from .parser import Parser

        lexer = Lexer(src, file=str(src_path))
        tokens = lexer.tokenize()
        parser = Parser(tokens, file=str(src_path), diagnostics=lexer.diagnostics)
        module_ast = parser.parse_module()
        if lexer.diagnostics.has_errors():
            errs = list(lexer.diagnostics)
            raise RuntimeError(f"{src_path.name} parse error: {errs}")

        py_src = torch_translate(
            module_ast,
            llm_model=llm_model,
            runtime_dim=runtime_dim,
            runtime_dtype=runtime_dtype,
        )

        # Atomic write: emit to a tmp file in the cache_dir (so the
        # rename stays on the same filesystem), then atomic-replace.
        # If Ctrl-C lands between fdopen() and replace(), the tmp file
        # is cleaned up; cache_path is never half-written.
        fd, tmp_name = tempfile.mkstemp(
            prefix="." + cache_path.name,
            suffix=".tmp",
            dir=str(cache_dir),
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
                f.write(py_src)
            os.replace(tmp_name, cache_path)
        except Exception:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise

    # Exec into a fresh module. Each call returns an independent module
    # so two compiles of the same .su don't share state.
    mod = types.ModuleType(src_path.stem)
    mod.__file__ = str(cache_path)
    exec(compile(py_src, str(cache_path), "exec"), mod.__dict__)
    return mod


__all__ = ["compile_su"]
