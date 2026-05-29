"""Trainable BINDING matrices — semantic bind as a learned matrix.

Emma's long-standing learned-matrix-binding vision (greenlit to build
2026-05-29): a *semantic* bind is a learned matrix (vs a non-semantic
bind, an arbitrary/random matrix), and "objects track which learned
matrices bound their fields." This experiment learns the per-field
binding matrices through the same compiled substrate path proven for the
other trainable matrices:

    function vector apply(matrix M, vector x) { return Tensor.MatrixMul(M, x); }

Setup (a VSA role-filler record). K fields, each with a binding matrix
B_i and an unbinding matrix U_i. Store K fillers in one bundle:

    S = (1/sqrt(K)) * sum_i  B_i @ f_i            (bind + bundle, substrate)
    f_hat_j = U_j @ S                              (unbind, substrate)

Every B_i @ f_i, the bundle sum, and every U_j @ S is a compiled
substrate op (matmul / add). The recovery score cos(f_hat_j, f_j) is
monitoring only.

Baseline = NON-semantic bind: B_i random orthogonal, U_i = B_i^T (the
standard VSA rotation-binding; near-optimal for random fillers).
Learned = SEMANTIC bind: B_i, U_i trained (init at the random-orthogonal
baseline) to maximise recovery of a KNOWN filler set from the bundle.

The hypothesis from VSA theory: for *random* fillers, random-orthogonal
binding is already near the capacity limit, so a learned bind cannot beat
it (perfect zero-crosstalk recovery for K>1 full-rank matrices is
impossible: U_j B_j = I forces U_j = B_j^-1, then U_j B_i = B_j^-1 B_i
!= 0). But for a KNOWN, FIXED filler set, the learned matrices can shape
the crosstalk to nearly cancel on exactly those fillers -- the "bind
specialised to known content" case, which is what "objects track which
learned matrices bound their fields" means. We measure both regimes.

Asserted (mechanism): substrate matmul is torch.matmul; gradient reaches
the binding matrices; learned recovery >= baseline on the trained
(known) filler set. Reported: the capacity curve over K and the
generalisation gap to NEW random fillers.

Usage:  py experiments/trainable_binding_matrix.py [--d D] [--epochs E]
        [--ks 2,4,8,16,32] [--lr LR]
"""
from __future__ import annotations

import argparse
import io
import json
import os
import statistics
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


APPLY_SU = (
    "function vector apply(matrix M, vector x) {\n"
    "    return Tensor.MatrixMul(M, x);\n"
    "}\n"
    'function string main() { return "ok"; }\n'
)


def _compile(runtime_dim: int):
    lx = Lexer(APPLY_SU, file="<bind>")
    ast = Parser(lx.tokenize(), file="<bind>", diagnostics=lx.diagnostics).parse_module()
    assert not lx.diagnostics.has_errors(), list(lx.diagnostics)
    py = translate_pytorch(ast, runtime_dim=runtime_dim, runtime_seed=42)
    m = types.ModuleType("_bind")
    exec(compile(py, "<bind>", "exec"), m.__dict__)
    return m, py


def random_orthogonal(d, gen, dtype, device):
    a = torch.randn(d, d, generator=gen, dtype=dtype, device=device)
    q, r = torch.linalg.qr(a)
    # fix signs so q is a proper random orthogonal (Haar)
    q = q * torch.sign(torch.diagonal(r))
    return q


def unit(v):
    return v / (v.norm(dim=-1, keepdim=True) + 1e-12)


def bundle_recover(mod, Bs, Us, F):
    """F: (K, d) fillers. Returns recovered (K, d) via the compiled
    substrate matmul. S = (1/sqrt(K)) sum_i B_i @ f_i; f_hat_j = U_j @ S."""
    K = F.shape[0]
    bound = torch.stack([mod.apply(Bs[i], F[i]) for i in range(K)])  # (K,d)
    S = bound.sum(dim=0) / (K ** 0.5)
    rec = torch.stack([mod.apply(Us[j], S) for j in range(K)])       # (K,d)
    return rec


