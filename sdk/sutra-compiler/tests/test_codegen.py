"""Tests for the canonical Sutra codegen.

Covers the 2026-04-22 "get GPU ready" work: fused bundle-of-binds,
vectorized argmax_cosine, disk-cache plumbing for embeddings, and
zero-vector absorption through the simplifier-then-codegen pipeline.
The tests assert on emitted Python — they don't exec it — so they
run without numpy or Ollama available. An end-to-end run lives in
examples/_smoke_test.py (requires Ollama).
"""
from __future__ import annotations

import unittest

from sutra_compiler.codegen import translate_module
from sutra_compiler.lexer import Lexer
from sutra_compiler.parser import Parser


def _compile(src: str) -> str:
    lexer = Lexer(src, file="<test>")
    tokens = lexer.tokenize()
    parser = Parser(tokens, file="<test>", diagnostics=lexer.diagnostics)
    module = parser.parse_module()
    assert not lexer.diagnostics.has_errors(), list(lexer.diagnostics)
    py_src = translate_module(module)
    # Always verify the emitted Python parses.
    compile(py_src, "<generated>", "exec")
    return py_src


class TestBundleOfBindsFusion(unittest.TestCase):
    """When every arg to bundle() is a bind() call, the codegen emits
    a single fused bundle_of_binds call on the runtime — one N-way
    batched op instead of N sequential binds plus a bundle."""

    def test_three_bind_bundle_fuses(self):
        src = (
            "vector r1 = basis_vector(\"r1\");\n"
            "vector r2 = basis_vector(\"r2\");\n"
            "vector r3 = basis_vector(\"r3\");\n"
            "vector f1 = basis_vector(\"f1\");\n"
            "vector f2 = basis_vector(\"f2\");\n"
            "vector f3 = basis_vector(\"f3\");\n"
            "function vector main() {\n"
            "  return bundle(bind(r1, f1), bind(r2, f2), bind(r3, f3));\n"
            "}\n"
        )
        py = _compile(src)
        self.assertIn(
            "_VSA.bundle_of_binds((r1, f1), (r2, f2), (r3, f3))", py
        )
        # The sequential form must not appear for this program.
        self.assertNotIn(
            "_VSA.bundle(_VSA.bind(r1, f1)", py
        )

    def test_mixed_bundle_does_not_fuse(self):
        # bundle(bind(r, f), raw_vec) keeps the standard bundle emission
        # because not every arg is a bind call.
        src = (
            "vector r = basis_vector(\"r\");\n"
            "vector f = basis_vector(\"f\");\n"
            "vector x = basis_vector(\"x\");\n"
            "function vector main() { return bundle(bind(r, f), x); }\n"
        )
        py = _compile(src)
        # `bundle_of_binds` always appears in the runtime class; check that
        # it's not called at the user-code level.
        self.assertNotIn("_VSA.bundle_of_binds(", _strip_runtime(py))
        self.assertIn("_VSA.bundle(_VSA.bind(r, f), x)", py)

    def test_single_arg_bundle_elides_before_fusion_check(self):
        # bundle(bind(r, f)) → bind(r, f) after simplify. Fusion path
        # shouldn't engage for a 1-arg bundle.
        src = (
            "vector r = basis_vector(\"r\");\n"
            "vector f = basis_vector(\"f\");\n"
            "function vector main() { return bundle(bind(r, f)); }\n"
        )
        py = _compile(src)
        self.assertNotIn("_VSA.bundle_of_binds(", _strip_runtime(py))
        self.assertIn("_VSA.bind(r, f)", py)

    def test_runtime_defines_bundle_of_binds(self):
        # The runtime class must include the fused primitive so the
        # emitted call resolves. Check on any trivial program.
        src = "function vector main() { return basis_vector(\"x\"); }\n"
        py = _compile(src)
        self.assertIn("def bundle_of_binds(self, *role_filler_pairs):", py)
        # And the einsum that makes it a single batched op.
        self.assertIn("_np.einsum('nij,nj->ni'", py)


