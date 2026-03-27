"""
Generate embeddings for Wikidata items using mxbai-embed-large (via Ollama).
Each item gets embeddings for: its label, and each alias separately.
Stores a mapping of QID -> {label_embedding, alias_embeddings[]}.
Also builds an RDF graph of all triples stored by QID.

Saves:
  data/embeddings.npz - all embedding vectors
  data/embedding_index.json - maps vector index -> (qid, text, type)
  data/triples.nt - all triples as N-Triples (RDF)
"""

import json
import sys
import io
import numpy as np
import ollama
from rdflib import Graph, URIRef, Literal, Namespace
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

MODEL = "mxbai-embed-large"

WD = Namespace("http://www.wikidata.org/entity/")
WDT = Namespace("http://www.wikidata.org/prop/direct/")


def embed_texts(texts):
    """Embed a list of texts via Ollama."""
    result = ollama.embed(model=MODEL, input=texts)
    return [np.array(e) for e in result.embeddings]


def build_rdf_graph(items):
    """Build an RDF graph from all item triples, stored by QID."""
    g = Graph()
    g.bind("wd", WD)
    g.bind("wdt", WDT)

    for item in items:
        subj = WD[item["qid"]]

        for triple in item["triples"]:
            pred = WDT[triple["predicate"]]
            val = triple["value"]

            if val["type"] == "wikibase-item":
                obj = WD[val["value"]]
                g.add((subj, pred, obj))
            elif val["type"] == "string":
                g.add((subj, pred, Literal(val["value"])))
            elif val["type"] == "monolingualtext":
                g.add((subj, pred, Literal(val["value"], lang=val.get("language", ""))))
            elif val["type"] == "quantity":
                g.add((subj, pred, Literal(val["value"])))
            elif val["type"] == "time":
                g.add((subj, pred, Literal(val["value"])))
            elif val["type"] == "coordinate":
                coord_str = f"{val['latitude']},{val['longitude']}"
                g.add((subj, pred, Literal(coord_str)))

    return g


def main():
    with open(str(DATA_DIR / "items.json"), "r", encoding="utf-8") as f:
        items = json.load(f)

    print(f"Loaded {len(items)} items")

    # Collect all texts to embed: label + each alias
    texts = []
    index = []  # maps vector position -> metadata

    for item in items:
        # Label embedding
        texts.append(item["label"])
        index.append({"qid": item["qid"], "text": item["label"], "type": "label"})

        # Each alias gets its own embedding
        for alias in item["aliases"]:
            texts.append(alias)
            index.append({"qid": item["qid"], "text": alias, "type": "alias"})

    print(f"Embedding {len(texts)} texts (labels + aliases)...")
    embeddings = embed_texts(texts)
    embeddings = np.array(embeddings)
    print(f"  Shape: {embeddings.shape}")

    # Save embeddings
    np.savez_compressed(str(DATA_DIR / "embeddings.npz"), vectors=embeddings)
    with open(str(DATA_DIR / "embedding_index.json"), "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)

    print(f"Saved {len(embeddings)} embeddings to data/embeddings.npz")

    # Build and save RDF graph
    print("Building RDF graph...")
    g = build_rdf_graph(items)
    g.serialize(str(DATA_DIR / "triples.nt"), format="nt")
    print(f"Saved {len(g)} RDF triples to data/triples.nt")

    # Summary
    label_count = sum(1 for e in index if e["type"] == "label")
    alias_count = sum(1 for e in index if e["type"] == "alias")
    print(f"\nSummary:")
    print(f"  {label_count} labels, {alias_count} aliases = {len(embeddings)} vectors")
    print(f"  {len(g)} RDF triples")
    print(f"  Embedding dim: {embeddings.shape[1]}")


if __name__ == "__main__":
    main()
