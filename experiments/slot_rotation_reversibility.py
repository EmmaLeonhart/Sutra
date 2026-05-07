"""2D-Givens-per-slot reversibility demo on the compiled runtime.

Exercises the `_VSA.slot_store` / `slot_load` / `rotate_slot`
primitives added to codegen.py on 2026-04-24. The primitives
implement the 2D-Givens-per-slot rotation-binding design from
`planning/findings/2026-04-21-extended-state-and-rotation-binding.md`,
validated against a reference numpy implementation on 2026-04-24 in
`planning/findings/2026-04-24-synthetic-subspace-validation.md`.

This script loads the real compiled `_VSA` from the demo harness
(not a reference reimplementation) and demonstrates three things:

1. **Slot independence.** Store distinct scalars at many slots; each
   slot_load returns the exact scalar for that slot, with no cross-
   talk from other slots or from the semantic block.
2. **Reversibility of imperative state.** The sequence `x = a; x = b;
   x = a` ends with the slot carrying the value a — indistinguishable
   from a single-assignment program. This is the "variable assignment
   is a pure transform of state" commitment from the design doc.
3. **Rotation roundtrip on the substrate.** Apply a sequence of
   rotate_slot calls forward, then the inverses in reverse; state
   returns to the starting point at FP roundoff.

Uses hello_world.su as a harness because only a compiled `_VSA`
is needed — no Sutra-language syntax for slot primitives exists
yet (the compiler-side allocation is follow-on work).

Usage: python experiments/slot_rotation_reversibility.py
"""
from __future__ import annotations

import os
import sys
import types

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, ".."))
SDK_PATH = os.path.join(REPO_ROOT, "sdk", "sutra-compiler")
sys.path.insert(0, SDK_PATH)

from sutra_compiler.codegen import translate_module  # noqa: E402
from sutra_compiler.lexer import Lexer  # noqa: E402
from sutra_compiler.parser import Parser  # noqa: E402


def load_vsa():
    """Compile hello_world.su, exec, return the instantiated _VSA."""
    path = os.path.join(REPO_ROOT, "examples", "hello_world.su")
    with open(path, encoding="utf-8") as f:
        src = f.read()
    lexer = Lexer(src, file=path)
    tokens = lexer.tokenize()
    parser = Parser(tokens, file=path, diagnostics=lexer.diagnostics)
    module = parser.parse_module()
    py_src = translate_module(module)
    mod = types.ModuleType("_slot_harness")
    mod.__file__ = "<slot_rotation_reversibility>"
    exec(compile(py_src, mod.__file__, "exec"), mod.__dict__)
    return mod._VSA


def test_slot_independence(vsa) -> dict:
    """Store distinct scalars at many slots; confirm each reads back
    cleanly regardless of what else is stored."""
    n_planes = (vsa.synthetic_dim - vsa.SLOT_BASE) // 2
    state = vsa.zero_vector()
    # Mix in some semantic-subspace content to verify the slot load
    # ignores it.
    rng = np.random.RandomState(42)
    state[:vsa.semantic_dim] = rng.randn(vsa.semantic_dim)
    state[:vsa.semantic_dim] /= (np.linalg.norm(state[:vsa.semantic_dim]) + 1e-12)

    # Assign distinct scalars to the first n_planes slots.
    values = [(s, 0.5 * (s + 1) * (-1 if s % 3 == 0 else 1))
              for s in range(n_planes)]
    for s, v in values:
        state = vsa.slot_store(state, s, v)

    # Read each slot back; verify exact match.
    max_err = 0.0
    for s, v in values:
        got = vsa.slot_load(state, s)
        err = abs(got - v)
        if err > max_err:
            max_err = err

    return dict(
        n_slots=n_planes, max_err=max_err,
        passed=(max_err < 1e-14),
    )


def test_reassignment_equals_single(vsa) -> dict:
    """Assigning x = a, x = b, x = a should leave the state at x=a's
    value, indistinguishable from a single x = a assignment."""
    s = 3  # pick a slot arbitrarily
    # Path 1: three assignments.
    st1 = vsa.zero_vector()
    st1 = vsa.slot_store(st1, s, 0.7)   # x = 0.7
    st1 = vsa.slot_store(st1, s, -0.3)  # x = -0.3
    st1 = vsa.slot_store(st1, s, 0.7)   # x = 0.7
    # Path 2: single assignment.
    st2 = vsa.zero_vector()
    st2 = vsa.slot_store(st2, s, 0.7)
    # Both should load the same scalar at slot s.
    diff_at_slot = abs(vsa.slot_load(st1, s) - vsa.slot_load(st2, s))
    # And the full state vectors should be identical (slot_store zeroes
    # the imaginary leg every time, so any accumulated phase is
    # discarded).
    full_diff = float(np.linalg.norm(st1 - st2))
    return dict(
        slot_diff=diff_at_slot, full_diff=full_diff,
        passed=(diff_at_slot < 1e-14 and full_diff < 1e-14),
    )


