"""Weights<->code corpus generator (v0) — the self-propagation payoff.

Emma's 2026-05-29 strategic direction: now that Sutra has a trainable
matrix component, mass-generate program variations whose behavior is
carried by (file-backed) matrices, and record (code, weights, IO) triples
as training data for the end goal — converting WEIGHTS back to CODE
(weight->code decompilation).

This v0 RANDOMISES the matrix components (Emma: "even just kind of
randomise the trainable components ... to create different code, different
matrix variations") rather than training them — fast, and every triple is
a valid datapoint. Each generated program is:

  - model-free (no embed / basis_vector -> no Ollama; compile_su
    llm_model defaults to "none"), runtime_dim = K (dim-audit honest);
  - a small structure drawn from a grammar, parameterised by one or two
    K×K matrices loaded from CSV via `load_matrix` (the file-backed weight
    store, enabler #12);
  - run on the real substrate (Tensor.MatrixMul + vector add) to produce
    the recorded input->output behavior.

Structure grammar (v0, 3 families):
  linear    : M0 @ x
  chain2    : M1 @ (M0 @ x)
  residual  : (M0 @ x) + x

Weight kinds: gaussian (randn) and perm (random permutation matrix).

Output: a directory with one CSV per weight matrix + a corpus.jsonl whose
each line is {id, structure, K, weight_kind, seed, source (with RELATIVE
csv basenames, portable), weights[], io[], runtime_dim, llm_model}. The
`source` is the canonical code; `weights` are the separate CSV files;
together with `io` that is one (code <-> weights <-> behavior) datapoint.

Usage:
    py experiments/weight_to_code_corpus.py [--out DIR] [--ks 4,6]
        [--kinds gaussian,perm] [--seeds 0] [--n-io 4]
"""
from __future__ import annotations

import argparse
import io as _io
import json
import os
import sys

sys.stdout = _io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(REPO, "sdk", "sutra-compiler"))
HERE = os.path.dirname(os.path.abspath(__file__))

import torch

from sutra_compiler.lexer import Lexer
from sutra_compiler.parser import Parser
from sutra_compiler.codegen_pytorch import translate_module as translate_pytorch


# Each structure: the matrices it uses (in order) and a body template over
# those matrix names + the input `x`. Every body below is verified to
# compile + run on the substrate (probed 2026-05-29). bind/unbind are
# excluded (they build full-extended-dim role rotations, not bare-K-vector
# ops) and vector `tanh` is excluded (no element-wise vector tanh) — both
# error on bare K-vectors, so they are not part of this bare-vector grammar.
STRUCTURES = {
    "linear":   {"mats": ["M0"],       "body": "Tensor.MatrixMul(M0, x)"},
    "chain2":   {"mats": ["M0", "M1"], "body": "Tensor.MatrixMul(M1, Tensor.MatrixMul(M0, x))"},
    "chain3":   {"mats": ["M0", "M1", "M2"], "body": "Tensor.MatrixMul(M2, Tensor.MatrixMul(M1, Tensor.MatrixMul(M0, x)))"},
    "residual": {"mats": ["M0"],       "body": "Tensor.MatrixMul(M0, x) + x"},
    "diff":     {"mats": ["M0"],       "body": "Tensor.MatrixMul(M0, x) - x"},
    "scaled":   {"mats": ["M0"],       "body": "2.0 * Tensor.MatrixMul(M0, x)"},
    "affine":   {"mats": ["M0"],       "body": "0.5 * Tensor.MatrixMul(M0, x) + 0.5 * x"},
    "sum2":     {"mats": ["M0", "M1"], "body": "Tensor.MatrixMul(M0, x) + Tensor.MatrixMul(M1, x)"},
    "bundle2":  {"mats": ["M0"],       "body": "bundle(Tensor.MatrixMul(M0, x), x)"},
    "bundle3":  {"mats": ["M0", "M1"], "body": "bundle(Tensor.MatrixMul(M0, x), Tensor.MatrixMul(M1, x), x)"},
}


# Cache one compiled `apply(matrix M, vector x) = M @ x` per K, so trained
# weights are produced by gradient descent THROUGH THE COMPILED SUBSTRATE
# matmul (the trainable component), not host-side torch.
_APPLY_CACHE: dict = {}


