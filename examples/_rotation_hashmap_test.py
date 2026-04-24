"""Rotation-hashmap prototype test (library-pattern, 2026-04-22).

The rotation-hashmap described in
`planning/open-questions/rotation-hashmap-as-language-feature.md`
is prototyped as runtime methods on `_NumpyVSA` (hashmap_new,
hashmap_set, hashmap_get) and accessed from this test harness. There
is no `.su` surface syntax for hashmaps yet; the purpose of this
test is to validate the mechanism empirically and feed the open
question a data point.

The mechanism (see the design note, and the hashmap_* methods in
codegen_numpy's emitted runtime):

- hashmap_set(acc, key, val) = acc + bind(key, val), reusing the
  same role-seeded Haar rotation mechanism as the language's bind.
- hashmap_get(acc, key) = unbind(key, acc), the inverse rotation.

Exact lookup works the same way bind + bundle + unbind works for
a role-filler record: the matched-key term in the bundle inverts
exactly to recover the stored value; other entries appear as
~1/sqrt(d) noise per entry. Soft lookup (noisy query recovers an
approximately-stored value) does NOT work with this prototype,
because the role-to-rotation map uses a bit-hash of the key bytes
and is discontinuous. Soft lookup needs a continuous hash (e.g.
Householder reflection parameterized by the key vector, or a
learned projection to angles); that's future work.

This test exercises exact lookup (should pass) and noisy-key lookup
(expected to fail under the current mechanism — the results are
informational and motivate the continuous-hash future work).

Usage: python examples/_rotation_hashmap_test.py

Expected: exact lookup recovers every stored value; noisy-key lookup
succeeds when the perturbation is small, degrades as perturbation
grows. Exit code 0 if the minimal bar is met (exact lookup works).
"""
from __future__ import annotations

import os
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, ".."))
SDK_PATH = os.path.join(REPO_ROOT, "sdk", "sutra-compiler")
sys.path.insert(0, SDK_PATH)

from sutra_compiler.codegen import translate_module  # noqa: E402
from sutra_compiler.lexer import Lexer  # noqa: E402
from sutra_compiler.parser import Parser  # noqa: E402


def load_vsa():
    """Compile any .su file that uses basis_vector and grab its _VSA.

    We need a compiled module that instantiated `_VSA` so we can call
    the hashmap_* methods. hello_world is the smallest .su file that
    triggers prelude emission and _VSA initialization.
    """
    path = os.path.join(HERE, "hello_world.su")
    with open(path, encoding="utf-8") as f:
        src = f.read()
    lexer = Lexer(src, file=path)
    tokens = lexer.tokenize()
    parser = Parser(tokens, file=path, diagnostics=lexer.diagnostics)
    module = parser.parse_module()
    py_src = translate_module(module)
    mod = types.ModuleType("_rh_harness")
    mod.__file__ = "<rotation_hashmap_test>"
    exec(compile(py_src, mod.__file__, "exec"), mod.__dict__)
    return mod._VSA, mod


def main() -> int:
    vsa, mod = load_vsa()
    embed = vsa.embed

    # Five (concept, attribute) pairs. Concepts are the keys; attributes
    # are the stored values. We retrieve attributes by concept lookup.
    store = [
        ("cat",       "whiskers"),
        ("dog",       "bark"),
        ("fish",      "scales"),
        ("bird",      "feathers"),
        ("elephant",  "trunk"),
    ]

    # Build the hashmap by successive set calls. Each set rotates the
    # value under the key's hash and adds into the accumulator.
    acc = vsa.hashmap_new()
    codebook = {}
    for concept, attr in store:
        k = embed(concept)
        v = embed(attr)
        acc = vsa.hashmap_set(acc, k, v)
        codebook[attr] = v
    print("=" * 72)
    print("Rotation-hashmap prototype test (library pattern, 2026-04-22)")
    print("=" * 72)
    print(f"Stored {len(store)} (concept, attribute) pairs.")
    print()

    # Exact lookup: retrieve each attribute by its concept.
    exact_ok = 0
    exact_total = 0
    print("Exact lookup:")
    candidate_vecs = list(codebook.values())
    candidate_names = list(codebook.keys())
    for concept, attr in store:
        k = embed(concept)
        recovered = vsa.hashmap_get(acc, k)
        # argmax cosine against the stored attribute codebook
        best_i, best_score = -1, -1.0
        for i, cv in enumerate(candidate_vecs):
            s = vsa.similarity(recovered, cv)
            if s > best_score:
                best_score = s
                best_i = i
        got = candidate_names[best_i]
        mark = "OK" if got == attr else "FAIL"
        exact_ok += int(got == attr)
        exact_total += 1
        print(f"  lookup({concept:<9}) expected={attr:<10} got={got:<10} "
              f"best_score={best_score:+.3f} {mark}")
    print(f"  {exact_ok}/{exact_total} exact lookups succeeded")
    print()

    # Noisy-key lookup: query with a slightly different word that embeds
    # nearby. Soft lookup should succeed when the query is semantically
    # close; degrade as distance grows.
    noisy_queries = [
        ("kitten",   "whiskers"),   # near "cat"
        ("puppy",    "bark"),       # near "dog"
        ("salmon",   "scales"),     # near "fish"
        ("sparrow",  "feathers"),   # near "bird"
        ("mammoth",  "trunk"),      # near "elephant"
    ]
    noisy_ok = 0
    noisy_total = 0
    print("Noisy-key (soft) lookup:")
    for qword, attr in noisy_queries:
        kq = embed(qword)
        recovered = vsa.hashmap_get(acc, kq)
        best_i, best_score = -1, -1.0
        for i, cv in enumerate(candidate_vecs):
            s = vsa.similarity(recovered, cv)
            if s > best_score:
                best_score = s
                best_i = i
        got = candidate_names[best_i]
        mark = "OK" if got == attr else "FAIL"
        noisy_ok += int(got == attr)
        noisy_total += 1
        print(f"  soft_lookup({qword:<9}) expected={attr:<10} got={got:<10} "
              f"best_score={best_score:+.3f} {mark}")
    print(f"  {noisy_ok}/{noisy_total} soft lookups succeeded")
    print()

    # Cross-check: a concept that was NEVER stored should return noise
    # (no stored attribute should dominate).
    print("Out-of-distribution lookup (key never stored):")
    for qword in ["octopus", "penguin", "rhinoceros"]:
        kq = embed(qword)
        recovered = vsa.hashmap_get(acc, kq)
        best_i, best_score = -1, -1.0
        for i, cv in enumerate(candidate_vecs):
            s = vsa.similarity(recovered, cv)
            if s > best_score:
                best_score = s
                best_i = i
        print(f"  soft_lookup({qword:<11}) top_match={candidate_names[best_i]:<10} "
              f"best_score={best_score:+.3f}")
    print()

    print("=" * 72)
    # Exit code: exact lookup is the minimum bar. Soft lookup is
    # informational — we record the result regardless of pass count.
    if exact_ok == exact_total:
        print(f"PASS (exact {exact_ok}/{exact_total}, soft {noisy_ok}/{noisy_total})")
        return 0
    print(f"FAIL (exact {exact_ok}/{exact_total}, soft {noisy_ok}/{noisy_total})")
    return 1


if __name__ == "__main__":
    sys.exit(main())
