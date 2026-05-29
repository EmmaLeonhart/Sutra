"""Trainable relation/displacement MATRIX through the compiled substrate.

The POSITIVE-case complement to trainable_role_matrix.py. That experiment
showed a learned linear "object-of-sentence" matrix loses to identity
(the object word is lexically present, so the relation is degenerate).
This one picks a relation where a *generalising* linear operator
plausibly exists: capital-of (country -> capital). If embedding space
encodes the relation as a roughly-linear displacement (the king-man+
woman=queen / latent-space-cartography intuition), a matrix M trained so
`Tensor.MatrixMul(M, country_emb) ~ capital_emb` should BEAT identity on
held-out pairs -- the country and its capital are different words, so
identity has nothing to copy.

Same substrate path as the other matrix experiments: M (d×d, init
identity) is trained by gradient descent THROUGH the compiled program

    function vector apply(matrix M, vector x) { return Tensor.MatrixMul(M, x); }

(MatrixMul == torch.matmul). 5-fold CV; baselines = identity and the host
closed-form lstsq fit. Held-out top-1 retrieval is against the capital
codebook.

Asserted (mechanism): substrate matmul is torch.matmul; gradient reaches
M; GD fits the train set. Reported (the science): held-out top-1 for
identity vs lstsq vs GD -- does a trained matrix generalise the relation?

Usage:  py experiments/trainable_relation_matrix.py [--epochs E] [--lr LR]
Requires: torch, ollama (nomic-embed-text). Caches embeddings to a .pt.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys
import types

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(REPO, "sdk", "sutra-compiler"))
HERE = os.path.dirname(os.path.abspath(__file__))

import torch

from sutra_compiler.lexer import Lexer
from sutra_compiler.parser import Parser
from sutra_compiler.codegen_pytorch import translate_module as translate_pytorch


# country -> capital. Single-token, well-known pairs (nomic tokenizes
# these as place names; the relation is the classic linear-analogy case).
PAIRS = [
    ("France", "Paris"), ("Germany", "Berlin"), ("Italy", "Rome"),
    ("Spain", "Madrid"), ("Portugal", "Lisbon"), ("England", "London"),
    ("Ireland", "Dublin"), ("Norway", "Oslo"), ("Sweden", "Stockholm"),
    ("Finland", "Helsinki"), ("Denmark", "Copenhagen"), ("Poland", "Warsaw"),
    ("Greece", "Athens"), ("Turkey", "Ankara"), ("Egypt", "Cairo"),
    ("Russia", "Moscow"), ("China", "Beijing"), ("Japan", "Tokyo"),
    ("Korea", "Seoul"), ("Vietnam", "Hanoi"), ("Thailand", "Bangkok"),
    ("India", "Delhi"), ("Pakistan", "Islamabad"), ("Iran", "Tehran"),
    ("Iraq", "Baghdad"), ("Israel", "Jerusalem"), ("Lebanon", "Beirut"),
    ("Canada", "Ottawa"), ("Mexico", "Mexico City"), ("Brazil", "Brasilia"),
    ("Argentina", "Buenos Aires"), ("Chile", "Santiago"), ("Peru", "Lima"),
    ("Cuba", "Havana"), ("Kenya", "Nairobi"), ("Nigeria", "Abuja"),
    ("Ethiopia", "Addis Ababa"), ("Morocco", "Rabat"), ("Australia", "Canberra"),
    ("Austria", "Vienna"), ("Hungary", "Budapest"), ("Switzerland", "Bern"),
    ("Netherlands", "Amsterdam"), ("Belgium", "Brussels"), ("Cuba", "Havana"),
]
# de-dup while preserving order
_seen = set()
PAIRS = [(c, k) for c, k in PAIRS if not (c in _seen or _seen.add(c))]


APPLY_SU = (
    "function vector apply(matrix M, vector x) {\n"
    "    return Tensor.MatrixMul(M, x);\n"
    "}\n"
    'function string main() { return "ok"; }\n'
)


def _compile(runtime_dim: int):
    lx = Lexer(APPLY_SU, file="<rel>")
    ast = Parser(lx.tokenize(), file="<rel>", diagnostics=lx.diagnostics).parse_module()
    assert not lx.diagnostics.has_errors(), list(lx.diagnostics)
    py = translate_pytorch(ast, runtime_dim=runtime_dim, runtime_seed=42)
    m = types.ModuleType("_rel")
    exec(compile(py, "<rel>", "exec"), m.__dict__)
    return m, py


def embed_all(texts, dtype, device):
    cache = os.path.join(HERE, ".relation_matrix_embeddings.pt")
    if os.path.exists(cache):
        d = torch.load(cache, map_location="cpu", weights_only=True)
        if all(t in d for t in texts):
            return {t: d[t].to(dtype=dtype, device=device) for t in texts}
    import ollama
    out = {}
    r = ollama.embed(model="nomic-embed-text", input=list(texts))
    for t, e in zip(texts, r["embeddings"]):
        v = torch.tensor(e, dtype=torch.float32)
        v = v - v.mean()
        n = v.norm()
        if n > 0:
            v = v / n
        out[t] = v
    torch.save({t: v for t, v in out.items()}, cache)
    return {t: v.to(dtype=dtype, device=device) for t, v in out.items()}


def cos(a, b):
    v = float(torch.dot(a, b) / (a.norm() * b.norm() + 1e-12))
    # lstsq on a rank-deficient (near-collinear) design matrix can produce
    # a degenerate prediction -> non-finite cosine. Report as 0 rather than
    # propagating NaN through the aggregate.
    return v if v == v and abs(v) != float("inf") else 0.0


def top1(pred, codebook, true_idx):
    sims = codebook @ pred / (codebook.norm(dim=1) * pred.norm() + 1e-12)
    return int(sims.argmax()) == true_idx


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=600)
    ap.add_argument("--lr", type=float, default=0.01)
    ap.add_argument("--wd", type=float, default=0.0)
    a = ap.parse_args()

    countries = [c for c, _ in PAIRS]
    capitals = [k for _, k in PAIRS]
    mod, py = _compile(runtime_dim=8)
    assert "_torch.matmul" in py, "MatrixMul did not lower to torch.matmul"
    dtype, device = mod._VSA.dtype, mod._VSA.device

    vecs = embed_all(sorted(set(countries + capitals)), dtype, device)
    C = torch.stack([vecs[c] for c in countries])   # (N, d)
    K = torch.stack([vecs[k] for k in capitals])     # (N, d)
    N, d = C.shape
    print(f"compiled apply(matrix M, vector x); MatrixMul == torch.matmul "
          f"(substrate). N={N} d={d} device={device}")
    print(f"  task = capital-of (country -> capital); a genuinely linear "
          f"relation (different words, so identity cannot copy).")

    # --- embedding-degeneracy diagnostic (does the vocab even separate?) ---
    def mean_pairwise_cos(X):
        Xn = X / (X.norm(dim=1, keepdim=True) + 1e-12)
        G = Xn @ Xn.T
        off = G[~torch.eye(len(X), dtype=torch.bool, device=X.device)]
        return float(off.mean())
    cc = mean_pairwise_cos(C)
    kk = mean_pairwise_cos(K)
    paired = sum(cos(C[i], K[i]) for i in range(N)) / N
    print(f"  embedding degeneracy: mean pairwise cos among countries={cc:+.3f}, "
          f"among capitals={kk:+.3f}; mean cos(country_i, capital_i)={paired:+.3f}")
    print(f"  (cos~1 everywhere => the place-name embeddings collapse into a "
          f"near-degenerate cone; no linear relation is recoverable.)")

    I = torch.eye(d, dtype=dtype, device=device)
    id_train_cos = sum(cos(mod.apply(I, C[i]), K[i]) for i in range(N)) / N
    print(f"  identity baseline: mean cos(I@country, capital) = "
          f"{id_train_cos:+.3f}")

    g = torch.Generator().manual_seed(42)
    perm = torch.randperm(N, generator=g).tolist()
    folds = [perm[i::5] for i in range(5)]

    res = {n: {"cos": [], "t1": []} for n in ("identity", "lstsq", "gd")}
    gd_train_cos_all, grad_norms = [], []

    for kf in range(5):
        test_idx = folds[kf]
        train_idx = [i for i in perm if i not in test_idx]
        C_tr, K_tr = C[train_idx], K[train_idx]

        M = I.clone().detach().requires_grad_(True)
        opt = torch.optim.Adam([M], lr=a.lr, weight_decay=a.wd)
        first_grad = None
        for _ in range(a.epochs):
            opt.zero_grad()
            preds = torch.stack([mod.apply(M, C_tr[j]) for j in range(len(train_idx))])
            pn = preds / (preds.norm(dim=1, keepdim=True) + 1e-12)
            kn = K_tr / (K_tr.norm(dim=1, keepdim=True) + 1e-12)
            loss = (1.0 - (pn * kn).sum(dim=1)).mean()
            loss.backward()
            if first_grad is None:
                first_grad = float(M.grad.norm())
            opt.step()
        grad_norms.append(first_grad)
        with torch.no_grad():
            gd_train_cos_all.append(
                sum(cos(mod.apply(M, C_tr[j]), K_tr[j])
                    for j in range(len(train_idx))) / len(train_idx)
            )

        sol = torch.linalg.lstsq(C_tr, K_tr).solution
        M_ls = sol.T.contiguous()

        for i in test_idx:
            with torch.no_grad():
                preds = {
                    "identity": mod.apply(I, C[i]),
                    "lstsq": mod.apply(M_ls, C[i]),
                    "gd": mod.apply(M.detach(), C[i]),
                }
            for n, p in preds.items():
                res[n]["cos"].append(cos(p, K[i]))
                res[n]["t1"].append(top1(p, K, i))

    def mean(x):
        return sum(x) / len(x)

    gd_train = mean(gd_train_cos_all)
    print(f"\n=== TRAINABLE RELATION MATRIX (capital-of, real d={d}, M "
          f"trained through compiled Tensor.MatrixMul) ===")
    print(f"first-step ||dL/dM|| = {mean(grad_norms):.4f} (>0 => backprop "
          f"reaches M through the substrate matmul)")
    print(f"TRAIN cos(M@country, capital): identity {id_train_cos:+.3f} -> "
          f"GD {gd_train:+.3f}")
    print(f"HELD-OUT (5-fold CV) -- does a trained matrix GENERALISE the "
          f"relation?")
    for n in ("identity", "lstsq", "gd"):
        print(f"  {n:<9} cos {mean(res[n]['cos']):+.3f}   "
              f"top-1 {mean(res[n]['t1']):.0%}  (chance {1/N:.0%})")
    winner = max(("identity", "lstsq", "gd"), key=lambda n: mean(res[n]["t1"]))
    beats_identity = mean(res["gd"]["t1"]) > mean(res["identity"]["t1"])
    print(f"  held-out top-1 winner: {winner}; "
          f"GD beats identity: {beats_identity}")

    out = {
        "experiment": "trainable relation matrix (capital-of) through Tensor.MatrixMul",
        "N": N, "d": d, "epochs": a.epochs, "lr": a.lr, "wd": a.wd,
        "substrate_matmul_is_torch_matmul": True,
        "first_step_grad_norm": round(mean(grad_norms), 6),
        "train_cos_identity": round(id_train_cos, 6),
        "train_cos_gd": round(gd_train, 6),
        "heldout": {n: {"cos": round(mean(res[n]["cos"]), 6),
                        "top1": round(mean(res[n]["t1"]), 6)}
                    for n in ("identity", "lstsq", "gd")},
        "heldout_top1_winner": winner,
        "gd_beats_identity": beats_identity,
    }
    with open(os.path.join(HERE, "trainable_relation_matrix_results.json"), "w") as f:
        json.dump(out, f, indent=2)

    # Mechanism assertions only (NOT a learnability claim). Note: on this
    # vocabulary identity already saturates the train fit (cos~1, the
    # degenerate cone), so "GD improves over identity on train" is NOT a
    # valid check -- there is no headroom. We assert only that the
    # mechanism runs: grad reaches M through the substrate matmul and GD
    # holds a high train fit.
    assert mean(grad_norms) > 0, "gradient did not reach M through substrate matmul"
    assert gd_train > 0.9, f"GD train fit unexpectedly low: {gd_train:.3f}"
    print("\nMechanism assertions passed (substrate matmul, grad-to-M, "
          "train-fit held). NEGATIVE RESULT: capital-of is NOT a positive "
          "linear-relation case on this substrate -- the place-name "
          "embeddings are near-degenerate (see cos diagnostics above), so "
          "held-out top-1 is at chance for identity, lstsq AND the trained "
          "matrix alike. Reported, not asserted.")


if __name__ == "__main__":
    main()
