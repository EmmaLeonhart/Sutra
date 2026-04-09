"""Experiment 15b: Syllogism Gap Grid — 10×10×10 Systematic Test.

Uniform template across all 1000 syllogisms:
  P1: "All {class_plural} are {adjective}"
  P2: "{member} is a {class_singular}"
  C:  "{member} is {adjective}"

Full grid: 10 members × 10 classes × 10 adjectives = 1000 syllogisms.
Only 300 unique sentences (P1 depends on class+adj, P2 on member+class,
C on member+adj), plus 30 bare word embeddings = 330 total embeddings.

Analyses:
  1. Gap rate — fraction of 1000 where P1↔P2 is the weakest pair
  2. Per-component breakdown — gap rate by member, class, adjective
  3. Bare word pull — how bare member/class/adjective embeddings relate to
     sentence embeddings, connecting to the S > O > P hierarchy
  4. Cross-syllogism displacement consistency
  5. Similarity distributions by shared components

Usage:
    python prototype/syllogism_gap_grid.py
"""

from __future__ import annotations

import io
import json
import os
import sys
from itertools import combinations

import numpy as np

_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from prototype.pillar2_mapping import embed_texts


# ── Constants ────────────────────────────────────────────────────────────────

MEMBERS = [
    "Socrates", "Aristotle", "Einstein", "Mozart", "Shakespeare",
    "Cleopatra", "Darwin", "Galileo", "Confucius", "Archimedes",
]

# (singular, plural) — singular for P2 "X is a {singular}", plural for P1 "All {plural} are"
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


# ══════════════════════════════════════════════════════════════════════════════
# 1. GAP RATE
# ══════════════════════════════════════════════════════════════════════════════

def analyze_gap_rate(p1_vecs, p2_vecs, c_vecs) -> dict:
    """Core test: in how many of 1000 syllogisms is P1↔P2 the weakest pair?"""

    print("=" * 70)
    print("  1. SYLLOGISM GAP RATE (n=1000)")
    print("=" * 70)
    print("  Template: All {class} are {adj} + {member} is a {class}")
    print("          → {member} is {adj}\n")

    all_p1p2 = []
    all_p1c = []
    all_p2c = []
    weakest_counts = {"P1↔P2": 0, "P1↔C": 0, "P2↔C": 0}

    for member in MEMBERS:
        for cls_s, _ in CLASSES:
            for adj in ADJECTIVES:
                s_p1p2 = cosine(p1_vecs[(cls_s, adj)], p2_vecs[(member, cls_s)])
                s_p1c = cosine(p1_vecs[(cls_s, adj)], c_vecs[(member, adj)])
                s_p2c = cosine(p2_vecs[(member, cls_s)], c_vecs[(member, adj)])

                all_p1p2.append(s_p1p2)
                all_p1c.append(s_p1c)
                all_p2c.append(s_p2c)

                sims = {"P1↔P2": s_p1p2, "P1↔C": s_p1c, "P2↔C": s_p2c}
                weakest_counts[min(sims, key=sims.get)] += 1

    gap_count = weakest_counts["P1↔P2"]

    print(f"  Weakest pair distribution:")
    for pair, count in sorted(weakest_counts.items(), key=lambda x: -x[1]):
        print(f"    {pair}: {count}/1000 ({count/10:.1f}%)")

    print(f"\n  Syllogism gap (P1↔P2 weakest): {gap_count}/1000 ({gap_count/10:.1f}%)")
    print(f"\n  {'Pair':<10s} {'Mean':>8s} {'Std':>8s} {'Min':>8s} {'Max':>8s}")
    print(f"  {'-'*42}")
    for label, vals in [("P1↔P2", all_p1p2), ("P1↔C", all_p1c), ("P2↔C", all_p2c)]:
        print(f"  {label:<10s} {np.mean(vals):>8.4f} {np.std(vals):>8.4f} "
              f"{np.min(vals):>8.4f} {np.max(vals):>8.4f}")

    return {
        "gap_count": gap_count,
        "gap_rate": gap_count / 1000,
        "weakest_counts": weakest_counts,
        "mean_P1_P2": float(np.mean(all_p1p2)),
        "mean_P1_C": float(np.mean(all_p1c)),
        "mean_P2_C": float(np.mean(all_p2c)),
        "std_P1_P2": float(np.std(all_p1p2)),
        "std_P1_C": float(np.std(all_p1c)),
        "std_P2_C": float(np.std(all_p2c)),
        "all_P1_P2": [float(x) for x in all_p1p2],
        "all_P1_C": [float(x) for x in all_p1c],
        "all_P2_C": [float(x) for x in all_p2c],
    }


