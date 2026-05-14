"""Multi-process Sutra runtime: N programs sharing one _VSA.

The first shippable shape of "multi-process Sutra." Compiles N `.su`
sources, rebinds each compiled module's `_VSA` to a single shared
instance so the codebook + Ollama embedding cache + rotation cache
are shared, and exposes a `tick(name, input) -> output` API for
invoking each program by name.

What this is:

  - **One Python process, N admitted Sutra programs.** Each program
    gets its own compiled module (its own `on_axon` function, its
    own static-analysis results) but all share one `_VSA` runtime
    object. Axons cross between programs as in-memory torch tensors
    on the runtime's device — no `.npy` serialization, no second
    interpreter process.
  - **Shared codebook + embedding cache.** Without rebinding, each
    compiled module would have its own `_VSA._codebook` dict and
    re-fetch every `basis_vector("...")` from Ollama. The shared
    `_VSA` makes the codebook a connectome-wide thing — the cost
    that the v0.3.0 batched `embed_batch` was added to amortize.
  - **CUDA-stream-level parallelism on independent compute.** When
    multiple programs' `on_axon` calls are independent, the GPU's
    own scheduler runs them in parallel on separate streams.
    Sequential Python dispatch + parallel device execution is the
    natural "multi-process on one GPU" shape today.

What this is NOT:

  - **Per-process GPU memory arena carve-outs.** All admitted
    programs share the same GPU memory pool (the shared `_VSA`
    owns it). Real per-process arenas need device-level work
    (CUDA stream isolation, possibly CUDA IPC) and stay out of
    scope until that lands.
  - **Independent codebooks per process.** This implementation
    explicitly couples the codebook across programs. A
    multi-tenant-Yantra deployment that wants per-tenant
    codebooks would need a different runtime shape (probably one
    `MultiProcessRuntime` per tenant rather than one across the
    whole machine).

Use case driver: Yantra's kernel router. Today Yantra creates one
`SutraService` per program, each with its own compiled module and
its own `_VSA`. Codebook duplication wastes Ollama round trips and
GPU memory. With this runtime, Yantra can construct one
`MultiProcessRuntime` for all admitted services and dispatch their
ticks against the shared infrastructure.
"""

from __future__ import annotations

import dataclasses
import pathlib
import types
from typing import Any, Iterable

from .codegen_pytorch import translate_module
from .lexer import Lexer
from .parser import Parser


@dataclasses.dataclass(frozen=True)
class ProgramSpec:
    """One process's admission descriptor.

    `name`         — unique identifier the runtime invokes by.
    `source_path`  — path to the `.su` file.
    `entry_point`  — name of the function the runtime calls per tick
                     (default: "on_axon"; signature `(vector) -> vector`).
    """
    name: str
    source_path: pathlib.Path
    entry_point: str = "on_axon"


@dataclasses.dataclass
class _AdmittedProgram:
    """Internal: a compiled module + its on_axon binding + key sets."""
    module: types.ModuleType
    on_axon: Any  # callable
    axon_keys_bound: frozenset[str]
    axon_keys_read: frozenset[str]


