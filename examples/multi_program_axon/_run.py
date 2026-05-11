"""Multi-program axon-passing demonstration.

Two .su programs in this directory:
  - producer.su  — exposes make_state(), returns a 12-key axon
  - consumer.su  — exposes consume_animal/color/user, each reads ONE key

This script orchestrates the cross-program exchange:
  1. Compile producer.su to a Python module.
  2. Run producer's make_state() to get the axon vector.
  3. Serialize the vector to disk (numpy .npy — the wire format).
  4. Compile consumer.su to a SEPARATE Python module.
  5. Load the serialized vector.
  6. Hand the loaded vector to the consumer's consume_* functions.
  7. Verify the consumer recovers the producer-encoded values
     ("dog", "red", "carol") via VSA unbind + argmax_cosine.

The two programs never share a Python process state. The only thing
that crosses the boundary is the serialized vector. Both programs
use the same `nomic-embed-text` embedding (declared in atman.toml
in this directory) so the basis vectors line up across the boundary
— that's how the consumer's `axon_item` rotations match the
producer's `axon_add` rotations.

Per axons.md §"Lazy evaluation across boundaries", the spec's long-
term promise is that only the keys consumer references would
actually materialize on the wire. This MVP demonstrates the wire-
passing itself; lazy materialization is the next layer (sketched in
README.md).

Run:   python examples/multi_program_axon/_run.py
"""
from __future__ import annotations

import os
import sys
import tempfile
import types

import numpy as np
import torch

# Make the test harness importable regardless of cwd. _run.py lives
# in examples/multi_program_axon/, harness lives in examples/.
HERE = os.path.dirname(os.path.abspath(__file__))
EXAMPLES_DIR = os.path.dirname(HERE)
REPO_ROOT = os.path.dirname(EXAMPLES_DIR)
SDK_PATH = os.path.join(REPO_ROOT, "sdk", "sutra-compiler")
for p in (EXAMPLES_DIR, SDK_PATH):
    if p not in sys.path:
        sys.path.insert(0, p)

from sutra_compiler.codegen_pytorch import translate_module as torch_translate  # noqa: E402
from sutra_compiler.lexer import Lexer  # noqa: E402
from sutra_compiler.parser import Parser  # noqa: E402


def compile_to_torch_module(src_path: str) -> types.ModuleType:
    """Compile a .su file via the PyTorch backend.

    Axon intrinsics (axon_new/add/item) live on _TorchVSA only — the
    numpy backend (the harness default) doesn't carry them. This demo
    therefore uses pytorch codegen directly. Embedding model is read
    from the atman.toml in this directory.
    """
    with open(src_path, encoding="utf-8") as f:
        src = f.read()
    lexer = Lexer(src, file=src_path)
    tokens = lexer.tokenize()
    parser = Parser(tokens, file=src_path, diagnostics=lexer.diagnostics)
    module = parser.parse_module()
    py_src = torch_translate(
        module, llm_model="nomic-embed-text", runtime_dim=768
    )
    mod = types.ModuleType(os.path.basename(src_path))
    mod.__file__ = f"<generated from {src_path}>"
    exec(compile(py_src, mod.__file__, "exec"), mod.__dict__)
    return mod


