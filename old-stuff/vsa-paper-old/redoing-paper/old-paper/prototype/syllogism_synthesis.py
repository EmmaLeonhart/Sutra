"""Experiment 15d: Proposition Synthesis via Bridge Removal.

The syllogism as a logical operation in embedding space:
  1. Detect the shared entity (bridge) between P1 and P2
  2. Remove the bridge from both premises
  3. Compose the residuals to synthesize the conclusion

This is analogous to resolution in logic:
  P1: ∀x. Class(x) → Adj(x)    [contains: class, adjective, template]
  P2: Class(member)              [contains: member, class, template]
  Resolve on Class → Adj(member)

In embedding space:
  P1 - bridge ≈ "the adjective property" (what's new in P1)
  P2 - bridge ≈ "the member identity"    (what's new in P2)
  Synthesis = compose these residuals

Analyses:
  1. Bridge removal variants (zero-param logical operations)
  2. What do the residuals look like? (cosine to bare words)
  3. Scaled synthesis (fit weights on residuals)
  4. Automatic bridge detection (can we find K without knowing it?)
  5. Projection removal (remove bridge direction, not magnitude)

Usage:
    python prototype/syllogism_synthesis.py
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


# ── Constants (must match syllogism_gap_grid.py) ─────────────────────────────

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

def cosine(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-10))


def cosine_batch(A: np.ndarray, B: np.ndarray) -> np.ndarray:
    dot = np.sum(A * B, axis=1)
    nA = np.linalg.norm(A, axis=1) + 1e-10
    nB = np.linalg.norm(B, axis=1) + 1e-10
    return dot / (nA * nB)


def normalize_rows(X: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(X, axis=1, keepdims=True) + 1e-10
    return X / norms


def project_out(vectors: np.ndarray, direction: np.ndarray) -> np.ndarray:
    """Remove the component of each row along `direction`."""
    d_hat = direction / (np.linalg.norm(direction) + 1e-10)
    projections = (vectors @ d_hat)[:, None] * d_hat[None, :]
    return vectors - projections


def eval_model(C_pred, C_actual):
    cos = cosine_batch(C_pred, C_actual)
    return {
        "mean": float(np.mean(cos)),
        "std": float(np.std(cos)),
        "min": float(np.min(cos)),
        "max": float(np.max(cos)),
    }


def fit_global_scalars(features, target):
    X = np.column_stack([f.ravel() for f in features])
    y = target.ravel()
    weights, _, _, _ = np.linalg.lstsq(X, y, rcond=None)
    return weights


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    print("Proposition Synthesis via Bridge Removal")
    print("Loading embeddings...\n")

    # ── Load ─────────────────────────────────────────────────────────────
    npz_path = os.path.join(_project_root, "prototype",
                            "syllogism_gap_grid_embeddings.npz")
    data = np.load(npz_path, allow_pickle=True)
    all_vecs = data["all_vecs"]

    idx = 0
    p1_vecs = {}
    for cls_s, _ in CLASSES:
        for adj in ADJECTIVES:
            p1_vecs[(cls_s, adj)] = all_vecs[idx]; idx += 1
    p2_vecs = {}
    for member in MEMBERS:
        for cls_s, _ in CLASSES:
            p2_vecs[(member, cls_s)] = all_vecs[idx]; idx += 1
    c_vecs = {}
    for member in MEMBERS:
        for adj in ADJECTIVES:
            c_vecs[(member, adj)] = all_vecs[idx]; idx += 1
    bare_member_vecs = {}
    for member in MEMBERS:
        bare_member_vecs[member] = all_vecs[idx]; idx += 1
    bare_class_vecs = {}
    for cls_s, _ in CLASSES:
        bare_class_vecs[cls_s] = all_vecs[idx]; idx += 1
    bare_adj_vecs = {}
    for adj in ADJECTIVES:
        bare_adj_vecs[adj] = all_vecs[idx]; idx += 1

    d = all_vecs.shape[1]
    n = 1000

    # Build arrays
    P1 = np.zeros((n, d), dtype=np.float32)
    P2 = np.zeros((n, d), dtype=np.float32)
    C = np.zeros((n, d), dtype=np.float32)
    M = np.zeros((n, d), dtype=np.float32)
    A = np.zeros((n, d), dtype=np.float32)
    K = np.zeros((n, d), dtype=np.float32)
    member_idx = np.zeros(n, dtype=int)
    class_idx = np.zeros(n, dtype=int)
    adj_idx = np.zeros(n, dtype=int)

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

    results = {}
    model_table = []

    def run(name, C_pred, n_params=0, notes=""):
        stats = eval_model(C_pred, C)
        model_table.append((name, n_params, stats, notes))
        return stats

    # ══════════════════════════════════════════════════════════════════════
    # 1. BRIDGE REMOVAL VARIANTS
    # ══════════════════════════════════════════════════════════════════════

    print("=" * 70)
    print("  1. BRIDGE REMOVAL — LOGICAL SYNTHESIS (0 fitted params)")
    print("=" * 70)
    print("  Bridge = class embedding (shared entity between P1 and P2)")
    print("  Residual_P1 = P1 - K  (the 'adjective property')")
    print("  Residual_P2 = P2 - K  (the 'member identity')\n")

    # Residuals
    R1 = P1 - K  # "property residual"
    R2 = P2 - K  # "member residual"

    # L1: Symmetric — remove bridge from both, add residuals
    # (P1 - K) + (P2 - K) = P1 + P2 - 2K
    run("L1: (P1-K) + (P2-K)", R1 + R2, notes="P1 + P2 - 2K")

    # L2: Asymmetric — keep P2, add P1's new information
    # P2 + (P1 - K) = P1 + P2 - K
    run("L2: P2 + (P1-K)", P2 + R1, notes="P1 + P2 - K")

    # L3: Asymmetric — keep P1, add P2's identity
    # P1 + (P2 - K) = P1 + P2 - K (same as L2!)
    # So instead: keep the P2 template but swap content
    # Use normalized residuals
    run("L3: norm(P1-K) + norm(P2-K)", normalize_rows(R1) + normalize_rows(R2),
        notes="direction-only residuals")

    # L4: S1 from previous (best zero-param): P2 + (bare_adj - bare_class)
    run("L4: P2 + (A - K)", P2 + (A - K), notes="previous S1, reference")

    # L5: Like L1 but re-add bridge (tests if double-subtraction is too aggressive)
    # (P1 - K) + (P2 - K) + K = P1 + P2 - K
    run("L5: (P1-K) + (P2-K) + K", R1 + R2 + K, notes="= P1 + P2 - K = L2")

    # L6: Half-bridge removal
    run("L6: P1 + P2 - 0.5K", P1 + P2 - 0.5 * K, notes="partial removal")

    # ══════════════════════════════════════════════════════════════════════
    # 2. RESIDUAL ANALYSIS — What do the residuals encode?
    # ══════════════════════════════════════════════════════════════════════

    print(f"\n{'=' * 70}")
    print("  2. RESIDUAL ANALYSIS")
    print("=" * 70)
    print("  What does P1 - K encode? What does P2 - K encode?\n")

    # For each syllogism, compute cosine of residuals to bare words
    # P1 - K should be close to bare_adj (the "new info" in P1)
    # P2 - K should be close to bare_member (the "new info" in P2)
    r1_to_adj = cosine_batch(R1, A)
    r1_to_member = cosine_batch(R1, M)
    r1_to_class = cosine_batch(R1, K)

    r2_to_member = cosine_batch(R2, M)
    r2_to_adj = cosine_batch(R2, A)
    r2_to_class = cosine_batch(R2, K)

    print("  P1 - K (property residual):")
    print(f"    cos to bare adjective:  {np.mean(r1_to_adj):.4f} ± {np.std(r1_to_adj):.4f}")
    print(f"    cos to bare member:     {np.mean(r1_to_member):.4f} ± {np.std(r1_to_member):.4f}")
    print(f"    cos to bare class:      {np.mean(r1_to_class):.4f} ± {np.std(r1_to_class):.4f}")

    print("\n  P2 - K (member residual):")
    print(f"    cos to bare member:     {np.mean(r2_to_member):.4f} ± {np.std(r2_to_member):.4f}")
    print(f"    cos to bare adjective:  {np.mean(r2_to_adj):.4f} ± {np.std(r2_to_adj):.4f}")
    print(f"    cos to bare class:      {np.mean(r2_to_class):.4f} ± {np.std(r2_to_class):.4f}")

    # How much of P1 is the class? How much of P2?
    p1_class_component = np.mean(np.abs(np.sum(P1 * normalize_rows(K), axis=1)))
    p2_class_component = np.mean(np.abs(np.sum(P2 * normalize_rows(K), axis=1)))
    print(f"\n  Class component magnitude (|P·K̂|):")
    print(f"    In P1: {p1_class_component:.4f}")
    print(f"    In P2: {p2_class_component:.4f}")

    # What fraction of variance does bridge removal explain?
    p1_var = np.mean(np.sum(P1**2, axis=1))
    r1_var = np.mean(np.sum(R1**2, axis=1))
    p2_var = np.mean(np.sum(P2**2, axis=1))
    r2_var = np.mean(np.sum(R2**2, axis=1))
    print(f"\n  Variance remaining after bridge removal:")
    print(f"    P1: {p1_var:.4f} → P1-K: {r1_var:.4f} ({r1_var/p1_var*100:.1f}%)")
    print(f"    P2: {p2_var:.4f} → P2-K: {r2_var:.4f} ({r2_var/p2_var*100:.1f}%)")

    results["residual_analysis"] = {
        "R1_to_adj": float(np.mean(r1_to_adj)),
        "R1_to_member": float(np.mean(r1_to_member)),
        "R1_to_class": float(np.mean(r1_to_class)),
        "R2_to_member": float(np.mean(r2_to_member)),
        "R2_to_adj": float(np.mean(r2_to_adj)),
        "R2_to_class": float(np.mean(r2_to_class)),
    }

    # ══════════════════════════════════════════════════════════════════════
    # 3. SCALED SYNTHESIS
    # ══════════════════════════════════════════════════════════════════════

    print(f"\n{'=' * 70}")
    print("  3. SCALED SYNTHESIS (fitted weights on residuals)")
    print("=" * 70)
    print("  C ≈ α(P1-K) + β(P2-K)  — how to weight the residuals?\n")

    # Fit α, β on residuals
    w = fit_global_scalars([R1, R2], C)
    C_scaled = w[0] * R1 + w[1] * R2
    run("S1: α(P1-K) + β(P2-K)", C_scaled, 2,
        f"α={w[0]:.4f}, β={w[1]:.4f}")

    print(f"  Fitted: α={w[0]:.4f} (property weight), β={w[1]:.4f} (member weight)")

    # With bias (template vector)
    C_mean = C.mean(axis=0)
    R1_mean = R1.mean(axis=0)
    R2_mean = R2.mean(axis=0)
    w2 = fit_global_scalars([R1 - R1_mean, R2 - R2_mean], C - C_mean)
    mu = C_mean - w2[0] * R1_mean - w2[1] * R2_mean
    C_scaled_bias = w2[0] * R1 + w2[1] * R2 + mu
    run("S2: α(P1-K) + β(P2-K) + μ", C_scaled_bias, d + 2,
        f"α={w2[0]:.4f}, β={w2[1]:.4f}")

    # S2 cross-validation
    cv_cos = []
    for mi in range(10):
        tr = member_idx != mi
        te = member_idx == mi
        cm = C[tr].mean(0); r1m = R1[tr].mean(0); r2m = R2[tr].mean(0)
        wc = fit_global_scalars([R1[tr]-r1m, R2[tr]-r2m], C[tr]-cm)
        mc = cm - wc[0]*r1m - wc[1]*r2m
        pred = wc[0]*R1[te] + wc[1]*R2[te] + mc
        cv_cos.extend(cosine_batch(pred, C[te]).tolist())
    cv_stats = {"mean": float(np.mean(cv_cos)), "std": float(np.std(cv_cos)),
                "min": float(np.min(cv_cos)), "max": float(np.max(cv_cos))}
    model_table.append(("S2: α(P1-K)+β(P2-K)+μ (CV)", d+2, cv_stats, "leave-one-member-out"))

    print(f"  With bias: α={w2[0]:.4f}, β={w2[1]:.4f}")
    print(f"  Cross-validated: {cv_stats['mean']:.4f}")

    # ══════════════════════════════════════════════════════════════════════
    # 4. PROJECTION BRIDGE REMOVAL
    # ══════════════════════════════════════════════════════════════════════

    print(f"\n{'=' * 70}")
    print("  4. PROJECTION BRIDGE REMOVAL")
    print("=" * 70)
    print("  Instead of subtracting K, project out the K-direction.\n")

    # Per-syllogism projection (each has its own K direction)
    P1_proj = np.zeros_like(P1)
    P2_proj = np.zeros_like(P2)
    for i in range(n):
        k_hat = K[i] / (np.linalg.norm(K[i]) + 1e-10)
        P1_proj[i] = P1[i] - np.dot(P1[i], k_hat) * k_hat
        P2_proj[i] = P2[i] - np.dot(P2[i], k_hat) * k_hat

    run("Proj1: proj⊥K(P1) + proj⊥K(P2)", P1_proj + P2_proj,
        notes="remove K direction from both")

    # Asymmetric projection
    run("Proj2: P2 + proj⊥K(P1)", P2 + P1_proj,
        notes="keep P2, project out K from P1 only")

    # Also project out K from P2 but keep P1
    run("Proj3: P1 + proj⊥K(P2)", P1 + P2_proj,
        notes="keep P1, project out K from P2 only")

    # ══════════════════════════════════════════════════════════════════════
    # 5. AUTOMATIC BRIDGE DETECTION
    # ══════════════════════════════════════════════════════════════════════

    print(f"\n{'=' * 70}")
    print("  5. AUTOMATIC BRIDGE DETECTION")
    print("=" * 70)
    print("  Can we find the bridge without knowing it's the class?\n")

    # For each syllogism, we have three bare words: M, A, K.
    # The bridge is the word with highest min(cos_to_P1, cos_to_P2).
    # Test: does this correctly identify K as the bridge?

    correct_bridge = 0
    bridge_scores = {"member": [], "class": [], "adjective": []}

    for i in range(n):
        # Score each candidate
        m_score = min(cosine(M[i], P1[i]), cosine(M[i], P2[i]))
        k_score = min(cosine(K[i], P1[i]), cosine(K[i], P2[i]))
        a_score = min(cosine(A[i], P1[i]), cosine(A[i], P2[i]))

        bridge_scores["member"].append(m_score)
        bridge_scores["class"].append(k_score)
        bridge_scores["adjective"].append(a_score)

        # The bridge is the one with highest min-score
        if k_score >= m_score and k_score >= a_score:
            correct_bridge += 1

    print(f"  Bridge detection accuracy: {correct_bridge}/1000 ({correct_bridge/10:.1f}%)")
    print(f"\n  Mean min(cos_to_P1, cos_to_P2) per candidate:")
    print(f"    Member:    {np.mean(bridge_scores['member']):.4f}")
    print(f"    Class:     {np.mean(bridge_scores['class']):.4f}")
    print(f"    Adjective: {np.mean(bridge_scores['adjective']):.4f}")

    results["bridge_detection"] = {
        "accuracy": correct_bridge / 1000,
        "mean_member_score": float(np.mean(bridge_scores["member"])),
        "mean_class_score": float(np.mean(bridge_scores["class"])),
        "mean_adj_score": float(np.mean(bridge_scores["adjective"])),
    }

    # What if we use max instead of min? (word that's most present in both)
    correct_max = 0
    for i in range(n):
        m_s = (cosine(M[i], P1[i]) + cosine(M[i], P2[i])) / 2
        k_s = (cosine(K[i], P1[i]) + cosine(K[i], P2[i])) / 2
        a_s = (cosine(A[i], P1[i]) + cosine(A[i], P2[i])) / 2
        if k_s >= m_s and k_s >= a_s:
            correct_max += 1

    print(f"\n  Using mean(cos_to_P1, cos_to_P2) instead:")
    print(f"    Bridge detection accuracy: {correct_max}/1000 ({correct_max/10:.1f}%)")

    # What if we use the product? (word that's significantly present in both)
    correct_prod = 0
    for i in range(n):
        m_s = cosine(M[i], P1[i]) * cosine(M[i], P2[i])
        k_s = cosine(K[i], P1[i]) * cosine(K[i], P2[i])
        a_s = cosine(A[i], P1[i]) * cosine(A[i], P2[i])
        if k_s >= m_s and k_s >= a_s:
            correct_prod += 1

    print(f"\n  Using product cos_to_P1 × cos_to_P2:")
    print(f"    Bridge detection accuracy: {correct_prod}/1000 ({correct_prod/10:.1f}%)")

    # ══════════════════════════════════════════════════════════════════════
    # 6. END-TO-END: DETECT BRIDGE THEN SYNTHESIZE
    # ══════════════════════════════════════════════════════════════════════

    print(f"\n{'=' * 70}")
    print("  6. END-TO-END: DETECT BRIDGE → REMOVE → SYNTHESIZE")
    print("=" * 70)
    print("  Use automatic bridge detection, then apply synthesis.\n")

    # For each syllogism, pick the bridge as the bare word with highest
    # mean cosine to both P1 and P2, then apply L4-style synthesis
    C_auto = np.zeros_like(C)
    for i in range(n):
        candidates = [
            (M[i], "member"),
            (K[i], "class"),
            (A[i], "adjective"),
        ]
        # Bridge = highest mean cosine to both premises
        best_bridge = max(candidates,
                          key=lambda c: (cosine(c[0], P1[i]) + cosine(c[0], P2[i])) / 2)
        bridge_vec = best_bridge[0]

        # Remaining bare words (the "new information" from each side)
        remaining = [c[0] for c in candidates if c[1] != best_bridge[1]]

        # Synthesize: P2 + (other_bare_word - bridge) where other is the
        # bare word most similar to P1 (the "property source")
        cos_to_p1 = [cosine(r, P1[i]) for r in remaining]
        property_word = remaining[np.argmax(cos_to_p1)]
        C_auto[i] = P2[i] + (property_word - bridge_vec)

    run("E2E: auto-detect → P2+(prop-bridge)", C_auto, 0,
        "fully automatic synthesis")

    # ══════════════════════════════════════════════════════════════════════
    # SUMMARY
    # ══════════════════════════════════════════════════════════════════════

    print(f"\n\n{'=' * 70}")
    print("  SUMMARY — ALL MODELS RANKED BY MEAN COSINE(Ĉ, C)")
    print("=" * 70)

    ranked = sorted(model_table, key=lambda x: x[2]["mean"], reverse=True)

    print(f"\n  {'Model':<40s} {'Params':>6s} {'Mean':>7s} {'Std':>7s} "
          f"{'Min':>7s}  Notes")
    print(f"  {'-'*90}")

    for name, n_params, stats, notes in ranked:
        print(f"  {name:<40s} {n_params:>6d} {stats['mean']:>7.4f} "
              f"{stats['std']:>7.4f} {stats['min']:>7.4f}  {notes}")

    # Reference models from previous experiment
    print(f"\n  Reference (from Exp 15c):")
    print(f"  {'R6: α·m + β·adj + μ (CV)':<40s} {'1026':>6s} {'0.9478':>7s}")
    print(f"  {'S1: P2 + (adj - class)':<40s} {'0':>6s} {'0.8809':>7s}")
    print(f"  {'R1: αP1 + βP2':<40s} {'2':>6s} {'0.7895':>7s}")
    print(f"  {'B1: P2 alone':<40s} {'0':>6s} {'0.7794':>7s}")

    # ── Key comparisons ──────────────────────────────────────────────────
    print(f"\n{'=' * 70}")
    print("  KEY INSIGHT: SUBTRACTION vs PROJECTION")
    print("=" * 70)

    l1 = [s for n, _, s, _ in model_table if n.startswith("L1")][0]
    l2 = [s for n, _, s, _ in model_table if n.startswith("L2")][0]
    l4 = [s for n, _, s, _ in model_table if n.startswith("L4")][0]
    pr1 = [s for n, _, s, _ in model_table if n.startswith("Proj1")][0]
    pr2 = [s for n, _, s, _ in model_table if n.startswith("Proj2")][0]
    s1 = [s for n, _, s, _ in model_table if n.startswith("S1")][0]

    print(f"\n  Subtraction approach:")
    print(f"    (P1-K) + (P2-K)     = P1+P2-2K:  {l1['mean']:.4f}")
    print(f"    P2 + (P1-K)         = P1+P2-K:   {l2['mean']:.4f}")
    print(f"    P2 + (bare_adj - K) = S1:        {l4['mean']:.4f}")

    print(f"\n  Projection approach:")
    print(f"    proj⊥K(P1) + proj⊥K(P2):         {pr1['mean']:.4f}")
    print(f"    P2 + proj⊥K(P1):                  {pr2['mean']:.4f}")

    print(f"\n  Scaled residuals:")
    print(f"    α(P1-K) + β(P2-K):                {s1['mean']:.4f} "
          f"(α={w[0]:.3f}, β={w[1]:.3f})")

    # ── Save ─────────────────────────────────────────────────────────────
    results["models"] = {
        name: {"n_params": np, "notes": notes, **stats}
        for name, np, stats, notes in model_table
    }

    json_path = os.path.join(_project_root, "prototype",
                             "syllogism_synthesis_results.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"\n\nResults saved to: {json_path}")


if __name__ == "__main__":
    main()