# ══════════════════════════════════════════════════════════════════════════════
# 2. PER-COMPONENT BREAKDOWN
# ══════════════════════════════════════════════════════════════════════════════

def analyze_per_component(p1_vecs, p2_vecs, c_vecs) -> dict:
    """Gap rate and mean similarities broken down by member, class, adjective."""

    print(f"\n{'=' * 70}")
    print("  2. PER-COMPONENT BREAKDOWN")
    print("=" * 70)

    results = {}

    # By member (each member appears in 100 syllogisms)
    print(f"\n  By MEMBER (n=100 each):")
    print(f"  {'Member':<14s} {'Gap%':>6s} {'P1↔P2':>7s} {'P1↔C':>7s} {'P2↔C':>7s}")
    print(f"  {'-'*46}")

    member_results = {}
    for member in MEMBERS:
        gaps = 0
        sims_p1p2, sims_p1c, sims_p2c = [], [], []
        for cls_s, _ in CLASSES:
            for adj in ADJECTIVES:
                s12 = cosine(p1_vecs[(cls_s, adj)], p2_vecs[(member, cls_s)])
                s1c = cosine(p1_vecs[(cls_s, adj)], c_vecs[(member, adj)])
                s2c = cosine(p2_vecs[(member, cls_s)], c_vecs[(member, adj)])
                sims_p1p2.append(s12)
                sims_p1c.append(s1c)
                sims_p2c.append(s2c)
                if s12 <= s1c and s12 <= s2c:
                    gaps += 1

        print(f"  {member:<14s} {gaps:>5d}% {np.mean(sims_p1p2):>7.3f} "
              f"{np.mean(sims_p1c):>7.3f} {np.mean(sims_p2c):>7.3f}")
        member_results[member] = {
            "gap_rate": gaps / 100,
            "mean_P1_P2": float(np.mean(sims_p1p2)),
            "mean_P1_C": float(np.mean(sims_p1c)),
            "mean_P2_C": float(np.mean(sims_p2c)),
        }
    results["by_member"] = member_results

    # By class (each class appears in 100 syllogisms)
    print(f"\n  By CLASS (n=100 each):")
    print(f"  {'Class':<14s} {'Gap%':>6s} {'P1↔P2':>7s} {'P1↔C':>7s} {'P2↔C':>7s}")
    print(f"  {'-'*46}")

    class_results = {}
    for cls_s, cls_p in CLASSES:
        gaps = 0
        sims_p1p2, sims_p1c, sims_p2c = [], [], []
        for member in MEMBERS:
            for adj in ADJECTIVES:
                s12 = cosine(p1_vecs[(cls_s, adj)], p2_vecs[(member, cls_s)])
                s1c = cosine(p1_vecs[(cls_s, adj)], c_vecs[(member, adj)])
                s2c = cosine(p2_vecs[(member, cls_s)], c_vecs[(member, adj)])
                sims_p1p2.append(s12)
                sims_p1c.append(s1c)
                sims_p2c.append(s2c)
                if s12 <= s1c and s12 <= s2c:
                    gaps += 1

        print(f"  {cls_s:<14s} {gaps:>5d}% {np.mean(sims_p1p2):>7.3f} "
              f"{np.mean(sims_p1c):>7.3f} {np.mean(sims_p2c):>7.3f}")
        class_results[cls_s] = {
            "gap_rate": gaps / 100,
            "mean_P1_P2": float(np.mean(sims_p1p2)),
            "mean_P1_C": float(np.mean(sims_p1c)),
            "mean_P2_C": float(np.mean(sims_p2c)),
        }
    results["by_class"] = class_results

    # By adjective (each adjective appears in 100 syllogisms)
    print(f"\n  By ADJECTIVE (n=100 each):")
    print(f"  {'Adjective':<14s} {'Gap%':>6s} {'P1↔P2':>7s} {'P1↔C':>7s} {'P2↔C':>7s}")
    print(f"  {'-'*46}")

    adj_results = {}
    for adj in ADJECTIVES:
        gaps = 0
        sims_p1p2, sims_p1c, sims_p2c = [], [], []
        for member in MEMBERS:
            for cls_s, _ in CLASSES:
                s12 = cosine(p1_vecs[(cls_s, adj)], p2_vecs[(member, cls_s)])
                s1c = cosine(p1_vecs[(cls_s, adj)], c_vecs[(member, adj)])
                s2c = cosine(p2_vecs[(member, cls_s)], c_vecs[(member, adj)])
                sims_p1p2.append(s12)
                sims_p1c.append(s1c)
                sims_p2c.append(s2c)
                if s12 <= s1c and s12 <= s2c:
                    gaps += 1

        print(f"  {adj:<14s} {gaps:>5d}% {np.mean(sims_p1p2):>7.3f} "
              f"{np.mean(sims_p1c):>7.3f} {np.mean(sims_p2c):>7.3f}")
        adj_results[adj] = {
            "gap_rate": gaps / 100,
            "mean_P1_P2": float(np.mean(sims_p1p2)),
            "mean_P1_C": float(np.mean(sims_p1c)),
            "mean_P2_C": float(np.mean(sims_p2c)),
        }
    results["by_adjective"] = adj_results

    return results


