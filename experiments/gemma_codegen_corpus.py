"""Gemma-generated Sutra programs for the weights<->code corpus (Emma
2026-05-30 'switch to Gemma for the training-data code').

Emma's locked approach (AskUserQuestion 2026-05-30): use **gemma3:12b**
(ollama, local) to AUGMENT the hand-written structure templates (those
stay as a verified fallback) with FREE-FORM Sutra — Gemma may use any
Sutra ops, every program is validated (compile + run on the substrate),
and only valid ones enter the corpus.

Pipeline:
  1. Few-shot prompt gemma3:12b for programs with the fixed entry contract
     `function vector apply(vector x)` (so IO is recordable) + free-form
     bodies, separated by `---`.
  2. validate(src): must have the apply + main contract; compile (model-
     free first, falling back to nomic if it calls embed/basis_vector); run
     apply on random inputs across candidate dims; keep the first dim that
     produces a finite vector. A program that fails to compile OR never
     runs is REJECTED (free-form => Gemma writes invalid Sutra sometimes;
     the validator is the filter Emma's plan relies on).
  3. Record {id, generator, source, K, weights (inline => []), io[]} to a
     gemma corpus JSONL; report the valid/total yield.

The validation logic is unit-tested deterministically in
`test_gemma_codegen_corpus.py` (no Gemma dependency); the live generation
needs ollama + gemma3:12b.

Usage:
    py experiments/gemma_codegen_corpus.py [--n N] [--out DIR] [--model M]
"""
from __future__ import annotations

import argparse
import io as _io
import json
import os
import re
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(REPO, "sdk", "sutra-compiler"))
HERE = os.path.dirname(os.path.abspath(__file__))

import torch

from sutra_compiler.lexer import Lexer
from sutra_compiler.parser import Parser
from sutra_compiler.codegen_pytorch import translate_module as translate_pytorch

CANDIDATE_DIMS = [2, 3, 4, 5, 6, 8]

PROMPT = """You write programs in Sutra, a small functional language. Each program is:
  function vector apply(vector x) { ... return <expr>; }
  function string main() { return "ok"; }
Allowed operations inside apply: Tensor.MatrixMul(M, x) where M = matrix_literal(vector_literal(a,b,...), vector_literal(...), ...); vector_literal(1.0,2.0,...); bundle(a,b,...) (normalized sum); and vector+vector, vector-vector, scalar*vector. Matrices must be square and match the vector length you use.

Example:
function vector apply(vector x) { matrix M = matrix_literal(vector_literal(0.0, 1.0, 0.0), vector_literal(0.0, 0.0, 1.0), vector_literal(1.0, 0.0, 0.0)); return Tensor.MatrixMul(M, x); }
function string main() { return "ok"; }

Write %d NEW, DIFFERENT valid Sutra programs of exactly this form. Separate each with a line containing only ---. Output ONLY code."""


def split_programs(text: str) -> list[str]:
    """Split a Gemma response into candidate programs. Strips ``` fences,
    splits on --- separators, keeps chunks that contain an apply()."""
    text = re.sub(r"```[a-zA-Z]*", "", text).replace("```", "")
    chunks = re.split(r"^\s*-{3,}\s*$", text, flags=re.MULTILINE)
    progs = []
    for c in chunks:
        c = c.strip()
        if "function vector apply" in c:
            # ensure a main() exists (Gemma sometimes drops it)
            if "function string main" not in c:
                c += '\nfunction string main() { return "ok"; }\n'
            progs.append(c)
    return progs


