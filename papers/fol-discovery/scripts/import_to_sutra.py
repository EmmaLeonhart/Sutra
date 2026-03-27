"""
Import Wikidata items into SutraDB.

This is a refactored version of import_wikidata.py that saves directly
to a running SutraDB instance instead of flat files.

Usage:
  # First start SutraDB: sutra serve --port 3030
  # Then run:
  python import_to_sutra.py Q8502              # import one item
  python import_to_sutra.py Q8502 Q513 Q524    # import multiple items
  python import_to_sutra.py --instances Q8502 --limit 10
  python import_to_sutra.py --load-existing    # load existing flat file data into SutraDB
"""

import json
import sys
import io
import os
import time
import argparse
import numpy as np

if hasattr(sys.stdout, 'buffer'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from import_wikidata import (
    load_existing, save_all, fetch_entity, fetch_labels_batch,
    process_entity, embed_texts, get_instances,
    build_triples_graph, compute_trajectories_for_items,
    WD, WDT, EMB
)
from sutra_client import SutraClient, save_to_sutra, save_trajectories_to_sutra

SUTRA_ENDPOINT = "http://localhost:3030"
EMBEDDING_PREDICATE = "http://embedding-mapping.local/ontology/hasEmbedding"
EMBEDDING_DIMENSIONS = 1024


def ensure_sutra_ready(client):
    """Check SutraDB is running and declare the embedding predicate."""
    if not client.health():
        print("ERROR: SutraDB is not running at", client.endpoint)
        print("Start it with: sutra serve --port 3030")
        sys.exit(1)
    print(f"SutraDB connected at {client.endpoint}")

    # Declare the embedding predicate (idempotent — errors if already declared)
    try:
        client.declare_vector_predicate(
            EMBEDDING_PREDICATE,
            dimensions=EMBEDDING_DIMENSIONS,
            m=16,
            ef_construction=200,
            metric="cosine",
        )
        print(f"Declared vector predicate: {EMBEDDING_PREDICATE} ({EMBEDDING_DIMENSIONS}-dim)")
    except Exception as e:
        if "already declared" in str(e).lower():
            print(f"Vector predicate already declared: {EMBEDDING_PREDICATE}")
        else:
            print(f"Warning: could not declare vector predicate: {e}")


def load_existing_into_sutra(client):
    """Load existing flat file data (items.json, embeddings.npz, etc.) into SutraDB."""
    items, index, emb = load_existing()
    if not items:
        print("No existing data found in data/ directory.")
        return

    print(f"\n--- Loading existing data into SutraDB ---")
    print(f"Items: {len(items)}")
    print(f"Embeddings: {emb.shape[0]} x {emb.shape[1] if emb.size else 0}")

    # Insert triples
    triple_count = save_to_sutra(client, items, index, emb, EMBEDDING_PREDICATE)

    # Insert trajectories
    traj_count = save_trajectories_to_sutra(client, items, index, emb)

    print(f"\n--- Load complete ---")
    print(f"Triples loaded: {triple_count}")
    print(f"Trajectories loaded: {traj_count}")
    print(f"Vectors loaded: {emb.shape[0] if emb.size else 0}")


def import_to_sutra(qids_to_import, client):
    """Import specific QIDs into SutraDB."""
    # Load existing data (still keep flat files as cache)
    items, index, emb = load_existing()
    existing_qids = {i["qid"] for i in items}

    # Step 1: Fetch full entities for new QIDs
    new_qids = [q for q in qids_to_import if q not in existing_qids]
    print(f"\n--- Step 1: Fetch full items ---")
    print(f"Requested: {len(qids_to_import)}, already imported: {len(qids_to_import) - len(new_qids)}, new: {len(new_qids)}")

    new_items = []
    for qid in new_qids:
        print(f"  Fetching {qid}...")
        entity = fetch_entity(qid)
        if entity and "missing" not in entity:
            item = process_entity(entity)
            new_items.append(item)
            print(f"    {item['label']}: {len(item['triples'])} triples, {len(item['aliases'])} aliases")
        else:
            print(f"    {qid}: missing/deleted, skipping")
        time.sleep(0.5)

    items.extend(new_items)
    existing_qids = {i["qid"] for i in items}

    # Step 2: Find and fetch linked QIDs + property IDs
    print(f"\n--- Step 2: Fetch linked QIDs and properties ---")
    linked = set()
    properties = set()
    for item in items:
        for t in item["triples"]:
            if t["value"]["type"] == "wikibase-item":
                linked.add(t["value"]["value"])
            properties.add(t["predicate"])
            for qual in t.get("qualifiers", []):
                if qual["value"]["type"] == "wikibase-item":
                    linked.add(qual["value"]["value"])
                properties.add(qual["predicate"])
            for src in t.get("sources", []):
                if src["value"]["type"] == "wikibase-item":
                    linked.add(src["value"]["value"])
                properties.add(src["predicate"])

    all_needed = linked | properties
    unresolved = sorted(all_needed - existing_qids)
    print(f"Linked QIDs + properties needing labels: {len(unresolved)}")

    for i in range(0, len(unresolved), 50):
        batch = unresolved[i:i + 50]
        print(f"  Fetching batch {i // 50 + 1} ({len(batch)} items)...")
        entities = fetch_labels_batch(batch)
        for qid in batch:
            entity = entities.get(qid, {})
            if "missing" in entity:
                continue
            labels = entity.get("labels", {})
            label = labels.get("en", {}).get("value", qid)
            alias_list = entity.get("aliases", {}).get("en", [])
            aliases = [a["value"] for a in alias_list]
            items.append({"qid": qid, "label": label, "aliases": aliases, "triples": []})
        time.sleep(1)

    # Step 3: Embed new texts
    print(f"\n--- Step 3: Generate embeddings ---")
    embedded_texts = {(e["qid"], e["text"]) for e in index}
    new_texts = []
    new_index_entries = []

    for item in items:
        key = (item["qid"], item["label"])
        if key not in embedded_texts:
            new_texts.append(item["label"])
            new_index_entries.append({"qid": item["qid"], "text": item["label"], "type": "label"})
            embedded_texts.add(key)
        for alias in item["aliases"]:
            key = (item["qid"], alias)
            if key not in embedded_texts:
                new_texts.append(alias)
                new_index_entries.append({"qid": item["qid"], "text": alias, "type": "alias"})
                embedded_texts.add(key)

    if new_texts:
        print(f"Embedding {len(new_texts)} new texts...")
        new_emb = embed_texts(new_texts)
        emb = np.vstack([emb, new_emb]) if emb.size > 0 else new_emb
        index.extend(new_index_entries)
        print(f"  Total embeddings: {emb.shape[0]}")
    else:
        print("No new texts to embed")

    # Step 4: Save to flat files (as cache) and to SutraDB
    print(f"\n--- Step 4: Save to flat files (cache) ---")
    save_all(items, index, emb)

    print(f"\n--- Step 5: Save to SutraDB ---")
    triple_count = save_to_sutra(client, items, index, emb, EMBEDDING_PREDICATE)

    print(f"\n--- Step 6: Compute and save trajectories ---")
    traj_count = save_trajectories_to_sutra(client, items, index, emb)

    print(f"\n--- Done ---")
    print(f"Items: {len(items)}")
    print(f"Embeddings: {emb.shape[0]} x {emb.shape[1]}")
    print(f"Triples in SutraDB: {triple_count}")
    print(f"Trajectories in SutraDB: {traj_count}")


def main():
    parser = argparse.ArgumentParser(description="Import Wikidata items into SutraDB")
    parser.add_argument("qids", nargs="*", help="QIDs to import (e.g. Q8502 Q513)")
    parser.add_argument("--instances", help="Import instances of this class QID")
    parser.add_argument("--limit", type=int, default=10, help="Max instances to fetch (default 10)")
    parser.add_argument("--load-existing", action="store_true",
                        help="Load existing flat file data into SutraDB")
    parser.add_argument("--endpoint", default=SUTRA_ENDPOINT,
                        help=f"SutraDB endpoint (default: {SUTRA_ENDPOINT})")
    args = parser.parse_args()

    client = SutraClient(args.endpoint)
    ensure_sutra_ready(client)

    if args.load_existing:
        load_existing_into_sutra(client)
        return

    # Determine QIDs to import
    qids_to_import = list(args.qids)
    if args.instances:
        print(f"Finding up to {args.limit} instances of {args.instances}...")
        instance_qids = get_instances(args.instances, args.limit)
        print(f"  Found: {instance_qids}")
        qids_to_import.extend(instance_qids)
        if args.instances not in qids_to_import:
            qids_to_import.insert(0, args.instances)

    if not qids_to_import:
        print("No QIDs specified. Usage:")
        print("  python import_to_sutra.py Q8502 Q513")
        print("  python import_to_sutra.py --instances Q8502 --limit 10")
        print("  python import_to_sutra.py --load-existing")
        return

    import_to_sutra(qids_to_import, client)


if __name__ == "__main__":
    main()