# ══════════════════════════════════════════════════════════════════════════════
# 3. BARE WORD PULL ANALYSIS
# ══════════════════════════════════════════════════════════════════════════════

def analyze_bare_word_pull(p1_vecs, p2_vecs, c_vecs,
                           bare_member_vecs, bare_class_vecs, bare_adj_vecs) -> dict:
    """How much does each bare word 'pull' sentence embeddings toward it?

    Connects to the S > O > P hierarchy from the semantic grid experiments.

    In our template:
      P1: "All {class} are {adj}"   — class=subject, adjective=predicate
      P2: "{member} is a {class}"   — member=subject, class=object
      C:  "{member} is {adj}"       — member=subject, adjective=predicate

    We measure: cosine(bare_word, sentence_containing_word) vs
                cosine(bare_word, sentence_NOT_containing_word)
    """

    print(f"\n{'=' * 70}")
    print("  3. BARE WORD PULL ANALYSIS")
    print("=" * 70)
    print("  How much does each bare word pull the sentence embedding?")
    print("  Connects to the Subject > Object > Predicate hierarchy.\n")

    # Collect all sentence vectors by type for easy iteration
    p1_list = list(p1_vecs.values())  # 100 vectors
    p2_list = list(p2_vecs.values())  # 100 vectors
    c_list = list(c_vecs.values())    # 100 vectors

    results = {}

    # ── Member pull ──────────────────────────────────────────────────────
    # Member appears as SUBJECT in P2 and C. Absent from P1.
    member_pull_p2 = []  # cosine(bare_m, P2_with_m) - cosine(bare_m, P2_without_m)
    member_pull_c = []
    member_baseline_p1 = []  # cosine(bare_m, P1) — member never in P1

    for member in MEMBERS:
        bv = bare_member_vecs[member]

        # P2 sentences with this member vs without
        with_p2 = [cosine(bv, p2_vecs[(member, c)]) for c, _ in CLASSES]
        without_p2 = [cosine(bv, p2_vecs[(m, c)])
                      for m in MEMBERS for c, _ in CLASSES if m != member]
        member_pull_p2.append(np.mean(with_p2) - np.mean(without_p2))

        # C sentences with this member vs without
        with_c = [cosine(bv, c_vecs[(member, a)]) for a in ADJECTIVES]
        without_c = [cosine(bv, c_vecs[(m, a)])
                     for m in MEMBERS for a in ADJECTIVES if m != member]
        member_pull_c.append(np.mean(with_c) - np.mean(without_c))

        # Baseline: member against P1 (where it never appears)
        baseline = [cosine(bv, v) for v in p1_list]
        member_baseline_p1.append(np.mean(baseline))

    # ── Class pull ───────────────────────────────────────────────────────
    # Class appears as SUBJECT in P1 (via "All {class}"), OBJECT in P2.
    # Absent from C.
    class_pull_p1 = []
    class_pull_p2 = []
    class_baseline_c = []

    for cls_s, _ in CLASSES:
        bv = bare_class_vecs[cls_s]

        # P1 sentences with this class vs without
        with_p1 = [cosine(bv, p1_vecs[(cls_s, a)]) for a in ADJECTIVES]
        without_p1 = [cosine(bv, p1_vecs[(c, a)])
                      for c, _ in CLASSES for a in ADJECTIVES if c != cls_s]
        class_pull_p1.append(np.mean(with_p1) - np.mean(without_p1))

        # P2 sentences with this class vs without
        with_p2 = [cosine(bv, p2_vecs[(m, cls_s)]) for m in MEMBERS]
        without_p2 = [cosine(bv, p2_vecs[(m, c)])
                      for m in MEMBERS for c, _ in CLASSES if c != cls_s]
        class_pull_p2.append(np.mean(with_p2) - np.mean(without_p2))

        # Baseline: class against C (where it never appears)
        baseline = [cosine(bv, v) for v in c_list]
        class_baseline_c.append(np.mean(baseline))

    # ── Adjective pull ───────────────────────────────────────────────────
    # Adjective appears as PREDICATE in P1 and C. Absent from P2.
    adj_pull_p1 = []
    adj_pull_c = []
    adj_baseline_p2 = []

    for adj in ADJECTIVES:
        bv = bare_adj_vecs[adj]

        # P1 sentences with this adjective vs without
        with_p1 = [cosine(bv, p1_vecs[(c, adj)]) for c, _ in CLASSES]
        without_p1 = [cosine(bv, p1_vecs[(c, a)])
                      for c, _ in CLASSES for a in ADJECTIVES if a != adj]
        adj_pull_p1.append(np.mean(with_p1) - np.mean(without_p1))

        # C sentences with this adjective vs without
        with_c = [cosine(bv, c_vecs[(m, adj)]) for m in MEMBERS]
        without_c = [cosine(bv, c_vecs[(m, a)])
                     for m in MEMBERS for a in ADJECTIVES if a != adj]
        adj_pull_c.append(np.mean(with_c) - np.mean(without_c))

        # Baseline: adjective against P2 (where it never appears)
        baseline = [cosine(bv, v) for v in p2_list]
        adj_baseline_p2.append(np.mean(baseline))

    # ── Summary table ────────────────────────────────────────────────────
    print(f"  {'Word type':<12s} {'Sentence':<6s} {'Role in sent':<14s} "
          f"{'Pull (Δ)':>9s} {'Baseline':>9s}")
    print(f"  {'-'*56}")

    rows = [
        ("Member", "P2", "subject", np.mean(member_pull_p2), np.mean(member_baseline_p1)),
        ("Member", "C", "subject", np.mean(member_pull_c), np.mean(member_baseline_p1)),
        ("Class", "P1", "subject", np.mean(class_pull_p1), np.mean(class_baseline_c)),
        ("Class", "P2", "object", np.mean(class_pull_p2), np.mean(class_baseline_c)),
        ("Adjective", "P1", "predicate", np.mean(adj_pull_p1), np.mean(adj_baseline_p2)),
        ("Adjective", "C", "predicate", np.mean(adj_pull_c), np.mean(adj_baseline_p2)),
    ]

    for wtype, sent, role, pull, baseline in rows:
        print(f"  {wtype:<12s} {sent:<6s} {role:<14s} {pull:>+9.4f} {baseline:>9.4f}")

    # Per-word detail tables
    print(f"\n  Per-member pull (subject role):")
    print(f"  {'Member':<14s} {'→P2':>8s} {'→C':>8s} {'baseline':>8s}")
    print(f"  {'-'*40}")
    for i, member in enumerate(MEMBERS):
        print(f"  {member:<14s} {member_pull_p2[i]:>+8.4f} {member_pull_c[i]:>+8.4f} "
              f"{member_baseline_p1[i]:>8.4f}")

    print(f"\n  Per-class pull:")
    print(f"  {'Class':<14s} {'→P1 (subj)':>11s} {'→P2 (obj)':>11s} {'baseline':>8s}")
    print(f"  {'-'*48}")
    for i, (cls_s, _) in enumerate(CLASSES):
        print(f"  {cls_s:<14s} {class_pull_p1[i]:>+11.4f} {class_pull_p2[i]:>+11.4f} "
              f"{class_baseline_c[i]:>8.4f}")

    print(f"\n  Per-adjective pull (predicate role):")
    print(f"  {'Adjective':<14s} {'→P1':>8s} {'→C':>8s} {'baseline':>8s}")
    print(f"  {'-'*40}")
    for i, adj in enumerate(ADJECTIVES):
        print(f"  {adj:<14s} {adj_pull_p1[i]:>+8.4f} {adj_pull_c[i]:>+8.4f} "
              f"{adj_baseline_p2[i]:>8.4f}")

    # Subject vs Object vs Predicate summary
    subj_pulls = member_pull_p2 + member_pull_c + class_pull_p1
    obj_pulls = class_pull_p2[:]
    pred_pulls = adj_pull_p1 + adj_pull_c

    print(f"\n  Role summary (connecting to S > O > P hierarchy):")
    print(f"    Subject pull (member→P2, member→C, class→P1): "
          f"{np.mean(subj_pulls):+.4f} (n={len(subj_pulls)})")
    print(f"    Object pull  (class→P2):                      "
          f"{np.mean(obj_pulls):+.4f} (n={len(obj_pulls)})")
    print(f"    Predicate pull (adj→P1, adj→C):               "
          f"{np.mean(pred_pulls):+.4f} (n={len(pred_pulls)})")

    results = {
        "summary": {r[0] + "_" + r[1]: {"role": r[2], "pull": r[3], "baseline": r[4]}
                    for r in rows},
        "role_summary": {
            "subject_pull": float(np.mean(subj_pulls)),
            "object_pull": float(np.mean(obj_pulls)),
            "predicate_pull": float(np.mean(pred_pulls)),
        },
        "per_member": {m: {"pull_P2": float(member_pull_p2[i]),
                           "pull_C": float(member_pull_c[i]),
                           "baseline_P1": float(member_baseline_p1[i])}
                       for i, m in enumerate(MEMBERS)},
        "per_class": {c: {"pull_P1": float(class_pull_p1[i]),
                          "pull_P2": float(class_pull_p2[i]),
                          "baseline_C": float(class_baseline_c[i])}
                      for i, (c, _) in enumerate(CLASSES)},
        "per_adjective": {a: {"pull_P1": float(adj_pull_p1[i]),
                              "pull_C": float(adj_pull_c[i]),
                              "baseline_P2": float(adj_baseline_p2[i])}
                          for i, a in enumerate(ADJECTIVES)},
    }

    return results