def mean_recovery_cos(rec, F):
    return float((unit(rec) * unit(F)).sum(dim=1).mean())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--d", type=int, default=64)
    ap.add_argument("--epochs", type=int, default=400)
    ap.add_argument("--ks", default="2,4,8,16,32")
    ap.add_argument("--lr", type=float, default=0.01)
    a = ap.parse_args()
    Ks = [int(k) for k in a.ks.split(",") if k.strip()]
    d = a.d

    mod, py = _compile(runtime_dim=8)  # no basis_vector -> codebook unused
    assert "_torch.matmul" in py, "MatrixMul did not lower to torch.matmul"
    dtype, device = mod._VSA.dtype, mod._VSA.device
    print(f"compiled apply(matrix M, vector x); MatrixMul == torch.matmul "
          f"(substrate). d={d} device={device} (dim audit: no basis_vector, "
          f"codebook unused)")
    print(f"  bind/bundle/unbind all run on the substrate; cos is monitoring.")

    rows = []
    any_grad = []
    for K in Ks:
        gen = torch.Generator(device=device).manual_seed(100 + K)
        # fixed, known filler set (the content the object's fields hold)
        F = unit(torch.randn(K, d, generator=gen, dtype=dtype, device=device))

        # --- NON-semantic baseline: random orthogonal bind, transpose unbind ---
        B0 = [random_orthogonal(d, gen, dtype, device) for _ in range(K)]
        U0 = [B0[i].T.contiguous() for i in range(K)]
        base_cos = mean_recovery_cos(bundle_recover(mod, B0, U0, F), F)

        # --- SEMANTIC learned bind: train B_i, U_i (init at baseline) ---
        Bs = [B0[i].clone().detach().requires_grad_(True) for i in range(K)]
        Us = [U0[i].clone().detach().requires_grad_(True) for i in range(K)]
        opt = torch.optim.Adam(Bs + Us, lr=a.lr)
        grad_B = grad_U = None
        for _ in range(a.epochs):
            opt.zero_grad()
            rec = bundle_recover(mod, Bs, Us, F)
            loss = (1.0 - (unit(rec) * unit(F)).sum(dim=1)).mean()
            loss.backward()
            if grad_B is None:
                # Split the first-step gradient by side. At the orthogonal
                # init the BIND side is near-stationary (~0); the UNBIND
                # side carries the learning -- so "perfect known recovery"
                # is the unbind matrices memorising the one fixed bundle
                # vector, NOT the bind matrices improving.
                grad_B = float(torch.stack([b.grad.norm() for b in Bs]).norm())
                grad_U = float(torch.stack([u.grad.norm() for u in Us]).norm())
            opt.step()
        learned_cos = mean_recovery_cos(
            bundle_recover(mod, [b.detach() for b in Bs],
                           [u.detach() for u in Us], F), F)
        any_grad.append(grad_U)

        # --- generalisation probe: recover NEW random fillers with the
        #     learned matrices (did it learn binding, or memorise content?) ---
        genF = unit(torch.randn(K, d, generator=gen, dtype=dtype, device=device))
        gen_base = mean_recovery_cos(bundle_recover(mod, B0, U0, genF), genF)
        gen_learned = mean_recovery_cos(
            bundle_recover(mod, [b.detach() for b in Bs],
                           [u.detach() for u in Us], genF), genF)

        print(f"  K={K:>2}: recovery cos  random-orth {base_cos:+.3f}  ->  "
              f"learned {learned_cos:+.3f}   | new-filler generalisation: "
              f"random-orth {gen_base:+.3f}  learned {gen_learned:+.3f}  "
              f"(init ||dL/dB||={grad_B:.2e} ||dL/dU||={grad_U:.2e})")
        rows.append({
            "K": K, "d": d,
            "recovery_cos_random_orth": round(base_cos, 6),
            "recovery_cos_learned": round(learned_cos, 6),
            "newfiller_cos_random_orth": round(gen_base, 6),
            "newfiller_cos_learned": round(gen_learned, 6),
            "init_grad_bind": grad_B,
            "init_grad_unbind": grad_U,
        })

    print(f"\n=== TRAINABLE BINDING MATRIX (semantic bind = learned matrix, "
          f"through compiled Tensor.MatrixMul) ===")
    print("Known (trained) filler set -- 'objects track which learned "
          "matrices bound their fields':")
    for r in rows:
        gain = r["recovery_cos_learned"] - r["recovery_cos_random_orth"]
        print(f"  K={r['K']:>2}: random-orth {r['recovery_cos_random_orth']:+.3f} "
              f"-> learned {r['recovery_cos_learned']:+.3f}  (Δ={gain:+.3f})")
    print("New random fillers (generalisation = is it a binding op or memorised "
          "content?):")
    for r in rows:
        print(f"  K={r['K']:>2}: random-orth {r['newfiller_cos_random_orth']:+.3f} "
              f"learned {r['newfiller_cos_learned']:+.3f}")

    out = {
        "experiment": "trainable binding matrices through compiled Tensor.MatrixMul",
        "d": d, "epochs": a.epochs, "lr": a.lr, "Ks": Ks,
        "substrate_matmul_is_torch_matmul": True,
        "rows": rows,
    }
    with open(os.path.join(HERE, "trainable_binding_matrix_results.json"), "w") as f:
        json.dump(out, f, indent=2)

    # mechanism + the known-content claim
    assert all(g > 1e-4 for g in any_grad), (
        "gradient did not meaningfully reach the (unbind) matrices through "
        "the substrate matmul"
    )
    assert all(
        r["recovery_cos_learned"] >= r["recovery_cos_random_orth"] - 1e-3
        for r in rows
    ), f"learned did not match/beat random-orth on the known fillers: {rows}"
    print("\nMechanism assertions passed (substrate matmul; gradient reaches "
          "the matrices via the UNBIND side; learned >= random-orth on known "
          "fillers).")
    print("HONEST FRAMING: 'perfect known recovery' is the UNBIND matrices "
          "memorising the single fixed bundle vector (init ||dL/dB||~1e-7 "
          "near-stationary; the unbind side carries it). It does NOT "
          "generalise to new fillers -- for arbitrary content, random-"
          "orthogonal (non-semantic) binding stays near-optimal. Semantic "
          "bind = a matrix specialised to KNOWN content, exactly the "
          "'objects track which learned matrices bound their fields' case.")


if __name__ == "__main__":
    main()
