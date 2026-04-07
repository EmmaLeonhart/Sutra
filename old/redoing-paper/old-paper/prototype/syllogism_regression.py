"""Experiment 15c: Syllogism Regression — Can C be constructed from P1, P2?

The question is NOT "are premises similar to each other?" but "can we
construct the conclusion from the premises (or from bare words) via a
consistent vector transformation?"

Template:
  P1: "All {class} are {adjective}"
  P2: "{member} is a {class}"
  C:  "{member} is {adjective}"

Models tested (cosine to actual C as metric):

  Baselines (0 fitted params):
    B1: C ≈ P2                          (just the membership premise)
    B2: C ≈ (P1 + P2) / 2              (naive average)
    B3: C ≈ bare_member                 (just the name embedding)

  Structural (0 fitted params, uses syllogistic structure):
    S1: C ≈ P2 + (bare_adj - bare_class)    (swap class→adj in P2)
    S2: C ≈ bare_member + P1 - bare_class   (member + property from P1)

  Simple regressions (1-4 global scalars):
    R1: C ≈ αP1 + βP2                  (optimal premise blend)
    R2: C ≈ P2 + γP1                   (P1 as displacement)
    R3: C ≈ α·bare_m + β·bare_adj      (bare word composition)
    R4: C ≈ αP1 + βP2 + γ·bare_m + δ·bare_adj  (kitchen sink, 4 scalars)

  Rich regressions (1024+ params, cross-validated):
    R5: C ≈ P2 + μ                     (constant displacement)
    R6: C ≈ α·bare_m + β·bare_adj + μ  (composition + template bias)

Usage:
    python prototype/syllogism_regression.py
"""

from __future__ import annotations

import io
import json
import os
import sys

import numpy as np

_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")


# ── Constants (must match syllogism_gap_grid.py exactly) ─────────────────────

MEMBERS = [
    "Socrates", "Aristotle", "Einstein", "Mozart", "Shakespeare",
    "Cleopatra", "Darwin", "Galileo", "Confucius", "Archimedes",
]

CLASSES = [
    ("human", "humans"),
    ("bird", "birds"),
    ("cat", "cats"),
    ("dog", "dogs"),
    ("flower", "flowers"),
    ("insect", "insects"),
    ("reptile", "reptiles"),
    ("mammal", "mammals"),
    ("vehicle", "vehicles"),
    ("mineral", "minerals"),
]

ADJECTIVES = [
    "mortal", "beautiful", "dangerous", "ancient", "fragile",
    "powerful", "mysterious", "resilient", "valuable", "complex",
]


# ── Helpers ──────────────────────────────────────────────────────────────────

def cosine_batch(A: np.ndarray, B: np.ndarray) -> np.ndarray:
    """Cosine similarity between corresponding rows of A and B."""
    dot = np.sum(A * B, axis=1)
    nA = np.linalg.norm(A, axis=1) + 1e-10
    nB = np.linalg.norm(B, axis=1) + 1e-10
    return dot / (nA * nB)


def fit_global_scalars(features: list[np.ndarray], target: np.ndarray) -> np.ndarray:
    """Fit target ≈ Σ w_i * feature_i with global scalar weights.

    features: list of k arrays, each (n, d)
    target: (n, d) array
    Returns: (k,) array of weights
    """
    X = np.column_stack([f.ravel() for f in features])
    y = target.ravel()
    weights, _, _, _ = np.linalg.lstsq(X, y, rcond=None)
    return weights


def predict_scalars(features: list[np.ndarray], weights: np.ndarray) -> np.ndarray:
    """Predict: Σ w_i * feature_i."""
    result = np.zeros_like(features[0])
    for f, w in zip(features, weights):
        result = result + w * f
    return result