# ══════════════════════════════════════════════════════════════════════════════
# 4. CROSS-SYLLOGISM DISPLACEMENT CONSISTENCY
# ══════════════════════════════════════════════════════════════════════════════

def analyze_displacement_consistency(p1_vecs, p2_vecs, c_vecs) -> dict:
    """Do P2→C displacements share a common direction across syllogisms?

    Since P2→C = C(member, adj) - P2(member, class), these depend on
    which (member, class, adj) triple we use. We sample all 100 unique
    P2→C displacements (holding member fixed, varying class+adj gives
    different displacements; but for a given member, class→adj pairing
    gives one displacement per (class, adj) pair).

    Actually: for each of 1000 syllogisms, P2→C is unique. But many share
    the same P2 or same C. We'll sample 200 random syllogisms for the
    pairwise analysis to keep it tractable (200 choose 2 = 19900 pairs).
    """

    print(f"\n{'=' * 70}")
    print("  4. DISPLACEMENT CONSISTENCY")
    print("=" * 70)
    print("  Do P2→C displacements share a common direction?\n")

    results = {}

    # Compute all P2→C, P1→C, P1→P2 displacements for all 1000
    # But for pairwise cosine, use a stratified sample
    all_disps = {"P2→C": [], "P1→C": [], "P1→P2": []}
    all_labels = []

    for member in MEMBERS:
        for cls_s, _ in CLASSES:
            for adj in ADJECTIVES:
                v_p1 = p1_vecs[(cls_s, adj)]
                v_p2 = p2_vecs[(member, cls_s)]
                v_c = c_vecs[(member, adj)]

                all_disps["P2→C"].append(v_c - v_p2)
                all_disps["P1→C"].append(v_c - v_p1)
                all_disps["P1→P2"].append(v_p2 - v_p1)
                all_labels.append(f"{member}/{cls_s}/{adj}")

    # For pairwise cosine, sample 200 evenly spaced
    n = len(all_labels)
    rng = np.random.RandomState(42)
    sample_idx = rng.choice(n, size=min(200, n), replace=False)
    sample_idx.sort()

    for disp_name in ["P2→C", "P1→C", "P1→P2"]:
        disps = [all_disps[disp_name][i] for i in sample_idx]

        pair_cosines = []
        for i in range(len(disps)):
            for j in range(i + 1, len(disps)):
                pair_cosines.append(cosine(disps[i], disps[j]))

        mean_cos = float(np.mean(pair_cosines))
        std_cos = float(np.std(pair_cosines))

        # Mean direction and alignment
        mean_disp = np.mean(disps, axis=0)
        alignments = [cosine(d, mean_disp) for d in disps]
        mean_align = float(np.mean(alignments))

        print(f"  {disp_name}:")
        print(f"    Pairwise cosine (n={len(pair_cosines)} pairs): "
              f"mean={mean_cos:.4f} std={std_cos:.3f}")
        print(f"    Mean alignment to grand mean: {mean_align:.4f}")

        results[disp_name] = {
            "mean_pairwise_cosine": mean_cos,
            "std": std_cos,
            "mean_alignment": mean_align,
        }

    # Also check: does sharing a component increase consistency?
    print(f"\n  Conditioning on shared components (P2→C displacement):")

    disps_by_member = {m: [] for m in MEMBERS}
    disps_by_class = {c: [] for c, _ in CLASSES}
    disps_by_adj = {a: [] for a in ADJECTIVES}

    for i, label in enumerate(all_labels):
        member, cls_s, adj = label.split("/")
        d = all_disps["P2→C"][i]
        disps_by_member[member].append(d)
        disps_by_class[cls_s].append(d)
        disps_by_adj[adj].append(d)

    for group_name, groups in [("member", disps_by_member),
                                ("class", disps_by_class),
                                ("adjective", disps_by_adj)]:
        within_cosines = []
        for key, disps in groups.items():
            # Sample up to 20 for tractability
            sample = disps[:20] if len(disps) > 20 else disps
            for i in range(len(sample)):
                for j in range(i + 1, len(sample)):
                    within_cosines.append(cosine(sample[i], sample[j]))

        mean_within = float(np.mean(within_cosines)) if within_cosines else 0
        print(f"    Same {group_name:>10s}: {mean_within:.4f} "
              f"(n={len(within_cosines)} pairs)")

    return results


