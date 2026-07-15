"""Diagnostic probe for the axon-cache readback flake (CI runs 29386156802 /
29387477961: key "tree" reads back 11.0 instead of 4.0 from a 10-key bundle).

Prints, for the exact key set the failing test uses:
  - the pairwise cosine matrix of the raw key embeddings (the crosstalk source),
  - each key's readback value from the 10-key axon bundle.

RESOLVED 2026-07-15 — see
planning/findings/2026-07-15-axon-flake-root-cause-server-version.md. Two
distinct effects, both measured with this probe:

1. Run WITHOUT the test suite's conftest (as a plain script) and the probe uses
   the in-process transformers backend — which reproduces the collision that
   tests/conftest.py already documents ("go" reads back telephone's 9.0). That
   is the known backend-realization difference, NOT a bug.
2. The CI flake was the ollama SERVER version (local 0.17.1 = tuned geometry,
   passes; CI unpinned install.sh → 0.32.0, same model digest, different
   realization → "tree" → 11.0). compiler-ci.yml now pins OLLAMA_VERSION.

Keep this probe for re-measuring margins when bumping the pinned server version
(set SUTRA_EMBED_BACKEND=ollama to probe the gated substrate).

Non-gating: exits 0 always; the numbers are the product.
"""

import sys
import os
import types

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "sdk", "sutra-compiler"))

import torch  # noqa: E402
from sutra_compiler.codegen_pytorch import translate_module  # noqa: E402
from sutra_compiler.lexer import Lexer  # noqa: E402
from sutra_compiler.parser import Parser  # noqa: E402

KEYS = ["go", "sun", "tree", "house", "garden",
        "machine", "mountain", "telephone", "strawberry", "hippopotamus"]


def _vsa(runtime_dim: int = 256):
    # identical construction to tests/test_axon_build.py::_vsa
    src = "function int main() { return 0; }"
    lx = Lexer(src, file="t.su")
    ps = Parser(lx.tokenize(), file="t.su", diagnostics=lx.diagnostics)
    py = translate_module(ps.parse_module(), llm_model="nomic-embed-text",
                          runtime_dim=runtime_dim)
    m = types.ModuleType("t")
    exec(compile(py, "t.su", "exec"), m.__dict__)
    return m._VSA


def main():
    v = _vsa()
    embs = {k: v.embed(k) for k in KEYS}

    # Embedding-collapse check (the LSC-paper failure class): the axon rotation
    # operator is a pure function of a 32-bit hash of the embedding BYTES, so
    # two keys with byte-identical embeddings get the SAME operator and both
    # read back the pair's SUM — the exact signature of CI runs 29386156802
    # (tree->11.0 = 4+7 machine) / the 0.17.1-pinned run (house->13.0 = 5+8
    # mountain). Print per-key byte-hashes and flag any identical pair.
    import hashlib
    print("embedding byte-hashes (collapse check):")
    hashes = {}
    for k in KEYS:
        b = bytes(embs[k].detach().cpu().contiguous().view(torch.uint8).tolist())
        h = hashlib.blake2b(b, digest_size=8).hexdigest()
        dup = [k2 for k2, h2 in hashes.items() if h2 == h]
        hashes[k] = h
        print(f"  {k}: {h}" + (f"  <-- IDENTICAL TO {dup}" if dup else ""))
    # pairwise cosines of the raw key embeddings
    print("pairwise cosines (upper triangle, >0.5 flagged):")
    worst = (0.0, "", "")
    for i, a in enumerate(KEYS):
        for b in KEYS[i + 1:]:
            ea, eb = embs[a], embs[b]
            c = float(torch.dot(ea, eb) / (torch.norm(ea) * torch.norm(eb) + 1e-12))
            flag = "  <-- HIGH" if abs(c) > 0.5 else ""
            print(f"  cos({a}, {b}) = {c:+.4f}{flag}")
            if abs(c) > abs(worst[0]):
                worst = (c, a, b)
    print(f"max |cos|: {worst[0]:+.4f} ({worst[1]}, {worst[2]})")

    # the failing test's readback, verbatim
    built = v.axon_build(v.zero_vector(), KEYS, [float(len(k)) for k in KEYS])
    print("readback from 10-key bundle (expected = len(key)):")
    for k in KEYS:
        got = float(torch.dot(v.axon_item(built, k), v.make_real(1.0)))
        mark = "" if abs(got - len(k)) < 1e-3 else "  <-- WRONG"
        print(f"  {k}: got {got:.4f}, expected {float(len(k)):.1f}{mark}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # non-gating: the numbers are diagnostics, never a build verdict
        print(f"probe error (non-gating): {type(e).__name__}: {e}")
    sys.exit(0)
