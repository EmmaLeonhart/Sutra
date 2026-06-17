"""Service abstraction for the kernel.

A `Service` is what backs an admitted process. It has two lifecycle
hooks the kernel calls:

  - `bind(manifest, router)` — once at admission, so the service
    knows its name (for capability checks) and how to send axons.
  - `tick() -> int` — once per kernel tick, drains any inbound
    axons and pushes any outbound ones. Returns the count of
    inbound axons processed.

**The default service implementation in this kernel is `SutraService`
— a real Sutra-compiled `.su` program whose `on_axon(vector) -> vector`
function is invoked on every inbound axon, with the result emitted on
the configured output role.** The Python `PythonService` exists only
for tests and harness code that doesn't need real Sutra compute.

Compilation pattern follows
`external/Sutra/examples/multi_program_axon/_run.py`: lex → parse →
torch_translate → exec into a fresh module → call the exposed
function. The first call into a freshly-compiled service downloads
the embedding model on first use (handled by Sutra's runtime),
which can be slow on cold start; subsequent calls reuse the cached
embedding tables.
"""

from __future__ import annotations

import dataclasses
import gc
import os
import pathlib
import sys
import types
from typing import Any, Callable

from kernel.manifest import Manifest
from kernel.router import Axon, AxonRouter, CapabilityError


# Make the Sutra compiler importable from the submodule. We do this
# at module-import time rather than per-call so SutraService can rely
# on the import succeeding in __init__.
_SUTRA_SDK = pathlib.Path(__file__).resolve().parent.parent.parent.parent / "sdk" / "sutra-compiler"  # Yantra vendored in-tree: Sutra is the grandparent of the Yantra root
if _SUTRA_SDK.is_dir() and str(_SUTRA_SDK) not in sys.path:
    sys.path.insert(0, str(_SUTRA_SDK))


class Service:
    """Base class. The only protocol the kernel actually depends on."""

    def bind(self, *, manifest: Manifest, router: AxonRouter) -> None:
        self._manifest = manifest
        self._router = router

    @property
    def name(self) -> str:
        return self._manifest.name

    # --- GPU residency (Connectome Manager tier moves) -------------
    #
    # The kernel decides which programs are resident on the GPU vs
    # at rest. The base service is always "loaded" and cannot be
    # unloaded — only a real Sutra runtime holds GPU tensors worth
    # evicting. SutraService overrides these.

    @property
    def is_loaded(self) -> bool:
        return True

    @property
    def unloadable(self) -> bool:
        return False

    def unload(self) -> None:
        raise NotImplementedError(
            f"{type(self).__name__} is not unloadable"
        )

    def load(self) -> None:
        """Re-instantiate after an unload. No-op for always-loaded
        services."""
        return None

    def emit(
        self, role: str, payload: Any,
        *, keys: frozenset[str] | set[str] = frozenset(),
    ) -> int:
        """Send an axon; capability check + lazy-skip happen in the router.

        `keys` is the set of axon-internal keys actually bound in
        `payload`. Pass it (the Sutra compiler emits this set in
        production; for v0.0 the calling service passes it
        explicitly) to enable the router's lazy-skip filter against
        receivers' `axon_keys` declarations. Empty (default) =
        eager-fallback: the router delivers to every receiver on
        the role regardless.
        """
        return self._router.send(
            Axon(
                role=role, payload=payload, from_proc=self.name,
                keys=frozenset(keys),
            )
        )

    def tick(self) -> int:  # pragma: no cover — overridden
        raise NotImplementedError