def eval_model(C_pred: np.ndarray, C_actual: np.ndarray) -> dict:
    """Compute cosine similarity stats."""
    cos = cosine_batch(C_pred, C_actual)
    return {
        "mean_cosine": float(np.mean(cos)),
        "std_cosine": float(np.std(cos)),
        "min_cosine": float(np.min(cos)),
        "max_cosine": float(np.max(cos)),
        "median_cosine": float(np.median(cos)),
    }


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    print("Syllogism Regression — Can C be constructed from P1, P2?")
    print("Loading embeddings from syllogism_gap_grid_embeddings.npz...\n")

    # ── Load embeddings ──────────────────────────────────────────────────
    npz_path = os.path.join(_project_root, "prototype",
                            "syllogism_gap_grid_embeddings.npz")
    if not os.path.exists(npz_path):
        print("ERROR: Run syllogism_gap_grid.py first to generate embeddings.")
        sys.exit(1)

    data = np.load(npz_path, allow_pickle=True)
    all_vecs = data["all_vecs"]

    # Reconstruct lookup dicts (same ordering as grid script)
    idx = 0
    p1_vecs = {}
    for cls_s, _ in CLASSES:
        for adj in ADJECTIVES:
            p1_vecs[(cls_s, adj)] = all_vecs[idx]
            idx += 1

    p2_vecs = {}
    for member in MEMBERS:
        for cls_s, _ in CLASSES:
            p2_vecs[(member, cls_s)] = all_vecs[idx]
            idx += 1

    c_vecs = {}
    for member in MEMBERS:
        for adj in ADJECTIVES:
            c_vecs[(member, adj)] = all_vecs[idx]
            idx += 1

    bare_member_vecs = {}
    for member in MEMBERS:
        bare_member_vecs[member] = all_vecs[idx]
        idx += 1

    bare_class_vecs = {}
    for cls_s, _ in CLASSES:
        bare_class_vecs[cls_s] = all_vecs[idx]
        idx += 1

    bare_adj_vecs = {}
    for adj in ADJECTIVES:
        bare_adj_vecs[adj] = all_vecs[idx]
        idx += 1

    assert idx == len(all_vecs), f"Index mismatch: {idx} vs {len(all_vecs)}"
    d = all_vecs.shape[1]  # 1024
    print(f"  Loaded {len(all_vecs)} vectors, dim={d}\n")

    # ── Build (1000, d) arrays for all syllogisms ────────────────────────
    n = len(MEMBERS) * len(CLASSES) * len(ADJECTIVES)  # 1000
    P1 = np.zeros((n, d), dtype=np.float32)
    P2 = np.zeros((n, d), dtype=np.float32)
    C = np.zeros((n, d), dtype=np.float32)
    M = np.zeros((n, d), dtype=np.float32)   # bare member
    A = np.zeros((n, d), dtype=np.float32)   # bare adjective
    K = np.zeros((n, d), dtype=np.float32)   # bare class
    member_idx = np.zeros(n, dtype=int)      # which member (0-9)
    class_idx = np.zeros(n, dtype=int)       # which class (0-9)
    adj_idx = np.zeros(n, dtype=int)         # which adjective (0-9)

    row = 0
    for mi, member in enumerate(MEMBERS):
        for ci, (cls_s, _) in enumerate(CLASSES):
            for ai, adj in enumerate(ADJECTIVES):
                P1[row] = p1_vecs[(cls_s, adj)]
                P2[row] = p2_vecs[(member, cls_s)]
                C[row] = c_vecs[(member, adj)]
                M[row] = bare_member_vecs[member]
                A[row] = bare_adj_vecs[adj]
                K[row] = bare_class_vecs[cls_s]
                member_idx[row] = mi
                class_idx[row] = ci
                adj_idx[row] = ai
                row += 1

    print(f"  Built {n} syllogism triples.\n")

    # ── Run all models ───────────────────────────────────────────────────
    results_table = []  # (name, params, stats, notes)

    def run_model(name, C_pred, n_params, notes=""):
        stats = eval_model(C_pred, C)
        results_table.append((name, n_params, stats, notes))
        return stats

    # ── BASELINES ────────────────────────────────────────────────────────
    print("=" * 70)
    print("  BASELINES (0 fitted parameters)")
    print("=" * 70)

    run_model("B1: P2 alone", P2, 0)
    run_model("B2: (P1+P2)/2", (P1 + P2) / 2, 0)
    run_model("B3: bare member", M, 0)

    # ── STRUCTURAL (0 fitted params, syllogistic structure) ──────────────
    print(f"\n{'=' * 70}")
    print("  STRUCTURAL MODELS (0 fitted params, use syllogistic structure)")
    print("=" * 70)
    print('  S1: C ≈ P2 + (bare_adj - bare_class)')
    print('      "Swap class→adjective in the membership premise"')
    print('  S2: C ≈ bare_member + P1 - bare_class')
    print('      "Member name + property content of P1"\n')

    S1_pred = P2 + (A - K)
    run_model("S1: P2 + (adj - class)", S1_pred, 0)

    S2_pred = M + P1 - K
    run_model("S2: member + P1 - class", S2_pred, 0)

    # ── SIMPLE REGRESSIONS ───────────────────────────────────────────────
    print(f"\n{'=' * 70}")
    print("  FITTED MODELS (global scalar weights)")
    print("=" * 70)

    # R1: αP1 + βP2
    w_r1 = fit_global_scalars([P1, P2], C)
    C_r1 = predict_scalars([P1, P2], w_r1)
    run_model("R1: αP1 + βP2", C_r1, 2,
              f"α={w_r1[0]:.4f}, β={w_r1[1]:.4f}")

    # R2: P2 + γP1 (fit γ on displacement C - P2)
    w_r2 = fit_global_scalars([P1], C - P2)
    C_r2 = P2 + w_r2[0] * P1
    run_model("R2: P2 + γP1", C_r2, 1,
              f"γ={w_r2[0]:.4f}")

    # R3: α·bare_m + β·bare_adj
    w_r3 = fit_global_scalars([M, A], C)
    C_r3 = predict_scalars([M, A], w_r3)
    run_model("R3: α·member + β·adj", C_r3, 2,
              f"α={w_r3[0]:.4f}, β={w_r3[1]:.4f}")

    # R3b: α·bare_m + β·bare_adj + γ·bare_class
    w_r3b = fit_global_scalars([M, A, K], C)
    C_r3b = predict_scalars([M, A, K], w_r3b)
    run_model("R3b: α·m + β·adj + γ·class", C_r3b, 3,
              f"α={w_r3b[0]:.4f}, β={w_r3b[1]:.4f}, γ={w_r3b[2]:.4f}")

    # R4: αP1 + βP2 + γ·bare_m + δ·bare_adj (kitchen sink)
    w_r4 = fit_global_scalars([P1, P2, M, A], C)
    C_r4 = predict_scalars([P1, P2, M, A], w_r4)
    run_model("R4: αP1 + βP2 + γ·m + δ·adj", C_r4, 4,
              f"α={w_r4[0]:.4f}, β={w_r4[1]:.4f}, γ={w_r4[2]:.4f}, δ={w_r4[3]:.4f}")

    # R4b: everything including bare class
    w_r4b = fit_global_scalars([P1, P2, M, A, K], C)
    C_r4b = predict_scalars([P1, P2, M, A, K], w_r4b)
    run_model("R4b: all 5 inputs", C_r4b, 5,
              f"α={w_r4b[0]:.4f}, β={w_r4b[1]:.4f}, γ={w_r4b[2]:.4f}, "
              f"δ={w_r4b[3]:.4f}, ε={w_r4b[4]:.4f}")

    # ── RICH REGRESSIONS (1024+ params, need cross-validation) ───────────
    print(f"\n{'=' * 70}")
    print("  RICH MODELS (1024+ params, with leave-one-member-out CV)")
    print("=" * 70)

    # R5: C ≈ P2 + μ (constant displacement)
    mu_r5 = np.mean(C - P2, axis=0)
    C_r5 = P2 + mu_r5
    run_model("R5: P2 + μ (train)", C_r5, d)

    # R5 cross-validation
    cv_cosines_r5 = []
    for mi in range(10):
        train = member_idx != mi
        test = member_idx == mi
        mu_cv = np.mean(C[train] - P2[train], axis=0)
        c_pred_cv = P2[test] + mu_cv
        cv_cosines_r5.extend(cosine_batch(c_pred_cv, C[test]).tolist())
    cv_r5 = {
        "mean_cosine": float(np.mean(cv_cosines_r5)),
        "std_cosine": float(np.std(cv_cosines_r5)),
        "min_cosine": float(np.min(cv_cosines_r5)),
    }
    results_table.append(("R5: P2 + μ (CV)", d, cv_r5, "leave-one-member-out"))

    # R6: C ≈ α·bare_m + β·bare_adj + μ (composition + template)
    C_mean = C.mean(axis=0)
    M_mean = M.mean(axis=0)
    A_mean = A.mean(axis=0)
    w_r6 = fit_global_scalars([M - M_mean, A - A_mean], C - C_mean)
    mu_r6 = C_mean - w_r6[0] * M_mean - w_r6[1] * A_mean
    C_r6 = w_r6[0] * M + w_r6[1] * A + mu_r6
    run_model("R6: α·m + β·adj + μ (train)", C_r6, d + 2,
              f"α={w_r6[0]:.4f}, β={w_r6[1]:.4f}")

    # R6 cross-validation
    cv_cosines_r6 = []
    for mi in range(10):
        train = member_idx != mi
        test = member_idx == mi
        C_tr_mean = C[train].mean(axis=0)
        M_tr_mean = M[train].mean(axis=0)
        A_tr_mean = A[train].mean(axis=0)
        w_cv = fit_global_scalars(
            [M[train] - M_tr_mean, A[train] - A_tr_mean],
            C[train] - C_tr_mean)
        mu_cv = C_tr_mean - w_cv[0] * M_tr_mean - w_cv[1] * A_tr_mean
        c_pred_cv = w_cv[0] * M[test] + w_cv[1] * A[test] + mu_cv
        cv_cosines_r6.extend(cosine_batch(c_pred_cv, C[test]).tolist())
    cv_r6 = {
        "mean_cosine": float(np.mean(cv_cosines_r6)),
        "std_cosine": float(np.std(cv_cosines_r6)),
        "min_cosine": float(np.min(cv_cosines_r6)),
    }
    results_table.append(("R6: α·m + β·adj + μ (CV)", d + 2, cv_r6,
                          "leave-one-member-out"))

    # ══════════════════════════════════════════════════════════════════════
    # SUMMARY TABLE
    # ══════════════════════════════════════════════════════════════════════
    print(f"\n\n{'=' * 70}")
    print("  SUMMARY — ALL MODELS RANKED BY MEAN COSINE(C_pred, C_actual)")
    print("=" * 70)

    # Sort by mean cosine descending
    ranked = sorted(results_table, key=lambda x: x[2]["mean_cosine"], reverse=True)

    print(f"\n  {'Model':<36s} {'Params':>6s} {'Mean':>7s} {'Std':>7s} "
          f"{'Min':>7s}  Notes")
    print(f"  {'-'*90}")

    for name, n_params, stats, notes in ranked:
        print(f"  {name:<36s} {n_params:>6d} {stats['mean_cosine']:>7.4f} "
              f"{stats['std_cosine']:>7.4f} {stats.get('min_cosine', 0):>7.4f}  "
              f"{notes}")

    # ══════════════════════════════════════════════════════════════════════
    # INTERPRETATION
    # ══════════════════════════════════════════════════════════════════════
    print(f"\n\n{'=' * 70}")
    print("  KEY COMPARISONS")
    print("=" * 70)

    # Find specific models by name prefix
    def get_model(prefix):
        for name, _, stats, notes in results_table:
            if name.startswith(prefix):
                return stats["mean_cosine"]
        return None

    b1 = get_model("B1")
    s1 = get_model("S1")
    s2 = get_model("S2")
    r1 = get_model("R1")
    r3 = get_model("R3:")
    r5_cv = get_model("R5: P2 + μ (CV)")
    r6_cv = get_model("R6: α·m + β·adj + μ (CV)")

    print(f"\n  1. Does P1 add information beyond P2?")
    print(f"     P2 alone: {b1:.4f}")
    print(f"     P2 + γP1: {get_model('R2'):.4f}  "
          f"(Δ = {get_model('R2') - b1:+.4f})")
    print(f"     αP1 + βP2: {r1:.4f}  (Δ = {r1 - b1:+.4f})")

    print(f"\n  2. Can bare words compose the conclusion?")
    print(f"     bare member alone: {get_model('B3'):.4f}")
    print(f"     α·member + β·adj: {r3:.4f}  "
          f"(Δ from member alone = {r3 - get_model('B3'):+.4f})")
    print(f"     α·m + β·adj + μ (CV): {r6_cv:.4f}")

    print(f"\n  3. Structural models (zero fitted params):")
    print(f"     S1: P2 + (adj - class): {s1:.4f}  "
          f"(Δ from P2 alone = {s1 - b1:+.4f})")
    print(f"     S2: member + P1 - class: {s2:.4f}")

    print(f"\n  4. Do premises beat bare words?")
    print(f"     αP1 + βP2 (premises): {r1:.4f}")
    print(f"     α·m + β·adj (words):  {r3:.4f}  "
          f"(Δ = {r3 - r1:+.4f})")

    print(f"\n  5. Best achievable (CV):")
    print(f"     R5: P2 + μ:              {r5_cv:.4f}")
    print(f"     R6: α·m + β·adj + μ:     {r6_cv:.4f}")

    # ── Save ─────────────────────────────────────────────────────────────
    save_results = {}
    for name, n_params, stats, notes in results_table:
        key = name.split(":")[0].strip()
        save_results[name] = {
            "n_params": n_params,
            "notes": notes,
            **stats,
        }

    # Add fitted coefficients
    save_results["fitted_coefficients"] = {
        "R1_alpha_beta": w_r1.tolist(),
        "R2_gamma": float(w_r2[0]),
        "R3_alpha_beta": w_r3.tolist(),
        "R3b_alpha_beta_gamma": w_r3b.tolist(),
        "R4_all": w_r4.tolist(),
        "R4b_all": w_r4b.tolist(),
        "R6_alpha_beta": w_r6.tolist(),
    }

    json_path = os.path.join(_project_root, "prototype",
                             "syllogism_regression_results.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(save_results, f, indent=2)
    print(f"\n\nResults saved to: {json_path}")


if __name__ == "__main__":
    main()
