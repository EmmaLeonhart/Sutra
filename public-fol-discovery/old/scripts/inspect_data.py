"""
Inspect imported Wikidata data: items, embeddings, and triples.
Prints a readable summary of everything we have.
"""

import json
import sys
import io
import numpy as np
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')


def main():
    # Load items
    with open(str(DATA_DIR / "items.json"), "r", encoding="utf-8") as f:
        items = json.load(f)

    # Load embeddings
    emb = np.load(str(DATA_DIR / "embeddings.npz"))["vectors"]
    with open(str(DATA_DIR / "embedding_index.json"), "r", encoding="utf-8") as f:
        index = json.load(f)

    print("=" * 70)
    print("EMBEDDING MAP DATA SUMMARY")
    print("=" * 70)
    print(f"\nItems:      {len(items)}")
    print(f"Embeddings: {emb.shape[0]} vectors x {emb.shape[1]} dimensions")
    print(f"RDF triples: {sum(len(i['triples']) for i in items)}")

    print("\n" + "=" * 70)
    print("ITEMS")
    print("=" * 70)

    for item in items:
        print(f"\n--- {item['qid']}: {item['label']} ---")
        if item["aliases"]:
            print(f"  Aliases: {', '.join(item['aliases'])}")
        else:
            print(f"  Aliases: (none)")
        print(f"  Triples: {len(item['triples'])}")

        # Group triples by predicate
        by_pred = {}
        for t in item["triples"]:
            by_pred.setdefault(t["predicate"], []).append(t)

        print(f"  Properties ({len(by_pred)} distinct):")
        for pred, triples in sorted(by_pred.items()):
            values = []
            for t in triples[:3]:  # show up to 3 values per property
                v = t["value"]
                if v["type"] == "wikibase-item":
                    values.append(v["value"])
                elif v["type"] in ("string", "monolingualtext", "time"):
                    val_str = str(v["value"])
                    if len(val_str) > 40:
                        val_str = val_str[:40] + "..."
                    values.append(val_str)
                elif v["type"] == "quantity":
                    values.append(v["value"])
                elif v["type"] == "coordinate":
                    values.append(f"{v['latitude']:.4f}, {v['longitude']:.4f}")
                else:
                    values.append(f"({v['type']})")
            suffix = f" (+{len(triples)-3} more)" if len(triples) > 3 else ""
            print(f"    {pred}: {' | '.join(values)}{suffix}")

    print("\n" + "=" * 70)
    print("EMBEDDINGS")
    print("=" * 70)

    for i, entry in enumerate(index):
        vec = emb[i]
        print(f"  [{i:3d}] {entry['qid']} ({entry['type']}): \"{entry['text']}\"  norm={np.linalg.norm(vec):.4f}")

    # Basic similarity check
    print("\n" + "=" * 70)
    print("COSINE SIMILARITIES (labels only)")
    print("=" * 70)

    label_indices = [i for i, e in enumerate(index) if e["type"] == "label"]
    label_vecs = emb[label_indices]
    label_names = [index[i]["text"] for i in label_indices]

    # Normalize
    norms = np.linalg.norm(label_vecs, axis=1, keepdims=True)
    normed = label_vecs / norms

    sims = normed @ normed.T

    # Print matrix
    max_name = max(len(n) for n in label_names)
    header = " " * (max_name + 2) + "  ".join(f"{n[:6]:>6}" for n in label_names)
    print(header)
    for i, name in enumerate(label_names):
        row = f"{name:>{max_name}}  " + "  ".join(f"{sims[i,j]:6.3f}" for j in range(len(label_names)))
        print(row)

    input("\nPress Enter to exit...")


if __name__ == "__main__":
    main()
