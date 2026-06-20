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
  - **A concurrent dispatch point (`tick_all`).** Programs' independent
    `on_axon` calls can be launched on separate CUDA streams so the GPU
    overlaps their kernels. MEASURED CAVEAT (2026-06-20,
    planning/findings/2026-06-20-tick-all-no-speedup-python-bound.md): on
    today's runtime this delivers NO speedup (0.95x at N=8), because a
    program's per-tick cost is ~98% GIL-bound Python orchestration and
    only ~2% GPU kernel time — and streams overlap only the kernels.
    `tick_all` is correct and is the right ABI shape; real throughput
    needs the per-tick Python to shrink (the compile-time fusion pass) so
    the GPU kernels dominate, or genuine parallel orchestration.

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

    def tick_all(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """Invoke MANY admitted programs CONCURRENTLY on one GPU.

        `inputs` maps program name -> input axon. Returns name -> output
        axon. This is the "run all admitted programs simultaneously on a
        single GPU" primitive (concurrency.md: a concurrent program is two
        or more simultaneous trajectories through the same embedding space;
        every spawned path runs, none is discarded).

        Mechanism: each program's `on_axon` is launched on its OWN CUDA
        stream with no inter-stream synchronization, so the device's
        scheduler overlaps their kernels; a single `torch.cuda.synchronize()`
        then joins all paths before the outputs are read. The Python launch
        loop runs sequentially under the GIL, so the shared `_VSA` lazy
        caches (codebook / rotation / permutation dicts) are populated
        without a data race — only the GPU kernels overlap, not the
        cache-writing Python. On CPU (no CUDA) the streams are a no-op and
        this degrades to correct sequential execution.

        Results are IDENTICAL to calling `tick(name, input)` per program;
        the only difference is the dispatch path. Axon routing between
        programs is still the caller's job — `tick_all` fires one
        independent round, it does not thread one program's output into
        another's input.

        THROUGHPUT CAVEAT (measured 2026-06-20): on the current runtime
        `tick_all` gives NO speedup over sequential `tick` (0.95x at N=8) —
        a program's per-tick cost is ~98% GIL-bound Python orchestration
        and only ~2% GPU kernel time, so overlapping the kernels does not
        help. See planning/findings/2026-06-20-tick-all-no-speedup-python-
        bound.md. Use this for the correct concurrency SHAPE; the speedup
        arrives when the per-tick Python shrinks (fusion pass).
        """
        for name in inputs:
            self._get(name)  # validate every name before launching anything

        import torch as _torch

        use_streams = (
            _torch.cuda.is_available()
            and getattr(self._shared_vsa, "device", None) is not None
            and getattr(self._shared_vsa.device, "type", None) == "cuda"
        )
        if not use_streams:
            # CPU (or non-CUDA device): correct sequential execution.
            return {name: self._programs[name].on_axon(inp)
                    for name, inp in inputs.items()}

        # CUDA: one stream per program, launch without inter-stream sync,
        # then a single device-wide synchronize joins every path.
        outputs: dict[str, Any] = {}
        streams: list[Any] = []
        for name, inp in inputs.items():
            s = _torch.cuda.Stream()
            streams.append(s)
            with _torch.cuda.stream(s):
                outputs[name] = self._programs[name].on_axon(inp)
        _torch.cuda.synchronize()
        return outputs

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