class SutraService(Service):
    """A service whose computation is a real Sutra-compiled .su program.

    The `.su` source must export a function whose name is given by
    `entry_point` (default: "on_axon") with signature
    `(vector) -> vector`. On each tick, the service drains its inbox
    and invokes `entry_point(payload)` once per inbound axon, then
    emits the returned vector on `output_role`.

    Inputs and outputs are torch tensors of shape `(axon_width,)` —
    the axon-shaped vectors Sutra programs operate on natively. The
    router carries them through as the `payload` field of `Axon`.

    **Lazy axon evaluation: the compiled module's `AXON_KEYS_BOUND`
    and `AXON_KEYS_READ` constants** (emitted by Sutra v0.3.3+'s
    static-analysis pass) drive the kernel router's lazy delivery:

      - On `bind()`, if the receiver's manifest has empty
        `axon_keys`, the service auto-populates it from the compiled
        module's `AXON_KEYS_READ` so the router can skip-deliver
        based on what the .su source actually reads — no need to
        hand-write `axon_keys` in the manifest TOML.
      - On `tick()` emission, the service tags outgoing axons with
        the compiled module's `AXON_KEYS_BOUND` so receivers'
        intersection check has data to work with.

    Compilation happens in `bind()`, not in `__init__()`, so the
    service can read the manifest's `axon_width` for the
    `runtime_dim` parameter. First compile of a fresh `.su` source
    downloads the embedding model (Sutra's first-use side effect);
    subsequent compiles in the same process reuse the cache.
    """

    def __init__(
        self,
        *,
        source_path: str | pathlib.Path,
        entry_point: str = "on_axon",
        output_role: str,
        llm_model: str = "nomic-embed-text",
        runtime: Any = None,
        runtime_program_name: str | None = None,
        runtime_dtype: str = "float32",
    ) -> None:
        self._source_path = pathlib.Path(source_path)
        self._entry_point = entry_point
        self._output_role = output_role
        self._llm_model = llm_model
        # Substrate float dtype for the per-service compile path. "float64"
        # extends the exact-integer range from float32's ~2^24 to 2^53 on
        # the real/synthetic axis (needs Sutra >= v0.6.2). Ignored on the
        # shared-runtime path (the runtime owns its dtype).
        self._runtime_dtype = runtime_dtype
        # Optional shared MultiProcessRuntime (Sutra v0.4.0+).
        # When provided, `bind()` skips per-service compilation and
        # pulls handles + key sets from the shared runtime instead.
        # `runtime_program_name` is the name the program is registered
        # under in the runtime — required when `runtime` is set.
        self._runtime = runtime
        self._runtime_program_name = runtime_program_name
        if runtime is not None and runtime_program_name is None:
            raise ValueError(
                "SutraService(runtime=...) also requires runtime_program_name"
            )
        self._compiled_module: types.ModuleType | None = None
        self._on_axon: Callable[[Any], Any] | None = None
        # Populated from compiled-module constants in bind(). Used
        # for lazy axon evaluation (router-side skip-uninterested-
        # receivers + out-emission key tagging).
        self._axon_keys_bound: frozenset[str] = frozenset()
        self._axon_keys_read: frozenset[str] = frozenset()

    @property
    def axon_keys_bound(self) -> frozenset[str]:
        """Keys this service binds (from the compiled module's static analysis)."""
        return self._axon_keys_bound

    @property
    def axon_keys_read(self) -> frozenset[str]:
        """Keys this service reads (from the compiled module's static analysis)."""
        return self._axon_keys_read

    # --- GPU residency: load / unload (the kernel's tier move) -----

    @property
    def is_loaded(self) -> bool:
        """True iff the Sutra runtime is instantiated and GPU-resident."""
        return self._on_axon is not None

    @property
    def unloadable(self) -> bool:
        # Shared-MultiProcessRuntime services share one `_VSA`;
        # residency is a property of the runtime, not one service.
        # Per-service-compile services own their `_VSA` and can be
        # individually evicted. (Shared-runtime eviction is a
        # documented follow-on, not the MVP.)
        return self._runtime is None

    def unload(self) -> None:
        """Evict this program from the GPU: tear down its Sutra
        runtime and free the GPU memory it held. The process stays
        admitted (route entry kept) and can be `load()`-ed again.

        Honest scope: this is *residency* load-fresh/drop, NOT a
        running-state checkpoint. A program's mutated runtime state
        is NOT preserved across unload — preserving it needs the
        Sutra `serialise-process-state` primitive, which does not
        exist yet. For the MVP "start/stop a program on the GPU",
        drop-and-reload is the correct semantics.
        """
        if not self.unloadable:
            raise NotImplementedError(
                f"{self.name!r} runs on a shared MultiProcessRuntime; "
                f"per-service GPU eviction is a documented follow-on, "
                f"not the MVP. Unload the whole runtime instead."
            )
        if self._on_axon is None:
            return  # already unloaded — idempotent
        # The router's projector closure captures the compiled
        # module's `_VSA`; leaving it registered pins the GPU
        # tensors and defeats the free. Drop it first.
        self._router.unregister_projector(self.name)
        # Proactively release the runtime's device tensors. Nulling
        # the module ref alone does NOT reliably drop GPU memory
        # (measured: 0 bytes freed) — a lingering Python ref to the
        # `_VSA` (e.g. a held traceback, a debugger, an interactive
        # frame) keeps every tensor alive. So we explicitly None out
        # the `_VSA`'s tensor attributes and clear its caches /
        # module globals: the *evicted* program's GPU arena is
        # released regardless of any dangling ref to the (now
        # gutted) objects. This is the correct eviction teardown —
        # the Rust orchestrator's per-process GPU-arena free has the
        # same shape. `load()` rebuilds a fresh module, so gutting
        # the old one is safe.
        try:
            import torch
            _is_tensor = torch.is_tensor
        except Exception:
            torch = None

            def _is_tensor(_):
                return False

        mod = self._compiled_module
        if mod is not None:
            vsa = getattr(mod, "_VSA", None)
            if vsa is not None and hasattr(vsa, "__dict__"):
                for k, v in list(vars(vsa).items()):
                    if _is_tensor(v):
                        setattr(vsa, k, None)
                    elif isinstance(v, dict):
                        v.clear()   # _rot_cache, _perm_cache, codebook
                    elif isinstance(v, list):
                        v.clear()
            for k in list(vars(mod).keys()):
                if not k.startswith("__"):
                    try:
                        setattr(mod, k, None)
                    except Exception:
                        pass
        self._on_axon = None
        self._compiled_module = None
        gc.collect()
        if torch is not None:
            try:
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except Exception:
                pass

    def load(self) -> None:
        """(Re)instantiate the Sutra runtime so the program is
        GPU-resident again. Idempotent. Requires a prior bind
        (admission) so the manifest + router are known."""
        if self._on_axon is not None:
            return  # already loaded — idempotent
        if not hasattr(self, "_manifest") or not hasattr(self, "_router"):
            raise RuntimeError(
                f"{self._source_path.name!r} cannot load before its "
                f"first admission (no manifest/router bound yet)"
            )
        self.bind(manifest=self._manifest, router=self._router)

    def bind(self, *, manifest: Manifest, router: AxonRouter) -> None:
        super().bind(manifest=manifest, router=router)
        if self._runtime is not None:
            # Shared-runtime path: pull handles from the
            # MultiProcessRuntime instead of compiling here.
            # The runtime already compiled this program at
            # construction time and rebound its _VSA to the
            # shared one; we just need to surface the entry
            # point + key sets to ourselves.
            name = self._runtime_program_name
            assert name is not None  # ctor guarantees this
            prog = self._runtime._programs.get(name)  # noqa: SLF001
            if prog is None:
                raise KeyError(
                    f"SutraService(runtime=...) program {name!r} not "
                    f"admitted to the runtime; admitted: "
                    f"{self._runtime.admitted()}"
                )
            self._compiled_module = prog.module
            self._on_axon = prog.on_axon
            self._axon_keys_bound = prog.axon_keys_bound
            self._axon_keys_read = prog.axon_keys_read
        else:
            # Per-service-compile path (original v0.0 behaviour).
            self._compiled_module = _compile_su_to_module(
                self._source_path,
                llm_model=self._llm_model,
                runtime_dim=manifest.axon_width,
                runtime_dtype=self._runtime_dtype,
            )
            if not hasattr(self._compiled_module, self._entry_point):
                raise AttributeError(
                    f"{self._source_path} compiled module has no "
                    f"`{self._entry_point}` symbol; available: "
                    f"{[n for n in dir(self._compiled_module) if not n.startswith('_')]}"
                )
            self._on_axon = getattr(self._compiled_module, self._entry_point)
            # Pull the static-analysis results out of the compiled
            # module. Always present in Sutra v0.3.3+; getattr with
            # frozenset() default keeps us safe against an older
            # compiled module slipping in via cache.
            self._axon_keys_bound = frozenset(
                getattr(self._compiled_module, "AXON_KEYS_BOUND", frozenset())
            )
            self._axon_keys_read = frozenset(
                getattr(self._compiled_module, "AXON_KEYS_READ", frozenset())
            )
        # Register the per-receiver projection function with the
        # router. Sutra v0.3.5+ ships _VSA.axon_project. With this
        # registered, the router can slim payloads to per-receiver
        # interest sets at delivery time. Older compiled modules
        # that lack axon_project fall through to no projection —
        # router delivers the full payload, which is correct but
        # bandwidth-non-optimal.
        if hasattr(self._compiled_module._VSA, "axon_project"):
            vsa = self._compiled_module._VSA

            def _project(payload, requested_keys):
                # Frozenset → list for the runtime API.
                return vsa.axon_project(payload, list(requested_keys))

            router.register_projector(manifest.name, _project)
        # If the manifest didn't hand-declare axon_keys, auto-populate
        # from what the compiled .su actually reads. The router only
        # checks the receiver-side (axon_keys), not the sender-side
        # (it gets that via Axon.keys at send-time), so this hooks
        # the static-analysis result into the router's lazy-skip
        # path without any router changes. Manifests that DID
        # declare axon_keys are respected as-is — explicit override.
        if not manifest.axon_keys and self._axon_keys_read:
            # Manifests are frozen dataclasses; rebuild with the new
            # axon_keys value, then re-register the route entry so
            # the router knows about the now-non-empty interest set.
            new_manifest = dataclasses.replace(
                manifest, axon_keys=self._axon_keys_read,
            )
            # Swap the manifest in the router's process table. Done
            # in-place — the router reads receiver.axon_keys at
            # send-time so updating the dict entry is enough.
            router._processes[manifest.name] = new_manifest  # noqa: SLF001
            # Update self._manifest too so the property surfaces the
            # right values.
            self._manifest = new_manifest

    def tick(self) -> int:
        if self._on_axon is None:
            raise RuntimeError(
                f"SutraService for {self._source_path.name!r} not bound; "
                f"call init.admit(...) first"
            )
        n = 0
        for inbound in self._router.drain(self.name):
            outbound = self._on_axon(inbound.payload)
            # Tag outgoing axons with the producer's bound-keys set
            # so receivers' lazy-skip intersection check has data
            # to work with. emit() forwards these to the router.
            self.emit(
                self._output_role, outbound, keys=self._axon_keys_bound,
            )
            n += 1
        return n