def _apply_for(K: int):
    if K not in _APPLY_CACHE:
        src = (
            "function vector apply(matrix M, vector x) {\n"
            "    return Tensor.MatrixMul(M, x);\n"
            "}\n"
            'function string main() { return "ok"; }\n'
        )
        lx = Lexer(src, file="<train>")
        ast = Parser(lx.tokenize(), file="<train>", diagnostics=lx.diagnostics).parse_module()
        ns: dict = {}
        exec(translate_pytorch(ast, llm_model="none", runtime_dim=K), ns)
        _APPLY_CACHE[K] = (ns["apply"], ns["_VSA"])
    return _APPLY_CACHE[K]


def _random_perm_matrix(K, gen):
    perm = torch.randperm(K, generator=gen)
    P = torch.zeros(K, K, dtype=torch.float64)
    for i in range(K):
        P[perm[i], i] = 1.0
    return P


def _random_rotation(K, gen):
    a = torch.randn(K, K, generator=gen, dtype=torch.float64)
    q, r = torch.linalg.qr(a)
    return q * torch.sign(torch.diagonal(r))  # Haar-ish orthogonal


def _train_to_target(target: torch.Tensor, K: int, gen: torch.Generator,
                     epochs: int = 250) -> torch.Tensor:
    """Train a matrix M (init small-random) so M @ e_i == target's column i,
    by MSE through the COMPILED substrate matmul. Returns the trained M —
    weights reached by gradient descent on the substrate (provenance:
    'trained'), carrying the target's structure (orthogonal / permutation)."""
    apply_fn, vsa = _apply_for(K)
    es = [torch.eye(K, dtype=vsa.dtype, device=vsa.device)[i] for i in range(K)]
    tgt = target.to(dtype=vsa.dtype, device=vsa.device).T.contiguous()  # rows = target cols
    M = (0.1 * torch.randn(K, K, generator=gen, dtype=torch.float64)).to(
        dtype=vsa.dtype, device=vsa.device).clone().detach().requires_grad_(True)
    opt = torch.optim.Adam([M], lr=0.05)
    for _ in range(epochs):
        opt.zero_grad()
        outs = torch.stack([apply_fn(M, e) for e in es])  # (K, K) = M columns
        loss = torch.nn.functional.mse_loss(outs, tgt)
        loss.backward()
        opt.step()
    return M.detach().to(dtype=torch.float64, device="cpu")


def make_weight(kind: str, K: int, gen: torch.Generator) -> torch.Tensor:
    if kind == "gaussian":
        return torch.randn(K, K, generator=gen, dtype=torch.float64)
    if kind == "perm":
        return _random_perm_matrix(K, gen)
    # Trained kinds: weights produced by GD through the compiled substrate
    # matmul toward a structured target (Emma's stated targets: rotations,
    # permutations) — "meaning, not noise". The trained M carries the
    # target's structure (near-orthogonal / near-permutation).
    if kind == "trained_rotation":
        return _train_to_target(_random_rotation(K, gen), K, gen)
    if kind == "trained_perm":
        return _train_to_target(_random_perm_matrix(K, gen), K, gen)
    raise ValueError(f"unknown weight kind {kind!r}")


def write_csv(path: str, M: torch.Tensor) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        for row in M.tolist():
            f.write(",".join(repr(float(v)) for v in row) + "\n")


def build_source(structure: str, mat_to_path: dict) -> str:
    spec = STRUCTURES[structure]
    decls = "".join(
        f'    matrix {m} = load_matrix("{mat_to_path[m]}");\n' for m in spec["mats"]
    )
    return (
        "function vector apply(vector x) {\n"
        f"{decls}"
        f"    return {spec['body']};\n"
        "}\n"
        'function string main() { return "ok"; }\n'
    )


def compile_source(src: str, K: int):
    lx = Lexer(src, file="<corpus>")
    ast = Parser(lx.tokenize(), file="<corpus>", diagnostics=lx.diagnostics).parse_module()
    if lx.diagnostics.has_errors():
        raise RuntimeError(f"corpus program failed to parse: {list(lx.diagnostics)}")
    # model-free (llm_model defaults to 'none' in codegen base only when
    # passed; pass 'none' explicitly), runtime_dim = K (no basis_vector).
    py = translate_pytorch(ast, llm_model="none", runtime_dim=K)
    ns: dict = {}
    exec(py, ns)
    return ns


