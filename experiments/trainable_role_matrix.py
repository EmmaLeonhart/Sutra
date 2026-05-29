"""Trainable role MATRIX at real scale, through the compiled substrate.

Closes the loop between two things:
  - planning/exploratory/object_matrix_probe.py -- the HOST least-squares
    probe asking "does a learned linear 'object-of-sentence' matrix M
    exist (M @ sentence_emb ~ object_emb)?" Its finding: the identity
    baseline wins, because the object word is lexically present in the
    sentence embedding.
  - experiments/trainable_matrix_adjustment.py -- the trainable-matrix
    MECHANISM (a `matrix` parameter trained through the compiled
    Tensor.MatrixMul) demonstrated on clean toy permutations.

This experiment runs the trainable-matrix mechanism on the probe's REAL
d=768 nomic embeddings: M (init identity) is trained by gradient descent
THROUGH the compiled Sutra program

    function vector apply(matrix M, vector x) { return Tensor.MatrixMul(M, x); }

(MatrixMul == torch.matmul, substrate). We validate the mechanism at real
scale and reproduce the probe's identity-wins conclusion via the
substrate path, with the host closed-form lstsq fit as a second baseline.

What is asserted (mechanism, true regardless of task learnability):
  - the matmul the program runs IS torch.matmul (substrate),
  - gradient reaches M through the compiled matmul (||dL/dM|| > 0),
  - GD drives the TRAIN-set cos(M@s, o) up from the identity baseline.
What is only reported (the probe's open question, small-N + d>>N):
  - held-out cos / top-1 vs identity and vs host lstsq.

Usage:  py experiments/trainable_role_matrix.py [--epochs E] [--lr LR]
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

# Reuse the exact SVO pairs from the dark-code probe so this is a true
# substrate reproduction of the same task.
sys.path.insert(0, os.path.join(REPO, "planning", "exploratory"))
from object_matrix_probe import PAIRS  # noqa: E402


APPLY_SU = (
    "function vector apply(matrix M, vector x) {\n"
    "    return Tensor.MatrixMul(M, x);\n"
    "}\n"
    'function string main() { return "ok"; }\n'
)


def _compile(runtime_dim: int):
    src = APPLY_SU
    lx = Lexer(src, file="<role>")
    ast = Parser(lx.tokenize(), file="<role>", diagnostics=lx.diagnostics).parse_module()
    assert not lx.diagnostics.has_errors(), list(lx.diagnostics)
    py = translate_pytorch(ast, runtime_dim=runtime_dim, runtime_seed=42)
    m = types.ModuleType("_role")
    exec(compile(py, "<role>", "exec"), m.__dict__)
    return m, py


def embed_all(texts, dtype, device):
    cache = os.path.join(HERE, ".role_matrix_embeddings.pt")
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
    return float(torch.dot(a, b) / (a.norm() * b.norm() + 1e-12))


def top1(pred, O_codebook, true_idx):
    sims = O_codebook @ pred / (
        O_codebook.norm(dim=1) * pred.norm() + 1e-12
    )
    return int(sims.argmax()) == true_idx


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=400)
    ap.add_argument("--lr", type=float, default=0.01)
    ap.add_argument("--wd", type=float, default=1e-4)
    a = ap.parse_args()

    sentences = [s for s, _ in PAIRS]
    objects = [o for _, o in PAIRS]
    mod, py = _compile(runtime_dim=8)  # codebook unused; dim irrelevant
    assert "_torch.matmul" in py, "MatrixMul did not lower to torch.matmul"
    dtype, device = mod._VSA.dtype, mod._VSA.device

    vecs = embed_all(sorted(set(sentences + objects)), dtype, device)
    S = torch.stack([vecs[s] for s in sentences])  # (N, d)
    O = torch.stack([vecs[o] for o in objects])     # (N, d)
    N, d = S.shape
    print(f"compiled apply(matrix M, vector x); MatrixMul == torch.matmul "
          f"(substrate). N={N} d={d} device={device}")
    print(f"  task = object_matrix_probe SVO pairs; M (d×d) trained through "
          f"the compiled matmul.")

    # ---- identity baseline (M = I) through the SAME compiled apply ----
    I = torch.eye(d, dtype=dtype, device=device)
    id_train_cos = sum(cos(mod.apply(I, S[i]), O[i]) for i in range(N)) / N
    print(f"  identity baseline: mean cos(I@s, o) = {id_train_cos:+.3f} "
          f"(probe's 'identity wins' baseline)")

    # ---- 5-fold CV: GD-trained M vs host lstsq vs identity ----
    g = torch.Generator().manual_seed(42)
    perm = torch.randperm(N, generator=g).tolist()
    folds = [perm[i::5] for i in range(5)]

    gd_heldout_cos, gd_heldout_top1 = [], []
    ls_heldout_cos, ls_heldout_top1 = [], []
    id_heldout_cos, id_heldout_top1 = [], []
    gd_train_cos_all, grad_norms = [], []

    for kf in range(5):
        test_idx = folds[kf]
        train_idx = [i for i in perm if i not in test_idx]
        S_tr, O_tr = S[train_idx], O[train_idx]

        # GD-trained M through the compiled substrate matmul, init identity
        M = I.clone().detach().requires_grad_(True)
        opt = torch.optim.Adam([M], lr=a.lr, weight_decay=a.wd)
        first_grad = None
        for _ in range(a.epochs):
            opt.zero_grad()
            preds = torch.stack([mod.apply(M, S_tr[j]) for j in range(len(train_idx))])
            # cosine loss (1 - cos) summed over train pairs
            pn = preds / (preds.norm(dim=1, keepdim=True) + 1e-12)
            on = O_tr / (O_tr.norm(dim=1, keepdim=True) + 1e-12)
            loss = (1.0 - (pn * on).sum(dim=1)).mean()
            loss.backward()
            if first_grad is None:
                first_grad = float(M.grad.norm())
            opt.step()
        grad_norms.append(first_grad)
        with torch.no_grad():
            gd_train_cos_all.append(
                sum(cos(mod.apply(M, S_tr[j]), O_tr[j])
                    for j in range(len(train_idx))) / len(train_idx)
            )

        # host lstsq baseline: M_ls with S_tr @ M_ls.T ~ O_tr (compile-time fit)
        sol = torch.linalg.lstsq(S_tr, O_tr).solution  # (d, d), M_ls.T
        M_ls = sol.T.contiguous()

        for i in test_idx:
            with torch.no_grad():
                p_gd = mod.apply(M.detach(), S[i])
                p_ls = mod.apply(M_ls, S[i])
                p_id = mod.apply(I, S[i])
            gd_heldout_cos.append(cos(p_gd, O[i]))
            ls_heldout_cos.append(cos(p_ls, O[i]))
            id_heldout_cos.append(cos(p_id, O[i]))
            gd_heldout_top1.append(top1(p_gd, O, i))
            ls_heldout_top1.append(top1(p_ls, O, i))
            id_heldout_top1.append(top1(p_id, O, i))

    def mean(x):
        return sum(x) / len(x)

    gd_train = mean(gd_train_cos_all)
    print(f"\n=== TRAINABLE ROLE MATRIX (real d={d} embeddings, M trained "
          f"through compiled Tensor.MatrixMul) ===")
    print(f"first-step ||dL/dM|| = {mean(grad_norms):.4f} "
          f"(>0 => backprop reaches M through the substrate matmul)")
    print(f"TRAIN cos(M@s, o):  identity {id_train_cos:+.3f}  ->  "
          f"GD-trained {gd_train:+.3f}  (mechanism: GD fits the train set)")
    print(f"HELD-OUT (5-fold CV) -- the probe's open question:")
    print(f"  mean cos(pred, o_true):  identity {mean(id_heldout_cos):+.3f}  "
          f"lstsq {mean(ls_heldout_cos):+.3f}  GD {mean(gd_heldout_cos):+.3f}")
    print(f"  top-1 retrieval:         identity {mean(id_heldout_top1):.0%}  "
          f"lstsq {mean(ls_heldout_top1):.0%}  GD {mean(gd_heldout_top1):.0%}  "
          f"(chance {1/N:.0%})")

    winner = max(
        [("identity", mean(id_heldout_top1)),
         ("lstsq", mean(ls_heldout_top1)),
         ("GD", mean(gd_heldout_top1))],
        key=lambda kv: kv[1],
    )[0]
    print(f"  held-out top-1 winner: {winner} "
          f"(probe predicted identity; small-N d>>N regime)")

    out = {
        "experiment": "trainable role matrix through compiled Tensor.MatrixMul",
        "N": N, "d": d, "epochs": a.epochs, "lr": a.lr, "wd": a.wd,
        "substrate_matmul_is_torch_matmul": True,
        "first_step_grad_norm": round(mean(grad_norms), 6),
        "train_cos_identity": round(id_train_cos, 6),
        "train_cos_gd": round(gd_train, 6),
        "heldout_cos": {
            "identity": round(mean(id_heldout_cos), 6),
            "lstsq": round(mean(ls_heldout_cos), 6),
            "gd": round(mean(gd_heldout_cos), 6),
        },
        "heldout_top1": {
            "identity": round(mean(id_heldout_top1), 6),
            "lstsq": round(mean(ls_heldout_top1), 6),
            "gd": round(mean(gd_heldout_top1), 6),
        },
        "heldout_top1_winner": winner,
    }
    with open(os.path.join(HERE, "trainable_role_matrix_results.json"), "w") as f:
        json.dump(out, f, indent=2)

    # ---- mechanism assertions (NOT task-learnability claims) ----
    assert mean(grad_norms) > 0, "gradient did not reach M through substrate matmul"
    assert gd_train > id_train_cos + 0.05, (
        f"GD did not fit the train set better than identity: "
        f"{id_train_cos:.3f} -> {gd_train:.3f}"
    )
    print("\nMechanism assertions passed (substrate matmul, grad-to-M, "
          "train-fit). Held-out numbers are reported, not asserted.")


if __name__ == "__main__":
    main()