class TestVectorizedArgmaxCosine(unittest.TestCase):
    """_argmax_cosine in the emitted module stacks candidates and
    matmuls, instead of Python-looping over _VSA.similarity."""

    def test_argmax_cosine_emits_vectorized_form(self):
        src = (
            "vector a = basis_vector(\"a\");\n"
            "vector b = basis_vector(\"b\");\n"
            "vector c = basis_vector(\"c\");\n"
            "vector q = basis_vector(\"q\");\n"
            "function vector main() {\n"
            "  return argmax_cosine(q, [a, b, c]);\n"
            "}\n"
        )
        py = _compile(src)
        # Stacked candidates + matmul + argmax.
        self.assertIn("_np.stack([_np.asarray(c, dtype=_np.float64) "
                      "for c in candidates])", py)
        self.assertIn("scores = (M @ q) / (safe_rn * q_norm)", py)
        self.assertIn("_np.argmax(scores)", py)

    def test_vector_map_lookup_vectorized_fallback(self):
        # Maps with vector keys get _vector_map_lookup; the cosine
        # fallback path must also be vectorized.
        src = "function vector main() { return basis_vector(\"x\"); }\n"
        py = _compile(src)
        self.assertIn(
            "keys = _np.stack([_np.asarray(k, dtype=_np.float64) "
            "for k, _ in pairs])", py
        )
        self.assertIn("scores = (keys @ q) / (safe_rn * q_norm)", py)


class TestZeroVectorThroughSimplifier(unittest.TestCase):
    """Simplifier emits `zero_vector()`; codegen routes it through the
    builtin table to `_VSA.zero_vector()`. Absorption into bundle and
    + / - collapses at the AST layer, so the emitted Python is clean."""

    def test_displacement_of_self_emits_zero_vector(self):
        src = (
            "vector x = basis_vector(\"x\");\n"
            "function vector main() { return displacement(x, x); }\n"
        )
        py = _compile(src)
        self.assertIn("_VSA.zero_vector()", py)
        # The literal `x - x` subtract should NOT survive the simplifier.
        self.assertNotIn("(x - x)", py)

    def test_bundle_with_self_displacement_drops_it(self):
        # displacement(x, x) → zero_vector(); bundle(a, zero) → a.
        # The final emission is just `a`, with no surviving zero.
        src = (
            "vector a = basis_vector(\"a\");\n"
            "vector x = basis_vector(\"x\");\n"
            "function vector main() {"
            " return bundle(a, displacement(x, x)); }\n"
        )
        py = _compile(src)
        # No zero_vector, no bundle call for main's return.
        self.assertNotIn("zero_vector()", _strip_runtime(py))
        self.assertNotIn(
            "_VSA.bundle(", _strip_runtime(py)
        )

    def test_runtime_defines_zero_vector(self):
        src = "function vector main() { return basis_vector(\"x\"); }\n"
        py = _compile(src)
        self.assertIn("def zero_vector(self):", py)


class TestEmbeddingDiskCache(unittest.TestCase):
    """Runtime cache plumbing: load from disk at __init__, write back
    after embed / embed_batch. Invalidation is implicit via the
    (model, dim) filename key."""

    def test_init_loads_disk_cache(self):
        src = "function vector main() { return basis_vector(\"x\"); }\n"
        py = _compile(src)
        self.assertIn("self._load_disk_cache()", py)
        self.assertIn("def _load_disk_cache(self):", py)

    def test_cache_path_uses_model_and_dim(self):
        src = "function vector main() { return basis_vector(\"x\"); }\n"
        py = _compile(src)
        # Filename template for cache entries — (model, total dim) keyed
        # so changing either produces a different file. Uses `self.dim`
        # (= semantic_dim + synthetic_dim after the 2026-04-23 extended-
        # state-vector change), so extending or shrinking the synthetic
        # block invalidates the cache automatically.
        self.assertIn("f'{_safe_model}-d{self.dim}.npz'", py)

    def test_embed_writes_back_to_disk(self):
        src = "function vector main() { return basis_vector(\"x\"); }\n"
        py = _compile(src)
        # Both the single and batched embed paths persist new vectors.
        # Count: at least one inside embed, one inside embed_batch.
        self.assertGreaterEqual(py.count("self._write_disk_cache()"), 2)

    def test_write_is_atomic(self):
        src = "function vector main() { return basis_vector(\"x\"); }\n"
        py = _compile(src)
        # Tempfile + os.replace pattern: a partial write can't corrupt
        # the cache.
        self.assertIn("_tempfile.mkstemp(", py)
        self.assertIn("_os.replace(tmp, self._cache_path)", py)

    def test_cache_load_tolerates_missing_file(self):
        src = "function vector main() { return basis_vector(\"x\"); }\n"
        py = _compile(src)
        self.assertIn(
            "if not _os.path.exists(self._cache_path):", py
        )

    def test_cache_load_tolerates_corrupt_file(self):
        src = "function vector main() { return basis_vector(\"x\"); }\n"
        py = _compile(src)
        # Corrupt cache must not crash module init.
        self.assertIn("except Exception:", py)
        self.assertIn("self._codebook = {}", py)


