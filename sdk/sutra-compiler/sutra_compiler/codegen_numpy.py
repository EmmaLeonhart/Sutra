"""AST -> pure-numpy Python source translator.

This is the demo-path backend. It emits self-contained Python modules
that depend only on numpy — no fly-brain imports, no spiking simulator,
no learned MBON readouts. VSA ops run as plain matrix operations on CPU.

The fly-brain backend (`codegen_flybrain.py`) stays for fly-brain-only
work. The demo path (what the paper points at, what fresh clones run)
goes through this file.

Design is a thin subclass of `FlyBrainCodegen`: the translator logic for
expressions, statements, loops, declarations is identical — only the
prelude changes. `snap` is not supported here (the demo substrate has no
cleanup circuit; programs that need `snap` should target the fly-brain
backend).

The VSA runtime itself (the `_NumpyVSA` class and the helper functions
`_argmax_cosine`, `_select_softmax`, `_vector_map_lookup`) lives in
`runtime_numpy.py` as real, lint-able, testable Python. `_emit_prelude`
reads that file and inlines it verbatim into the generated module. The
alternative — building the runtime line-by-line with `self._emit(...)`
calls — made adding a PyTorch/CUDA backend a copy-paste-of-strings
exercise; keeping the runtime as source keeps each backend port to
"write a new `runtime_<target>.py`".
"""

from __future__ import annotations

from pathlib import Path
from typing import List

from . import ast_nodes as ast
from .codegen_flybrain import FlyBrainCodegen, CodegenNotSupported