def _compile_su_to_module(
    src_path: pathlib.Path, *, llm_model: str, runtime_dim: int,
    runtime_dtype: str = "float32",
) -> types.ModuleType:
    """Compile a .su file via the PyTorch backend.

    Thin wrapper over ``sutra_compiler.compile_su`` (Sutra >= v0.7.1) -- the
    SDK helper does the lex -> parse -> translate -> exec dance AND caches
    the emitted Python on disk, so a re-admit of the same service skips the
    full codegen pass. Each call still returns an independent module so two
    services instantiated from the same .su file have independent state.
    """
    # Lazy-import inside the function so that environments without the
    # Sutra SDK on sys.path can still import kernel.services as long
    # as they don't actually instantiate a SutraService.
    from sutra_compiler import compile_su
    return compile_su(
        src_path,
        llm_model=llm_model,
        runtime_dim=runtime_dim,
        runtime_dtype=runtime_dtype,
        verbose=False,
    )


def make_shared_sutra_services(
    specs: list[dict],
    *,
    llm_model: str = "nomic-embed-text",
    runtime_dim: int,
) -> tuple[Any, list["SutraService"]]:
    """Construct N SutraServices over a single shared MultiProcessRuntime.

    `specs` is a list of dicts:
      [{"name": str, "source_path": Path, "output_role": str,
        "entry_point": str = "on_axon"}, ...]

    Returns (runtime, services). The runtime is a Sutra v0.4.0
    `MultiProcessRuntime`; the services are constructed wired to it,
    so admission to the same `Init` shares one _VSA + codebook +
    embedding cache across all of them. Reduces per-service compile
    overhead and makes cross-service axon-passing coherent without
    each service rebuilding its own rotation cache.

    The kernel `Init.admit()` workflow is unchanged — call it once
    per returned service. The shared runtime is held alive by the
    services' references to it (each service stores its
    `runtime=...`); callers don't need to keep a separate reference
    unless they want runtime-level operations like
    `runtime.axon_project(...)` or `runtime.tick("name", input)`.

    Sutra v0.4.0+ required.
    """
    # Lazy import — only callers that actually use shared services
    # pay the import cost. Same pattern as _compile_su_to_module.
    from sutra_compiler.multi_process import (
        MultiProcessRuntime,
        ProgramSpec,
    )

    program_specs = [
        ProgramSpec(
            name=s["name"],
            source_path=pathlib.Path(s["source_path"]),
            entry_point=s.get("entry_point", "on_axon"),
        )
        for s in specs
    ]
    runtime = MultiProcessRuntime(
        program_specs, llm_model=llm_model, runtime_dim=runtime_dim,
    )
    services = [
        SutraService(
            source_path=s["source_path"],
            entry_point=s.get("entry_point", "on_axon"),
            output_role=s["output_role"],
            llm_model=llm_model,
            runtime=runtime,
            runtime_program_name=s["name"],
        )
        for s in specs
    ]
    return runtime, services


# --- Python service variant — for harness code only ---------------------


class PythonService(Service):
    """A Python-callback service. For tests + harnesses, NOT real services.

    Real kernel services use SutraService. PythonService exists so
    that admission control + router behaviour can be tested without
    paying the cost of compiling a .su file (which downloads the
    embedding model on first use). Production code should not use
    this.
    """

    def __init__(self, on_axon: Callable[["PythonService", Axon], None]) -> None:
        self._on_axon = on_axon

    def tick(self) -> int:
        n = 0
        for ax in self._router.drain(self.name):
            self._on_axon(self, ax)
            n += 1
        return n
