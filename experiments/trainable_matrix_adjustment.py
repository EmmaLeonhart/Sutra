"""Trainable MATRIX through Sutra's compiled tensor-op graph.

The constrain-train inventory so far trains SCALARS through the
compiled graph (equality-cosine T, defuzz beta, select temperature,
rank-k gains). This experiment is the first trainable *matrix*: a
`matrix`-typed parameter flows through the compiled Sutra program

    function vector apply(matrix M, vector x) {
        return Tensor.MatrixMul(M, x);
    }

`Tensor.MatrixMul` lowers to `_VSA.matmul` == `torch.matmul`, so the
whole forward runs on the substrate. M is a `torch.nn.Parameter`;
gradient descent updates it through the compiled matmul.

This is Emma's next arc tier after the scalar instances ("harder
matrix stuff") and the natural consumer of the 2026-05-28 matrix-
literal work: training produces a matrix, and the bake-back round-
trips it into a `matrix_literal(...)` .su source (weight -> code).

Task (clean ground truth, no embeddings needed): learn a target
permutation of K one-hot glyph states. M is initialised at the frozen
font.su cyclic-shift-by-1 permutation P and trained to a *different*
target permutation -- literally "shifting the matrix around" under
gradient descent. We measure:

  - gradient flow: ||dL/dM|| nonzero  => backprop reaches the matrix
    through the compiled Tensor.MatrixMul (not a host reimplementation)
  - convergence: Frobenius ||M - target||_F before -> after
  - exact-transform accuracy: argmax(M @ e_i) == perm(i), all i
  - signal-separation gap: min_i (M@e_i)[perm(i)] - max_{j!=perm(i)}
    (M@e_i)[j]   (per CLAUDE.md "Subtler substrate breaches" #3)
  - bake-back: trained M rounded into a matrix_literal .su, recompiled
    frozen, reproduces the param-M transform within 1e-4

Dim audit (CLAUDE.md "Subtler substrate breaches" #1): this .su makes
ZERO basis_vector calls -- the LLM codebook is unused -- so runtime_dim
is set to the task size, not the 768 default. The matmul operates on
the K-dim one-hot states we pass in; the codebook never appears.

Usage:
    py experiments/trainable_matrix_adjustment.py [--k K] [--epochs E]
        [--seeds 0,1,2] [--lr LR] [--target shift3|random]
"""
from __future__ import annotations

import argparse
import io
import json
import os
import statistics
import sys
import time
import types

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(REPO, "sdk", "sutra-compiler"))
HERE = os.path.dirname(os.path.abspath(__file__))

import torch
import torch.nn.functional as F

from sutra_compiler.lexer import Lexer
from sutra_compiler.parser import Parser
from sutra_compiler.codegen_pytorch import translate_module as translate_pytorch


# ---------------------------------------------------------------------------
# .su sources
# ---------------------------------------------------------------------------

def _su_param() -> str:
    """apply(M, x) with M a trainable matrix parameter."""
    return (
        "// Trainable matrix: M flows in as a parameter; the matmul runs\n"
        "// on the substrate via Tensor.MatrixMul (_VSA.matmul).\n"
        "function vector apply(matrix M, vector x) {\n"
        "    return Tensor.MatrixMul(M, x);\n"
        "}\n\n"
        'function string main() { return "ok"; }\n'
    )


def _fmt_row(row: list[float]) -> str:
    # Fixed-point, NOT repr() -- the Sutra parser rejects scientific
    # notation (4.5e-05). 8 decimals = ~5e-9 precision, far under the
    # 1e-4 round-trip threshold. (Same fix as equality_cosine /
    # rank_k_is_x bake-backs.)
    return "vector_literal(" + ", ".join(f"{v:.8f}" for v in row) + ")"


def _su_baked(M: torch.Tensor) -> str:
    """Frozen apply with the trained M inlined as a matrix_literal --
    the trained matrix AS legible Sutra source (weight -> code)."""
    rows = ",\n        ".join(_fmt_row(r.tolist()) for r in M)
    return (
        "// Baked trained matrix as a matrix_literal -- frozen, no M param.\n"
        "function vector apply_baked(vector x) {\n"
        "    matrix M = matrix_literal(\n"
        f"        {rows});\n"
        "    return Tensor.MatrixMul(M, x);\n"
        "}\n\n"
        'function string main() { return "ok"; }\n'
    )


