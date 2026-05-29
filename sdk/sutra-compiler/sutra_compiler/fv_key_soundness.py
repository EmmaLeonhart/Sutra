"""Formal-verification contract key-soundness checker (FV paper §3.1).

Discharges the open half of the §3.1 contract obligation: that the
compiler's STATIC axon-key analysis (`AXON_KEYS_READ` / `AXON_KEYS_BOUND`,
computed by `axon_keys.collect_axon_keys` and emitted as module-scope
frozensets) is SOUND with respect to the keys a program actually touches
at RUNTIME.

Mechanism. The PyTorch runtime's `axon_add` / `axon_item` carry opt-in
key-usage instrumentation (`_VSA._fv_key_trace`, OFF by default so the
hot path is untouched). When enabled it records, per access, the key
actually bound/read — a `str` key by name, or `'<dynamic>'` for a
non-str (pre-embedded vector) key the static analysis could not name.
Soundness then is the set inclusion

    runtime_read  ⊆ AXON_KEYS_READ
    runtime_bound ⊆ AXON_KEYS_BOUND

A runtime key NOT in the static set means the static analysis MISSED a
key the program touches — i.e. it is unsound for that program. The
`'<dynamic>'` marker makes any non-namable runtime key an automatic
escape (it is never in the static literal set), so a program that reaches
an axon via a runtime-computed / pre-embedded key is caught.

The check is non-vacuous: it passes for programs whose accesses use only
the statically-collected string-literal keys and FAILS the moment an
access escapes that set (see `tests/test_fv_key_soundness.py` for both a
sound program and a caught escape).

This is a *monitoring* harness — it runs the real substrate program with
a host-side recorder around the substrate ops, never inside the tensor
math. It does not change what executes.
"""
from __future__ import annotations

from typing import Callable


def check_key_soundness(
    module_ns: dict,
    run_fn: Callable[[object], object],
) -> dict:
    """Run a compiled Sutra program with key-tracing on and gate the
    runtime key set against the static AXON_KEYS_* sets.

    Args:
        module_ns: the namespace of an exec'd PyTorch-compiled Sutra
            module. Must expose `_VSA` and (optionally) `AXON_KEYS_READ`
            / `AXON_KEYS_BOUND` (treated as empty if absent).
        run_fn: callable taking the module's `_VSA` instance and
            exercising the program's axon accesses (typically calls the
            entry function on a sample axon). Its return value is ignored.

    Returns a verdict dict:
        sound (bool): runtime keys ⊆ static keys for both read and bound.
        runtime_read / runtime_bound (set[str]): keys touched at runtime.
        static_read / static_bound (set[str]): the emitted static sets.
        read_escapes / bound_escapes (set[str]): runtime keys not in the
            static set (the unsoundness witnesses; empty iff sound).
    """
    vsa = module_ns["_VSA"]
    static_read = set(module_ns.get("AXON_KEYS_READ", frozenset()))
    static_bound = set(module_ns.get("AXON_KEYS_BOUND", frozenset()))

    prev = getattr(vsa, "_fv_key_trace", None)
    vsa._fv_key_trace = {"read": set(), "bound": set()}
    try:
        run_fn(vsa)
        trace = vsa._fv_key_trace
    finally:
        vsa._fv_key_trace = prev

    runtime_read = set(trace["read"])
    runtime_bound = set(trace["bound"])
    read_escapes = runtime_read - static_read
    bound_escapes = runtime_bound - static_bound
    sound = not read_escapes and not bound_escapes

    return {
        "sound": sound,
        "runtime_read": runtime_read,
        "runtime_bound": runtime_bound,
        "static_read": static_read,
        "static_bound": static_bound,
        "read_escapes": read_escapes,
        "bound_escapes": bound_escapes,
    }
