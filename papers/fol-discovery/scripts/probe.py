"""
Probe the embedding space by constructing synthetic points and finding
what's nearby. The nearest neighbors to a synthetic point are the "exit"
from the embedding space - they tell you what a region means.

Usage:
  python probe.py random                         # random direction from origin
  python probe.py random --from Q513             # random direction from Mount Everest
  python probe.py between Q513 Q8502             # interpolate between two entities
  python probe.py displace Q513 Q8502 Q39231     # apply (Q8502-Q513) displacement to Q39231
  python probe.py direction Q513 Q8502 --steps 5 # walk from Q513 toward Q8502 in steps
  python probe.py neighbors Q513                 # just show nearest neighbors
"""

import json
import sys
import io
import argparse
import numpy as np
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

if hasattr(sys.stdout, 'buffer'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')


def load_data():
    emb = np.load(str(DATA_DIR / "embeddings.npz"))["vectors"]
    with open(str(DATA_DIR / "embedding_index.json"), "r", encoding="utf-8") as f:
        index = json.load(f)
    return emb, index


def find_nearest(point, emb, index, top_k=10, exclude_indices=None):
    """Find top_k nearest embedded texts to a synthetic point."""
    norms = np.linalg.norm(emb, axis=1)
    point_norm = np.linalg.norm(point)
    sims = emb @ point / (norms * point_norm + 1e-10)

    if exclude_indices:
        for idx in exclude_indices:
            sims[idx] = -2

    top = np.argsort(sims)[-top_k:][::-1]
    results = []
    for idx in top:
        results.append({
            "idx": int(idx),
            "qid": index[idx]["qid"],
            "text": index[idx]["text"],
            "type": index[idx]["type"],
            "similarity": float(sims[idx]),
        })
    return results


def get_entity_vec(qid, emb, index):
    """Get the label embedding for a QID. Falls back to first available."""
    for i, entry in enumerate(index):
        if entry["qid"] == qid and entry["type"] == "label":
            return emb[i], i
    for i, entry in enumerate(index):
        if entry["qid"] == qid:
            return emb[i], i
    return None, None


def get_entity_label(qid, index):
    for entry in index:
        if entry["qid"] == qid and entry["type"] == "label":
            return entry["text"]
    return qid


def print_results(results, header=""):
    if header:
        print(f"\n{header}")
        print("-" * 60)
    for r in results:
        print(f"  {r['similarity']:+.4f}  {r['text']:<40} ({r['qid']}, {r['type']})")


def cmd_random(args, emb, index):
    """Probe a random direction from a point."""
    if args.from_qid:
        origin, _ = get_entity_vec(args.from_qid, emb, index)
        if origin is None:
            print(f"QID {args.from_qid} not found")
            return
        origin_label = get_entity_label(args.from_qid, index)
    else:
        origin = np.zeros(emb.shape[1])
        origin_label = "origin"

    # Random unit vector
    direction = np.random.randn(emb.shape[1])
    direction /= np.linalg.norm(direction)

    # Walk in that direction
    alpha = args.alpha
    point = origin + alpha * direction

    print(f"Random probe from {origin_label}, alpha={alpha}")
    results = find_nearest(point, emb, index, top_k=args.top)
    print_results(results, f"Nearest to synthetic point (alpha={alpha})")

    # Also show what's in the opposite direction
    point_neg = origin - alpha * direction
    results_neg = find_nearest(point_neg, emb, index, top_k=args.top)
    print_results(results_neg, f"Nearest in opposite direction (alpha=-{alpha})")


def cmd_between(args, emb, index):
    """Interpolate between two entities."""
    vec_a, _ = get_entity_vec(args.qid_a, emb, index)
    vec_b, _ = get_entity_vec(args.qid_b, emb, index)
    if vec_a is None or vec_b is None:
        print("One or both QIDs not found")
        return

    label_a = get_entity_label(args.qid_a, index)
    label_b = get_entity_label(args.qid_b, index)

    cos_sim = float(np.dot(vec_a, vec_b) / (np.linalg.norm(vec_a) * np.linalg.norm(vec_b)))
    print(f"Interpolating: {label_a} <-> {label_b} (cosine sim: {cos_sim:.4f})")

    steps = args.steps
    for i in range(steps + 1):
        t = i / steps
        point = vec_a * (1 - t) + vec_b * t
        results = find_nearest(point, emb, index, top_k=3)
        top_text = results[0]["text"]
        top_sim = results[0]["similarity"]
        print(f"  t={t:.2f}: {top_text} ({top_sim:.4f})  |  {results[1]['text']} ({results[1]['similarity']:.4f})  |  {results[2]['text']} ({results[2]['similarity']:.4f})")


def cmd_displace(args, emb, index):
    """Apply displacement vector from A->B onto C."""
    vec_a, _ = get_entity_vec(args.qid_a, emb, index)
    vec_b, _ = get_entity_vec(args.qid_b, emb, index)
    vec_c, _ = get_entity_vec(args.qid_c, emb, index)
    if any(v is None for v in [vec_a, vec_b, vec_c]):
        print("One or more QIDs not found")
        return

    label_a = get_entity_label(args.qid_a, index)
    label_b = get_entity_label(args.qid_b, index)
    label_c = get_entity_label(args.qid_c, index)

    displacement = vec_b - vec_a
    point = vec_c + displacement

    print(f"Displacement: ({label_b} - {label_a}) + {label_c} = ?")
    print(f"  i.e. {label_c} + ({label_a} -> {label_b})")
    results = find_nearest(point, emb, index, top_k=args.top)
    print_results(results, "Nearest to displaced point")


def cmd_direction(args, emb, index):
    """Walk from A toward B in steps, overshooting past B."""
    vec_a, _ = get_entity_vec(args.qid_a, emb, index)
    vec_b, _ = get_entity_vec(args.qid_b, emb, index)
    if vec_a is None or vec_b is None:
        print("One or both QIDs not found")
        return

    label_a = get_entity_label(args.qid_a, index)
    label_b = get_entity_label(args.qid_b, index)
    direction = vec_b - vec_a

    print(f"Walking from {label_a} toward {label_b} (and beyond)")

    # Walk from -0.5 to 1.5 (overshooting both ends)
    steps = args.steps
    for i in range(steps + 1):
        t = -0.5 + (2.0 * i / steps)
        point = vec_a + t * direction
        results = find_nearest(point, emb, index, top_k=3)
        marker = " <-- A" if abs(t) < 0.01 else (" <-- B" if abs(t - 1.0) < 0.01 else "")
        top = results[0]
        print(f"  t={t:+.2f}: {top['text']:<35} ({top['similarity']:.4f}){marker}")


def cmd_neighbors(args, emb, index):
    """Show nearest neighbors of an entity."""
    vec, idx = get_entity_vec(args.qid, emb, index)
    if vec is None:
        print(f"QID {args.qid} not found")
        return

    label = get_entity_label(args.qid, index)
    results = find_nearest(vec, emb, index, top_k=args.top + 1, exclude_indices={idx})
    print_results(results[:args.top], f"Nearest neighbors of {label} ({args.qid})")


def main():
    parser = argparse.ArgumentParser(description="Probe the embedding space")
    parser.add_argument("--top", type=int, default=10, help="Number of results (default 10)")
    sub = parser.add_subparsers(dest="command")

    p_random = sub.add_parser("random", help="Random direction probe")
    p_random.add_argument("--from", dest="from_qid", help="Start from this QID (default: origin)")
    p_random.add_argument("--alpha", type=float, default=1.0, help="Step size (default 1.0)")

    p_between = sub.add_parser("between", help="Interpolate between two entities")
    p_between.add_argument("qid_a", help="First QID")
    p_between.add_argument("qid_b", help="Second QID")
    p_between.add_argument("--steps", type=int, default=10, help="Interpolation steps (default 10)")

    p_displace = sub.add_parser("displace", help="Apply displacement A->B onto C")
    p_displace.add_argument("qid_a", help="Displacement start")
    p_displace.add_argument("qid_b", help="Displacement end")
    p_displace.add_argument("qid_c", help="Apply displacement to this")

    p_direction = sub.add_parser("direction", help="Walk from A toward B and beyond")
    p_direction.add_argument("qid_a", help="Start QID")
    p_direction.add_argument("qid_b", help="Target QID")
    p_direction.add_argument("--steps", type=int, default=10, help="Number of steps (default 10)")

    p_neighbors = sub.add_parser("neighbors", help="Show nearest neighbors")
    p_neighbors.add_argument("qid", help="QID to find neighbors of")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    emb, index = load_data()

    if args.command == "random":
        cmd_random(args, emb, index)
    elif args.command == "between":
        cmd_between(args, emb, index)
    elif args.command == "displace":
        cmd_displace(args, emb, index)
    elif args.command == "direction":
        cmd_direction(args, emb, index)
    elif args.command == "neighbors":
        cmd_neighbors(args, emb, index)


if __name__ == "__main__":
    main()
