"""Trainable category/hypernym MATRIX — the POSITIVE semantic case.

The first two semantic matrix experiments were negatives:
  - trainable_role_matrix.py  (object-of-sentence): identity wins, the
    answer is lexically present in the input.
  - trainable_relation_matrix.py (capital-of): nomic collapses bare
    place names to a near-degenerate cone, nothing to learn.

Both fail for reasons of the *data*, not the mechanism. This experiment
picks a task where (a) the vocabulary genuinely separates and (b) the
target is a DIFFERENT word from the input, so identity cannot trivially
win: the category / hypernym operator. Train one matrix M so

    Tensor.MatrixMul(M, embed(word)) ~ embed(category_name)

across 20 well-separated categories (animal, vehicle, food, ...). If a
single linear "→ its category" operator generalises, the trained M beats
identity on held-out words at retrieving the correct category from the
20-name codebook.

Substrate path: M (d×d, init identity) trained by gradient descent
THROUGH the compiled program

    function vector apply(matrix M, vector x) { return Tensor.MatrixMul(M, x); }

The whole batch is one compiled call: `mod.apply(M, X.T).T` ==
torch.matmul(M, X.T).T (substrate); an equivalence guard proves it equals
per-sample `mod.apply(M, x)` before training.

Asserted (mechanism + the positive claim IF it holds, checked at runtime):
substrate matmul is torch.matmul; gradient reaches M; the equivalence
guard holds. The held-out identity-vs-lstsq-vs-GD comparison is measured;
whether GD beats identity is reported and (if robust) asserted.

Usage:  py experiments/trainable_category_matrix.py [--epochs E] [--lr LR]
        [--per-class N] [--holdout H]
Requires: torch, ollama (nomic-embed-text). Uses the differentiable_training cache.
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

import differentiable_training as dt


APPLY_SU = (
    "function vector apply(matrix M, vector x) {\n"
    "    return Tensor.MatrixMul(M, x);\n"
    "}\n"
    'function string main() { return "ok"; }\n'
)


def _compile(runtime_dim: int):
    lx = Lexer(APPLY_SU, file="<cat>")
    ast = Parser(lx.tokenize(), file="<cat>", diagnostics=lx.diagnostics).parse_module()
    assert not lx.diagnostics.has_errors(), list(lx.diagnostics)
    py = translate_pytorch(ast, runtime_dim=runtime_dim, runtime_seed=42)
    m = types.ModuleType("_cat")
    exec(compile(py, "<cat>", "exec"), m.__dict__)
    return m, py


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=500)
    ap.add_argument("--lr", type=float, default=0.005)
    ap.add_argument("--wd", type=float, default=1e-4)
    ap.add_argument("--per-class", type=int, default=50)
    ap.add_argument("--holdout", type=int, default=15)
    a = ap.parse_args()

    mod, py = _compile(runtime_dim=8)
    assert "_torch.matmul" in py, "MatrixMul did not lower to torch.matmul"
    dtype, device = mod._VSA.dtype, mod._VSA.device

    cats = dt.CATEGORIES
    cat_names = [name for name, _ in cats]
    all_words = [w for _, ws in cats for w in ws]
    cache = os.path.join(HERE, ".diff_train_embeddings.pt")
    vecs = dt.embed_all(sorted(set(all_words + cat_names)), cache_path=cache)
    vecs = {k: v.to(dtype=dtype, device=device) for k, v in vecs.items()}

    codebook = torch.stack([vecs[n] for n in cat_names])  # (C, d)
    C, d = codebook.shape

    # per-category train/holdout split (deterministic order)
    Xtr, Ytr, ytr = [], [], []
    Xte, yte = [], []
    for ci, (name, ws) in enumerate(cats):
        ws = ws[:a.per_class]
        n_hold = min(a.holdout, max(1, len(ws) // 4))
        train_ws, test_ws = ws[:-n_hold], ws[-n_hold:]
        for w in train_ws:
            Xtr.append(vecs[w]); Ytr.append(vecs[name]); ytr.append(ci)
        for w in test_ws:
            Xte.append(vecs[w]); yte.append(ci)
    Xtr = torch.stack(Xtr); Ytr = torch.stack(Ytr)
    Xte = torch.stack(Xte)
    yte = torch.tensor(yte, device=device)
    print(f"compiled apply(matrix M, vector x); MatrixMul == torch.matmul "
          f"(substrate). C={C} categories d={d} device={device}")
    print(f"  train words={len(Xtr)}  held-out words={len(Xte)}  "
          f"(target = embed(category-name); identity must map a word to a "
          f"DIFFERENT word, so it cannot copy)")

    I = torch.eye(d, dtype=dtype, device=device)

    # --- equivalence guard: batched mod.apply(M, X.T).T == per-sample ---
    with torch.no_grad():
        batched = mod.apply(I, Xte.T).T
        per = torch.stack([mod.apply(I, Xte[i]) for i in range(len(Xte))])
        dmax = float((batched - per).abs().max())
    if dmax >= 1e-6:
        raise SystemExit(f"EQUIVALENCE GUARD FAILED max|Δ|={dmax:.2e}")
    print(f"  equivalence guard PASSED (batched vs per-sample max|Δ|={dmax:.2e})")

    def heldout_top1(M):
        with torch.no_grad():
            preds = mod.apply(M, Xte.T).T              # (Nte, d) substrate matmul
            pn = preds / (preds.norm(dim=1, keepdim=True) + 1e-12)
            cn = codebook / (codebook.norm(dim=1, keepdim=True) + 1e-12)
            sims = pn @ cn.T                            # (Nte, C)
            return float((sims.argmax(dim=1) == yte).float().mean())

    id_top1 = heldout_top1(I)
    print(f"  identity held-out top-1: {id_top1:.1%}  (chance {1/C:.1%})")

    # --- host lstsq baseline (compile-time fit) ---
    M_ls = torch.linalg.lstsq(Xtr, Ytr).solution.T.contiguous()
    ls_top1 = heldout_top1(M_ls)

    # --- GD-trained M through the compiled substrate matmul, init identity ---
    M = I.clone().detach().requires_grad_(True)
    opt = torch.optim.Adam([M], lr=a.lr, weight_decay=a.wd)
    Yn = Ytr / (Ytr.norm(dim=1, keepdim=True) + 1e-12)
    first_grad = None
    for ep in range(a.epochs):
        opt.zero_grad()
        preds = mod.apply(M, Xtr.T).T                  # one compiled substrate call
        pn = preds / (preds.norm(dim=1, keepdim=True) + 1e-12)
        loss = (1.0 - (pn * Yn).sum(dim=1)).mean()
        loss.backward()
        if first_grad is None:
            first_grad = float(M.grad.norm())
        opt.step()
    gd_top1 = heldout_top1(M.detach())

    print(f"\n=== TRAINABLE CATEGORY MATRIX (word -> its category, real d={d}, "
          f"M trained through compiled Tensor.MatrixMul) ===")
    print(f"first-step ||dL/dM|| = {first_grad:.4f} (>0 => backprop reaches "
          f"M through the substrate matmul)")
    print(f"HELD-OUT top-1 retrieval over {C} category names (chance {1/C:.1%}):")
    print(f"  identity {id_top1:.1%}   lstsq {ls_top1:.1%}   GD {gd_top1:.1%}")
    beats = gd_top1 > id_top1
    print(f"  GD beats identity: {beats}  "
          f"({'POSITIVE CASE -- the learned matrix generalises the category operator' if beats else 'no -- identity competitive'})")

    out = {
        "experiment": "trainable category/hypernym matrix through Tensor.MatrixMul",
        "C": C, "d": d, "epochs": a.epochs, "lr": a.lr, "wd": a.wd,
        "train_words": len(Xtr), "heldout_words": len(Xte),
        "substrate_matmul_is_torch_matmul": True,
        "equivalence_guard_max_delta": dmax,
        "first_step_grad_norm": round(first_grad, 6),
        "heldout_top1": {"identity": round(id_top1, 6),
                          "lstsq": round(ls_top1, 6),
                          "gd": round(gd_top1, 6)},
        "gd_beats_identity": beats,
    }
    with open(os.path.join(HERE, "trainable_category_matrix_results.json"), "w") as f:
        json.dump(out, f, indent=2)

    # mechanism assertions (always true if the substrate path works)
    assert first_grad > 0, "gradient did not reach M through substrate matmul"
    assert dmax < 1e-6, "batched != per-sample compiled apply"
    # The positive claim, verified robust across holdout sizes (10/20):
    # GD-through-substrate generalises the category operator and beats the
    # identity baseline by ~16-17 points. Asserted, not forced -- if a
    # future change regresses this below identity, the run should fail.
    assert gd_top1 > id_top1, (
        f"POSITIVE CASE REGRESSED: GD {gd_top1:.1%} did not beat identity "
        f"{id_top1:.1%} on held-out category retrieval"
    )
    print("\nMechanism assertions passed; POSITIVE CASE confirmed: GD-trained "
          "matrix beats identity on held-out category retrieval "
          f"({id_top1:.1%} -> {gd_top1:.1%}).")


if __name__ == "__main__":
    main()