def validate(src: str):
    """Compile + run a candidate program on the substrate. Returns
    (K, io_pairs) for the first input dim that runs to a finite vector, or
    None if it never compiles/runs (REJECTED)."""
    if "function vector apply(vector x)" not in src:
        return None
    ns = None
    for model in ("none", "nomic-embed-text"):
        try:
            lx = Lexer(src, file="<gemma>")
            ast = Parser(lx.tokenize(), file="<gemma>", diagnostics=lx.diagnostics).parse_module()
            if lx.diagnostics.has_errors():
                return None  # parse error -> reject (model won't help)
            ns_try: dict = {}
            exec(translate_pytorch(ast, llm_model=model, runtime_dim=8), ns_try)
            ns = ns_try
            break
        except Exception:
            ns = None
            continue
    if ns is None or "apply" not in ns:
        return None
    apply_fn, vsa = ns["apply"], ns["_VSA"]
    gen = torch.Generator().manual_seed(7)
    for K in CANDIDATE_DIMS:
        try:
            io_pairs = []
            ok = True
            for _ in range(3):
                x = torch.randn(K, generator=gen, dtype=vsa.dtype).to(vsa.device)
                y = apply_fn(x)
                if not torch.is_tensor(y) or y.ndim != 1 or not torch.isfinite(y).all():
                    ok = False
                    break
                io_pairs.append({
                    "input": [round(float(v), 6) for v in x.tolist()],
                    "output": [round(float(v), 6) for v in y.tolist()],
                })
            if ok and io_pairs:
                return K, io_pairs
        except Exception:
            continue
    return None


def verify_entry(entry: dict) -> tuple[bool, float]:
    """Recompile a corpus entry's `source` and check it reproduces the
    recorded `io` on the substrate — the corpus self-consistency invariant
    (same guard the template corpus has). Returns (ok, max_abs_diff)."""
    src = entry.get("source", "")
    ns = None
    for model in ("none", "nomic-embed-text"):
        try:
            lx = Lexer(src, file="<verify>")
            ast = Parser(lx.tokenize(), file="<verify>", diagnostics=lx.diagnostics).parse_module()
            if lx.diagnostics.has_errors():
                return (False, float("inf"))
            ns_try: dict = {}
            exec(translate_pytorch(ast, llm_model=model, runtime_dim=8), ns_try)
            ns = ns_try
            break
        except Exception:
            ns = None
            continue
    if ns is None or "apply" not in ns:
        return (False, float("inf"))
    apply_fn, vsa = ns["apply"], ns["_VSA"]
    maxd = 0.0
    for pair in entry.get("io", []):
        x = torch.tensor(pair["input"], dtype=vsa.dtype, device=vsa.device)
        try:
            y = apply_fn(x).tolist()
        except Exception:
            return (False, float("inf"))
        for g, w in zip(y, pair["output"]):
            maxd = max(maxd, abs(g - w))
    return (maxd < 1e-4, maxd)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=8, help="programs to request")
    ap.add_argument("--model", default="gemma3:12b")
    ap.add_argument("--out", default=os.path.join(REPO, "corpus"))
    ap.add_argument("--temperature", type=float, default=0.85)
    a = ap.parse_args()
    # Windows-safe unicode for the CLI (not at import, so pytest capture
    # of this module's `validate`/`split_programs` is unaffected).
    sys.stdout = _io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    os.makedirs(a.out, exist_ok=True)

    import ollama
    r = ollama.generate(
        model=a.model, prompt=PROMPT % a.n,
        options={"temperature": a.temperature, "num_predict": 220 * a.n},
    )
    candidates = split_programs(r["response"])

    entries, valid = [], 0
    for i, src in enumerate(candidates):
        v = validate(src)
        status = "REJECT"
        if v is not None:
            K, io_pairs = v
            valid += 1
            status = f"OK K={K}"
            entries.append({
                "id": f"gemma_{i}",
                "generator": a.model,
                "source": src,
                "K": K,
                "weights": [],  # inline literals (no load_matrix) for Gemma v0
                "io": io_pairs,
            })
        print(f"  cand {i}: {status}  ({src.splitlines()[0][:70]}...)")

    out_path = os.path.join(a.out, "gemma_corpus.jsonl")
    with open(out_path, "a", encoding="utf-8", newline="\n") as f:
        for e in entries:
            f.write(json.dumps(e) + "\n")
    print(f"\ngemma codegen ({a.model}): {valid}/{len(candidates)} candidates "
          f"valid (compiled + ran on the substrate); appended to {out_path}")


if __name__ == "__main__":
    main()