class MultiProcessRuntime:
    """Hosts N Sutra programs over a shared `_VSA` instance.

    Construct with a list of `ProgramSpec`s. The constructor
    compiles each `.su`, then rebinds each compiled module's
    `_VSA` attribute to a single shared instance taken from the
    first compiled module. From that point on every program
    operates against the same codebook, embedding cache, and
    runtime device.

    Subsequent `tick(name, input)` calls invoke the named
    program's entry point. Axon-passing between programs is the
    *caller's* responsibility — call A's tick, take its output,
    feed it as B's input. The runtime doesn't dictate routing
    policy; that lives one layer up (Yantra's kernel router).
    """

    def __init__(
        self,
        specs: Iterable[ProgramSpec],
        *,
        llm_model: str = "nomic-embed-text",
        runtime_dim: int = 768,
    ) -> None:
        specs = list(specs)
        if not specs:
            raise ValueError("MultiProcessRuntime requires at least one program")
        # Detect duplicates early — caller bug, surface loudly.
        seen: set[str] = set()
        for s in specs:
            if s.name in seen:
                raise ValueError(f"duplicate program name in specs: {s.name!r}")
            seen.add(s.name)

        self._llm_model = llm_model
        self._runtime_dim = runtime_dim

        # Compile each .su to its own module.
        modules: dict[str, types.ModuleType] = {}
        for s in specs:
            modules[s.name] = _compile(
                s.source_path,
                llm_model=llm_model,
                runtime_dim=runtime_dim,
            )

        # Rebind every module's _VSA to the first one's. This is the
        # actual "multi-process" mechanism — without it each module
        # has its own codebook and the cross-program axon-passing
        # would not work because the rotation matrices wouldn't
        # match. With it, all programs operate on a single shared
        # codebook + embedding cache + rotation cache.
        first_name = specs[0].name
        self._shared_vsa = modules[first_name]._VSA
        for s in specs[1:]:
            modules[s.name]._VSA = self._shared_vsa

        # Bind each entry point + collect static-analysis results.
        self._programs: dict[str, _AdmittedProgram] = {}
        for s in specs:
            mod = modules[s.name]
            if not hasattr(mod, s.entry_point):
                raise AttributeError(
                    f"program {s.name!r} has no entry point "
                    f"{s.entry_point!r}; available: "
                    f"{[n for n in dir(mod) if not n.startswith('_')]}"
                )
            self._programs[s.name] = _AdmittedProgram(
                module=mod,
                on_axon=getattr(mod, s.entry_point),
                axon_keys_bound=frozenset(
                    getattr(mod, "AXON_KEYS_BOUND", frozenset())
                ),
                axon_keys_read=frozenset(
                    getattr(mod, "AXON_KEYS_READ", frozenset())
                ),
            )

    # --- public API ---

    def admitted(self) -> list[str]:
        """Names of all admitted programs, sorted."""
        return sorted(self._programs)

    def vsa(self):
        """The shared `_VSA` instance. Same object every program sees."""
        return self._shared_vsa

    def axon_keys_bound(self, name: str) -> frozenset[str]:
        """Static-analysis bound-keys set for the named program."""
        return self._get(name).axon_keys_bound

    def axon_keys_read(self, name: str) -> frozenset[str]:
        """Static-analysis read-keys set for the named program."""
        return self._get(name).axon_keys_read

    def tick(self, name: str, input_axon: Any) -> Any:
        """Invoke the named program's entry point on `input_axon`."""
        prog = self._get(name)
        return prog.on_axon(input_axon)

    def axon_project(self, payload: Any, requested_keys: Iterable[str]) -> Any:
        """Delegate to the shared `_VSA.axon_project` (Sutra v0.3.5+)."""
        return self._shared_vsa.axon_project(payload, list(requested_keys))

    # --- internals ---

    def _get(self, name: str) -> _AdmittedProgram:
        if name not in self._programs:
            raise KeyError(
                f"no admitted program {name!r}; admitted: {sorted(self._programs)}"
            )
        return self._programs[name]


# ---------- internals -----------------------------------------------


def _compile(
    src_path: pathlib.Path | str,
    *,
    llm_model: str,
    runtime_dim: int,
) -> types.ModuleType:
    """Compile a .su via the pytorch backend; return a fresh module."""
    src_path = pathlib.Path(src_path).resolve()
    if not src_path.is_file():
        raise FileNotFoundError(f"Sutra source not found: {src_path}")
    src = src_path.read_text(encoding="utf-8")
    lexer = Lexer(src, file=str(src_path))
    tokens = lexer.tokenize()
    parser = Parser(tokens, file=str(src_path), diagnostics=lexer.diagnostics)
    module_ast = parser.parse_module()
    py_src = translate_module(
        module_ast, llm_model=llm_model, runtime_dim=runtime_dim,
    )
    mod = types.ModuleType(src_path.stem)
    mod.__file__ = f"<compiled from {src_path}>"
    exec(compile(py_src, mod.__file__, "exec"), mod.__dict__)
    return mod
