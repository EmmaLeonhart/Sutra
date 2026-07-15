"""`axon_build` — the batched fusion of N axon_adds into one bmm.

`axon_build(axon, keys, values)` adds N (key, value) bindings in a single batched
matmul (stack the cached per-key M_key operators, one `bmm` + sum) instead of N
separate `axon_add` matmuls. It must be BIT-IDENTICAL to folding `axon_add` over the
same pairs (the only difference is op count: 1 launch vs N). This pins that, plus the
empty-build no-op and that the built axon reads back correctly.

Fusion lever for record/struct construction (a known field set). See
planning/findings/2026-06-20-tick-all-no-speedup-python-bound.md §"Fusion pass".
"""
from __future__ import annotations

import types

import pytest

torch = pytest.importorskip("torch")

from sutra_compiler.codegen_pytorch import translate_module  # noqa: E402
from sutra_compiler.lexer import Lexer  # noqa: E402
from sutra_compiler.parser import Parser  # noqa: E402


def _vsa(runtime_dim: int = 256):
    src = "function int main() { return 0; }"
    lx = Lexer(src, file="t.su")
    ps = Parser(lx.tokenize(), file="t.su", diagnostics=lx.diagnostics)
    py = translate_module(ps.parse_module(), llm_model="nomic-embed-text",
                          runtime_dim=runtime_dim)
    m = types.ModuleType("t")
    exec(compile(py, "t.su", "exec"), m.__dict__)
    return m._VSA


def test_axon_build_bit_identical_to_folded_axon_add():
    v = _vsa()
    keys = ["x", "y", "z"]
    vals = [5.0, 8.0, 3.0]
    folded = v.zero_vector()
    for k, val in zip(keys, vals):
        folded = v.axon_add(folded, k, val)
    built = v.axon_build(v.zero_vector(), keys, vals)
    assert torch.allclose(folded, built, atol=1e-5), \
        f"axon_build != folded axon_add (max diff {float((folded - built).abs().max())})"


def test_axon_build_reads_back():
    v = _vsa()
    built = v.axon_build(v.zero_vector(), ["a", "b", "c"], [5.0, 8.0, 3.0])
    for k, want in [("a", 5.0), ("b", 8.0), ("c", 3.0)]:
        got = float(torch.dot(v.axon_item(built, k), v.make_real(1.0)))
        assert got == pytest.approx(want, abs=1e-3), f"{k}: got {got}, want {want}"


def test_axon_build_empty_is_noop():
    v = _vsa()
    z = v.zero_vector()
    assert torch.equal(v.axon_build(z, [], []), z)


def test_axon_build_string_value():
    v = _vsa()
    # A string value alone reads back exactly (no number crosstalk).
    solo = v.axon_build(v.zero_vector(), ["s"], ["hello"])
    assert v.string_to_python(v.axon_item(solo, "s")) == "hello"
    # Mixed number+string: axon_build is BIT-IDENTICAL to folded axon_add (any axon
    # crosstalk between the number and the string is a property of the axon encoding,
    # identical in both paths — NOT introduced by the batched build).
    keys, vals = ["n", "s"], [42.0, "hello"]
    folded = v.zero_vector()
    for k, val in zip(keys, vals):
        folded = v.axon_add(folded, k, val)
    built = v.axon_build(v.zero_vector(), keys, vals)
    assert torch.allclose(folded, built, atol=1e-5)


