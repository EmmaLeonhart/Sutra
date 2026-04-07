"""
Fetch English labels and aliases for all QIDs referenced in triples
but not yet imported. These are the "other ends" of trajectories.
Only fetches labels+aliases, not full properties.
Appends to data/items.json (with triples=[] for linked-only items).
"""

import json
import sys
import io
import time
import requests
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

WIKIDATA_API = "https://www.wikidata.org/w/api.php"
USER_AGENT = "embedding-mapping/0.1 (https://github.com/Immanuelle/embedding-mapping)"
BATCH_SIZE = 50  # wbgetentities supports up to 50 IDs per request


def fetch_entities_batch(qids):
    """Fetch labels and aliases for a batch of QIDs."""
    resp = requests.get(
        WIKIDATA_API,
        params={
            "action": "wbgetentities",
            "ids": "|".join(qids),
            "props": "labels|aliases",
            "languages": "en",
            "format": "json",
        },
        headers={"User-Agent": USER_AGENT},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json().get("entities", {})


def main():
    with open(str(DATA_DIR / "items.json"), "r", encoding="utf-8") as f:
        items = json.load(f)

    imported = {i["qid"] for i in items}

    # Find all linked QIDs
    linked = set()
    for item in items:
        for t in item["triples"]:
            if t["value"]["type"] == "wikibase-item":
                linked.add(t["value"]["value"])

    unresolved = sorted(linked - imported)
    print(f"Need to fetch {len(unresolved)} linked QIDs")

    # Fetch in batches
    new_items = []
    for i in range(0, len(unresolved), BATCH_SIZE):
        batch = unresolved[i:i + BATCH_SIZE]
        print(f"  Fetching batch {i // BATCH_SIZE + 1} ({len(batch)} items)...")

        entities = fetch_entities_batch(batch)

        for qid in batch:
            entity = entities.get(qid, {})

            # Handle missing/deleted entities
            if "missing" in entity:
                print(f"    {qid}: missing/deleted, skipping")
                continue

            labels = entity.get("labels", {})
            label = labels.get("en", {}).get("value", qid)

            alias_list = entity.get("aliases", {}).get("en", [])
            aliases = [a["value"] for a in alias_list]

            new_items.append({
                "qid": qid,
                "label": label,
                "aliases": aliases,
                "triples": [],  # linked-only, no properties imported
            })

        time.sleep(1)

    # Append to items
    items.extend(new_items)

    with open(str(DATA_DIR / "items.json"), "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)

    print(f"\nAdded {len(new_items)} linked items")
    print(f"Total items now: {len(items)}")

    # Show some examples
    for item in new_items[:10]:
        aliases_str = ", ".join(item["aliases"][:3]) if item["aliases"] else "(none)"
        print(f"  {item['qid']}: {item['label']} — aliases: {aliases_str}")


if __name__ == "__main__":
    main()
