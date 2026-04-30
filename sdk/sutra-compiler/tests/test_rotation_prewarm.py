"""Tests for compile-time rotation pre-warm (queue item 3).

After embed_batch + populate_sutradb, the codegen prelude calls
`_VSA.prewarm_rotation_cache()` which pre-computes a rotation matrix
for every codebook entry. The runtime never pays the QR cost on
the hot path.
"""
from __future__ import annotations

import unittest

import torch

from sutra_compiler import ast_nodes
from sutra_compiler.codegen_pytorch import PyTorchCodegen


def _make_vsa():
    """Compile an empty module + exec to get a working _VSA instance."""
    cg = PyTorchCodegen()
    cg._prefetch_strings = []
    empty = ast_nodes.Module(items=[], span=None)  # type: ignore[arg-type]
    py = cg.translate(empty)
    ns: dict = {}
    exec(py, ns)
    return ns["_VSA"]


class TestRotationPrewarm(unittest.TestCase):
    """`prewarm_rotation_cache` populates `_rot_cache` for every codebook
    entry, so subsequent `bind` / `_rotation_for` calls hit the cache.
    """

    def test_prewarm_populates_rot_cache_for_each_codebook_entry(self):
        vsa = _make_vsa()
        sem = vsa.semantic_dim
        syn = vsa.synthetic_dim
        # Hand-build three codebook entries.
        v1 = torch.zeros(sem + syn, dtype=vsa.dtype, device=vsa.device)
        v2 = torch.zeros(sem + syn, dtype=vsa.dtype, device=vsa.device)
        v3 = torch.zeros(sem + syn, dtype=vsa.dtype, device=vsa.device)
        v1[0] = 1.0
        v2[1] = 1.0
        v3[2] = 1.0
        vsa._codebook = {"a": v1, "b": v2, "c": v3}
        # Cache empty before pre-warm.
        self.assertEqual(len(vsa._rot_cache), 0)
        vsa.prewarm_rotation_cache()
        # Cache has 3 entries after.
        self.assertEqual(len(vsa._rot_cache), 3)

    def test_post_prewarm_bind_does_not_grow_cache(self):
        vsa = _make_vsa()
        sem = vsa.semantic_dim
        syn = vsa.synthetic_dim
        role = torch.zeros(sem + syn, dtype=vsa.dtype, device=vsa.device)
        role[0] = 1.0
        filler = torch.zeros(sem + syn, dtype=vsa.dtype, device=vsa.device)
        filler[1] = 1.0
        vsa._codebook = {"role": role, "filler": filler}
        vsa.prewarm_rotation_cache()
        before = len(vsa._rot_cache)
        # Bind: should hit cache, not add to it.
        _ = vsa.bind(role, filler)
        after = len(vsa._rot_cache)
        self.assertEqual(before, after,
                         "bind() after pre-warm should not grow the cache")

    def test_prewarm_handles_empty_codebook(self):
        vsa = _make_vsa()
        vsa._codebook = {}
        # Should not raise.
        vsa.prewarm_rotation_cache()
        self.assertEqual(len(vsa._rot_cache), 0)


if __name__ == "__main__":
    unittest.main()
