"""Demo: read text from RAM via a Sutra NTM read head + orchestrator.

planning/sutra-spec/ram-pointers.md, queue.md "RAM pointers -> NTM".

Lays a string out in the host RAM device, then drives the compiled
non-halting `read_head` program tick by tick through the orchestrator.
The program emits a program-controlled address each tick (its recurring
substrate cursor); the orchestrator serves RAM[address] back. The
retrieved read stream, decoded, is compared to the ground-truth string
and the true delta is reported.

Run: python experiments/ntm_ram/run_demo.py
"""
from __future__ import annotations

import io
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(REPO, "sdk", "sutra-compiler"))
sys.path.insert(0, os.path.dirname(__file__))

from sutra_compiler.lexer import Lexer            # noqa: E402
from sutra_compiler.parser import Parser          # noqa: E402
from sutra_compiler.codegen_pytorch import translate_module as translate_pytorch  # noqa: E402

from ram_device import RamDevice                  # noqa: E402
from orchestrator import Orchestrator             # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))


def compile_su(path: str, semantic_dim: int):
    with open(path, "r", encoding="utf-8") as f:
        src = f.read()
    lx = Lexer(src, file=path)
    toks = lx.tokenize()
    ast = Parser(toks, file=path, diagnostics=lx.diagnostics).parse_module()
    if lx.diagnostics.has_errors():
        raise RuntimeError(f"parse errors: {list(lx.diagnostics)}")
    # Model-free program (no basis_vector / embed) -> tiny semantic_dim
    # is honest (dim audit, CLAUDE.md). Numbers live in the synthetic
    # block, which keeps its default width.
    py = translate_pytorch(ast, llm_model="none", runtime_dim=semantic_dim)
    ns: dict = {}
    exec(py, ns)
    return ns


def main():
    text = "HELLO, RAM!"
    ns = compile_su(os.path.join(HERE, "text_scan.su"), semantic_dim=2)
    vsa = ns["_VSA"]
    print(f"runtime layout: semantic_dim={vsa.semantic_dim} "
          f"synthetic_dim={vsa.synthetic_dim} dim={vsa.dim}  (model-free)")

    ram = RamDevice(vsa, size=64)
    end = ram.load_text(text, base=0, terminator=True)
    print(f"loaded {len(text)} chars into RAM[0:{end}], sentinel at RAM[{end}]")

    orch = Orchestrator(vsa, ram, ns["read_head"])
    trace = orch.run_read_scan(max_steps=64, stop_on_sentinel=True)
    decoded = orch.decode_text(trace)

    addrs = [a for a, _ in trace]
    print(f"program-emitted address sequence: {addrs}")
    print(f"ground truth : {text!r}")
    print(f"decoded      : {decoded!r}")
    match = decoded == text
    print(f"exact match  : {match}")
    if not match:
        # Report the true delta, character by character (integrity rule).
        n = max(len(text), len(decoded))
        diffs = [(i, text[i] if i < len(text) else None,
                  decoded[i] if i < len(decoded) else None)
                 for i in range(n)
                 if (text[i] if i < len(text) else None)
                 != (decoded[i] if i < len(decoded) else None)]
        print(f"delta ({len(diffs)} mismatched positions): {diffs}")
    return 0 if match else 1


if __name__ == "__main__":
    sys.exit(main())