class NumpyCodegen(FlyBrainCodegen):
    """Emits a self-contained numpy-only module.

    Overrides the prelude and rejects `snap()` at codegen time. Everything
    else (function bodies, bind/bundle/unbind/similarity/argmax_cosine,
    map lookup, loop unrolling) is inherited unchanged.
    """

    # Frozen-LLM substrate. The numpy backend runs on frozen LLM
    # embeddings via Ollama — no random-vector fallback. If Ollama is
    # unavailable or the model is missing, compiled programs raise.
    # Default model: nomic-embed-text (768-dim). Avoid mxbai-embed-large
    # per CLAUDE.md — it has a documented attention-sink defect on
    # diacritics and is treated as a known-broken baseline.
    DEFAULT_LLM_MODEL = "nomic-embed-text"
    DEFAULT_LLM_DIM = 768

    _RUNTIME_PATH = Path(__file__).parent / "runtime_numpy.py"

    def __init__(self, *, runtime_dim: int | None = None,
                 runtime_seed: int = 42,
                 llm_model: str | None = None) -> None:
        self._llm_model = llm_model if llm_model is not None else self.DEFAULT_LLM_MODEL
        # If using LLM default, dim is the LLM's; otherwise allow override.
        if runtime_dim is None:
            runtime_dim = self.DEFAULT_LLM_DIM
        # List of strings that appear in `basis_vector("...")` calls,
        # populated by translate_module() between simplify and codegen.
        # The codegen emits a batched Ollama pre-fetch at module init
        # to replace N sequential HTTP round-trips with one call.
        self._prefetch_strings: list[str] = []
        super().__init__(
            runtime_dim=runtime_dim,
            runtime_seed=runtime_seed,
            runtime_n_kc=0,
            runtime_use_hemibrain=False,
        )

    # Ops not supported by the pure-numpy substrate. `snap` requires a
    # cleanup circuit (MB spiking model or equivalent); rotation-based
    # loop primitives need the same. Programs that use these should
    # target `codegen_flybrain` instead.
    _UNSUPPORTED_BUILTINS = frozenset({
        "snap",
        "make_rotation",
        "compile_prototypes",
        "geometric_loop",
    })

    def _translate_eigenrotation_loop(self, stmt):
        """Eigenrotation on the numpy substrate.

        Differences from fly-brain:
        - Haar-random orthogonal matrix (fly-brain's uniform-angle
          Givens gives a tight periodic orbit that never explores).
        - Threshold is parsed from the condition (the numeric literal
          side of `similarity(state, target) < T`). Fly-brain uses a
          fixed 0.3 because matching is KC-pattern Jaccard; numpy
          matches on raw cosine, which has a very different scale.
        """
        from . import ast_nodes as ast
        lid = self._next_loop_id()
        state_var = self._extract_loop_state_var(stmt.body)
        target_expr = self._extract_loop_target(stmt.condition)

        threshold = 0.9
        cond = stmt.condition
        if isinstance(cond, ast.BinaryOp):
            for side in (cond.left, cond.right):
                if isinstance(side, ast.FloatLiteral):
                    threshold = side.value
                elif isinstance(side, ast.IntLiteral):
                    threshold = float(side.value)

        self._emit(f"{lid}_R = _VSA.make_random_rotation("
                   f"angle=1.0, n_planes=_VSA.dim // 2, seed=_VSA.seed)")
        self._emit(f"{lid}_target = {target_expr}")
        self._emit(f"{lid}_protos = _VSA.compile_prototypes("
                   f"{{\"target\": {lid}_target}})")
        self._emit(f"{lid}_name, {state_var}, {lid}_iters = _VSA.loop(")
        self._indent += 1
        self._emit(f"{state_var}, {lid}_R, {lid}_protos,")
        self._emit(f"target_name=\"target\", threshold={threshold}, max_iters=500)")
        self._indent -= 1

    def _translate_call(self, call: ast.Call) -> str:
        callee = call.callee
        if isinstance(callee, ast.Identifier):
            if callee.name in self._UNSUPPORTED_BUILTINS:
                raise CodegenNotSupported(
                    call,
                    f"`{callee.name}` is not supported on the pure-numpy "
                    f"substrate; use the fly-brain backend if you need it",
                )
        return super()._translate_call(call)

    @classmethod
    def _load_runtime_source(cls) -> str:
        # Read runtime_numpy.py and strip its own module docstring.
        # The runtime file starts with a docstring explaining that it
        # is a template (not imported at runtime). That docstring is
        # for humans reading the source; the generated module gets its
        # own Generated-by docstring from the codegen, so the template
        # docstring is dropped before inlining.
        text = cls._RUNTIME_PATH.read_text(encoding="utf-8")
        assert text.startswith('"""'), (
            "runtime_numpy.py must begin with a module docstring"
        )
        close = text.index('"""', 3) + 3
        return text[close:].lstrip("\n").rstrip("\n")

    def _emit_prelude(self) -> None:
        self._emit('"""Generated by sutra_compiler.codegen_numpy. Do not edit by hand."""')
        # Inline the runtime module verbatim. Appending directly to
        # self._lines bypasses the indent-prefix logic in `_emit` —
        # the runtime file already carries its own indentation.
        for line in self._load_runtime_source().split("\n"):
            self._lines.append(line)
        self._emit()
        self._emit()
        self._emit(
            f"_VSA = _NumpyVSA(dim={self.runtime_dim}, seed={self.runtime_seed}, "
            f"llm_model={self._llm_model!r})"
        )
        # Batched pre-fetch of every basis_vector("...") string argument
        # the program uses. One Ollama round-trip instead of N sequential
        # ones. Collected by the simplify pass (see translate_module).
        if self._prefetch_strings:
            self._emit(f"_VSA.embed_batch({self._prefetch_strings!r})")


def translate_module(module: ast.Module, **kwargs) -> str:
    """Translate a parsed Sutra module to self-contained numpy Python.

    Runs the simplification pass over the AST before handing to the
    codegen so identity rewrites (bundle(v) -> v, bundle flattening)
    happen in source-to-source form rather than in the emitted
    Python. Also collects every `basis_vector("...")` string literal
    so the codegen can emit a batched Ollama pre-fetch at module init
    (N HTTP round-trips collapse into one batched embed call).
    These are prerequisites for the PyTorch/GPU backend port.
    """
    from .simplify import simplify_module, collect_basis_vector_strings
    simplify_module(module)
    strings = collect_basis_vector_strings(module)
    cg = NumpyCodegen(**kwargs)
    cg._prefetch_strings = strings
    return cg.translate(module)
