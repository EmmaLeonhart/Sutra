"""
Random walk through Wikidata, building the geodesic map.

Starts at a seed entity and follows random triples to discover new entities.
At each step: import the entity, compute geodesics, track density and collisions.

Usage:
  python random_walk.py                          # start from Q133284072 (embedding)
  python random_walk.py Q8502                    # start from mountain
  python random_walk.py Q8502 --steps 50         # 50 steps
  python random_walk.py --resume                 # continue from last position
"""

import json
import sys
import io
import os
import time
import random
import argparse
import numpy as np
import requests
import ollama
from import_wikidata import (
    load_existing, save_all, fetch_entity, fetch_labels_batch,
    process_entity, extract_value, embed_texts, value_to_rdf,
    build_triples_graph, compute_geodesics_for_items,
    WD, WDT, EMB, EMBED_MODEL
)

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

WIKIDATA_API = "https://www.wikidata.org/w/api.php"
USER_AGENT = "embedding-mapping/0.1 (https://github.com/Immanuelle/embedding-mapping)"
DEFAULT_SEED = "Q133284072"  # embedding
WALK_STATE_FILE = "data/walk_state.json"


def pick_next_entity(item, existing_qids):
    """Pick a random linked QID from an item's triples to walk to next."""
    candidates = []
    for t in item["triples"]:
        if t["value"]["type"] == "wikibase-item":
            qid = t["value"]["value"]
            # Prefer items we haven't fully imported yet
            if qid.startswith("Q"):
                candidates.append(qid)

    if not candidates:
        return None

    # Shuffle and prefer unvisited
    random.shuffle(candidates)
    unvisited = [q for q in candidates if q not in existing_qids]
    if unvisited:
        return unvisited[0]
    return candidates[0]


def import_single(qid, items, index, emb):
    """Import a single QID with all linked entities. Returns updated data."""
    existing_qids = {i["qid"] for i in items}

    if qid in existing_qids:
        # Check if it's linked-only (no triples)
        for item in items:
            if item["qid"] == qid and item["triples"]:
                return items, index, emb, item  # already fully imported

    # Fetch full entity
    entity = fetch_entity(qid)
    if not entity or "missing" in entity:
        return items, index, emb, None

    item = process_entity(entity)

    # Remove any linked-only stub for this QID
    items = [i for i in items if i["qid"] != qid]
    items.append(item)
    existing_qids = {i["qid"] for i in items}

    # Resolve linked QIDs and properties
    linked = set()
    properties = set()
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

    return items, index, emb, item


def save_walk_state(state):
    with open(WALK_STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def load_walk_state():
    if os.path.exists(WALK_STATE_FILE):
        with open(WALK_STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def main():
    parser = argparse.ArgumentParser(description="Random walk through Wikidata")
    parser.add_argument("seed", nargs="?", default=DEFAULT_SEED, help=f"Seed QID (default: {DEFAULT_SEED})")
    parser.add_argument("--steps", type=int, default=20, help="Number of steps (default 20)")
    parser.add_argument("--resume", action="store_true", help="Resume from last walk position")
    args = parser.parse_args()

    items, index, emb = load_existing()
    existing_qids = {i["qid"] for i in items}

    # Determine starting point
    if args.resume:
        state = load_walk_state()
        if state:
            current_qid = state["current_qid"]
            walk_history = state["history"]
            print(f"Resuming walk from {current_qid} (step {len(walk_history)})")
        else:
            print("No walk state found, starting fresh")
            current_qid = args.seed
            walk_history = []
    else:
        current_qid = args.seed
        walk_history = []

    print(f"Starting random walk from {current_qid}")
    print(f"Steps: {args.steps}")
    print(f"Current data: {len(items)} items, {emb.shape[0] if emb.size else 0} embeddings\n")

    for step in range(args.steps):
        print(f"--- Step {step + 1}/{args.steps}: {current_qid} ---")

        # Import this entity
        items, index, emb, item = import_single(current_qid, items, index, emb)

        if item is None:
            print(f"  Could not fetch {current_qid}, picking random known item")
            full_items = [i for i in items if i["triples"]]
            if full_items:
                item = random.choice(full_items)
                current_qid = item["qid"]
            else:
                print("  No items to walk to, stopping")
                break

        print(f"  {item['label']} — {len(item['triples'])} triples")
        walk_history.append({"qid": current_qid, "label": item["label"]})

        # Pick next entity
        next_qid = pick_next_entity(item, {i["qid"] for i in items if i["triples"]})
        if next_qid:
            print(f"  Walking to: {next_qid}")
            current_qid = next_qid
        else:
            print(f"  Dead end, jumping to random known item")
            full_items = [i for i in items if i["triples"]]
            if full_items:
                item = random.choice(full_items)
                current_qid = item["qid"]

        # Save progress every 5 steps
        if (step + 1) % 5 == 0:
            print(f"\n  Saving progress... ({len(items)} items, {emb.shape[0]} embeddings)")
            save_all(items, index, emb)
            save_walk_state({"current_qid": current_qid, "history": walk_history})

        time.sleep(1)

    # Final save
    print(f"\n--- Walk complete ---")
    save_all(items, index, emb)
    save_walk_state({"current_qid": current_qid, "history": walk_history})

    # Rebuild triples and geodesics
    print("Rebuilding triples and geodesics...")
    triples_g = build_triples_graph(items)
    triples_g.serialize("data/triples.nt", format="nt")

    geo_g, geo_count = compute_geodesics_for_items(items, index, emb)
    geo_g.serialize("data/geodesics.ttl", format="turtle")

    print(f"\nFinal state:")
    print(f"  Items: {len(items)}")
    print(f"  Embeddings: {emb.shape[0]} x {emb.shape[1]}")
    print(f"  Geodesics: {geo_count}")
    print(f"  Walk history: {len(walk_history)} steps")

    print(f"\nWalk path:")
    for i, h in enumerate(walk_history):
        print(f"  {i+1}. {h['label']} ({h['qid']})")


if __name__ == "__main__":
    main()