# ══════════════════════════════════════════════════════════════════════════════
# 5. SHARED COMPONENT SIMILARITY ANALYSIS
# ══════════════════════════════════════════════════════════════════════════════

def analyze_shared_components(p1_vecs, p2_vecs, c_vecs) -> dict:
    """How does sharing member/class/adjective affect each pairwise similarity?

    For P1↔P2: they always share the class. They never share member (not in P1)
               or adjective (not in P2). So P1↔P2 similarity comes from class.
    For P1↔C:  they always share the adjective. Never share member or class.
    For P2↔C:  they always share the member. Never share class or adjective.

    But across different syllogisms in the grid, we can compare:
    - Same class vs different class (for P1↔P2 pairs from different syllogisms)
    - Same member vs different member (for P2↔C pairs from different syllogisms)
    """

    print(f"\n{'=' * 70}")
    print("  5. WHAT EACH PAIR SHARES (STRUCTURAL ANALYSIS)")
    print("=" * 70)
    print("  Why P2↔C > P1↔C > P1↔P2:")
    print("    P2↔C share: member (as SUBJECT in both)")
    print("    P1↔C share: adjective (as PREDICATE in both)")
    print("    P1↔P2 share: class (as SUBJECT in P1, OBJECT in P2)\n")

    # Cross-sentence type: compare same-component P1 vs different-component P1
    # E.g., how similar are two P1 sentences with the same class vs different class?
    results = {}

    # P1 × P1: same class vs different class, same adj vs different adj
    p1_keys = list(p1_vecs.keys())
    same_cls_p1 = []
    diff_cls_p1 = []
    same_adj_p1 = []
    diff_adj_p1 = []
    for i in range(len(p1_keys)):
        for j in range(i + 1, len(p1_keys)):
            c = cosine(p1_vecs[p1_keys[i]], p1_vecs[p1_keys[j]])
            if p1_keys[i][0] == p1_keys[j][0]:
                same_cls_p1.append(c)
            else:
                diff_cls_p1.append(c)
            if p1_keys[i][1] == p1_keys[j][1]:
                same_adj_p1.append(c)
            else:
                diff_adj_p1.append(c)

    print(f"  Within P1 sentences ('{CLASSES[0][1]}' as subject, adjective as predicate):")
    print(f"    Same class (subject): {np.mean(same_cls_p1):.4f} vs diff: {np.mean(diff_cls_p1):.4f} "
          f"(Δ={np.mean(same_cls_p1)-np.mean(diff_cls_p1):+.4f})")
    print(f"    Same adj (predicate): {np.mean(same_adj_p1):.4f} vs diff: {np.mean(diff_adj_p1):.4f} "
          f"(Δ={np.mean(same_adj_p1)-np.mean(diff_adj_p1):+.4f})")

    # P2 × P2: same member vs different, same class vs different
    p2_keys = list(p2_vecs.keys())
    same_mem_p2 = []
    diff_mem_p2 = []
    same_cls_p2 = []
    diff_cls_p2 = []
    for i in range(len(p2_keys)):
        for j in range(i + 1, len(p2_keys)):
            c = cosine(p2_vecs[p2_keys[i]], p2_vecs[p2_keys[j]])
            if p2_keys[i][0] == p2_keys[j][0]:
                same_mem_p2.append(c)
            else:
                diff_mem_p2.append(c)
            if p2_keys[i][1] == p2_keys[j][1]:
                same_cls_p2.append(c)
            else:
                diff_cls_p2.append(c)

    print(f"\n  Within P2 sentences (member as subject, class as object):")
    print(f"    Same member (subject): {np.mean(same_mem_p2):.4f} vs diff: {np.mean(diff_mem_p2):.4f} "
          f"(Δ={np.mean(same_mem_p2)-np.mean(diff_mem_p2):+.4f})")
    print(f"    Same class (object):   {np.mean(same_cls_p2):.4f} vs diff: {np.mean(diff_cls_p2):.4f} "
          f"(Δ={np.mean(same_cls_p2)-np.mean(diff_cls_p2):+.4f})")

    # C × C: same member vs different, same adj vs different
    c_keys = list(c_vecs.keys())
    same_mem_c = []
    diff_mem_c = []
    same_adj_c = []
    diff_adj_c = []
    for i in range(len(c_keys)):
        for j in range(i + 1, len(c_keys)):
            co = cosine(c_vecs[c_keys[i]], c_vecs[c_keys[j]])
            if c_keys[i][0] == c_keys[j][0]:
                same_mem_c.append(co)
            else:
                diff_mem_c.append(co)
            if c_keys[i][1] == c_keys[j][1]:
                same_adj_c.append(co)
            else:
                diff_adj_c.append(co)

    print(f"\n  Within C sentences (member as subject, adjective as predicate):")
    print(f"    Same member (subject):   {np.mean(same_mem_c):.4f} vs diff: {np.mean(diff_mem_c):.4f} "
          f"(Δ={np.mean(same_mem_c)-np.mean(diff_mem_c):+.4f})")
    print(f"    Same adj (predicate):    {np.mean(same_adj_c):.4f} vs diff: {np.mean(diff_adj_c):.4f} "
          f"(Δ={np.mean(same_adj_c)-np.mean(diff_adj_c):+.4f})")

    # Cross-type summary for the gap explanation
    print(f"\n  GAP EXPLANATION via role hierarchy:")
    subj_pull = np.mean([
        np.mean(same_cls_p1) - np.mean(diff_cls_p1),  # class as subject in P1
        np.mean(same_mem_p2) - np.mean(diff_mem_p2),  # member as subject in P2
        np.mean(same_mem_c) - np.mean(diff_mem_c),    # member as subject in C
    ])
    obj_pull = np.mean([
        np.mean(same_cls_p2) - np.mean(diff_cls_p2),  # class as object in P2
    ])
    pred_pull = np.mean([
        np.mean(same_adj_p1) - np.mean(diff_adj_p1),  # adjective as predicate in P1
        np.mean(same_adj_c) - np.mean(diff_adj_c),    # adjective as predicate in C
    ])

    print(f"    Subject pull (class→P1, member→P2, member→C):  {subj_pull:+.4f}")
    print(f"    Object pull  (class→P2):                       {obj_pull:+.4f}")
    print(f"    Predicate pull (adj→P1, adj→C):                {pred_pull:+.4f}")
    print(f"    Ratio: S={subj_pull/pred_pull:.1f}x  O={obj_pull/pred_pull:.1f}x  P=1.0x")

    results = {
        "P1_same_class": float(np.mean(same_cls_p1)),
        "P1_diff_class": float(np.mean(diff_cls_p1)),
        "P1_class_delta": float(np.mean(same_cls_p1) - np.mean(diff_cls_p1)),
        "P1_same_adj": float(np.mean(same_adj_p1)),
        "P1_diff_adj": float(np.mean(diff_adj_p1)),
        "P1_adj_delta": float(np.mean(same_adj_p1) - np.mean(diff_adj_p1)),
        "P2_same_member": float(np.mean(same_mem_p2)),
        "P2_diff_member": float(np.mean(diff_mem_p2)),
        "P2_member_delta": float(np.mean(same_mem_p2) - np.mean(diff_mem_p2)),
        "P2_same_class": float(np.mean(same_cls_p2)),
        "P2_diff_class": float(np.mean(diff_cls_p2)),
        "P2_class_delta": float(np.mean(same_cls_p2) - np.mean(diff_cls_p2)),
        "C_same_member": float(np.mean(same_mem_c)),
        "C_diff_member": float(np.mean(diff_mem_c)),
        "C_member_delta": float(np.mean(same_mem_c) - np.mean(diff_mem_c)),
        "C_same_adj": float(np.mean(same_adj_c)),
        "C_diff_adj": float(np.mean(diff_adj_c)),
        "C_adj_delta": float(np.mean(same_adj_c) - np.mean(diff_adj_c)),
        "role_summary": {
            "subject_pull": float(subj_pull),
            "object_pull": float(obj_pull),
            "predicate_pull": float(pred_pull),
        },
    }

    return results


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    print("Syllogism Gap Grid — 10×10×10 Systematic Test")
    print("Embedding with mxbai-embed-large (1024-dim)...\n")

    # ── Generate unique sentences ────────────────────────────────────────
    texts = []
    text_meta = []  # (type, key_tuple) for mapping back

    # P1: "All {plural} are {adj}" — 100 unique
    for cls_s, cls_p in CLASSES:
        for adj in ADJECTIVES:
            texts.append(f"All {cls_p} are {adj}")
            text_meta.append(("P1", (cls_s, adj)))

    # P2: "{member} is a {singular}" — 100 unique
    for member in MEMBERS:
        for cls_s, cls_p in CLASSES:
            texts.append(f"{member} is a {cls_s}")
            text_meta.append(("P2", (member, cls_s)))

    # C: "{member} is {adj}" — 100 unique
    for member in MEMBERS:
        for adj in ADJECTIVES:
            texts.append(f"{member} is {adj}")
            text_meta.append(("C", (member, adj)))

    # Bare words — 30
    for member in MEMBERS:
        texts.append(member)
        text_meta.append(("bare_member", member))
    for cls_s, _ in CLASSES:
        texts.append(cls_s)
        text_meta.append(("bare_class", cls_s))
    for adj in ADJECTIVES:
        texts.append(adj)
        text_meta.append(("bare_adj", adj))

    print(f"  Unique texts: {len(texts)} "
          f"(100 P1 + 100 P2 + 100 C + 30 bare words)")
    print(f"  Grid: {len(MEMBERS)} members × {len(CLASSES)} classes × "
          f"{len(ADJECTIVES)} adjectives = "
          f"{len(MEMBERS)*len(CLASSES)*len(ADJECTIVES)} syllogisms\n")

    # ── Embed ────────────────────────────────────────────────────────────
    print(f"  Embedding {len(texts)} texts...")
    all_vecs = embed_texts(texts)
    print(f"  Done. Shape: {all_vecs.shape}\n")

    # ── Build lookup dicts ───────────────────────────────────────────────
    p1_vecs = {}
    p2_vecs = {}
    c_vecs = {}
    bare_member_vecs = {}
    bare_class_vecs = {}
    bare_adj_vecs = {}

    for i, (typ, key) in enumerate(text_meta):
        if typ == "P1":
            p1_vecs[key] = all_vecs[i]
        elif typ == "P2":
            p2_vecs[key] = all_vecs[i]
        elif typ == "C":
            c_vecs[key] = all_vecs[i]
        elif typ == "bare_member":
            bare_member_vecs[key] = all_vecs[i]
        elif typ == "bare_class":
            bare_class_vecs[key] = all_vecs[i]
        elif typ == "bare_adj":
            bare_adj_vecs[key] = all_vecs[i]

    # ── Run analyses ─────────────────────────────────────────────────────
    results = {}
    results["gap_rate"] = analyze_gap_rate(p1_vecs, p2_vecs, c_vecs)
    results["per_component"] = analyze_per_component(p1_vecs, p2_vecs, c_vecs)
    results["bare_word_pull"] = analyze_bare_word_pull(
        p1_vecs, p2_vecs, c_vecs,
        bare_member_vecs, bare_class_vecs, bare_adj_vecs)
    results["displacement_consistency"] = analyze_displacement_consistency(
        p1_vecs, p2_vecs, c_vecs)
    results["shared_components"] = analyze_shared_components(
        p1_vecs, p2_vecs, c_vecs)

    # Remove large arrays from JSON output
    gap_for_json = {k: v for k, v in results["gap_rate"].items()
                    if k not in ("all_P1_P2", "all_P1_C", "all_P2_C")}
    results_for_json = dict(results)
    results_for_json["gap_rate"] = gap_for_json

    # ── Save ─────────────────────────────────────────────────────────────
    json_path = os.path.join(_project_root, "prototype",
                             "syllogism_gap_grid_results.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(results_for_json, f, indent=2)
    print(f"\n\nResults saved to: {json_path}")

    npz_path = os.path.join(_project_root, "prototype",
                            "syllogism_gap_grid_embeddings.npz")
    np.savez(
        npz_path,
        all_vecs=all_vecs,
        texts=np.array(texts, dtype=object),
        meta_types=np.array([m[0] for m in text_meta], dtype=object),
        meta_keys=np.array([str(m[1]) for m in text_meta], dtype=object),
        members=np.array(MEMBERS, dtype=object),
        classes=np.array([c[0] for c in CLASSES], dtype=object),
        adjectives=np.array(ADJECTIVES, dtype=object),
    )
    print(f"Embeddings saved to: {npz_path}")


if __name__ == "__main__":
    main()