def _compile(su_text: str, tag: str, runtime_dim: int):
    path = os.path.join(HERE, f".trainmat_{tag}.su")
    with open(path, "w", encoding="utf-8") as f:
        f.write(su_text)
    src = open(path, encoding="utf-8").read()
    lx = Lexer(src, file=path)
    ast = Parser(
        lx.tokenize(), file=path, diagnostics=lx.diagnostics
    ).parse_module()
    if lx.diagnostics.has_errors():
        print(f"COMPILE ERRORS ({tag}):")
        for d in lx.diagnostics:
            print(" ", d)
        raise SystemExit(1)
    py = translate_pytorch(ast, runtime_dim=runtime_dim, runtime_seed=42)
    m = types.ModuleType(f"_trainmat_{tag}")
    m.__file__ = f"<trainmat {tag}>"
    exec(compile(py, m.__file__, "exec"), m.__dict__)
    return m, py


# ---------------------------------------------------------------------------
# Permutation matrices (the matrices we shift around)
# ---------------------------------------------------------------------------

def cyclic_shift_matrix(K: int, by: int, dtype, device) -> torch.Tensor:
    """P with (P @ e_i)[j] = 1 iff j == (i + by) % K. Column i is the
    one-hot at (i+by)%K, so P @ e_i = e_{(i+by)%K}."""
    P = torch.zeros(K, K, dtype=dtype, device=device)
    for i in range(K):
        P[(i + by) % K, i] = 1.0
    return P


def permutation_matrix(perm: list[int], dtype, device) -> torch.Tensor:
    """P @ e_i = e_{perm[i]}; column i is one-hot at perm[i]."""
    K = len(perm)
    P = torch.zeros(K, K, dtype=dtype, device=device)
    for i in range(K):
        P[perm[i], i] = 1.0
    return P


def onehots(K: int, dtype, device) -> list[torch.Tensor]:
    return [
        torch.eye(K, dtype=dtype, device=device)[i] for i in range(K)
    ]


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def transform_accuracy(mod, M, es, perm) -> float:
    correct = 0
    with torch.no_grad():
        for i, e in enumerate(es):
            y = mod.apply(M, e)
            if int(y.argmax()) == perm[i]:
                correct += 1
    return correct / len(es)