class TestVectorAccessors(unittest.TestCase):
    """Surface-level `v.component(i)`, `v.semantic(i)`, `v.synthetic(i)`
    lower to `_VSA.component(v, i)` etc. The runtime methods return a
    Python float so the value can print or feed back into the program.
    Purpose is introspection / debugging / teaching — not algebra.
    """

    def test_component_method_lowers_to_vsa_call(self):
        src = (
            "vector x = basis_vector(\"x\");\n"
            "function fuzzy main() { return x.component(3); }\n"
        )
        py = _compile(src)
        self.assertIn("_VSA.component(x, 3)", py)
        # The naive pass-through `x.component(3)` must NOT appear in
        # emitted user code — numpy arrays have no such method.
        self.assertNotIn("x.component(3)", _strip_runtime(py))

    def test_semantic_method_lowers(self):
        src = (
            "vector x = basis_vector(\"x\");\n"
            "function fuzzy main() { return x.semantic(0); }\n"
        )
        py = _compile(src)
        self.assertIn("_VSA.semantic(x, 0)", py)

    def test_synthetic_method_lowers(self):
        src = (
            "vector x = basis_vector(\"x\");\n"
            "function fuzzy main() { return x.synthetic(0); }\n"
        )
        py = _compile(src)
        self.assertIn("_VSA.synthetic(x, 0)", py)

    def test_runtime_defines_accessors(self):
        src = "function vector main() { return basis_vector(\"x\"); }\n"
        py = _compile(src)
        self.assertIn("def component(self, v, i):", py)
        self.assertIn("def semantic(self, v, i):", py)
        self.assertIn("def synthetic(self, v, i):", py)
        # Synthetic indexing offsets past the semantic block.
        self.assertIn("v[self.semantic_dim + idx]", py)


class TestCanonicalAxes(unittest.TestCase):
    """First three synthetic axes carry designated semantics:
    synthetic[0] = real, synthetic[1] = imag, synthetic[2] = truth.
    Accessor methods `.real()` / `.imag()` / `.truth()` and constructors
    `real_number(x)` / `complex_number(re, im)` / `truth_value(t)` lower
    to the appropriate runtime methods. Per the 2026-04-23 design.
    """

    def test_real_method_lowers_to_vsa_call(self):
        src = (
            "vector x = basis_vector(\"x\");\n"
            "function fuzzy main() { return x.real(); }\n"
        )
        py = _compile(src)
        self.assertIn("_VSA.real(x)", py)

    def test_imag_method_lowers_to_vsa_call(self):
        src = (
            "vector x = basis_vector(\"x\");\n"
            "function fuzzy main() { return x.imag(); }\n"
        )
        py = _compile(src)
        self.assertIn("_VSA.imag(x)", py)

    def test_truth_method_lowers_to_vsa_call(self):
        src = (
            "vector x = basis_vector(\"x\");\n"
            "function fuzzy main() { return x.truth(); }\n"
        )
        py = _compile(src)
        self.assertIn("_VSA.truth(x)", py)

    def test_real_number_constructor_lowers(self):
        src = (
            "function vector main() { return real_number(3.5); }\n"
        )
        py = _compile(src)
        self.assertIn("_VSA.make_real(3.5)", py)

    def test_complex_number_constructor_lowers(self):
        src = (
            "function vector main() { return complex_number(3.0, 2.0); }\n"
        )
        py = _compile(src)
        self.assertIn("_VSA.make_complex(3.0, 2.0)", py)

    def test_truth_value_constructor_lowers(self):
        src = (
            "function vector main() { return truth_value(0.9); }\n"
        )
        py = _compile(src)
        self.assertIn("_VSA.make_truth(0.9)", py)

    def test_runtime_defines_canonical_axis_constants(self):
        src = "function vector main() { return basis_vector(\"x\"); }\n"
        py = _compile(src)
        # The allocation is named at class scope so the layout is legible.
        self.assertIn("AXIS_REAL = 0", py)
        self.assertIn("AXIS_IMAG = 1", py)
        self.assertIn("AXIS_TRUTH = 2", py)

    def test_runtime_defines_canonical_methods(self):
        src = "function vector main() { return basis_vector(\"x\"); }\n"
        py = _compile(src)
        self.assertIn("def real(self, v):", py)
        self.assertIn("def imag(self, v):", py)
        self.assertIn("def truth(self, v):", py)
        self.assertIn("def make_real(self, x):", py)
        self.assertIn("def make_complex(self, re, im):", py)
        self.assertIn("def make_truth(self, t):", py)