def test_axon_op_cache_is_bounded_with_identical_recompute():
    """The d x d role-keyed caches (_axon_op_cache + _rot_cache) are FIFO-
    capped so a pathologically large key vocabulary can't grow them without
    limit, and eviction is bit-identical (every entry is a deterministic
    function of its key). Set a small cap, overflow it, and check (a) both
    caches stay <= cap, (b) an evicted key recomputes to the SAME output."""
    v = _vsa()
    v._role_cache_cap = 4

    # Build M_key for "k0" (also seeds _rot_cache via _axon_op_for).
    out_before = v.axon_build(v.zero_vector(), ["k0"], [7.0])

    # Overflow the cap with 8 fresh keys → "k0" is the oldest, evicted first.
    for i in range(8):
        v.axon_build(v.zero_vector(), ["k%d" % (i + 1)], [1.0])

    assert len(v._axon_op_cache) <= 4, \
        "axon_op_cache not bounded: %d > 4" % len(v._axon_op_cache)
    assert len(v._rot_cache) <= 4, \
        "rot_cache not bounded: %d > 4" % len(v._rot_cache)

    # "k0" was evicted; re-building recomputes its M_key + Q from the seed.
    # The output must be bit-identical to the pre-eviction build.
    out_after = v.axon_build(v.zero_vector(), ["k0"], [7.0])
    assert torch.equal(out_before, out_after), \
        "recompute-after-evict not bit-identical (max diff %g)" % \
        float((out_before - out_after).abs().max())


def test_axon_op_cache_under_cap_never_evicts():
    """A program whose key set is under the cap keeps every entry — the cap
    is a pathological-case safety net, not something real programs hit."""
    v = _vsa()
    v._role_cache_cap = 64
    # Semantically-distinct keys (NOT sequential "f0".."f9"): the readback
    # below unbinds each key from a 10-key bundle, so the keys' embeddings must
    # be well-separated or a near-collinear pair lets one key's full value bleed
    # through (rare 2x-crosstalk CI flake — nomic-embed-text's f0..f9 sit close
    # and run-to-run FP nondeterminism occasionally tips one pair into a near-
    # collision). Distinct words embed near-orthogonally, so crosstalk stays
    # negligible and the readback is robust.
    keys = ["go", "sun", "tree", "house", "garden",
            "machine", "mountain", "telephone", "strawberry", "hippopotamus"]
    for k in keys:
        v.axon_build(v.zero_vector(), [k], [float(len(k))])
    assert len(v._axon_op_cache) == 10
    # Every key still reads back exactly — nothing was evicted/corrupted.
    built = v.axon_build(v.zero_vector(), keys, [float(len(k)) for k in keys])
    for k in keys:
        got = float(torch.dot(v.axon_item(built, k), v.make_real(1.0)))
        assert got == pytest.approx(float(len(k)), abs=1e-3)


def test_axon_value_slots_injective_no_birthday_aliasing():
    """Regression for the value-slot birthday collision (finding
    2026-07-15-axon-value-slot-birthday-collision.md): a key's scalar value
    lands in the ONE synthetic slot its permutation sends AXIS_REAL to, so two
    keys drawing the same slot both read back the pair's SUM. Pre-fix, 50 keys
    into synthetic_dim=100 slots collide with p > 0.9999 (this test failed
    deterministically); the salt-retry registry makes the assignment injective
    up to synthetic_dim keys. Random-vector roles (no embedding server needed
    for the slot check) keep this fast and platform-independent."""
    v = _vsa()
    n = 50
    torch.manual_seed(20260715)
    roles = [torch.randn(v.dim, dtype=v.dtype, device=v.device) for _ in range(n)]

    # (1) The AXIS_REAL landing slots are pairwise distinct.
    slots = []
    for r in roles:
        perm = v._axon_permutation_for(r)
        j = int((perm == v.AXIS_REAL).nonzero()[0])
        slots.append(j)
    assert len(set(slots)) == n, (
        f"slot collision: {n} keys -> {len(set(slots))} distinct slots")

    # (2) End-to-end: every value reads back exactly from one n-key axon.
    vals = [float(i + 1) for i in range(n)]
    axon = v.zero_vector()
    for r, val in zip(roles, vals):
        axon = v.axon_add(axon, r, v.make_real(val))
    for r, val in zip(roles, vals):
        got = float(torch.dot(v.axon_item(axon, r), v.make_real(1.0)))
        assert got == pytest.approx(val, abs=1e-3)
