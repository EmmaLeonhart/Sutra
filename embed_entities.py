"""
Generate embeddings for mountain entities.
Embeds the label and all aliases for each entity.
Each entity gets one vector (mean of label + alias embeddings).
Saves to data/mountains_embeddings.npy + data/mountains_qids.json
"""

import json
import sys
import io
import numpy as np
from sentence_transformers import SentenceTransformer

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

MODEL_NAME = "all-MiniLM-L6-v2"


def main():
    with open("data/mountains.json", "r", encoding="utf-8") as f:
        mountains = json.load(f)

    print(f"Loaded {len(mountains)} mountains")
    print(f"Loading model {MODEL_NAME}...")
    model = SentenceTransformer(MODEL_NAME)

    # Build text list: for each entity, combine label + aliases into one string
    # This gives the model more context about what the entity is
    texts = []
    qids = []
    for m in mountains:
        parts = [m["label"]] + m.get("aliases", [])
        text = "; ".join(parts)
        texts.append(text)
        qids.append(m["qid"])

    print(f"Embedding {len(texts)} entities...")
    embeddings = model.encode(texts, show_progress_bar=True, batch_size=256)

    # Save
    np.save("data/mountains_embeddings.npy", embeddings)
    with open("data/mountains_qids.json", "w", encoding="utf-8") as f:
        json.dump(qids, f)

    print(f"Saved embeddings: {embeddings.shape} to data/mountains_embeddings.npy")
    print(f"Saved {len(qids)} QIDs to data/mountains_qids.json")

    # Quick sanity check: find nearest neighbors for a well-known mountain
    from numpy.linalg import norm
    # Find Mt. Everest or first mountain
    test_idx = 0
    for i, m in enumerate(mountains):
        if "everest" in m["label"].lower():
            test_idx = i
            break

    test_vec = embeddings[test_idx]
    sims = embeddings @ test_vec / (norm(embeddings, axis=1) * norm(test_vec))
    top_indices = np.argsort(sims)[-6:][::-1]  # top 5 + self

    print(f"\nNearest neighbors to '{mountains[test_idx]['label']}':")
    for idx in top_indices:
        if idx != test_idx:
            print(f"  {mountains[idx]['label']} (sim={sims[idx]:.4f})")


if __name__ == "__main__":
    main()
