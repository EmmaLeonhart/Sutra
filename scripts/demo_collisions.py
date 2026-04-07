"""
Demonstrates the mxbai-embed-large diacritic stripping glitch.

WordPiece tokenization strips diacritical marks, causing semantically
unrelated terms to produce near-identical embeddings. This script
embeds test pairs and writes a CSV showing the collisions.

Requires: Ollama running locally with mxbai-embed-large pulled.
Usage: python demo_collisions.py
"""

import csv
import io
import json
import sys
import urllib.request
import math

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

OLLAMA_URL = "http://localhost:11434/api/embed"
MODEL = "mxbai-embed-large"
OUTPUT = "collisions.csv"


def embed(texts):
    """Get embeddings from Ollama."""
    payload = json.dumps({"model": MODEL, "input": texts}).encode()
    req = urllib.request.Request(OLLAMA_URL, data=payload,
                                headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())["embeddings"]


def cosine_sim(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    return dot / (na * nb) if na and nb else 0.0


# Test pairs grouped by category
TEST_PAIRS = [
    # Category 1: Cross-language collisions — completely unrelated terms that
    # collapse to cosine ~1.0 because all contain diacritical marks
    ("cross_collision", "Jinmyōchō", "kugyō"),
    ("cross_collision", "Hokkaidō", "Shōtai"),
    ("cross_collision", "Djazaïr", "Éire"),
    ("cross_collision", "Hokkaidō", "Jinmyōchō"),
    ("cross_collision", "Shōtoku", "Jinmyōchō"),
    ("cross_collision", "Hokkaidō", "Éire"),
    ("cross_collision", "kugyō", "Djazaïr"),
    ("cross_collision", "Shōtoku", "România"),
    ("cross_collision", "Filasṭīn", "Jinmyōchō"),
    ("cross_collision", "Filasṭīn", "Éire"),
    ("cross_collision", "Aikanã", "kugyō"),
    ("cross_collision", "naïve", "Zürich"),

    # Category 2: Diacritic vs plain — the diacritic version lives in a
    # completely different region from its own ASCII equivalent
    ("diacritic_vs_plain", "Hokkaidō", "Hokkaido"),
    ("diacritic_vs_plain", "Tōkyō", "Tokyo"),
    ("diacritic_vs_plain", "Jinmyōchō", "Jinmyocho"),
    ("diacritic_vs_plain", "Shōtoku", "Shotoku"),
    ("diacritic_vs_plain", "kugyō", "kugyo"),
    ("diacritic_vs_plain", "România", "Romania"),
    ("diacritic_vs_plain", "Éire", "Eire"),

    # Category 3: Control — plain ASCII terms (should be low similarity)
    ("control", "Tokyo", "Berlin"),
    ("control", "cat", "democracy"),
    ("control", "Hokkaido", "quantum physics"),
    ("control", "shrine", "economics"),
    ("control", "emperor", "bicycle"),
]


def main():
    # Collect all unique texts
    all_texts = list({t for _, a, b in TEST_PAIRS for t in (a, b)})
    print(f"Embedding {len(all_texts)} texts with {MODEL}...")

    try:
        vectors = embed(all_texts)
    except Exception as e:
        print(f"Error: {e}")
        print("Make sure Ollama is running and mxbai-embed-large is pulled:")
        print("  ollama pull mxbai-embed-large")
        sys.exit(1)

    text_to_vec = dict(zip(all_texts, vectors))

    # Compute similarities and write CSV
    rows = []
    for category, text_a, text_b in TEST_PAIRS:
        sim = cosine_sim(text_to_vec[text_a], text_to_vec[text_b])
        rows.append((category, text_a, text_b, sim))

    rows.sort(key=lambda r: -r[3])

    with open(OUTPUT, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["category", "text_a", "text_b", "cosine_similarity", "collision"])
        for category, text_a, text_b, sim in rows:
            collision = "YES" if sim >= 0.95 else "no"
            w.writerow([category, text_a, text_b, f"{sim:.6f}", collision])

    print(f"\nResults written to {OUTPUT}\n")
    print(f"{'Category':<20} {'Text A':<16} {'Text B':<18} {'Cosine':>8}  Collision?")
    print("-" * 85)
    for category, text_a, text_b, sim in rows:
        flag = " *** COLLISION" if sim >= 0.95 else ""
        print(f"{category:<20} {text_a:<16} {text_b:<18} {sim:>8.4f}{flag}")

    collisions = sum(1 for _, _, _, s in rows if s >= 0.95)
    print(f"\n{collisions}/{len(rows)} pairs are collisions (cosine >= 0.95)")


if __name__ == "__main__":
    main()