def test_rotation_roundtrip(vsa) -> dict:
    """Apply a sequence of rotate_slot(s_i, theta_i) forward, then
    rotate_slot(s_i, -theta_i) in reverse. State should return to
    start at FP roundoff."""
    n_planes = (vsa.synthetic_dim - vsa.SLOT_BASE) // 2
    rng = np.random.RandomState(7)
    state = vsa.zero_vector()
    # Start from a non-trivial initial state: populate every slot with
    # a random scalar so rotations actually do visible work.
    for s in range(n_planes):
        state = vsa.slot_store(state, s, float(rng.randn()))
    initial = state.copy()

    # 100 random rotations.
    ops = []
    for _ in range(100):
        s = int(rng.randint(0, n_planes))
        theta = float(rng.uniform(0.1, 2 * np.pi - 0.1))
        state = vsa.rotate_slot(state, s, theta)
        ops.append((s, theta))

    # Reverse with negated angles (inverse rotation).
    for s, theta in reversed(ops):
        state = vsa.rotate_slot(state, s, -theta)

    err = float(np.linalg.norm(state - initial))
    return dict(
        n_ops=len(ops), roundtrip_error=err,
        passed=(err < 1e-10),
    )


def test_semantic_isolation(vsa) -> dict:
    """Confirm slot operations do not touch the semantic block.

    Start with semantic content, store and rotate on slots, read back
    the semantic content — it should be byte-identical."""
    rng = np.random.RandomState(99)
    state = vsa.zero_vector()
    sem = rng.randn(vsa.semantic_dim)
    sem /= (np.linalg.norm(sem) + 1e-12)
    state[:vsa.semantic_dim] = sem

    for s in range(5):
        state = vsa.slot_store(state, s, 0.1 * s)
        state = vsa.rotate_slot(state, s, 0.3 + 0.1 * s)

    err = float(np.linalg.norm(state[:vsa.semantic_dim] - sem))
    return dict(
        semantic_drift=err,
        passed=(err < 1e-14),
    )


def main() -> int:
    print("=" * 72)
    print("2D-Givens-per-slot reversibility — compiled-runtime test")
    print("=" * 72)
    vsa = load_vsa()
    n_planes = (vsa.synthetic_dim - vsa.SLOT_BASE) // 2
    print(f"  semantic_dim:  {vsa.semantic_dim}")
    print(f"  synthetic_dim: {vsa.synthetic_dim}")
    print(f"  SLOT_BASE:     {vsa.SLOT_BASE}")
    print(f"  slot planes:   {n_planes}  "
          f"(each slot = disjoint 2D plane in synthetic subspace)")
    print()

    all_passed = True

    print("Test 1 — slot independence")
    print("-" * 72)
    r1 = test_slot_independence(vsa)
    print(f"  assigned distinct scalars to {r1['n_slots']} slots "
          f"with semantic noise present")
    print(f"  max load error: {r1['max_err']:.3e}")
    print(f"  verdict: {'PASS' if r1['passed'] else 'FAIL'}")
    if not r1["passed"]:
        all_passed = False
    print()

    print("Test 2 — reassignment = single assignment")
    print("-" * 72)
    r2 = test_reassignment_equals_single(vsa)
    print(f"  (x = 0.7; x = -0.3; x = 0.7)  vs  (x = 0.7)")
    print(f"  slot_load diff:   {r2['slot_diff']:.3e}")
    print(f"  full state diff:  {r2['full_diff']:.3e}")
    print(f"  verdict: {'PASS' if r2['passed'] else 'FAIL'}")
    if not r2["passed"]:
        all_passed = False
    print()

    print("Test 3 — rotation sequence roundtrip (100 ops)")
    print("-" * 72)
    r3 = test_rotation_roundtrip(vsa)
    print(f"  forward then inverse ({r3['n_ops']} random-slot rotations)")
    print(f"  L2 roundtrip error: {r3['roundtrip_error']:.3e}")
    print(f"  verdict: {'PASS' if r3['passed'] else 'FAIL'}")
    if not r3["passed"]:
        all_passed = False
    print()

    print("Test 4 — semantic block isolation")
    print("-" * 72)
    r4 = test_semantic_isolation(vsa)
    print(f"  slot stores + rotations do not touch semantic content")
    print(f"  L2 semantic drift: {r4['semantic_drift']:.3e}")
    print(f"  verdict: {'PASS' if r4['passed'] else 'FAIL'}")
    if not r4["passed"]:
        all_passed = False
    print()

    print("=" * 72)
    print(f"Overall: {'ALL PASS' if all_passed else 'AT LEAST ONE FAIL'}")
    print("=" * 72)
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