def main() -> int:
    producer_path = os.path.join(HERE, "producer.su")
    consumer_path = os.path.join(HERE, "consumer.su")

    print("=" * 64)
    print("Multi-program axon-passing demo")
    print("=" * 64)
    print()
    print(f"Producer source: {producer_path}")
    print(f"Consumer source: {consumer_path}")
    print(f"Wire format:     numpy .npy (one tensor per axon)")
    print()

    # 1-2. Compile + run producer in its own module.
    print("[1/4] Compiling producer.su ...")
    producer_mod = compile_to_torch_module(producer_path)
    print("[2/4] Calling producer.make_state() — building 12-key axon ...")
    state_vec = producer_mod.make_state()
    # Producer returns a torch tensor; pull to CPU + numpy for the
    # wire format. The cross-program nature of the demo means we
    # always go through a host-readable serialization step, never a
    # direct in-process tensor handoff.
    state_np = np.asarray(state_vec.detach().cpu())
    print(f"      Got vector shape={state_np.shape}, "
          f"dtype={state_np.dtype}, "
          f"L2 norm={float(np.linalg.norm(state_np)):.4f}")

    # 3. Serialize to the wire. This is the boundary — nothing else
    # crosses between producer and consumer.
    with tempfile.TemporaryDirectory(prefix="sutra-axon-wire-") as wire_dir:
        wire_path = os.path.join(wire_dir, "axon_state.npy")
        np.save(wire_path, state_np)
        wire_bytes = os.path.getsize(wire_path)
        print(f"      Serialized to {wire_path} ({wire_bytes} bytes)")
        print()

        # 4-5. Compile consumer separately, load the wire vector.
        print("[3/4] Compiling consumer.su (separate module) ...")
        consumer_mod = compile_to_torch_module(consumer_path)
        loaded_np = np.load(wire_path)
        # Hydrate back to a torch tensor on the consumer's device.
        # The consumer's _VSA was constructed with whatever device
        # torch.cuda.is_available() picks; we read it off _VSA so the
        # tensor lands in the right place.
        consumer_vsa = consumer_mod._VSA
        loaded_vec = torch.as_tensor(
            loaded_np, dtype=consumer_vsa.dtype, device=consumer_vsa.device
        )
        print(f"      Loaded vector shape={tuple(loaded_vec.shape)}, "
              f"dtype={loaded_vec.dtype}, device={loaded_vec.device}")
        print()

        # 6-7. Hand the loaded vector to each recover_* function. The
        # consumer reads three of the five keys; the other two are
        # never referenced (the slice lazy materialization would prune).
        print("[4/4] Consumer recovers three keys from the wire-passed axon:")
        rec_animal = consumer_mod.recover_animal(loaded_vec)
        rec_color  = consumer_mod.recover_color(loaded_vec)
        rec_user   = consumer_mod.recover_user(loaded_vec)
        print(f"      recovered animal_2 vector L2={float(torch.linalg.norm(rec_animal)):.4f}")
        print(f"      recovered color_1  vector L2={float(torch.linalg.norm(rec_color)):.4f}")
        print(f"      recovered user_1   vector L2={float(torch.linalg.norm(rec_user)):.4f}")
        print()

    # Host-side monitoring: cosine the recovered vectors against the
    # correct filler (which producer bundled) and against a decoy
    # filler (which producer did NOT bundle). Per CLAUDE.md, numpy at
    # the monitoring boundary is allowed; the recovery itself ran
    # entirely on the substrate inside the consumer module.
    print("Monitoring: cosine recovered vs correct filler vs decoy")
    print("-" * 60)
    vsa = consumer_mod._VSA
    def _cos(a, b):
        a = a / (torch.linalg.norm(a) + 1e-9)
        b = b / (torch.linalg.norm(b) + 1e-9)
        return float(torch.dot(a, b))

    # Correct fillers — must come from the SAME embedding that
    # producer used. Re-embedding via consumer_mod._VSA gives the
    # same vector because both programs share the disk cache.
    correct = {
        "animal_2": ("dog", consumer_mod._VSA.embed("dog")),
        "color_1":  ("red", consumer_mod._VSA.embed("red")),
        "user_1":   ("alice", consumer_mod._VSA.embed("alice")),
    }
    decoys = {
        "animal_2": ("octopus", consumer_mod._VSA.embed("octopus")),
        "color_1":  ("violet",  consumer_mod._VSA.embed("violet")),
        "user_1":   ("xavier",  consumer_mod._VSA.embed("xavier")),
    }
    recovered = {
        "animal_2": rec_animal,
        "color_1":  rec_color,
        "user_1":   rec_user,
    }
    margin_ok = True
    for key in ("animal_2", "color_1", "user_1"):
        c_name, c_vec = correct[key]
        d_name, d_vec = decoys[key]
        cos_correct = _cos(recovered[key], c_vec)
        cos_decoy   = _cos(recovered[key], d_vec)
        margin = cos_correct - cos_decoy
        verdict = "OK" if margin > 0 else "FAIL"
        print(f"  {key:>10}: cos(recovered, {c_name!r:>8}) = {cos_correct:+.4f}   "
              f"cos(recovered, {d_name!r:>8}) = {cos_decoy:+.4f}   "
              f"margin = {margin:+.4f}   [{verdict}]")
        if margin <= 0:
            margin_ok = False
    print()

    if margin_ok:
        print("RESULT: PASS — recovered vectors match producer-bundled fillers")
        print("        with positive cosine margin over not-bundled decoys.")
        print("        The wire-passing mechanism works end-to-end.")
        return 0
    print("RESULT: FAIL — at least one key's recovered vector is closer to its")
    print("        decoy than to its bundled filler. Could be capacity or could")
    print("        be wire corruption — inspect cosine numbers above.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