class TestExtendedStateVector(unittest.TestCase):
    """Runtime vectors are `[semantic (semantic_dim) | synthetic (synthetic_dim)]`.
    The synthetic block is reserved computational space that starts at zero
    and is preserved by the block-diagonal rotation used for bind/unbind.
    Design doc: planning/findings/2026-04-21-extended-state-and-rotation-binding.md.
    """

    def test_vsa_constructed_with_both_subspaces(self):
        src = "function vector main() { return basis_vector(\"x\"); }\n"
        py = _compile(src)
        # The instantiation site names both subspaces explicitly — so a
        # reader of the generated code can see the split without reading
        # the runtime class. Defaults: nomic semantic=768, synthetic=100.
        self.assertIn("semantic_dim=768", py)
        self.assertIn("synthetic_dim=100", py)

    def test_runtime_class_carries_both_dims(self):
        src = "function vector main() { return basis_vector(\"x\"); }\n"
        py = _compile(src)
        # _NumpyVSA stores semantic_dim and synthetic_dim separately; the
        # total dim is their sum.
        self.assertIn("self.semantic_dim = semantic_dim", py)
        self.assertIn("self.synthetic_dim = synthetic_dim", py)
        self.assertIn("self.dim = semantic_dim + synthetic_dim", py)

    def test_embed_emits_synthetic_zero_block(self):
        src = "function vector main() { return basis_vector(\"x\"); }\n"
        py = _compile(src)
        # The critical invariant: embed() appends `_np.zeros(self.synthetic_dim)`
        # to the semantic block, so every embedded vector has zeros in its
        # synthetic tail.
        self.assertIn(
            "v = _np.concatenate([v, _np.zeros(self.synthetic_dim)])", py
        )

    def test_rotation_is_block_diagonal(self):
        src = "function vector main() { return basis_vector(\"x\"); }\n"
        py = _compile(src)
        # _rotation_for draws a Haar rotation over the semantic block and
        # places it inside an identity of the full dim. Bind/unbind therefore
        # leave the synthetic block fixed.
        self.assertIn(
            "A = rng.randn(self.semantic_dim, self.semantic_dim)", py
        )
        self.assertIn("Q = _np.eye(self.dim, dtype=_np.float64)", py)
        self.assertIn(
            "Q[:self.semantic_dim, :self.semantic_dim] = Q_sem", py
        )


def _strip_runtime(py: str) -> str:
    """Drop the `class _NumpyVSA:` and its body — anything before the
    `_VSA = _NumpyVSA(` line is generic prelude. Tests that want to
    check the emitted user-function bodies pass the result through
    this helper to avoid accidental matches against the prelude's
    own uses of `zero_vector()` etc.
    """
    marker = "_VSA = _NumpyVSA("
    idx = py.find(marker)
    if idx < 0:
        return py
    return py[idx:]


if __name__ == "__main__":
    unittest.main()
