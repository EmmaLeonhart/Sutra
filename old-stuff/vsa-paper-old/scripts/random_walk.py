"""
Breadth-first search through Wikidata, building the trajectory map.

Starts at a seed entity and adds every linked QID to a queue.
Processes the queue breadth-first, maximizing density around the seed.

Usage:
  python random_walk.py                          # start from Q1342448 (Engishiki)
  python random_walk.py Q8502                    # start from mountain
  python random_walk.py Q8502 --limit 1000       # import up to 1000 QIDs
  python random_walk.py --resume                 # continue from saved queue
"""

import json
import sys
import io
import os
import time
import collections
import argparse
import numpy as np
import requests
import ollama
from pathlib import Path

DATA_DIR = Path(os.environ.get("FOL_DATA_DIR", str(Path(__file__).resolve().parent.parent / "data")))

from import_wikidata import (
    load_existing, save_all, fetch_entity, fetch_labels_batch,
    process_entity, embed_texts,
    build_triples_graph, compute_trajectories_for_items,
    WD, WDT, EMB, EMBED_MODEL
)

if hasattr(sys.stdout, 'buffer'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

DEFAULT_SEED = "Q1342448"  # Engishiki - dense ontological neighborhood
WALK_STATE_FILE = str(DATA_DIR / "walk_state.json")


def import_single(qid, items, index, emb):
    """Import a single QID with all linked entities. Returns updated data + linked QIDs found."""
    existing_qids = {i["qid"] for i in items}

    # Check if already fully imported
    if qid in existing_qids:
        for item in items:
            if item["qid"] == qid and item["triples"]:
                return items, index, emb, item, set()

    # Fetch full entity
    entity = fetch_entity(qid)
    if not entity or "missing" in entity:
        return items, index, emb, None, set()

    item = process_entity(entity)

    # Remove any linked-only stub for this QID
    items = [i for i in items if i["qid"] != qid]
    items.append(item)
    existing_qids = {i["qid"] for i in items}

    # Collect all linked QIDs and properties
    linked = set()
    properties = set()
    discovered_qids = set()

    for t in item["triples"]:
        if t["value"]["type"] == "wikibase-item":
            v = t["value"]["value"]
            linked.add(v)
            if v.startswith("Q"):
                discovered_qids.add(v)
        properties.add(t["predicate"])
        for qual in t.get("qualifiers", []):
            if qual["value"]["type"] == "wikibase-item":
                v = qual["value"]["value"]
                linked.add(v)
                if v.startswith("Q"):
                    discovered_qids.add(v)
            properties.add(qual["predicate"])
        for src in t.get("sources", []):
            if src["value"]["type"] == "wikibase-item":
                v = src["value"]["value"]
                linked.add(v)
                if v.startswith("Q"):
                    discovered_qids.add(v)
            properties.add(src["predicate"])

    # Resolve linked entities that need labels
    all_needed = linked | properties
    unresolved = sorted(all_needed - existing_qids)

    for i in range(0, len(unresolved), 50):
        batch = unresolved[i:i + 50]
        entities = fetch_labels_batch(batch)
        for uid in batch:
            ent = entities.get(uid, {})
            if "missing" in ent:
                continue
            labels = ent.get("labels", {})
            label = labels.get("en", {}).get("value", uid)
            alias_list = ent.get("aliases", {}).get("en", [])
            aliases = [a["value"] for a in alias_list]
            items.append({"qid": uid, "label": label, "aliases": aliases, "triples": []})
        time.sleep(0.5)

    # Embed new texts
    embedded_texts = {(e["qid"], e["text"]) for e in index}
    new_texts = []
    new_index_entries = []

    for it in items:
        key = (it["qid"], it["label"])
        if key not in embedded_texts:
            new_texts.append(it["label"])
            new_index_entries.append({"qid": it["qid"], "text": it["label"], "type": "label"})
            embedded_texts.add(key)
        for alias in it["aliases"]:
            key = (it["qid"], alias)
            if key not in embedded_texts:
                new_texts.append(alias)
                new_index_entries.append({"qid": it["qid"], "text": alias, "type": "alias"})
                embedded_texts.add(key)

    if new_texts:
        new_emb = embed_texts(new_texts)
        emb = np.vstack([emb, new_emb]) if emb.size > 0 else new_emb
        index.extend(new_index_entries)

    return items, index, emb, item, discovered_qids


def save_walk_state(state):
    with open(WALK_STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def load_walk_state():
    if os.path.exists(WALK_STATE_FILE):
        with open(WALK_STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def main():
    parser = argparse.ArgumentParser(description="BFS through Wikidata for maximum trajectory density")
    parser.add_argument("seed", nargs="?", default=DEFAULT_SEED, help=f"Seed QID (default: {DEFAULT_SEED} Engishiki)")
    parser.add_argument("--limit", type=int, default=1000, help="Max QIDs to fully import (default 1000)")
    parser.add_argument("--resume", action="store_true", help="Resume from saved queue state")
    args = parser.parse_args()

    items, index, emb = load_existing()
    fully_imported = {i["qid"] for i in items if i["triples"]}

    # Set up BFS queue
    if args.resume:
        state = load_walk_state()
        if state and "queue" in state:
            queue = collections.deque(state["queue"])
            visited = set(state.get("visited", []))
            imported_count = state.get("imported_count", 0)
            print(f"Resuming BFS: {len(queue)} in queue, {len(visited)} visited, {imported_count} imported")
        else:
            print("No BFS state found, starting fresh")
            queue = collections.deque([args.seed])
            visited = set()
            imported_count = 0
    else:
        queue = collections.deque([args.seed])
        visited = set()
        imported_count = 0

    print(f"BFS from {args.seed} - importing up to {args.limit} QIDs")
    print(f"Current data: {len(items)} items, {emb.shape[0] if emb.size else 0} embeddings\n")

    while queue and imported_count < args.limit:
        current_qid = queue.popleft()

        # Skip if already visited
        if current_qid in visited:
            continue
        visited.add(current_qid)

        # Skip if already fully imported
        if current_qid in fully_imported:
            # Still need to add its linked QIDs to the queue
            for item in items:
                if item["qid"] == current_qid and item["triples"]:
                    for t in item["triples"]:
                        if t["value"]["type"] == "wikibase-item":
                            v = t["value"]["value"]
                            if v.startswith("Q") and v not in visited:
                                queue.append(v)
            continue

        imported_count += 1
        print(f"[{imported_count}/{args.limit}] Importing {current_qid} (queue: {len(queue)})...")

        items, index, emb, item, discovered = import_single(current_qid, items, index, emb)

        if item is None:
            print(f"  Could not fetch, skipping")
            continue

        print(f"  {item['label']} - {len(item['triples'])} triples, discovered {len(discovered)} linked QIDs")
        fully_imported.add(current_qid)

        # Add discovered QIDs to queue
        for qid in discovered:
            if qid not in visited:
                queue.append(qid)

        # Save progress every 10 imports
        if imported_count % 10 == 0:
            print(f"\n  Saving progress... ({len(items)} items, {emb.shape[0]} embeddings, queue: {len(queue)})")
            save_all(items, index, emb)
            save_walk_state({
                "queue": list(queue),
                "visited": list(visited),
                "imported_count": imported_count,
                "seed": args.seed,
            })
            print()

        time.sleep(0.5)

    # Final save
    print(f"\n--- BFS complete ---")
    save_all(items, index, emb)
    save_walk_state({
        "queue": list(queue),
        "visited": list(visited),
        "imported_count": imported_count,
        "seed": args.seed,
    })

    # Rebuild triples and trajectories
    print("Rebuilding triples and trajectories...")
    triples_g = build_triples_graph(items)
    triples_g.serialize(str(DATA_DIR / "triples.nt"), format="nt")

    traj_g, traj_count = compute_trajectories_for_items(items, index, emb)
    traj_g.serialize(str(DATA_DIR / "trajectories.ttl"), format="turtle")

    print(f"\nFinal state:")
    print(f"  Items: {len(items)}")
    print(f"  Fully imported: {len(fully_imported)}")
    print(f"  Embeddings: {emb.shape[0]} x {emb.shape[1]}")
    print(f"  Trajectories: {traj_count}")
    print(f"  Remaining in queue: {len(queue)}")


if __name__ == "__main__":
    main()
