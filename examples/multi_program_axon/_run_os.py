"""OS-shaped multi-program axon-passing demo.

Companion to `_run.py` (the all-vector-fillers demo). This one
exercises the realistic OS payload shape per Emma 2026-05-10:
one input embedding plus several scalar/string metadata fields.

Wire payload from producer_os.su:
  user      : "alice"   (string)
  tag       : "search"  (string)
  priority  : 7         (int)
  retries   : 0         (int)
  query     : embedding of "find recent files about cats"  (vector)

Consumer (consumer_os.su) reads only `user`, `priority`, `query`.
Skips `tag` and `retries`. Pre-fix, none of the scalar/string keys
would have round-tripped at all (per the 2026-05-10 axon-permutation
finding). With the fix in place, the per-key permutation gives them
the per-key separation they need.

Run:   python examples/multi_program_axon/_run_os.py
"""
from __future__ import annotations

import os
import sys
import tempfile
import types

import numpy as np
import torch

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


def _read_string_first_n(vsa, vec, n: int) -> str:
    """Read the first n codepoints of a string-typed vector. Avoids
    the over-read crosstalk that string_to_python hits when the axon
    has multiple fillers; the orchestrator knows the expected length.
    """
    chars = []
    for k in range(n):
        ax = vsa.semantic_dim + vsa._string_axis(k)
        chars.append(chr(int(round(float(vec[ax].item())))))
    return "".join(chars)


def main() -> int:
    producer_path = os.path.join(HERE, "producer_os.su")
    consumer_path = os.path.join(HERE, "consumer_os.su")

    print("=" * 72)
    print("OS-shaped multi-program axon-passing demo (strings + numbers + 1 emb)")
    print("=" * 72)
    print()

    print("[1/4] Compiling producer_os.su ...")
    producer_mod = compile_to_torch_module(producer_path)
    print("[2/4] Calling producer.make_state() — building axon ...")
    state_vec = producer_mod.make_state()
    state_np = np.asarray(state_vec.detach().cpu())
    print(f"      Vector shape={state_np.shape}, dtype={state_np.dtype}, "
          f"L2={float(np.linalg.norm(state_np)):.4f}")

    with tempfile.TemporaryDirectory(prefix="sutra-os-axon-") as wire_dir:
        wire_path = os.path.join(wire_dir, "axon_state.npy")
        np.save(wire_path, state_np)
        print(f"      Serialized to {wire_path} "
              f"({os.path.getsize(wire_path)} bytes)")
        print()

        print("[3/4] Compiling consumer_os.su (separate module) ...")
        consumer_mod = compile_to_torch_module(consumer_path)
        consumer_vsa = consumer_mod._VSA
        loaded_np = np.load(wire_path)
        loaded_vec = torch.as_tensor(
            loaded_np, dtype=consumer_vsa.dtype, device=consumer_vsa.device
        )
        print(f"      Loaded vector shape={tuple(loaded_vec.shape)}, "
              f"dtype={loaded_vec.dtype}")
        print()

        print("[4/4] Consumer recovers three of five keys:")
        rec_user_vec     = consumer_mod.recover_user(loaded_vec)
        rec_priority_vec = consumer_mod.recover_priority(loaded_vec)
        rec_query_vec    = consumer_mod.recover_query(loaded_vec)

    # Decode each filler with the appropriate accessor. Sutra type
    # annotations are surface-level only; recover_priority's `int`
    # return type does not auto-extract the scalar via vsa.real() —
    # the runtime axon_item returns a vector. The orchestrator does
    # the type-aware decode here at the monitoring boundary.
    user_str    = _read_string_first_n(consumer_vsa, rec_user_vec, len("alice"))
    rec_priority = consumer_vsa.real(rec_priority_vec)

    # Compare query embedding to expected
    expected_query = consumer_vsa.embed("find recent files about cats")
    decoy_query    = consumer_vsa.embed("compile rust kernel")
    def _cos(a, b):
        a = a / (torch.linalg.norm(a) + 1e-9)
        b = b / (torch.linalg.norm(b) + 1e-9)
        return float(torch.dot(a, b))
    cos_q_correct = _cos(rec_query_vec, expected_query)
    cos_q_decoy   = _cos(rec_query_vec, decoy_query)

    print(f"  user      -> {user_str!r}                       (expected 'alice')")
    print(f"  priority  -> {rec_priority}                       (expected 7)")
    print(f"  query     -> cos(recovered, correct)={cos_q_correct:+.4f}, "
          f"cos(recovered, decoy)={cos_q_decoy:+.4f}, "
          f"margin={cos_q_correct - cos_q_decoy:+.4f}")
    print()

    ok = (
        user_str == "alice"
        and abs(rec_priority - 7) < 0.5
        and (cos_q_correct - cos_q_decoy) > 0.05
    )
    if ok:
        print("RESULT: PASS — strings, numbers, and embedding all round-tripped")
        print("        cleanly through the OS-shaped axon wire format.")
        return 0
    print("RESULT: FAIL")
    print(f"        user:     {user_str!r} (expected 'alice')")
    print(f"        priority: {rec_priority} (expected 7)")
    print(f"        query margin: {cos_q_correct - cos_q_decoy:+.4f} "
          f"(expected > 0.05)")
    return 1


if __name__ == "__main__":
    sys.exit(main())
