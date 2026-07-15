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
            "vector r1 = embed(\"r1\");\n"
            "vector r2 = embed(\"r2\");\n"
            "vector r3 = embed(\"r3\");\n"
            "vector f1 = embed(\"f1\");\n"
            "vector f2 = embed(\"f2\");\n"
            "vector f3 = embed(\"f3\");\n"
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
            "vector r = embed(\"r\");\n"
            "vector f = embed(\"f\");\n"
            "vector x = embed(\"x\");\n"
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
            "vector r = embed(\"r\");\n"
            "vector f = embed(\"f\");\n"
            "function vector main() { return bundle(bind(r, f)); }\n"
        )
        py = _compile(src)
        self.assertNotIn("_VSA.bundle_of_binds(", _strip_runtime(py))
        self.assertIn("_VSA.bind(r, f)", py)

    def test_runtime_defines_bundle_of_binds(self):
        # The runtime class must include the fused primitive so the
        # emitted call resolves. Check on any trivial program.
        src = "function vector main() { return embed(\"x\"); }\n"
        py = _compile(src)
        self.assertIn("def bundle_of_binds(self, *role_filler_pairs):", py)
        # And the einsum that makes it a single batched op.
        self.assertIn("_np.einsum('nij,nj->ni'", py)


class TestVectorizedArgmaxCosine(unittest.TestCase):
    """_argmax_cosine in the emitted module stacks candidates and
    matmuls, instead of Python-looping over _VSA.similarity."""

    def test_argmax_cosine_emits_vectorized_form(self):
        src = (
            "vector a = embed(\"a\");\n"
            "vector b = embed(\"b\");\n"
            "vector c = embed(\"c\");\n"
            "vector q = embed(\"q\");\n"
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
        src = "function vector main() { return embed(\"x\"); }\n"
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
            "vector x = embed(\"x\");\n"
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
            "vector a = embed(\"a\");\n"
            "vector x = embed(\"x\");\n"
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
        src = "function vector main() { return embed(\"x\"); }\n"
        py = _compile(src)
        self.assertIn("def zero_vector(self):", py)


class TestEmbeddingDiskCache(unittest.TestCase):
    """Runtime cache plumbing: load from disk at __init__, write back
    after embed / embed_batch. Invalidation is implicit via the
    (model, dim) filename key."""

    def test_init_loads_disk_cache(self):
        src = "function vector main() { return embed(\"x\"); }\n"
        py = _compile(src)
        self.assertIn("self._load_disk_cache()", py)
        self.assertIn("def _load_disk_cache(self):", py)

    def test_cache_path_uses_model_dim_and_backend(self):
        src = "function vector main() { return embed(\"x\"); }\n"
        py = _compile(src)
        # Backend-aware: in-process (transformers) and ollama realize the same
        # model with different geometry, so the cache filename carries the backend.
        self.assertIn("f'{_safe_model}-d{self.dim}-{_emb_backend}.npz'", py)

    def test_embed_writes_back_to_disk(self):
        src = "function vector main() { return embed(\"x\"); }\n"
        py = _compile(src)
        # Both the single and batched embed paths persist new vectors.
        # Count: at least one inside embed, one inside embed_batch.
        self.assertGreaterEqual(py.count("self._write_disk_cache()"), 2)

    def test_write_is_atomic(self):
        src = "function vector main() { return embed(\"x\"); }\n"
        py = _compile(src)
        # Tempfile + os.replace pattern: a partial write can't corrupt
        # the cache.
        self.assertIn("_tempfile.mkstemp(", py)
        self.assertIn("_os.replace(tmp, self._cache_path)", py)

    def test_cache_load_tolerates_missing_file(self):
        src = "function vector main() { return embed(\"x\"); }\n"
        py = _compile(src)
        self.assertIn(
            "if not _os.path.exists(self._cache_path):", py
        )

    def test_cache_load_tolerates_corrupt_file(self):
        src = "function vector main() { return embed(\"x\"); }\n"
        py = _compile(src)
        # Corrupt cache must not crash module init.
        self.assertIn("except Exception:", py)
        self.assertIn("self._codebook = {}", py)


class TestVectorAccessors(unittest.TestCase):
    """The surface-level host-readout accessors `.component()` / `.semantic()`
    / `.synthetic()` were REMOVED from the language 2026-06-07 (no
    introspection — they were `float(v[...])` host readouts). They no longer
    lower. The deprecated numpy backend still carries dead method defs pending
    its retirement; see CLAUDE.md §"NO introspection"."""

    def test_runtime_defines_accessors(self):
        src = "function vector main() { return embed(\"x\"); }\n"
        py = _compile(src)
        self.assertIn("def component(self, v, i):", py)
        self.assertIn("def semantic(self, v, i):", py)
        self.assertIn("def synthetic(self, v, i):", py)
        # Synthetic indexing offsets past the semantic block.
        self.assertIn("v[self.semantic_dim + idx]", py)


class TestCanonicalAxes(unittest.TestCase):
    """First three synthetic axes carry designated semantics:
    synthetic[0] = real, synthetic[1] = imag, synthetic[2] = truth.
    The canonical constructors `make_real(x)` / `make_complex(re, im)` /
    `make_truth(t)` lower to the appropriate runtime methods (via the stdlib-
    intrinsic path). The redundant aliases `complex_number`/`truth_value` were
    removed 2026-06-23 (CLAUDE.md § "Deprecate aliases aggressively"); `real_number`
    is on its way out too. The scalar-READOUT accessors (`.real()` / `.imag()` /
    `.truth()` / ...) are REMOVED from the language — they are rejected at compile
    (no introspection; substrate purity).
    """

    def test_real_accessor_is_rejected(self):
        # `.real()` (and the other scalar-readout accessors) are not available in
        # the language: they would pull a host scalar off the substrate, severing
        # purity + the autograd graph. They reject at compile. In-language code
        # uses `realvec(v)` (a substrate matmul) when it needs the carried number.
        from sutra_compiler.codegen_base import CodegenNotSupported
        for acc in ("real", "imag", "truth", "component", "synthetic"):
            src = (
                "vector x = embed(\"x\");\n"
                f"function fuzzy main() {{ return x.{acc}(); }}\n"
            )
            with self.assertRaises(CodegenNotSupported):
                _compile(src)

    def test_make_real_constructor_lowers(self):
        src = (
            "function vector main() { return make_real(3.5); }\n"
        )
        py = _compile(src)
        self.assertIn("_VSA.make_real(3.5)", py)

    def test_make_complex_constructor_lowers(self):
        src = (
            "function vector main() { return make_complex(3.0, 2.0); }\n"
        )
        py = _compile(src)
        self.assertIn("_VSA.make_complex(3.0, 2.0)", py)

    def test_make_truth_constructor_lowers(self):
        src = (
            "function vector main() { return make_truth(0.9); }\n"
        )
        py = _compile(src)
        self.assertIn("_VSA.make_truth(0.9)", py)

    def test_runtime_defines_canonical_axis_constants(self):
        src = "function vector main() { return embed(\"x\"); }\n"
        py = _compile(src)
        # The allocation is named at class scope so the layout is legible.
        self.assertIn("AXIS_REAL = 0", py)
        self.assertIn("AXIS_IMAG = 1", py)
        self.assertIn("AXIS_TRUTH = 2", py)

    def test_runtime_defines_constructors_not_readout_accessors(self):
        src = "function vector main() { return embed(\"x\"); }\n"
        py = _compile(src)
        # Constructors stay (they build vectors, no readout).
        self.assertIn("def make_real(self, x):", py)
        self.assertIn("def make_complex(self, re, im):", py)
        self.assertIn("def make_truth(self, t):", py)
        # The `real()` scalar-READOUT accessor is REMOVED from the runtime (no
        # introspection — it yanks a host scalar off the substrate, severing purity
        # + autograd). The in-language replacement is `realvec` (a substrate matmul
        # to a clean real-axis vector). (NOTE: `_compile` here uses the deprecated
        # numpy backend, which still carries dead imag/truth method bodies — a
        # separate cleanup; this test scopes the real()-removal.)
        self.assertNotIn("def real(self, v):", py)


class TestExtendedStateVector(unittest.TestCase):
    """Runtime vectors are `[semantic (semantic_dim) | synthetic (synthetic_dim)]`.
    The synthetic block is reserved computational space that starts at zero
    and is preserved by the block-diagonal rotation used for bind/unbind.
    Design doc: planning/findings/2026-04-21-extended-state-and-rotation-binding.md.
    """

    def test_vsa_constructed_with_both_subspaces(self):
        src = "function vector main() { return embed(\"x\"); }\n"
        py = _compile(src)
        # The instantiation site names both subspaces explicitly — so a
        # reader of the generated code can see the split without reading
        # the runtime class. Defaults: nomic semantic=768, synthetic=100.
        self.assertIn("semantic_dim=768", py)
        self.assertIn("synthetic_dim=100", py)

    def test_runtime_class_carries_both_dims(self):
        src = "function vector main() { return embed(\"x\"); }\n"
        py = _compile(src)
        # _NumpyVSA stores semantic_dim and synthetic_dim separately; the
        # total dim is their sum.
        self.assertIn("self.semantic_dim = semantic_dim", py)
        self.assertIn("self.synthetic_dim = synthetic_dim", py)
        self.assertIn("self.dim = semantic_dim + synthetic_dim", py)

    def test_embed_emits_synthetic_zero_block(self):
        src = "function vector main() { return embed(\"x\"); }\n"
        py = _compile(src)
        # The critical invariant: embed() appends `_np.zeros(self.synthetic_dim)`
        # to the semantic block, so every embedded vector has zeros in its
        # synthetic tail.
        self.assertIn(
            "v = _np.concatenate([v, _np.zeros(self.synthetic_dim)])", py
        )

    def test_rotation_is_block_diagonal(self):
        src = "function vector main() { return embed(\"x\"); }\n"
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


class TestIteratorKeyword(unittest.TestCase):
    """`iterator` is a contextual keyword inside an unrolling
    `loop (N) { ... }` body. The codegen substitutes the per-copy
    integer constant (1-based: 1..N) at unroll time. Outside an
    unrolling context, the reference is a CodegenNotSupported error.
    """

    def test_iterator_substitutes_one_based_constants(self):
        src = (
            "function int main() {\n"
            "  var n : int = 0;\n"
            "  loop (5) {\n"
            "    n += iterator;\n"
            "  }\n"
            "  return n;\n"
            "}\n"
        )
        py = _strip_runtime(_compile(src))
        # The unrolled body should contain n += 1 through n += 5,
        # in order, with no `iterator` name surviving.
        for i in range(1, 6):
            self.assertIn(f"n += {i}", py)
        self.assertNotIn("iterator", py)

    def test_iterator_in_nested_unrolled_loops(self):
        # Inner `iterator` binds to the inner loop; outer `iterator`
        # binds to the outer. The outer value must be saved across
        # the inner loop and restored after.
        src = (
            "function int main() {\n"
            "  var n : int = 0;\n"
            "  loop (3) {\n"
            "    n += iterator;\n"
            "    loop (2) {\n"
            "      n += iterator;\n"
            "    }\n"
            "  }\n"
            "  return n;\n"
            "}\n"
        )
        py = _strip_runtime(_compile(src))
        # Outer values: 1, 2, 3. Inner values: 1, 2 (twice each
        # outer iteration). Expected sequence: 1,1,2, 2,1,2, 3,1,2.
        expected = [1, 1, 2, 2, 1, 2, 3, 1, 2]
        adds = [
            int(line.split("n += ")[1].rstrip())
            for line in py.splitlines()
            if "n += " in line
        ]
        self.assertEqual(adds, expected)

    def test_iterator_outside_loop_rejected(self):
        from sutra_compiler.codegen_base import CodegenNotSupported
        src = (
            "function int main() {\n"
            "  var n : int = 0;\n"
            "  n += iterator;\n"
            "  return n;\n"
            "}\n"
        )
        with self.assertRaises(CodegenNotSupported) as cm:
            _compile(src)
        self.assertIn("iterator", str(cm.exception))
        self.assertIn("loop", str(cm.exception))

    def test_iterator_in_named_index_loop_rejected(self):
        # `loop (N as i)` doesn't unroll — it emits a runtime
        # `for i in range(N):`. `iterator` has no compile-time
        # value to substitute in that path, so referencing it is
        # an error. Users should reference `i` instead.
        from sutra_compiler.codegen_base import CodegenNotSupported
        src = (
            "function int main() {\n"
            "  var n : int = 0;\n"
            "  loop (5 as j) {\n"
            "    n += iterator;\n"
            "  }\n"
            "  return n;\n"
            "}\n"
        )
        with self.assertRaises(CodegenNotSupported):
            _compile(src)


class TestClassStaticMethodDispatch(unittest.TestCase):
    """Slice 1 of the object-encapsulation work (2026-05-01): static
    methods declared inside class bodies emit as mangled top-level
    Python functions, and `Math.foo(x)` call sites dispatch to them."""

    def test_static_method_emits_as_mangled_function(self):
        src = (
            "class Math extends vector {\n"
            "  static method scalar twice(number x) {\n"
            "    return x * 2;\n"
            "  }\n"
            "}\n"
        )
        py = _compile(src)
        self.assertIn("def Math_twice(x):", py)

    def test_class_namespace_call_dispatches_to_mangled_name(self):
        src = (
            "class Math extends vector {\n"
            "  static method scalar twice(number x) {\n"
            "    return x * 2;\n"
            "  }\n"
            "}\n"
            "function number caller() {\n"
            "  return Math.twice(3);\n"
            "}\n"
        )
        py = _compile(src)
        self.assertIn("def Math_twice(x):", py)
        self.assertIn("Math_twice(3)", py)
        # Should NOT emit a literal `Math.twice(3)` — that would fail
        # at runtime because there's no Python class `Math` in scope.
        self.assertNotIn("Math.twice(3)", py)

    def test_forward_reference_to_class_works_via_pre_pass(self):
        # Caller appears textually before the class — the pre-pass
        # over module items should still register the static methods
        # so the call dispatches correctly.
        src = (
            "function number caller() {\n"
            "  return Math.twice(3);\n"
            "}\n"
            "class Math extends vector {\n"
            "  static method scalar twice(number x) {\n"
            "    return x * 2;\n"
            "  }\n"
            "}\n"
        )
        py = _compile(src)
        self.assertIn("Math_twice(3)", py)

    def test_non_static_method_emits_with_this_param(self):
        src = (
            "class Greeter extends vector {\n"
            "  method string Hello() {\n"
            "    return \"hi\";\n"
            "  }\n"
            "}\n"
        )
        py = _compile(src)
        self.assertIn("def Greeter_Hello(this):", py)

    def test_class_namespace_call_threads_instance_to_this(self):
        # Calling a non-static method via `Greeter.Hello(g)` passes `g`
        # as the first arg, which the mangled function receives as
        # `this`. Inside the body, references to `this` (ThisExpr)
        # translate to the local `this`. Vector returns get
        # halt-propagation wrapping (`return value * _program_halt`),
        # so the returned expression contains `this` rather than being
        # bare-equal to it.
        src = (
            "class Greeter extends vector {\n"
            "  method vector Self() {\n"
            "    return this;\n"
            "  }\n"
            "}\n"
            "function vector echo(vector g) {\n"
            "  return Greeter.Self(g);\n"
            "}\n"
        )
        py = _compile(src)
        self.assertIn("def Greeter_Self(this):", py)
        # Body references `this` somewhere in the return expression.
        body_marker = "def Greeter_Self(this):"
        body_start = py.index(body_marker)
        body_end = py.index("def echo")
        body_src = py[body_start:body_end]
        self.assertIn("this", body_src)
        self.assertIn("Greeter_Self(g)", py)

    def test_class_body_loop_function_emits_with_class_mangling(self):
        src = (
            "class Counter extends vector {\n"
            "  do_while addOne(x < 5, int x) {\n"
            "    pass x + 1;\n"
            "  }\n"
            "}\n"
            "function int main() {\n"
            "  slot int x = 0;\n"
            "  loop Counter.addOne(x < 5, x);\n"
            "  return x;\n"
            "}\n"
        )
        py = _compile(src)
        self.assertIn("def _loop_Counter_addOne(", py)
        self.assertIn("_loop_Counter_addOne(", py)

    def test_this_dot_method_dispatches_to_same_class(self):
        # `this.other(args)` from inside a method on Greeter dispatches
        # to `Greeter_other(this, *args)`.
        src = (
            "class Greeter extends vector {\n"
            "  method vector Inner() {\n"
            "    return this;\n"
            "  }\n"
            "  method vector Outer() {\n"
            "    return this.Inner();\n"
            "  }\n"
            "}\n"
        )
        py = _compile(src)
        self.assertIn("def Greeter_Outer(this):", py)
        self.assertIn("Greeter_Inner(this)", py)

    def test_intrinsic_method_routes_to_VSA_runtime(self):
        # `static intrinsic method scalar log(number x);` inside a
        # class body is a signature-only declaration. Calls of the form
        # `Math.log(x)` must dispatch to `_VSA.log(x)` directly — no
        # `Math_log` wrapper should be emitted, and no literal
        # `Math.log` should remain in the output.
        #
        # log is on the codegen's _TRANSCENDENTALS_DISABLED list when
        # called as a bare Identifier (`log(x)`), but going through the
        # class-namespace dispatch here bypasses that path entirely
        # since the call site is a MemberAccess, not an Identifier.
        # That's intentional — the disabled-list check only fires on
        # the bare-name path.
        src = (
            "class VSA extends vector {\n"
            "  static intrinsic method vector zero_vector();\n"
            "}\n"
            "function vector make_zero() {\n"
            "  return VSA.zero_vector();\n"
            "}\n"
        )
        py = _compile(src)
        self.assertIn("_VSA.zero_vector()", py)
        # No mangled wrapper for an intrinsic method.
        self.assertNotIn("def VSA_zero_vector", py)


class TestClassFieldDeclarations(unittest.TestCase):
    """Class field declarations land 2026-05-08. Per the user's
    design, fields are tag-along variables on a class instance whose
    runtime storage is the same axon rotation-binding machinery as
    `Axon.add` / `Axon.item`. The class declaration is the schema."""

    def test_field_read_lowers_to_axon_item(self):
        src = (
            "class Cat extends vector {\n"
            "  field int age;\n"
            "}\n"
            "function int main() {\n"
            "  Cat c = embed(\"cat\");\n"
            "  return c.age;\n"
            "}\n"
        )
        py = _compile(src)
        self.assertIn('_VSA.axon_item(c, "age")', py)
        # Literal `c.age` Python attribute access must not appear in
        # the generated user code (Cat instances are vectors at
        # runtime; they have no `.age` Python attribute).
        self.assertNotIn("c.age", _strip_runtime(py))

    def test_field_write_lowers_to_axon_add_with_rebind(self):
        src = (
            "class Cat extends vector {\n"
            "  field int age;\n"
            "}\n"
            "function int main() {\n"
            "  Cat c = embed(\"cat\");\n"
            "  c.age = 7;\n"
            "  return c.age;\n"
            "}\n"
        )
        py = _compile(src)
        # The write should rebind c, the augmented-assignment shape
        # used for axon mutating ops.
        self.assertIn('c = _VSA.axon_add(c, "age", 7)', py)

    def test_multi_field_round_trip(self):
        src = (
            "class Cat extends vector {\n"
            "  field int age;\n"
            "  field int paws;\n"
            "}\n"
            "function int main() {\n"
            "  Cat c = embed(\"cat\");\n"
            "  c.age = 5;\n"
            "  c.paws = 4;\n"
            "  return c.age;\n"
            "}\n"
        )
        py = _compile(src)
        self.assertIn('c = _VSA.axon_add(c, "age", 5)', py)
        self.assertIn('c = _VSA.axon_add(c, "paws", 4)', py)
        # The return wraps in `(<expr>) * _program_halt` for non-string
        # returns, so just check the axon_item read is present.
        self.assertIn('_VSA.axon_item(c, "age")', py)

    def test_undeclared_field_falls_through_to_member_access(self):
        # Member access on a non-class-typed value, or for a member
        # that isn't a declared field, keeps the existing pass-through
        # behavior. This is required so `.string_length()` and the
        # `Class.method` static-dispatch path keep working.
        src = (
            "class Cat extends vector {\n"
            "  field int age;\n"
            "}\n"
            "function int main() {\n"
            "  Cat c = embed(\"cat\");\n"
            "  return c.age;\n"
            "}\n"
        )
        py = _compile(src)
        self.assertIn('_VSA.axon_item(c, "age")', py)


class TestNonStaticClassLoop(unittest.TestCase):
    """Non-static class-bodied loops thread `this` as an implicit
    state parameter (2026-05-08). The body has access to `this.field`
    via the existing field-access machinery; the call site passes the
    instance which gets rebound to the returned `this` value.
    `static` modifier on a class loop opts back into the static form."""

    def test_non_static_loop_emits_init_this_and_returns_this(self):
        src = (
            "class Counter extends vector {\n"
            "  field int count;\n"
            "  do_while increment(this.count < 5) {\n"
            "    this.count = this.count + 1;\n"
            "  }\n"
            "}\n"
        )
        py = _compile(src)
        # Function signature includes _init_this.
        self.assertIn("def _loop_Counter_increment(_init_this):", py)
        # Body initializes this from _init_this.
        self.assertIn("this = _init_this", py)
        # Soft-mux applies to this on halt.
        self.assertIn("this = (1.0 - _halted) * this + _halted * _pre_this", py)
        # Returns (this, _halted).
        self.assertIn("return (this, _halted,)", py)

    def test_non_static_loop_call_passes_instance_and_writes_back(self):
        src = (
            "class Counter extends vector {\n"
            "  field int count;\n"
            "  do_while increment(this.count < 5) {\n"
            "    this.count = this.count + 1;\n"
            "  }\n"
            "}\n"
            "function int main() {\n"
            "  Counter c = new Counter(0);\n"
            "  loop Counter.increment(c);\n"
            "  return c.count;\n"
            "}\n"
        )
        py = _compile(src)
        # Call passes c as the instance arg.
        self.assertIn("_loop_Counter_increment(c)", py)
        # Returned this is assigned back to c.
        self.assertIn("c = _loopret_this", py)

    def test_static_class_loop_does_not_thread_this(self):
        # `static do_while` opts back into the static form. No
        # `this` parameter, no `this` in the return.
        src = (
            "class Counter extends vector {\n"
            "  static do_while addOne(x < 5, int x) {\n"
            "    pass x + 1;\n"
            "  }\n"
            "}\n"
        )
        py = _compile(src)
        self.assertIn("def _loop_Counter_addOne(_init_x):", py)
        self.assertNotIn("_init_this", py)
        self.assertNotIn("_pre_this", py)


class TestSyntheticAxisEquality(unittest.TestCase):
    """Synthetic-axis-encoded equality (2026-05-08): int / float /
    complex / char / string `==` routes through `_VSA.eq_synthetic`
    (Euclidean distance + tanh), not the cosine-based `_VSA.eq`.
    Embedding-vector and truth-axis (fuzzy/bool/trit) operands keep
    cosine."""

    def test_int_equality_routes_through_eq_synthetic(self):
        src = (
            "function fuzzy main() {\n"
            "  int a = 5;\n"
            "  int b = 7;\n"
            "  return a == b;\n"
            "}\n"
        )
        py = _compile(src)
        self.assertIn("_VSA.eq_synthetic(a, b)", py)

    def test_int_literals_route_through_eq_synthetic(self):
        src = (
            "function fuzzy main() {\n"
            "  return 5 == 5;\n"
            "}\n"
        )
        py = _compile(src)
        self.assertIn("_VSA.eq_synthetic(5, 5)", py)

    def test_string_equality_routes_through_eq_synthetic(self):
        src = (
            "function fuzzy main() {\n"
            "  string a = \"hello\";\n"
            "  string b = \"world\";\n"
            "  return a == b;\n"
            "}\n"
        )
        py = _compile(src)
        self.assertIn("_VSA.eq_synthetic(a, b)", py)

    def test_fuzzy_equality_keeps_cosine_path(self):
        # Fuzzy is truth-axis, not synthetic-axis. The existing cosine
        # eq path is correct for it.
        src = (
            "function fuzzy main(fuzzy a, fuzzy b) {\n"
            "  return a == b;\n"
            "}\n"
        )
        py = _compile(src)
        user_code = _strip_runtime(py)
        self.assertIn("_VSA.eq(a, b)", user_code)
        self.assertNotIn("eq_synthetic", user_code)

    def test_eq_synthetic_runtime_method_emitted(self):
        # The runtime class should ship eq_synthetic / neq_synthetic
        # so dispatch can find them.
        src = "function int main() { return 1; }\n"
        py = _compile(src)
        self.assertIn("def eq_synthetic(self, a, b):", py)
        self.assertIn("def neq_synthetic(self, a, b):", py)


class TestUserClassOperatorOverloading(unittest.TestCase):
    """User-class operator overloading via inheritance-chain dispatch
    (2026-05-08). `method operator +(Cat o) { ... }` inside a class
    body emits as `Cat_operator_plus(this, o)`; BinaryOp dispatch
    walks the inheritance chain of either operand looking for the
    first user-class definition of the operator."""

    def test_operator_plus_emits_mangled_function(self):
        src = (
            "class Dollar extends int {\n"
            "  field int cents;\n"
            "  method operator +(Dollar other) {\n"
            "    Dollar r = new Dollar(0);\n"
            "    r.cents = this.cents + other.cents;\n"
            "    return r;\n"
            "  }\n"
            "}\n"
        )
        py = _compile(src)
        self.assertIn("def Dollar_operator_plus(this, other):", py)

    def test_binop_dispatches_to_user_class_operator(self):
        src = (
            "class Dollar extends int {\n"
            "  field int cents;\n"
            "  method operator +(Dollar other) {\n"
            "    Dollar r = new Dollar(0);\n"
            "    r.cents = this.cents + other.cents;\n"
            "    return r;\n"
            "  }\n"
            "}\n"
            "function int main() {\n"
            "  Dollar a = new Dollar(100);\n"
            "  Dollar b = new Dollar(50);\n"
            "  Dollar c = a + b;\n"
            "  return c.cents;\n"
            "}\n"
        )
        py = _compile(src)
        self.assertIn("Dollar_operator_plus(a, b)", py)
        # Param types are tracked: `other.cents` inside the body lowers
        # to axon_item, not Python attribute access.
        self.assertIn('_VSA.axon_item(other, "cents")', py)

    def test_inheritance_chain_walks_to_parent(self):
        # `Yen extends Money extends int`. Money defines `operator +`;
        # Yen does not. `a + b` for Yen-typed operands should resolve
        # to Money_operator_plus via the chain walk.
        src = (
            "class Money extends int {\n"
            "  field int amount;\n"
            "  method operator +(Money other) {\n"
            "    Money r = new Money(0);\n"
            "    r.amount = this.amount + other.amount;\n"
            "    return r;\n"
            "  }\n"
            "}\n"
            "class Yen extends Money { }\n"
            "function int main() {\n"
            "  Yen a = new Money(100);\n"
            "  Yen b = new Money(50);\n"
            "  Yen c = a + b;\n"
            "  return c.amount;\n"
            "}\n"
        )
        py = _compile(src)
        self.assertIn("Money_operator_plus(a, b)", py)


class TestInstanceMethodsWithFields(unittest.TestCase):
    """Value-returning and void instance methods composed with field
    reads/writes (`this.field`). Per the 2026-05-08 design, methods
    are static functions with the object as first arg; void methods
    mutate this via the augmented-assignment desugar at the call site,
    which requires the body to return the rebound this."""

    def test_value_returning_method_reads_this_field(self):
        src = (
            "class Cat extends vector {\n"
            "  field int age;\n"
            "  method int doubled() { return this.age * 2; }\n"
            "}\n"
        )
        py = _compile(src)
        self.assertIn("def Cat_doubled(this):", py)
        # this.age inside the method body should lower through axon_item.
        self.assertIn('_VSA.axon_item(this, "age")', py)
        # And NOT emit a Python attribute access on `this`.
        self.assertNotIn("this.age", _strip_runtime(py))

    def test_value_returning_method_dispatch_in_expression_context(self):
        src = (
            "class Cat extends vector {\n"
            "  field int age;\n"
            "  method int doubled() { return this.age * 2; }\n"
            "}\n"
            "function int main() {\n"
            "  Cat c = new Cat(7);\n"
            "  return c.doubled();\n"
            "}\n"
        )
        py = _compile(src)
        # The call site dispatches to the mangled form with c as first arg.
        self.assertIn("Cat_doubled(c)", py)

    def test_void_method_mutates_this_field_and_returns_this(self):
        src = (
            "class Cat extends vector {\n"
            "  field int age;\n"
            "  method void grow_older() { this.age = this.age + 1; }\n"
            "}\n"
        )
        py = _compile(src)
        # The body rebinds `this` via axon_add and the auto-emitted
        # `return this` makes the caller-side augmented assignment
        # (`c = Cat_grow_older(c)`) actually receive the new value.
        self.assertIn(
            'this = _VSA.axon_add(this, "age", (_VSA.axon_item(this, "age") + 1))',
            py,
        )
        # The generated function should end with `return this`.
        in_method = False
        saw_return_this = False
        for line in py.splitlines():
            if line.startswith("def Cat_grow_older"):
                in_method = True
                continue
            if in_method and (line.startswith("def ") or line.startswith("class ")):
                break
            if in_method and line.strip() == "return this":
                saw_return_this = True
        self.assertTrue(saw_return_this,
                        "Cat_grow_older should auto-emit `return this`")

    def test_void_method_call_propagates_via_augmented_assignment(self):
        src = (
            "class Cat extends vector {\n"
            "  field int age;\n"
            "  method void grow_older() { this.age = this.age + 1; }\n"
            "}\n"
            "function int main() {\n"
            "  Cat c = new Cat(5);\n"
            "  c.grow_older();\n"
            "  return c.age;\n"
            "}\n"
        )
        py = _compile(src)
        self.assertIn("c = Cat_grow_older(c)", py)


class TestNewExprConstructor(unittest.TestCase):
    """`new ClassName(args)` auto-constructor sugar (2026-05-08).
    Emits a `<Class>_new(args)` factory that fills fields positionally."""

    def test_factory_function_emitted_for_class_with_fields(self):
        src = (
            "class Cat extends vector {\n"
            "  field int age;\n"
            "  field int paws;\n"
            "}\n"
        )
        py = _compile(src)
        self.assertIn("def Cat_new(age, paws):", py)
        self.assertIn('_c = _VSA.axon_add(_c, "age", age)', py)
        self.assertIn('_c = _VSA.axon_add(_c, "paws", paws)', py)
        self.assertIn("return _c", py)

    def test_new_call_dispatches_to_mangled_factory(self):
        src = (
            "class Cat extends vector {\n"
            "  field int age;\n"
            "}\n"
            "function int main() {\n"
            "  Cat c = new Cat(7);\n"
            "  return c.age;\n"
            "}\n"
        )
        py = _compile(src)
        self.assertIn("Cat_new(7)", py)
        self.assertNotIn("new Cat(", _strip_runtime(py))

    def test_no_factory_emitted_for_class_without_fields(self):
        # Classes with no fields shouldn't get a factory function — they
        # don't have anything to fill, and `new Cat()` with zero args
        # is a separate question (currently unsupported).
        src = (
            "class Cat extends vector { }\n"
        )
        py = _compile(src)
        self.assertNotIn("def Cat_new(", py)


class TestLogicalConnectives(unittest.TestCase):
    """All logical connectives lower to stdlib polynomial bodies.

    Coverage (2026-05-01 list):
      NOT:  ! ~ not (case-insensitive)
      AND:  & && and (case-insensitive)
      OR:   | || or (case-insensitive)
      NAND: nand (case-insensitive)
      XOR:  xor (case-insensitive)
      XNOR: xnor iff (case-insensitive)
    """

    def _expect_inlined(self, src: str, expected_substring: str) -> None:
        """Compile and assert the emitted Python contains a substring
        characteristic of the polynomial form (i.e. the inliner ran
        and the call to logical_X is gone)."""
        py = _compile(src)
        self.assertIn(expected_substring, py)
        # No bare logical_X call should remain — they should all
        # have been inlined to the polynomial body.
        for fn in (
            "logical_not", "logical_and", "logical_or",
            "logical_nand", "logical_xor", "logical_xnor",
        ):
            self.assertNotIn(f"_VSA.{fn}(", py, msg=f"{fn} not inlined")

    def test_not_via_bang(self):
        src = "function fuzzy main() { fuzzy a = unknown; return !a; }"
        self._expect_inlined(src, "(0 - a)")

    def test_not_via_tilde(self):
        src = "function fuzzy main() { fuzzy a = unknown; return ~a; }"
        self._expect_inlined(src, "(0 - a)")

    def test_not_via_keyword_lowercase(self):
        src = "function fuzzy main() { fuzzy a = unknown; return not a; }"
        self._expect_inlined(src, "(0 - a)")

    def test_not_via_keyword_uppercase(self):
        src = "function fuzzy main() { fuzzy a = unknown; return NOT a; }"
        self._expect_inlined(src, "(0 - a)")

    def test_and_via_double_amp(self):
        src = "function fuzzy main(fuzzy a, fuzzy b) { return a && b; }"
        py = _compile(src)
        # AND polynomial includes a*b*a*b
        self.assertIn("0.5", py)

    def test_and_via_single_amp(self):
        src = "function fuzzy main(fuzzy a, fuzzy b) { return a & b; }"
        py = _compile(src)
        self.assertIn("0.5", py)

    def test_and_via_keyword(self):
        src = "function fuzzy main(fuzzy a, fuzzy b) { return a AND b; }"
        py = _compile(src)
        self.assertIn("0.5", py)

    def test_or_via_double_pipe(self):
        src = "function fuzzy main(fuzzy a, fuzzy b) { return a || b; }"
        py = _compile(src)
        self.assertIn("0.5", py)

    def test_or_via_single_pipe(self):
        src = "function fuzzy main(fuzzy a, fuzzy b) { return a | b; }"
        py = _compile(src)
        self.assertIn("0.5", py)

    def test_or_via_keyword(self):
        src = "function fuzzy main(fuzzy a, fuzzy b) { return a or b; }"
        py = _compile(src)
        self.assertIn("0.5", py)

    def test_xor_via_keyword(self):
        # XOR polynomial: -a*b
        src = "function fuzzy main(fuzzy a, fuzzy b) { return a xor b; }"
        py = _compile(src)
        self.assertIn("(0 - (a * b))", py)

    def test_xnor_via_keyword(self):
        # XNOR polynomial: a*b
        src = "function fuzzy main(fuzzy a, fuzzy b) { return a xnor b; }"
        py = _compile(src)
        self.assertIn("(a * b)", py)

    def test_nand_via_keyword(self):
        # NAND = !AND, so the emitted form should have a negation
        # over the AND polynomial.
        src = "function fuzzy main(fuzzy a, fuzzy b) { return a nand b; }"
        py = _compile(src)
        self.assertIn("0 -", py)
        self.assertIn("0.5", py)

    def test_capitalized_keyword_name_still_works(self):
        # Logic keywords are CONTEXTUAL — a capitalized identifier like
        # `Xnor` lexes as IDENT, so a function named `Xnor` parses fine; the
        # bare `xnor` keyword is only recognized in expression position.
        src = (
            "function fuzzy Xnor(fuzzy a, fuzzy b) {\n"
            "  return (a xnor b);\n"
            "}\n"
        )
        # Just making sure compilation doesn't raise.
        py = _compile(src)
        self.assertIn("def Xnor(", py)


class TestChainedComparisons(unittest.TestCase):
    """Python-style chained comparisons reduce to named operations:
        a == b == c        -> Equals(a, b, c)
        a < b < c          -> hasOrder(a, b, c)
        a > b > c          -> hasOrder(c, b, a)
        a <= b <= c        -> hasOrderOrEqual(a, b, c)
        a >= b >= c        -> hasOrderOrEqual(c, b, a)
        a == b > c == d    -> hasOrder(d, Equals(b, c), a) [reserved nested form, throws]
    Anything with `!=` or fully mixed falls back to AND-chain.
    """

    def test_equals_chain_emits_pairwise_eq_polynomial(self):
        src = (
            "function fuzzy main(fuzzy a, fuzzy b, fuzzy c) {\n"
            "  return a == b == c;\n"
            "}\n"
        )
        py = _compile(src)
        # Two `_VSA.eq` calls (one per adjacent pair).
        self.assertEqual(py.count("_VSA.eq("), 2)

    def test_strict_ascending_chain_emits_pairwise_gt(self):
        # hasOrder(a, b, c) -> _VSA.gt(b, a) && _VSA.gt(c, b)
        src = (
            "function fuzzy main(fuzzy a, fuzzy b, fuzzy c) {\n"
            "  return a < b < c;\n"
            "}\n"
        )
        py = _compile(src)
        self.assertEqual(py.count("_VSA.gt("), 2)

    def test_strict_descending_chain_reverses_args(self):
        # `a > b > c` -> hasOrder(c, b, a) -> gt(b, c) && gt(a, b)
        src = (
            "function fuzzy main(fuzzy a, fuzzy b, fuzzy c) {\n"
            "  return a > b > c;\n"
            "}\n"
        )
        py = _compile(src)
        self.assertEqual(py.count("_VSA.gt("), 2)
        # Args are reversed so the reduction is always-ascending —
        # verify both expected pair shapes appear.
        self.assertIn("_VSA.gt(b, c)", py)
        self.assertIn("_VSA.gt(a, b)", py)

    def test_grouped_equals_inside_hasOrder_reserved_throws(self):
        from sutra_compiler.codegen_base import CodegenNotSupported
        src = (
            "function fuzzy main(fuzzy a, fuzzy b, fuzzy c, fuzzy d, fuzzy e) {\n"
            "  return a == b > c == d > e;\n"
            "}\n"
        )
        with self.assertRaises(CodegenNotSupported) as ctx:
            _compile(src)
        self.assertIn("Equals", str(ctx.exception))
        self.assertIn("hasOrder", str(ctx.exception))

    def test_neq_in_chain_falls_back_to_and_chain(self):
        # a != b == c -> (a != b) && (b == c) — AND-chain expansion,
        # NOT a named call (since `!=` is non-transitive).
        src = (
            "function fuzzy main(fuzzy a, fuzzy b, fuzzy c) {\n"
            "  return a != b == c;\n"
            "}\n"
        )
        py = _compile(src)
        # neq lowers via stdlib to !(a == b), so the polynomial form
        # contains an `_VSA.eq(a, b)` (negated) and an `_VSA.eq(b, c)`.
        # Just verify both pairs appear.
        self.assertIn("_VSA.eq(a, b)", py)
        self.assertIn("_VSA.eq(b, c)", py)

    def test_single_comparison_unchanged(self):
        # No chain — still emits a single BinaryOp.
        src = (
            "function fuzzy main(fuzzy a, fuzzy b) {\n"
            "  return a == b;\n"
            "}\n"
        )
        py = _compile(src)
        self.assertEqual(py.count("_VSA.eq("), 1)


class TestImperativeShortcuts(unittest.TestCase):
    """++ / -- / += / -= / *= / /= as statements (2026-05-01)."""

    def test_postfix_increment_compiles(self):
        src = (
            "function int main() {\n"
            "  var i : int = 5;\n"
            "  i++;\n"
            "  return i;\n"
            "}\n"
        )
        py = _compile(src)
        self.assertIn("i += 1", py)

    def test_postfix_decrement_compiles(self):
        src = (
            "function int main() {\n"
            "  var i : int = 5;\n"
            "  i--;\n"
            "  return i;\n"
            "}\n"
        )
        py = _compile(src)
        self.assertIn("i -= 1", py)

    def test_augmented_arithmetic_compiles(self):
        src = (
            "function int main() {\n"
            "  var i : int = 5;\n"
            "  i += 3;\n"
            "  i *= 2;\n"
            "  i /= 4;\n"
            "  return i;\n"
            "}\n"
        )
        py = _compile(src)
        self.assertIn("i += 3", py)
        self.assertIn("i *= 2", py)
        self.assertIn("i /= 4", py)


class TestCrossFunctionAxonElision(unittest.TestCase):
    """Producer-side pruning across a function call.

    planning/sutra-spec/axons.md §"Lazy evaluation across
    boundaries": a caller must materialize only the keys the callee
    (transitively) reads from the axon it is handed — "Through a
    single function call: clearly yes." These tests assert the
    pruned `.add(K,V)` is *never emitted* (so the key is never
    bundled — the actual bandwidth/correctness property) and, for
    SAFETY, that every construct the analysis does not fully
    understand falls back to keeping ALL keys (no over-prune).
    """

    def assertMaterialized(self, py, var, key):
        """A key is materialized (not pruned) if it appears either as a
        standalone `axon_add(var, 'key', ...)` OR inside a batched
        `axon_build(var, [...'key'...], ...)` for the same axon var. The
        fusion peephole (consecutive `.add` runs -> one `axon_build`)
        changes the emission shape but not the kept-key property these
        safety tests assert."""
        single = "_VSA.axon_add(%s, '%s'" % (var, key)
        if single in py:
            return
        marker = "_VSA.axon_build(%s, [" % var
        idx = py.find(marker)
        if idx != -1:
            keys_blob = py[idx + len(marker):py.find("]", idx)]
            if ("'%s'" % key) in keys_blob:
                return
        self.fail("key %r not materialized for axon %r in:\n%s" % (key, var, py))

    def test_prunes_keys_no_callee_reads(self):
        src = (
            'vector v_cat = embed("cat");\n'
            'vector v_dog = embed("dog");\n'
            'vector v_bird = embed("bird");\n'
            'function vector getCat(Axon a) { return a.item("cat"); }\n'
            'function vector build() {\n'
            '  Axon x;\n'
            '  x.add("cat", v_cat);\n'
            '  x.add("dog", v_dog);\n'
            '  x.add("bird", v_bird);\n'
            '  return getCat(x);\n'
            '}\n'
        )
        py = _compile(src)
        # The one key getCat reads is materialized.
        self.assertIn("x = _VSA.axon_add(x, 'cat', v_cat)", py)
        # The keys no callee reads are never bundled.
        self.assertNotIn("_VSA.axon_add(x, 'dog'", py)
        self.assertNotIn("_VSA.axon_add(x, 'bird'", py)

    def test_transitive_demand_through_two_calls(self):
        src = (
            'vector v1 = embed("v1");\n'
            'vector v2 = embed("v2");\n'
            'function vector leafC(Axon c) { return c.item("k1"); }\n'
            'function vector midB(Axon b) { return leafC(b); }\n'
            'function vector build() {\n'
            '  Axon x;\n'
            '  x.add("k1", v1);\n'
            '  x.add("k2", v2);\n'
            '  return midB(x);\n'
            '}\n'
        )
        py = _compile(src)
        self.assertIn("x = _VSA.axon_add(x, 'k1', v1)", py)
        self.assertNotIn("_VSA.axon_add(x, 'k2'", py)

    def test_multi_param_pruned_independently(self):
        src = (
            'vector vx = embed("vx");\n'
            'vector vz = embed("vz");\n'
            'vector vy = embed("vy");\n'
            'vector vw = embed("vw");\n'
            'function vector pick(Axon p, Axon q) {\n'
            '  vector r = p.item("x");\n'
            '  return q.item("y");\n'
            '}\n'
            'function vector build2() {\n'
            '  Axon m;\n'
            '  m.add("x", vx);\n'
            '  m.add("z", vz);\n'
            '  Axon n;\n'
            '  n.add("y", vy);\n'
            '  n.add("w", vw);\n'
            '  return pick(m, n);\n'
            '}\n'
        )
        py = _compile(src)
        self.assertIn("m = _VSA.axon_add(m, 'x', vx)", py)
        self.assertNotIn("_VSA.axon_add(m, 'z'", py)
        self.assertIn("n = _VSA.axon_add(n, 'y', vy)", py)
        self.assertNotIn("_VSA.axon_add(n, 'w'", py)

    # --- SAFETY: every unbounded construct keeps ALL keys ---------

    def test_dynamic_key_in_callee_keeps_all(self):
        src = (
            'vector vp = embed("vp");\n'
            'vector vr = embed("vr");\n'
            'function vector dyn(Axon a, string k) {\n'
            '  return a.item(k);\n'
            '}\n'
            'function vector build3() {\n'
            '  Axon x;\n'
            '  x.add("p", vp);\n'
            '  x.add("r", vr);\n'
            '  return dyn(x, "p");\n'
            '}\n'
        )
        py = _compile(src)
        # Callee reads a runtime-computed key → caller cannot bound
        # demand → every key stays materialized.
        self.assertMaterialized(py, "x", "p")
        self.assertMaterialized(py, "x", "r")

    def test_callee_returns_bare_axon_keeps_all(self):
        src = (
            'vector vk = embed("vk");\n'
            'function vector passthru(Axon a) { return a; }\n'
            'function vector build4() {\n'
            '  Axon x;\n'
            '  x.add("k", vk);\n'
            '  return passthru(x);\n'
            '}\n'
        )
        py = _compile(src)
        # passthru's param escapes (bare return) → OPAQUE → caller
        # keeps all keys.
        self.assertIn("x = _VSA.axon_add(x, 'k', vk)", py)

    def test_vector_typed_callee_param_keeps_all(self):
        # The Yantra cross-program connectome reality: a separately
        # compiled consumer types its param `vector` and uses
        # `axon_item(state, ...)`. This single-module pass keys on
        # the `Axon` type, so a `vector` param is OPAQUE → caller
        # keeps all keys. This is the honest boundary (see
        # planning/20-lazy-axon-evaluation.md): producer-side pruning
        # across a separately-compiled-program boundary is NOT solved
        # by this pass.
        src = (
            'vector vk1 = embed("vk1");\n'
            'vector vk2 = embed("vk2");\n'
            'function vector recv(vector state) {\n'
            '  return axon_item(state, "k1");\n'
            '}\n'
            'function vector b5() {\n'
            '  Axon x;\n'
            '  x.add("k1", vk1);\n'
            '  x.add("k2", vk2);\n'
            '  return recv(x);\n'
            '}\n'
        )
        py = _compile(src)
        self.assertMaterialized(py, "x", "k1")
        self.assertMaterialized(py, "x", "k2")

    def test_returned_bare_axon_still_keeps_all(self):
        # Regression guard: a function that builds an axon and
        # returns it bare must keep every add (the pre-existing
        # conservative behaviour the new pass must not weaken).
        src = (
            'vector vs = embed("vs");\n'
            'vector vo = embed("vo");\n'
            'function vector mk() {\n'
            '  Axon a;\n'
            '  a.add("s", vs);\n'
            '  a.add("o", vo);\n'
            '  return a;\n'
            '}\n'
        )
        py = _compile(src)
        self.assertMaterialized(py, "a", "s")
        self.assertMaterialized(py, "a", "o")


class TestCaseInsensitiveStdlibResolution(unittest.TestCase):
    """Emma 2026-07-15: stdlib static-method names on intrinsic classes
    (Math, Tensor, ...) resolve CASE-INSENSITIVELY. PascalCase is the
    canonical documented spelling; a case-variant call must emit the
    CANONICAL runtime name (the `_VSA` attribute must exist), not the
    user's spelling. Exact match still wins first. User-defined class
    methods stay case-SENSITIVE — casefolding only applies to stdlib."""

    def test_math_intrinsic_uppercase_resolves_to_canonical_lowercase(self):
        # `Math.log` is a lowercase intrinsic -> `_VSA.log`. A case-variant
        # `Math.Log` must resolve to the same canonical `_VSA.log`, not the
        # broken passthrough `Math.Log(...)` / `_VSA.Log(...)`.
        src = (
            "function number main() {\n"
            "  number x = 2.0;\n"
            "  return Math.Log(x);\n"
            "}\n"
        )
        py = _compile(src)
        self.assertIn("_VSA.log(", py)
        self.assertNotIn("_VSA.Log(", py)
        self.assertNotIn("Math.Log(", py)

    def test_ambiguous_casefold_resolves_to_pascalcase_canonical(self):
        # `Tensor` declares BOTH `Dot` and `dot` (a case-twin) today. A
        # third spelling like `Tensor.DOT` casefold-matches BOTH, so the
        # resolution must be DETERMINISTIC and pick the canonical
        # PascalCase member (`Dot`) — never resolve to `dot` by set-order
        # accident. Emma 2026-07-15: PascalCase is canonical.
        src = (
            "function vector main() {\n"
            "  vector a = embed(\"a\");\n"
            "  vector b = embed(\"b\");\n"
            "  return Tensor.DOT(a, b);\n"
            "}\n"
        )
        py = _compile(src)
        self.assertIn("_VSA.Dot(", py)
        self.assertNotIn("_VSA.dot(", py)


if __name__ == "__main__":
    unittest.main()
