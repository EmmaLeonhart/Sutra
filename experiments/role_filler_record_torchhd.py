"""TorchHD equivalent of examples/role_filler_record.su.

Same task: encode a 3-field record (name, color, shape) as a single
bundled hypervector, then decode the color field. Companion to the
.su program for the side-by-side comparison in §2.1 of paper.md.

Run: python experiments/role_filler_record_torchhd.py

What this demonstrates:
    The minimum amount of code required to do the role_filler_record
    task in TorchHD. Note what the user has to write and what they
    have to maintain by hand:

    1. The string-to-hypervector mapping is manual. We construct
       random hypervectors for each role and filler and keep a
       Python dict {name: hypervector}. There is no concept of
       "embed this string"; if we wanted vectors that respected
       semantic similarity (e.g. so "red" and "crimson" are close
       in vector space), we'd have to embed them with a separate
       model and feed the resulting tensors into TorchHD as
       opaque hypervectors.
    2. The codebook for decoding is also manual. We stack the
       filler vectors into a tensor and run cosine similarity
       against it ourselves.
    3. The program control flow lives in Python: we call
       torchhd.bind, torchhd.bundle, torchhd.cosine_similarity in
       sequence; the whole thing is a Python function with
       host-side data flow.

    Compare with examples/role_filler_record.su which is one
    declarative module that the Sutra compiler reduces to a fused
    tensor-op graph with the codebook baked in. Both produce the
    same final string, but the Sutra version's substrate-purity
    guarantee, compile-time string lookup, and tensor-normal-form
    output are not properties the TorchHD version has.
"""

from __future__ import annotations

import torch
import torchhd

DIM = 768


def main() -> str:
    torch.manual_seed(42)

    # 1. MANUAL hypervector creation for roles + fillers.
    # No "embed this string" — user creates random vectors and
    # maintains the mapping in their head / in this dict.
    role_names = ["name", "color", "shape"]
    filler_names = ["alice", "bob", "red", "blue", "circle", "square"]

    roles = {n: torchhd.random(1, DIM, vsa="MAP") for n in role_names}
    fillers = {n: torchhd.random(1, DIM, vsa="MAP") for n in filler_names}

    # 2. MANUAL codebook tensor for decoding.
    codebook = torch.cat([fillers[n] for n in filler_names], dim=0)

    # 3. Build the record.  The "program" here is just a sequence
    # of library calls in Python; control flow is host-side.
    name_v = fillers["alice"]
    color_v = fillers["red"]
    shape_v = fillers["circle"]

    bound_name = torchhd.bind(roles["name"], name_v)
    bound_color = torchhd.bind(roles["color"], color_v)
    bound_shape = torchhd.bind(roles["shape"], shape_v)

    record = torchhd.bundle(bound_name, torchhd.bundle(bound_color, bound_shape))

    # 4. Decode the color field.
    recovered = torchhd.bind(record, torchhd.inverse(roles["color"]))
    sims = torchhd.cosine_similarity(recovered, codebook)
    winner_idx = int(torch.argmax(sims))
    return filler_names[winner_idx]


if __name__ == "__main__":
    result = main()
    print(f"decode color field -> {result!r}")
    assert result == "red", f"expected 'red', got {result!r}"
    print("OK")
