"""Experiment 15: Syllogism Gap — 20-Syllogism Systematic Test.

Section 4.2 claims the "syllogism gap" (premises being the most distant pair
in embedding space) but only tested 2 examples. This script tests 20 diverse
syllogisms to make the claim statistically testable.

All follow: Universal(Class, Property) + Member(Individual, Class) → Property(Individual)

Analyses:
  1. Pairwise similarities — P1↔P2, P1↔C, P2↔C; count P1↔P2 as weakest
  2. Displacement vectors — magnitudes and directions of P1→C, P2→C, P1→P2
  3. Cross-syllogism displacement consistency — do P2→C vectors share direction?
  4. Within-domain vs cross-domain consistency
  5. Individual name proximity — bare name cosine to P1/P2/C
  6. Proper noun vs generic — gap magnitudes by individual type

Usage:
    python prototype/syllogism_gap.py
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


# ── Syllogism definitions ────────────────────────────────────────────────────

SYLLOGISMS = [
    {
        "id": "socrates",
        "domain": "philosophy",
        "individual_type": "proper",
        "individual": "Socrates",
        "P1": "All men are mortal",
        "P2": "Socrates is a man",
        "C": "Socrates is mortal",
    },
    {
        "id": "robin",
        "domain": "biology",
        "individual_type": "generic",
        "individual": "robin",
        "P1": "All birds can fly",
        "P2": "A robin is a bird",
        "C": "A robin can fly",
    },
    {
        "id": "whiskers",
        "domain": "biology",
        "individual_type": "proper",
        "individual": "Whiskers",
        "P1": "All cats are carnivores",
        "P2": "Whiskers is a cat",
        "C": "Whiskers is a carnivore",
    },
    {
        "id": "rex",
        "domain": "biology",
        "individual_type": "proper",
        "individual": "Rex",
        "P1": "All dogs are mammals",
        "P2": "Rex is a dog",
        "C": "Rex is a mammal",
    },
    {
        "id": "nemo",
        "domain": "biology",
        "individual_type": "proper",
        "individual": "Nemo",
        "P1": "All fish have gills",
        "P2": "Nemo is a fish",
        "C": "Nemo has gills",
    },
    {
        "id": "mars",
        "domain": "astronomy",
        "individual_type": "proper",
        "individual": "Mars",
        "P1": "All planets are round",
        "P2": "Mars is a planet",
        "C": "Mars is round",
    },
    {
        "id": "amazon",
        "domain": "geography",
        "individual_type": "proper",
        "individual": "The Amazon",
        "P1": "All rivers flow downhill",
        "P2": "The Amazon is a river",
        "C": "The Amazon flows downhill",
    },
    {
        "id": "everest",
        "domain": "geography",
        "individual_type": "proper",
        "individual": "Everest",
        "P1": "All mountains have summits",
        "P2": "Everest is a mountain",
        "C": "Everest has a summit",
    },
    {
        "id": "johnson",
        "domain": "profession",
        "individual_type": "proper",
        "individual": "Ms. Johnson",
        "P1": "All teachers are educators",
        "P2": "Ms. Johnson is a teacher",
        "C": "Ms. Johnson is an educator",
    },
    {
        "id": "chen",
        "domain": "profession",
        "individual_type": "proper",
        "individual": "Dr. Chen",
        "P1": "All surgeons are doctors",
        "P2": "Dr. Chen is a surgeon",
        "C": "Dr. Chen is a doctor",
    },
    {
        "id": "gold",
        "domain": "chemistry",
        "individual_type": "generic",
        "individual": "Gold",
        "P1": "All metals conduct electricity",
        "P2": "Gold is a metal",
        "C": "Gold conducts electricity",
    },
    {
        "id": "oak",
        "domain": "biology",
        "individual_type": "generic",
        "individual": "oak",
        "P1": "All trees have roots",
        "P2": "An oak is a tree",
        "C": "An oak has roots",
    },
    {
        "id": "ruby",
        "domain": "geology",
        "individual_type": "generic",
        "individual": "ruby",
        "P1": "All gemstones are minerals",
        "P2": "A ruby is a gemstone",
        "C": "A ruby is a mineral",
    },
    {
        "id": "apple",
        "domain": "biology",
        "individual_type": "generic",
        "individual": "apple",
        "P1": "All fruits contain seeds",
        "P2": "An apple is a fruit",
        "C": "An apple contains seeds",
    },
    {
        "id": "penicillin",
        "domain": "pharmacology",
        "individual_type": "generic",
        "individual": "Penicillin",
        "P1": "All antibiotics kill bacteria",
        "P2": "Penicillin is an antibiotic",
        "C": "Penicillin kills bacteria",
    },
    {
        "id": "chess",
        "domain": "recreation",
        "individual_type": "generic",
        "individual": "Chess",
        "P1": "All games have rules",
        "P2": "Chess is a game",
        "C": "Chess has rules",
    },
    {
        "id": "french",
        "domain": "linguistics",
        "individual_type": "generic",
        "individual": "French",
        "P1": "All languages have grammar",
        "P2": "French is a language",
        "C": "French has grammar",
    },
    {
        "id": "beethoven",
        "domain": "music",
        "individual_type": "proper",
        "individual": "Beethoven's Fifth",
        "P1": "All symphonies are musical compositions",
        "P2": "Beethoven's Fifth is a symphony",
        "C": "Beethoven's Fifth is a musical composition",
    },
    {
        "id": "helium",
        "domain": "chemistry",
        "individual_type": "generic",
        "individual": "Helium",
        "P1": "All noble gases are inert",
        "P2": "Helium is a noble gas",
        "C": "Helium is inert",
    },
    {
        "id": "python",
        "domain": "computing",
        "individual_type": "generic",
        "individual": "Python",
        "P1": "All programming languages have syntax",
        "P2": "Python is a programming language",
        "C": "Python has syntax",
    },
]

DOMAINS = {
    "biology": ["robin", "whiskers", "rex", "nemo", "oak", "apple"],
    "geography": ["amazon", "everest"],
    "profession": ["johnson", "chen"],
    "chemistry": ["gold", "helium"],
}


# ── Helpers ──────────────────────────────────────────────────────────────────

def cosine(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-10))


def normalize(v: np.ndarray) -> np.ndarray:
    return v / (np.linalg.norm(v) + 1e-10)


# ══════════════════════════════════════════════════════════════════════════════
# 1. PAIRWISE SIMILARITIES
# ══════════════════════════════════════════════════════════════════════════════

def analyze_pairwise(vecs: dict[str, dict[str, np.ndarray]]) -> dict:
    """P1↔P2, P1↔C, P2↔C for each syllogism; count how many have P1↔P2 as weakest."""

    print("=" * 70)
    print("  1. PAIRWISE SIMILARITIES")
    print("=" * 70)
    print("  For each syllogism: which pair is most/least similar?\n")

    header = (f"  {'ID':<14s} {'P1↔P2':>7s} {'P1↔C':>7s} {'P2↔C':>7s}  "
              f"{'Weakest':>8s} {'Gap?':>5s}")
    print(header)
    print("  " + "-" * 60)

    results = []
    gap_count = 0

    for syl in SYLLOGISMS:
        sid = syl["id"]
        v = vecs[sid]
        p1p2 = cosine(v["P1"], v["P2"])
        p1c = cosine(v["P1"], v["C"])
        p2c = cosine(v["P2"], v["C"])

        sims = {"P1↔P2": p1p2, "P1↔C": p1c, "P2↔C": p2c}
        weakest = min(sims, key=sims.get)
        is_gap = weakest == "P1↔P2"
        if is_gap:
            gap_count += 1

        marker = "YES" if is_gap else "no"
        print(f"  {sid:<14s} {p1p2:>7.3f} {p1c:>7.3f} {p2c:>7.3f}  "
              f"{weakest:>8s} {marker:>5s}")

        results.append({
            "id": sid,
            "P1_P2": p1p2,
            "P1_C": p1c,
            "P2_C": p2c,
            "weakest_pair": weakest,
            "gap_confirmed": is_gap,
        })

    all_p1p2 = [r["P1_P2"] for r in results]
    all_p1c = [r["P1_C"] for r in results]
    all_p2c = [r["P2_C"] for r in results]

    print("  " + "-" * 60)
    print(f"  {'MEAN':<14s} {np.mean(all_p1p2):>7.3f} {np.mean(all_p1c):>7.3f} "
          f"{np.mean(all_p2c):>7.3f}")
    print(f"  {'STD':<14s} {np.std(all_p1p2):>7.3f} {np.std(all_p1c):>7.3f} "
          f"{np.std(all_p2c):>7.3f}")
    print(f"\n  Syllogism gap confirmed: {gap_count}/20 ({gap_count/20*100:.0f}%)")
    print(f"  Mean P1↔P2: {np.mean(all_p1p2):.4f}")
    print(f"  Mean P1↔C:  {np.mean(all_p1c):.4f}")
    print(f"  Mean P2↔C:  {np.mean(all_p2c):.4f}")

    return {
        "per_syllogism": results,
        "gap_count": gap_count,
        "gap_rate": gap_count / 20,
        "mean_P1_P2": float(np.mean(all_p1p2)),
        "mean_P1_C": float(np.mean(all_p1c)),
        "mean_P2_C": float(np.mean(all_p2c)),
        "std_P1_P2": float(np.std(all_p1p2)),
        "std_P1_C": float(np.std(all_p1c)),
        "std_P2_C": float(np.std(all_p2c)),
    }


# ══════════════════════════════════════════════════════════════════════════════
# 2. DISPLACEMENT VECTORS
# ══════════════════════════════════════════════════════════════════════════════

def analyze_displacements(vecs: dict[str, dict[str, np.ndarray]]) -> dict:
    """P1→C, P2→C, P1→P2 displacement magnitudes and directions."""

    print(f"\n{'=' * 70}")
    print("  2. DISPLACEMENT VECTORS")
    print("=" * 70)
    print("  Magnitudes of P1→C, P2→C, P1→P2 displacements.\n")

    header = (f"  {'ID':<14s} {'|P1→C|':>8s} {'|P2→C|':>8s} {'|P1→P2|':>8s}")
    print(header)
    print("  " + "-" * 42)

    results = []
    for syl in SYLLOGISMS:
        sid = syl["id"]
        v = vecs[sid]
        d_p1c = v["C"] - v["P1"]
        d_p2c = v["C"] - v["P2"]
        d_p1p2 = v["P2"] - v["P1"]

        m_p1c = float(np.linalg.norm(d_p1c))
        m_p2c = float(np.linalg.norm(d_p2c))
        m_p1p2 = float(np.linalg.norm(d_p1p2))

        print(f"  {sid:<14s} {m_p1c:>8.4f} {m_p2c:>8.4f} {m_p1p2:>8.4f}")

        results.append({
            "id": sid,
            "mag_P1_C": m_p1c,
            "mag_P2_C": m_p2c,
            "mag_P1_P2": m_p1p2,
        })

    mags_p1c = [r["mag_P1_C"] for r in results]
    mags_p2c = [r["mag_P2_C"] for r in results]
    mags_p1p2 = [r["mag_P1_P2"] for r in results]

    print("  " + "-" * 42)
    print(f"  {'MEAN':<14s} {np.mean(mags_p1c):>8.4f} {np.mean(mags_p2c):>8.4f} "
          f"{np.mean(mags_p1p2):>8.4f}")

    return {
        "per_syllogism": results,
        "mean_mag_P1_C": float(np.mean(mags_p1c)),
        "mean_mag_P2_C": float(np.mean(mags_p2c)),
        "mean_mag_P1_P2": float(np.mean(mags_p1p2)),
    }


# ══════════════════════════════════════════════════════════════════════════════
# 3. CROSS-SYLLOGISM DISPLACEMENT CONSISTENCY
# ══════════════════════════════════════════════════════════════════════════════

def analyze_cross_consistency(vecs: dict[str, dict[str, np.ndarray]]) -> dict:
    """Pairwise cosine of all 20 P2→C vectors (190 pairs). Tests for a
    latent 'apply universal' direction. Same for P1→C and P1→P2."""

    print(f"\n{'=' * 70}")
    print("  3. CROSS-SYLLOGISM DISPLACEMENT CONSISTENCY")
    print("=" * 70)
    print("  Do all syllogisms share a common displacement direction?")
    print("  (High consistency → latent 'apply universal' axis)\n")

    results = {}

    for disp_name, src, dst in [
        ("P2→C", "P2", "C"),
        ("P1→C", "P1", "C"),
        ("P1→P2", "P1", "P2"),
    ]:
        displacements = []
        for syl in SYLLOGISMS:
            v = vecs[syl["id"]]
            d = v[dst] - v[src]
            displacements.append(d)

        # Pairwise cosine of displacement vectors
        pair_cosines = []
        ids = [s["id"] for s in SYLLOGISMS]
        for i, j in combinations(range(20), 2):
            c = cosine(displacements[i], displacements[j])
            pair_cosines.append(c)

        mean_cos = float(np.mean(pair_cosines))
        std_cos = float(np.std(pair_cosines))
        min_cos = float(np.min(pair_cosines))
        max_cos = float(np.max(pair_cosines))

        # Mean displacement direction and alignment
        mean_disp = np.mean(displacements, axis=0)
        alignments = [cosine(d, mean_disp) for d in displacements]
        mean_align = float(np.mean(alignments))

        print(f"  {disp_name}:")
        print(f"    Pairwise cosine: mean={mean_cos:.4f} std={std_cos:.3f} "
              f"range=[{min_cos:.3f}, {max_cos:.3f}]")
        print(f"    Mean alignment to grand mean direction: {mean_align:.4f}")
        print()

        results[disp_name] = {
            "mean_pairwise_cosine": mean_cos,
            "std": std_cos,
            "min": min_cos,
            "max": max_cos,
            "mean_alignment": mean_align,
        }

    return results


# ══════════════════════════════════════════════════════════════════════════════
# 4. WITHIN-DOMAIN VS CROSS-DOMAIN
# ══════════════════════════════════════════════════════════════════════════════

def analyze_domain_consistency(vecs: dict[str, dict[str, np.ndarray]]) -> dict:
    """Group by domain, compare displacement consistency within vs across domains."""

    print(f"\n{'=' * 70}")
    print("  4. WITHIN-DOMAIN VS CROSS-DOMAIN CONSISTENCY")
    print("=" * 70)
    print("  Are displacements more consistent within the same domain?\n")

    # Compute P2→C displacements for all
    displacements = {}
    domain_map = {}
    for syl in SYLLOGISMS:
        sid = syl["id"]
        v = vecs[sid]
        displacements[sid] = v["C"] - v["P2"]
        domain_map[sid] = syl["domain"]

    # Within-domain pairs
    within_cosines = []
    cross_cosines = []
    ids = [s["id"] for s in SYLLOGISMS]

    for i, j in combinations(range(20), 2):
        c = cosine(displacements[ids[i]], displacements[ids[j]])
        if domain_map[ids[i]] == domain_map[ids[j]]:
            within_cosines.append(c)
        else:
            cross_cosines.append(c)

    within_mean = float(np.mean(within_cosines)) if within_cosines else 0
    cross_mean = float(np.mean(cross_cosines)) if cross_cosines else 0

    print(f"  Within-domain P2→C consistency: {within_mean:.4f} "
          f"(n={len(within_cosines)} pairs)")
    print(f"  Cross-domain P2→C consistency:  {cross_mean:.4f} "
          f"(n={len(cross_cosines)} pairs)")
    print(f"  Delta: {within_mean - cross_mean:+.4f}")

    # Per-domain breakdown
    print(f"\n  Per-domain (P2→C pairwise cosine):")
    domain_results = {}
    for domain, members in sorted(DOMAINS.items()):
        if len(members) < 2:
            continue
        domain_cos = []
        for i, j in combinations(members, 2):
            c = cosine(displacements[i], displacements[j])
            domain_cos.append(c)
        mean_d = float(np.mean(domain_cos))
        print(f"    {domain:<14s}: {mean_d:.4f} (n={len(domain_cos)}, "
              f"members: {', '.join(members)})")
        domain_results[domain] = mean_d

    return {
        "within_domain_mean": within_mean,
        "cross_domain_mean": cross_mean,
        "delta": within_mean - cross_mean,
        "n_within": len(within_cosines),
        "n_cross": len(cross_cosines),
        "per_domain": domain_results,
    }


# ══════════════════════════════════════════════════════════════════════════════
# 5. INDIVIDUAL NAME PROXIMITY
# ══════════════════════════════════════════════════════════════════════════════

def analyze_name_proximity(
    vecs: dict[str, dict[str, np.ndarray]],
    name_vecs: dict[str, np.ndarray],
) -> dict:
    """Cosine of bare individual name to each of P1, P2, C."""

    print(f"\n{'=' * 70}")
    print("  5. INDIVIDUAL NAME PROXIMITY")
    print("=" * 70)
    print("  How close is the bare name ('Socrates', 'Mars', etc.) to P1/P2/C?\n")

    header = (f"  {'ID':<14s} {'Individual':<20s} "
              f"{'Name↔P1':>8s} {'Name↔P2':>8s} {'Name↔C':>8s} {'Closest':>8s}")
    print(header)
    print("  " + "-" * 72)

    results = []
    for syl in SYLLOGISMS:
        sid = syl["id"]
        v = vecs[sid]
        nv = name_vecs[sid]

        n_p1 = cosine(nv, v["P1"])
        n_p2 = cosine(nv, v["P2"])
        n_c = cosine(nv, v["C"])

        sims = {"P1": n_p1, "P2": n_p2, "C": n_c}
        closest = max(sims, key=sims.get)

        print(f"  {sid:<14s} {syl['individual']:<20s} "
              f"{n_p1:>8.3f} {n_p2:>8.3f} {n_c:>8.3f} {closest:>8s}")

        results.append({
            "id": sid,
            "individual": syl["individual"],
            "name_P1": n_p1,
            "name_P2": n_p2,
            "name_C": n_c,
            "closest": closest,
        })

    # Count closest
    closest_counts = {"P1": 0, "P2": 0, "C": 0}
    for r in results:
        closest_counts[r["closest"]] += 1

    print("  " + "-" * 72)
    print(f"  Closest to P1: {closest_counts['P1']}/20  "
          f"P2: {closest_counts['P2']}/20  C: {closest_counts['C']}/20")
    print(f"  Mean Name↔P1: {np.mean([r['name_P1'] for r in results]):.4f}  "
          f"Name↔P2: {np.mean([r['name_P2'] for r in results]):.4f}  "
          f"Name↔C: {np.mean([r['name_C'] for r in results]):.4f}")

    return {
        "per_syllogism": results,
        "closest_counts": closest_counts,
        "mean_name_P1": float(np.mean([r["name_P1"] for r in results])),
        "mean_name_P2": float(np.mean([r["name_P2"] for r in results])),
        "mean_name_C": float(np.mean([r["name_C"] for r in results])),
    }


# ══════════════════════════════════════════════════════════════════════════════
# 6. PROPER NOUN VS GENERIC
# ══════════════════════════════════════════════════════════════════════════════

def analyze_proper_vs_generic(vecs: dict[str, dict[str, np.ndarray]]) -> dict:
    """Split by individual type, compare gap magnitudes."""

    print(f"\n{'=' * 70}")
    print("  6. PROPER NOUN VS GENERIC INDIVIDUAL")
    print("=" * 70)
    print("  Does the gap differ between proper nouns (Socrates, Rex)")
    print("  and generic terms (gold, chess)?\n")

    proper = [s for s in SYLLOGISMS if s["individual_type"] == "proper"]
    generic = [s for s in SYLLOGISMS if s["individual_type"] == "generic"]

    results = {}
    for label, group in [("Proper nouns", proper), ("Generic terms", generic)]:
        p1p2_sims = []
        p1c_sims = []
        p2c_sims = []
        gaps = []  # P2↔C minus P1↔P2 (positive = gap exists)

        for syl in group:
            v = vecs[syl["id"]]
            p1p2 = cosine(v["P1"], v["P2"])
            p1c = cosine(v["P1"], v["C"])
            p2c = cosine(v["P2"], v["C"])
            p1p2_sims.append(p1p2)
            p1c_sims.append(p1c)
            p2c_sims.append(p2c)
            gaps.append(p2c - p1p2)

        gap_count = sum(1 for g in gaps if g > 0)
        ids = [s["id"] for s in group]

        print(f"  {label} (n={len(group)}: {', '.join(ids)}):")
        print(f"    Mean P1↔P2: {np.mean(p1p2_sims):.4f}  "
              f"P1↔C: {np.mean(p1c_sims):.4f}  P2↔C: {np.mean(p2c_sims):.4f}")
        print(f"    Mean gap (P2↔C − P1↔P2): {np.mean(gaps):+.4f}")
        print(f"    Gap confirmed: {gap_count}/{len(group)}")
        print()

        results[label.lower().replace(" ", "_")] = {
            "n": len(group),
            "ids": ids,
            "mean_P1_P2": float(np.mean(p1p2_sims)),
            "mean_P1_C": float(np.mean(p1c_sims)),
            "mean_P2_C": float(np.mean(p2c_sims)),
            "mean_gap": float(np.mean(gaps)),
            "gap_count": gap_count,
        }

    return results


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    print("Syllogism Gap — 20-Syllogism Systematic Test")
    print("Embedding with mxbai-embed-large (1024-dim)...\n")

    # Collect all texts to embed
    sentences = []  # 60 sentences (20 × 3)
    sentence_keys = []  # (id, role) tuples for mapping back
    names = []  # 20 bare individual names
    name_keys = []

    for syl in SYLLOGISMS:
        for role in ["P1", "P2", "C"]:
            sentences.append(syl[role])
            sentence_keys.append((syl["id"], role))
        names.append(syl["individual"])
        name_keys.append(syl["id"])

    # Embed all 80 texts
    all_texts = sentences + names
    print(f"  Embedding {len(all_texts)} texts ({len(sentences)} sentences + "
          f"{len(names)} bare names)...")
    all_vecs = embed_texts(all_texts)
    print(f"  Done. Shape: {all_vecs.shape}\n")

    sentence_vecs = all_vecs[:len(sentences)]
    name_vecs_arr = all_vecs[len(sentences):]

    # Build lookup dicts
    vecs: dict[str, dict[str, np.ndarray]] = {}
    for i, (sid, role) in enumerate(sentence_keys):
        if sid not in vecs:
            vecs[sid] = {}
        vecs[sid][role] = sentence_vecs[i]

    name_vecs: dict[str, np.ndarray] = {}
    for i, sid in enumerate(name_keys):
        name_vecs[sid] = name_vecs_arr[i]

    # Run all 6 analyses
    results = {}
    results["pairwise"] = analyze_pairwise(vecs)
    results["displacements"] = analyze_displacements(vecs)
    results["cross_consistency"] = analyze_cross_consistency(vecs)
    results["domain_consistency"] = analyze_domain_consistency(vecs)
    results["name_proximity"] = analyze_name_proximity(vecs, name_vecs)
    results["proper_vs_generic"] = analyze_proper_vs_generic(vecs)

    # Save results
    json_path = os.path.join(_project_root, "prototype", "syllogism_gap_results.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"\n\nResults saved to: {json_path}")

    # Save embeddings
    npz_path = os.path.join(_project_root, "prototype", "syllogism_gap_embeddings.npz")
    np.savez(
        npz_path,
        sentence_vecs=sentence_vecs,
        sentence_texts=np.array(sentences, dtype=object),
        sentence_keys=np.array([f"{sid}|{role}" for sid, role in sentence_keys], dtype=object),
        name_vecs=name_vecs_arr,
        name_texts=np.array(names, dtype=object),
        name_keys=np.array(name_keys, dtype=object),
    )
    print(f"Embeddings saved to: {npz_path}")


if __name__ == "__main__":
    main()