def separation_gap(mod, M, es, perm) -> float:
    """min over inputs of (correct-slot value - max wrong-slot value).
    Positive => the substrate matmul cleanly separates target from
    every distractor for every input."""
    gaps = []
    with torch.no_grad():
        for i, e in enumerate(es):
            y = mod.apply(M, e)
            tgt = perm[i]
            correct = float(y[tgt])
            mask = torch.ones_like(y, dtype=torch.bool)
            mask[tgt] = False
            wrong_max = float(y[mask].max())
            gaps.append(correct - wrong_max)
    return min(gaps)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=int, default=8)
    ap.add_argument("--epochs", type=int, default=400)
    ap.add_argument("--seeds", default="0,1,2")
    ap.add_argument("--lr", type=float, default=0.05)
    ap.add_argument(
        "--target", default="shift3", choices=["shift3", "random"],
        help="shift3: init shift-by-1 -> target shift-by-3 (a clean "
        "'shift the matrix around' demo). random: target is a seeded "
        "random permutation (learn an arbitrary permutation).",
    )
    ap.add_argument(
        "--loss", default="ce", choices=["ce", "mse"],
        help="ce: cross-entropy on the matmul output -- learns the "
        "permutation FUNCTION (argmax correct) but not the canonical 0/1 "
        "matrix (entries grow, Frobenius to target rises). mse: regress "
        "M @ e_i to the target one-hot -- converges to the EXACT target "
        "permutation matrix (Frobenius -> 0). The two objectives are the "
        "'train the function' vs 'shift the matrix to a target' contrast.",
    )
    ap.add_argument(
        "--ortho", action="store_true",
        help="Add a soft orthogonality penalty w*||MᵀM − I||² to the loss "
        "(CE only). Plain CE learns the permutation FUNCTION but lets the "
        "matrix entries grow (Frobenius to the canonical 0/1 matrix RISES). "
        "Constraining M to the orthogonal manifold should keep accuracy 100% "
        "AND pull Frobenius DOWN — the function-learner also yielding a "
        "canonical matrix.",
    )
    ap.add_argument("--ortho-weight", type=float, default=1.0)
    a = ap.parse_args()
    seeds = [int(s) for s in a.seeds.split(",") if s.strip()]
    K = a.k
    # Dim audit: no basis_vector in apply.su -> codebook unused. The
    # matmul operates on K-dim one-hots; runtime_dim is irrelevant to the
    # computation, so pin it to the task size, not 768.
    runtime_dim = K

    mod, py = _compile(_su_param(), "param", runtime_dim)

    # Substrate-purity assertion: the matmul the program runs IS
    # torch.matmul (the substrate op), not a host reimplementation.
    assert "_torch.matmul" in py, (
        "Tensor.MatrixMul did not lower to torch.matmul -- substrate breach"
    )
    dtype = mod._VSA.dtype
    device = mod._VSA.device

    es = onehots(K, dtype, device)
    init_P = cyclic_shift_matrix(K, 1, dtype, device)  # font.su shift-by-1

    print(
        f"compiled apply(matrix M, vector x) via PyTorch codegen; "
        f"K={K} runtime_dim={runtime_dim} (codebook UNUSED -- dim audit) "
        f"epochs={a.epochs} seeds={seeds} lr={a.lr} target={a.target}"
    )
    print(
        f"  device={device} dtype={dtype}; matmul == torch.matmul "
        f"(substrate-pure, verified in emitted source)"
    )
    print(
        "  M initialised at the frozen font.su cyclic-shift-by-1 P; "
        "trained to the target permutation."
    )

    # --- equivalence guard: vmap-batched apply == per-sample apply ---
    M_guard = init_P.clone()
    Xstack = torch.stack(es)
    with torch.no_grad():
        per = torch.stack([mod.apply(M_guard, e) for e in es])
        bat = torch.vmap(lambda e: mod.apply(M_guard, e))(Xstack)
        dmax = float((per - bat).abs().max())
    if dmax >= 1e-6:
        raise SystemExit(
            f"EQUIVALENCE GUARD FAILED: batched != per-sample "
            f"(max|Δ|={dmax:.2e})."
        )
    print(f"  equivalence guard PASSED (vmap vs per-sample max|Δ|={dmax:.2e})")

    rows = []
    t0 = time.time()
    for s in seeds:
        torch.manual_seed(s)
        if a.target == "shift3":
            perm = [(i + 3) % K for i in range(K)]
        else:
            perm = torch.randperm(K, generator=torch.Generator().manual_seed(s)).tolist()
        target_P = permutation_matrix(perm, dtype, device)
        y_idx = torch.tensor(perm, device=device)

        # M is the trainable matrix parameter, init at frozen shift-by-1 P
        M = init_P.clone().detach().requires_grad_(True)
        opt = torch.optim.Adam([M], lr=a.lr)

        fro_before = float((M.detach() - target_P).norm())
        acc_before = transform_accuracy(mod, M.detach(), es, perm)
        gap_before = separation_gap(mod, M.detach(), es, perm)

        targets_onehot = torch.stack([es[perm[i]] for i in range(K)])  # (K,K)
        eye = torch.eye(K, dtype=dtype, device=device)
        grad_norm_first = None
        for ep in range(a.epochs):
            opt.zero_grad()
            # each forward IS the compiled substrate matmul M @ e_i
            outs = torch.stack([mod.apply(M, e) for e in es])  # (K, K)
            if a.loss == "ce":
                loss = F.cross_entropy(outs * 5.0, y_idx)
            else:
                loss = F.mse_loss(outs, targets_onehot)
            if a.ortho:
                # Soft orthogonality penalty: pull M onto the orthogonal
                # manifold (||MᵀM − I||²). A permutation matrix is the
                # orthogonal matrix with a one-hot argmax pattern, so
                # CE (fixes the argmax) + ortho (fixes the geometry)
                # together drive M toward the canonical permutation.
                loss = loss + a.ortho_weight * ((M.t() @ M - eye) ** 2).sum()
            loss.backward()
            if grad_norm_first is None:
                grad_norm_first = float(M.grad.norm())
            opt.step()

        fro_after = float((M.detach() - target_P).norm())
        acc_after = transform_accuracy(mod, M.detach(), es, perm)
        gap_after = separation_gap(mod, M.detach(), es, perm)

        # --- bake-back: trained M -> matrix_literal .su -> recompile ---
        M_round = torch.tensor(
            [[round(v, 8) for v in r] for r in M.detach().tolist()],
            dtype=dtype, device=device,
        )
        baked, _ = _compile(_su_baked(M_round), "baked", runtime_dim)
        with torch.no_grad():
            rt = 0.0
            for e in es:
                a_param = mod.apply(M.detach(), e)
                a_baked = baked.apply_baked(e)
                rt = max(rt, float((a_param - a_baked).abs().max()))
        rt_ok = rt < 1e-4

        print(
            f"  seed {s} ({a.target}): "
            f"Fro {fro_before:.3f} -> {fro_after:.3f}  "
            f"acc {acc_before:.0%} -> {acc_after:.0%}  "
            f"gap {gap_before:+.3f} -> {gap_after:+.3f}  "
            f"first-step ||dL/dM||={grad_norm_first:.4f}  "
            f"bake-back max|Δ|={rt:.2e} ok={rt_ok}"
        )
        rows.append({
            "seed": s,
            "target": a.target,
            "loss": a.loss,
            "ortho": a.ortho,
            "perm": perm,
            "fro_before": round(fro_before, 6),
            "fro_after": round(fro_after, 6),
            "acc_before": acc_before,
            "acc_after": acc_after,
            "gap_before": round(gap_before, 6),
            "gap_after": round(gap_after, 6),
            "first_step_grad_norm": round(grad_norm_first, 6),
            "bakeback_max_delta": rt,
            "bakeback_ok": rt_ok,
        })

    def agg(key):
        vals = [r[key] for r in rows]
        return (
            statistics.mean(vals),
            statistics.stdev(vals) if len(vals) > 1 else 0.0,
        )

    print(
        f"\n=== TRAINABLE MATRIX MEASURED (real compiled graph, M trained "
        f"through Tensor.MatrixMul) in {time.time() - t0:.1f}s ==="
    )
    fb_m, fb_s = agg("fro_before")
    fa_m, fa_s = agg("fro_after")
    print(f"K={K} target={a.target} loss={a.loss}{'+ortho' if a.ortho else ''} "
          f"epochs={a.epochs} n_seeds={len(seeds)}")
    if a.loss == "mse":
        fro_note = "(mse drives this -> 0)"
    elif a.ortho:
        fro_note = "(ce+ortho: function AND canonical matrix -> should FALL)"
    else:
        fro_note = "(ce learns the FUNCTION, not the canonical matrix -> rises)"
    print(f"Frobenius to target: {fb_m:.3f} ± {fb_s:.3f}  ->  "
          f"{fa_m:.4f} ± {fa_s:.4f}  {fro_note}")
    print(f"transform accuracy:  "
          f"{statistics.mean([r['acc_before'] for r in rows]):.0%}  ->  "
          f"{statistics.mean([r['acc_after'] for r in rows]):.0%}")
    ga_m, ga_s = agg("gap_after")
    print(f"separation gap after: {ga_m:+.4f} ± {ga_s:.4f} "
          f"(>0 => substrate matmul cleanly separates every input)")
    print(f"first-step ||dL/dM|| (nonzero => backprop reaches the matrix "
          f"through the substrate matmul): "
          f"{agg('first_step_grad_norm')[0]:.4f}")
    print(f"bake-back round-trip ok (all seeds): "
          f"{all(r['bakeback_ok'] for r in rows)}  "
          f"max|Δ|={max(r['bakeback_max_delta'] for r in rows):.2e}")

    out = {
        "experiment": "trainable matrix through compiled Sutra Tensor.MatrixMul",
        "K": K,
        "runtime_dim": runtime_dim,
        "dim_audit": "no basis_vector in apply.su; codebook unused",
        "target": a.target,
        "loss": a.loss,
        "ortho": a.ortho,
        "ortho_weight": a.ortho_weight if a.ortho else None,
        "epochs": a.epochs,
        "lr": a.lr,
        "seeds": seeds,
        "substrate_matmul_is_torch_matmul": True,
        "rows": rows,
    }
    out_path = os.path.join(HERE, "trainable_matrix_adjustment_results.json")
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2)
    print(f"\nResults saved to {out_path}")

    # --- assertions (SKILL.md / reproduction discipline) ---
    # Success criterion is FUNCTIONAL for both losses: the matrix must
    # learn the permutation (exact argmax + positive separation gap),
    # gradient must reach M through the substrate matmul, and the trained
    # matrix must bake back to a matrix_literal .su.
    assert all(r["acc_after"] == 1.0 for r in rows), (
        f"matrix did not learn the permutation exactly: {rows}"
    )
    assert all(r["gap_after"] > 0 for r in rows), (
        f"separation gap not positive after training: {rows}"
    )
    assert all(r["first_step_grad_norm"] > 0 for r in rows), (
        "gradient did not reach the matrix through the substrate matmul"
    )
    assert all(r["bakeback_ok"] for r in rows), (
        "bake-back to matrix_literal did not round-trip"
    )
    if a.loss == "mse":
        # MSE additionally drives M to the EXACT canonical permutation
        # matrix -- Frobenius collapses toward zero ("shift the matrix").
        assert all(r["fro_after"] < r["fro_before"] for r in rows), (
            "MSE did not move the matrix toward the target permutation"
        )
        assert all(r["fro_after"] < 0.1 for r in rows), (
            f"MSE did not converge to the canonical matrix: {rows}"
        )
    if a.loss == "ce" and a.ortho:
        # The headline claim: the orthogonality penalty makes the CE
        # function-learner ALSO yield a canonical matrix -- Frobenius to
        # the target FALLS (vs plain CE where it rises), while accuracy
        # stays exact (asserted above).
        assert all(r["fro_after"] < r["fro_before"] for r in rows), (
            f"ce+ortho did not pull Frobenius toward the target: {rows}"
        )
    print("All assertions passed.")


if __name__ == "__main__":
    main()