def main():
    ap = argparse.ArgumentParser()
    # Default output is the `corpus/` submodule (EmmaLeonhart/sutra-w2c-corpus,
    # pinned in Sutra, mirrored to Hugging Face) — the corpus data lives in its
    # own repo, not in Sutra. Override --out for scratch/large runs elsewhere.
    ap.add_argument("--out", default=os.path.join(REPO, "corpus"))
    ap.add_argument("--ks", default="4,6")
    ap.add_argument("--kinds", default="gaussian,perm,trained_rotation,trained_perm")
    ap.add_argument("--seeds", default="0")
    ap.add_argument("--n-io", type=int, default=4)
    a = ap.parse_args()
    Ks = [int(k) for k in a.ks.split(",") if k.strip()]
    kinds = [k for k in a.kinds.split(",") if k.strip()]
    seeds = [int(s) for s in a.seeds.split(",") if s.strip()]
    os.makedirs(a.out, exist_ok=True)

    entries = []
    for structure in STRUCTURES:
        for K in Ks:
            for kind in kinds:
                for seed in seeds:
                    rid = f"{structure}_K{K}_{kind}_s{seed}"
                    gen = torch.Generator().manual_seed(
                        hash((structure, K, kind, seed)) & 0x7FFFFFFF
                    )
                    # weights -> CSV (one per matrix); abs path for compile,
                    # relative basename stored in the portable source.
                    abs_paths, rel_paths, weights_meta = {}, {}, []
                    for m in STRUCTURES[structure]["mats"]:
                        W = make_weight(kind, K, gen)
                        base = f"{rid}_{m}.csv"
                        ap_ = os.path.join(a.out, base)
                        write_csv(ap_, W)
                        abs_paths[m] = ap_.replace("\\", "/")
                        rel_paths[m] = base
                        weights_meta.append(
                            {"name": m, "csv": base, "shape": [K, K], "kind": kind}
                        )

                    src_abs = build_source(structure, abs_paths)   # compiles here
                    src_rel = build_source(structure, rel_paths)   # portable, stored

                    ns = compile_source(src_abs, K)
                    apply_fn, vsa = ns["apply"], ns["_VSA"]

                    iogen = torch.Generator().manual_seed(1000 + seed)
                    io_pairs = []
                    for _ in range(a.n_io):
                        x = torch.randn(K, generator=iogen, dtype=vsa.dtype).to(vsa.device)
                        y = apply_fn(x)
                        io_pairs.append({
                            "input": [round(float(v), 6) for v in x.tolist()],
                            "output": [round(float(v), 6) for v in y.tolist()],
                        })

                    entries.append({
                        "id": rid,
                        "structure": structure,
                        "K": K,
                        "weight_kind": kind,
                        "seed": seed,
                        "source": src_rel,
                        "weights": weights_meta,
                        "io": io_pairs,
                        "runtime_dim": K,
                        "llm_model": "none",
                    })

    corpus_path = os.path.join(a.out, "corpus.jsonl")
    with open(corpus_path, "w", encoding="utf-8", newline="\n") as f:
        for e in entries:
            f.write(json.dumps(e) + "\n")

    print(f"weight<->code corpus v0: {len(entries)} programs "
          f"({len(STRUCTURES)} structures × {len(Ks)} K × {len(kinds)} kinds × "
          f"{len(seeds)} seeds), {a.n_io} IO pairs each, model-free, substrate.")
    print(f"  structures: {', '.join(STRUCTURES)}")
    print(f"  -> {corpus_path}  (+ {sum(len(e['weights']) for e in entries)} weight CSVs)")
    # one-line peek at a sample entry's shape
    e0 = entries[0]
    print(f"  sample id={e0['id']} weights={[w['csv'] for w in e0['weights']]} "
          f"io={len(e0['io'])} src_chars={len(e0['source'])}")


if __name__ == "__main__":
    main()
